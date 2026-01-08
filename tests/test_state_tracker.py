"""Tests for state tracker service."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from magister_cli.services.state_tracker import StateChange, StateTracker


class TestStateCleanup:
    """Tests for state cleanup functionality."""

    @pytest.fixture
    def tracker(self, tmp_path):
        """Create StateTracker with temporary directory."""
        with patch.object(Path, "home", return_value=tmp_path):
            tracker = StateTracker(school="test_school")
            # Create initial state
            tracker.mark_initialized()
            return tracker

    def test_cleanup_removes_old_grades(self, tracker):
        """Old grades (>90 days) should be removed."""
        state = tracker._load_state()

        # Add a recent grade
        recent_time = datetime.now(timezone.utc)
        state["grades"]["recent"] = {
            "vak": "Math",
            "waarde": "8.5",
            "seen_at": recent_time.isoformat(),
        }

        # Add an old grade (100 days ago)
        old_time = datetime.now(timezone.utc) - timedelta(days=100)
        state["grades"]["old"] = {
            "vak": "History",
            "waarde": "7.0",
            "seen_at": old_time.isoformat(),
        }

        # Run cleanup
        cleaned = tracker._cleanup_old_entries(state)

        # Recent grade should remain, old grade should be removed
        assert "recent" in cleaned["grades"]
        assert "old" not in cleaned["grades"]

    def test_cleanup_removes_old_schedule(self, tracker):
        """Old schedule entries (>90 days) should be removed."""
        state = tracker._load_state()

        # Add a recent appointment
        recent_time = datetime.now(timezone.utc)
        state["schedule"]["recent"] = {
            "vak": "Math",
            "fingerprint": "False:False:2026-01-09T09:00:00",
            "was_cancelled": False,
            "seen_at": recent_time.isoformat(),
        }

        # Add an old appointment (100 days ago)
        old_time = datetime.now(timezone.utc) - timedelta(days=100)
        state["schedule"]["old"] = {
            "vak": "History",
            "fingerprint": "False:False:2025-10-01T09:00:00",
            "was_cancelled": False,
            "seen_at": old_time.isoformat(),
        }

        # Run cleanup
        cleaned = tracker._cleanup_old_entries(state)

        # Recent entry should remain, old entry should be removed
        assert "recent" in cleaned["schedule"]
        assert "old" not in cleaned["schedule"]

    def test_cleanup_removes_old_homework(self, tracker):
        """Old homework notifications (>90 days) should be removed."""
        state = tracker._load_state()

        # Add a recent notification
        recent_time = datetime.now(timezone.utc)
        state["homework"]["recent:24h"] = {
            "subject": "Math",
            "deadline": "2026-01-10T12:00:00",
            "notified_at": recent_time.isoformat(),
        }

        # Add an old notification (100 days ago)
        old_time = datetime.now(timezone.utc) - timedelta(days=100)
        state["homework"]["old:24h"] = {
            "subject": "History",
            "deadline": "2025-10-02T12:00:00",
            "notified_at": old_time.isoformat(),
        }

        # Run cleanup
        cleaned = tracker._cleanup_old_entries(state)

        # Recent notification should remain, old notification should be removed
        assert "recent:24h" in cleaned["homework"]
        assert "old:24h" not in cleaned["homework"]

    def test_cleanup_handles_missing_fields(self, tracker):
        """Cleanup should handle entries with missing timestamp fields."""
        state = tracker._load_state()

        # Add entries with missing fields
        state["grades"]["no_timestamp"] = {
            "vak": "Math",
            "waarde": "8.5",
            # Missing seen_at field
        }

        state["schedule"]["no_timestamp"] = {
            "vak": "History",
            # Missing seen_at field
        }

        state["homework"]["no_timestamp"] = {
            "subject": "English",
            # Missing notified_at field
        }

        # Run cleanup - should not crash
        cleaned = tracker._cleanup_old_entries(state)

        # Entries without timestamps should be removed (treated as "" < cutoff_str)
        assert "no_timestamp" not in cleaned["grades"]
        assert "no_timestamp" not in cleaned["schedule"]
        assert "no_timestamp" not in cleaned["homework"]

    def test_cleanup_handles_malformed_state(self, tracker):
        """Cleanup should handle malformed state gracefully."""
        state = {
            "grades": "not_a_dict",  # Wrong type
            "schedule": None,  # None instead of dict
            "homework": {},
            "last_check": None,
            "initialized": True,
        }

        # Run cleanup - should not crash
        cleaned = tracker._cleanup_old_entries(state)

        # Malformed entries should remain unchanged
        assert cleaned["grades"] == "not_a_dict"
        assert cleaned["schedule"] is None

    def test_cleanup_called_on_save(self, tracker):
        """Cleanup should be called automatically when saving state."""
        # Create state with old entry
        state = tracker._load_state()
        old_time = datetime.now(timezone.utc) - timedelta(days=100)
        state["grades"]["old_grade"] = {
            "vak": "History",
            "waarde": "7.0",
            "seen_at": old_time.isoformat(),
        }

        # Save state
        tracker._save_state(state)

        # Load state again and check old entry was removed
        loaded_state = tracker._load_state()
        assert "old_grade" not in loaded_state["grades"]

    def test_cleanup_custom_retention_days(self, tracker):
        """Cleanup should respect custom retention period."""
        state = tracker._load_state()

        # Add entry from 50 days ago
        time_50_days_ago = datetime.now(timezone.utc) - timedelta(days=50)
        state["grades"]["medium_old"] = {
            "vak": "Math",
            "waarde": "8.5",
            "seen_at": time_50_days_ago.isoformat(),
        }

        # Cleanup with 90 days retention - should keep entry
        cleaned_90 = tracker._cleanup_old_entries(state.copy(), retention_days=90)
        assert "medium_old" in cleaned_90["grades"]

        # Cleanup with 30 days retention - should remove entry
        cleaned_30 = tracker._cleanup_old_entries(state.copy(), retention_days=30)
        assert "medium_old" not in cleaned_30["grades"]

    def test_cleanup_preserves_other_fields(self, tracker):
        """Cleanup should preserve non-collection fields in state."""
        state = tracker._load_state()
        state["initialized"] = True
        state["last_check"] = datetime.now(timezone.utc).isoformat()
        state["custom_field"] = "custom_value"

        # Run cleanup
        cleaned = tracker._cleanup_old_entries(state)

        # Other fields should be preserved
        assert cleaned["initialized"] is True
        assert "last_check" in cleaned
        assert cleaned["custom_field"] == "custom_value"


class TestStateChange:
    """Tests for StateChange dataclass."""

    def test_state_change_creation(self):
        """StateChange can be created with required fields."""
        change = StateChange(
            change_type="new_grade",
            subject="Math",
            description="New grade: 8.5",
        )

        assert change.change_type == "new_grade"
        assert change.subject == "Math"
        assert change.description == "New grade: 8.5"
        assert isinstance(change.timestamp, datetime)

    def test_state_change_with_details(self):
        """StateChange can include optional details."""
        change = StateChange(
            change_type="schedule_change",
            subject="History",
            description="Class cancelled",
            details={"apt_id": "123", "cancelled": True},
        )

        assert change.details["apt_id"] == "123"
        assert change.details["cancelled"] is True
