"""Tests for agent context management."""

import sys
from pathlib import Path

# Import context module directly to avoid FastMCP import in __init__.py
# This allows tests to run without installing the mcp package
import importlib.util
spec = importlib.util.spec_from_file_location(
    "context",
    Path(__file__).parent.parent / "src" / "magister_cli" / "mcp" / "context.py"
)
context_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(context_module)
ContextData = context_module.ContextData
ContextManager = context_module.ContextManager

import pytest
from datetime import datetime
from unittest.mock import patch


class TestContextData:
    """Tests for ContextData dataclass."""

    def test_context_data_creation(self):
        """ContextData can be created with frontmatter and body."""
        data = ContextData(
            frontmatter={"school_code": "test", "preferences": {}},
            body="## Notes\n\nTest notes."
        )

        assert data.frontmatter["school_code"] == "test"
        assert "## Notes" in data.body


class TestContextManager:
    """Tests for ContextManager."""

    @pytest.fixture
    def context_manager(self, tmp_path):
        """Create ContextManager with temporary directory."""
        with patch.object(Path, "home", return_value=tmp_path):
            cm = ContextManager("test_school")
            yield cm

    def test_default_context(self, context_manager):
        """Reading non-existent context returns default."""
        context = context_manager.read()

        assert context.frontmatter["schema_version"] == "1.0"
        assert context.frontmatter["school_code"] == "test_school"
        assert context.frontmatter["preferences"] == {}
        assert context.frontmatter["recent_activity"] == {}
        assert context.frontmatter["cached_data"] == {}
        assert "Session Notes" in context.body

    def test_write_and_read_context(self, context_manager):
        """Context can be written and read back."""
        frontmatter = {
            "schema_version": "1.0",
            "school_code": "test_school",
            "preferences": {"default_days_ahead": 14},
            "recent_activity": {},
            "cached_data": {},
        }
        body = "## Custom Notes\n\nMy notes here."

        context_manager.write(frontmatter, body)
        context = context_manager.read()

        assert context.frontmatter["preferences"]["default_days_ahead"] == 14
        assert "Custom Notes" in context.body

    def test_update_preferences_merge(self, context_manager):
        """Preferences are merged, not replaced."""
        # Set initial preferences
        context_manager.update_preferences({"setting_a": 1})

        # Update with new preference
        context_manager.update_preferences({"setting_b": 2})

        context = context_manager.read()
        assert context.frontmatter["preferences"]["setting_a"] == 1
        assert context.frontmatter["preferences"]["setting_b"] == 2

    def test_update_cached_data_merge(self, context_manager):
        """Cached data is merged, not replaced."""
        context_manager.update_cached_data({"grade_average": 7.5})
        context_manager.update_cached_data({"unread_messages": 3})

        context = context_manager.read()
        assert context.frontmatter["cached_data"]["grade_average"] == 7.5
        assert context.frontmatter["cached_data"]["unread_messages"] == 3

    def test_log_activity(self, context_manager):
        """Activity logging tracks queries."""
        context_manager.log_activity("What homework is due?")

        context = context_manager.read()
        activity = context.frontmatter["recent_activity"]

        assert activity["last_query"] == "What homework is due?"
        assert activity["queries_today"] == 1
        assert "last_query_time" in activity

    def test_log_activity_increments_count(self, context_manager):
        """Multiple activity logs increment query count."""
        context_manager.log_activity("Query 1")
        context_manager.log_activity("Query 2")
        context_manager.log_activity("Query 3")

        context = context_manager.read()
        assert context.frontmatter["recent_activity"]["queries_today"] == 3
        assert context.frontmatter["recent_activity"]["last_query"] == "Query 3"

    def test_update_notes(self, context_manager):
        """Notes can be replaced entirely."""
        context_manager.update_notes("## New Notes\n\nFresh content.")

        context = context_manager.read()
        assert "New Notes" in context.body
        assert "Fresh content" in context.body

    def test_update_notes_preserves_frontmatter(self, context_manager):
        """Updating notes preserves frontmatter."""
        context_manager.update_preferences({"important": True})
        context_manager.update_notes("Updated notes")

        context = context_manager.read()
        assert context.frontmatter["preferences"]["important"] is True
        assert "Updated notes" in context.body

    def test_get_preferences(self, context_manager):
        """Get preferences returns preferences dict."""
        context_manager.update_preferences({"days_ahead": 7})

        prefs = context_manager.get_preferences()
        assert prefs["days_ahead"] == 7

    def test_get_preferences_empty_default(self, context_manager):
        """Get preferences returns empty dict by default."""
        prefs = context_manager.get_preferences()
        assert prefs == {}

    def test_get_cached_data(self, context_manager):
        """Get cached data returns cached data dict."""
        context_manager.update_cached_data({"average": 8.0})

        data = context_manager.get_cached_data()
        assert data["average"] == 8.0

    def test_get_cached_data_empty_default(self, context_manager):
        """Get cached data returns empty dict by default."""
        data = context_manager.get_cached_data()
        assert data == {}

    def test_clear_context(self, context_manager):
        """Clear removes context file."""
        context_manager.update_preferences({"test": True})
        context_manager.clear()

        # After clear, should get default context
        context = context_manager.read()
        assert context.frontmatter["preferences"] == {}

    def test_context_file_permissions(self, context_manager):
        """Context file has restrictive permissions."""
        context_manager.write({"test": True}, "body")

        # Check file permissions (0o600 = rw-------)
        mode = context_manager.context_file.stat().st_mode & 0o777
        assert mode == 0o600

    def test_context_directory_permissions(self, context_manager):
        """Context directory has restrictive permissions."""
        context_manager.write({"test": True}, "body")

        # Check directory permissions (0o700 = rwx------)
        mode = context_manager.context_dir.stat().st_mode & 0o777
        assert mode == 0o700

    def test_last_updated_timestamp(self, context_manager):
        """Write adds last_updated timestamp."""
        context_manager.write({"test": True}, "body")

        context = context_manager.read()
        assert "last_updated" in context.frontmatter

        # Verify it's a valid ISO timestamp
        timestamp = context.frontmatter["last_updated"]
        datetime.fromisoformat(timestamp)

    def test_handles_malformed_frontmatter(self, context_manager, tmp_path):
        """Malformed frontmatter returns default context."""
        # Create malformed file
        context_manager._ensure_dir()
        context_manager.context_file.write_text("not valid yaml frontmatter")

        context = context_manager.read()
        assert context.frontmatter["schema_version"] == "1.0"

    def test_handles_missing_frontmatter_delimiters(self, context_manager):
        """Missing frontmatter delimiters returns default context."""
        context_manager._ensure_dir()
        context_manager.context_file.write_text("Just plain text without frontmatter")

        context = context_manager.read()
        assert context.frontmatter["school_code"] == "test_school"

    def test_concurrent_writes_use_locking(self, context_manager):
        """Multiple writes use file locking for safety."""
        # This is a basic test - true concurrent testing is complex
        # The implementation uses fcntl.LOCK_EX which is process-level locking
        context_manager.update_preferences({"a": 1})
        context_manager.update_preferences({"b": 2})

        context = context_manager.read()
        assert context.frontmatter["preferences"]["a"] == 1
        assert context.frontmatter["preferences"]["b"] == 2
