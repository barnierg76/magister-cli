"""State tracking service for notification change detection."""

import fcntl
import json
import os
import stat
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


@dataclass
class StateChange:
    """Represents a detected change."""

    change_type: str  # "new_grade", "schedule_change", "homework_due"
    subject: str
    description: str
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class StateTracker:
    """Tracks state changes between API calls for notifications.

    Stores state in ~/.config/magister-cli/state.json
    """

    def __init__(self, school: str):
        self.school = school
        self.state_dir = Path.home() / ".config" / "magister-cli"
        self.state_file = self.state_dir / f"state_{school}.json"
        self._ensure_dir()

    def _ensure_dir(self) -> None:
        """Ensure config directory exists with proper permissions."""
        if not self.state_dir.exists():
            self.state_dir.mkdir(parents=True, mode=0o700)  # Owner only (rwx------)
        else:
            # Fix permissions if directory is readable by others
            current_mode = self.state_dir.stat().st_mode
            if current_mode & 0o077:  # Check if group/other have any permissions
                os.chmod(self.state_dir, 0o700)

    def _load_state(self) -> dict[str, Any]:
        """Load existing state from file with shared lock."""
        if not self.state_file.exists():
            return {
                "grades": {},
                "schedule": {},
                "homework": {},
                "last_check": None,
                "initialized": False,
            }

        try:
            with open(self.state_file) as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_SH)  # Shared lock for reading
                try:
                    return json.load(f)
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except (json.JSONDecodeError, OSError):
            return {
                "grades": {},
                "schedule": {},
                "homework": {},
                "last_check": None,
                "initialized": False,
            }

    def _cleanup_old_entries(self, state: dict[str, Any], retention_days: int = 90) -> dict[str, Any]:
        """Remove state entries older than retention period.

        Args:
            state: Current state dictionary
            retention_days: Number of days to retain entries (default 90)

        Returns:
            Cleaned state dictionary
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        cutoff_str = cutoff.isoformat()

        # Clean grades
        if "grades" in state and isinstance(state["grades"], dict):
            state["grades"] = {
                k: v for k, v in state["grades"].items()
                if v.get("seen_at", "") > cutoff_str
            }

        # Clean schedule entries
        if "schedule" in state and isinstance(state["schedule"], dict):
            state["schedule"] = {
                k: v for k, v in state["schedule"].items()
                if v.get("seen_at", "") > cutoff_str
            }

        # Clean homework notifications
        if "homework" in state and isinstance(state["homework"], dict):
            state["homework"] = {
                k: v for k, v in state["homework"].items()
                if v.get("notified_at", "") > cutoff_str
            }

        return state

    def _save_state(self, state: dict[str, Any]) -> None:
        """Save state to file with exclusive lock, atomic write, and restrictive permissions."""
        state["last_check"] = datetime.now(timezone.utc).isoformat()

        # Clean up old entries before saving
        state = self._cleanup_old_entries(state)

        # Use a lock file for exclusive access
        lock_file = self.state_file.with_suffix('.lock')
        with open(lock_file, 'w') as lock_f:
            fcntl.flock(lock_f.fileno(), fcntl.LOCK_EX)  # Exclusive lock
            try:
                temp_file = self.state_file.with_suffix('.tmp')
                with open(temp_file, 'w') as f:
                    json.dump(state, f, indent=2, default=str)
                    f.flush()
                    os.fsync(f.fileno())

                # Set restrictive permissions before moving to final location
                os.chmod(temp_file, stat.S_IRUSR | stat.S_IWUSR)  # 0600 - owner read/write only (rw-------)

                # Atomic rename
                temp_file.replace(self.state_file)
            finally:
                fcntl.flock(lock_f.fileno(), fcntl.LOCK_UN)

    def is_initialized(self) -> bool:
        """Check if state has been initialized (first run completed)."""
        state = self._load_state()
        return state.get("initialized", False)

    def mark_initialized(self) -> None:
        """Mark state as initialized after first successful check."""
        state = self._load_state()
        state["initialized"] = True
        self._save_state(state)

    def get_last_check(self) -> datetime | None:
        """Get timestamp of last check."""
        state = self._load_state()
        last_check = state.get("last_check")
        if last_check:
            return datetime.fromisoformat(last_check)
        return None

    def check_grades(self, grades: list[dict[str, Any]]) -> list[StateChange]:
        """Check for new grades since last check.

        Args:
            grades: List of grade dicts with at least 'id', 'vak', 'waarde' keys

        Returns:
            List of StateChange objects for new grades
        """
        state = self._load_state()
        known_grades = state.get("grades", {})
        changes: list[StateChange] = []

        for grade in grades:
            grade_id = str(grade.get("id", ""))
            if not grade_id:
                continue

            if grade_id not in known_grades:
                # New grade found
                subject = grade.get("vak", "Onbekend")
                value = grade.get("waarde", "?")
                description = grade.get("omschrijving", "")

                # Only report if state was already initialized
                # (prevents flood on first run)
                if state.get("initialized", False):
                    changes.append(
                        StateChange(
                            change_type="new_grade",
                            subject=subject,
                            description=f"Nieuw cijfer: {value}",
                            details={
                                "grade_id": grade_id,
                                "value": value,
                                "description": description,
                            },
                        )
                    )

                # Always update state
                known_grades[grade_id] = {
                    "vak": subject,
                    "waarde": value,
                    "seen_at": datetime.now(timezone.utc).isoformat(),
                }

        state["grades"] = known_grades
        self._save_state(state)
        return changes

    def check_schedule(self, appointments: list[dict[str, Any]]) -> list[StateChange]:
        """Check for schedule changes since last check.

        Args:
            appointments: List of appointment dicts

        Returns:
            List of StateChange objects for schedule changes
        """
        state = self._load_state()
        known_schedule = state.get("schedule", {})
        changes: list[StateChange] = []

        for apt in appointments:
            apt_id = str(apt.get("id", ""))
            if not apt_id:
                continue

            subject = apt.get("vak_naam", apt.get("omschrijving", "Onbekend"))
            is_cancelled = apt.get("is_vervallen", False)
            is_modified = apt.get("is_gewijzigd", False)
            start_time = apt.get("start", "")

            # Create a fingerprint for comparison
            fingerprint = f"{is_cancelled}:{is_modified}:{start_time}"

            if apt_id in known_schedule:
                old_fingerprint = known_schedule[apt_id].get("fingerprint", "")
                if fingerprint != old_fingerprint:
                    # Schedule changed
                    if state.get("initialized", False):
                        if is_cancelled and not known_schedule[apt_id].get("was_cancelled"):
                            changes.append(
                                StateChange(
                                    change_type="schedule_change",
                                    subject=subject,
                                    description="Les uitgevallen",
                                    details={
                                        "apt_id": apt_id,
                                        "start": start_time,
                                        "cancelled": True,
                                    },
                                )
                            )
                        elif is_modified:
                            changes.append(
                                StateChange(
                                    change_type="schedule_change",
                                    subject=subject,
                                    description="Roosterwijziging",
                                    details={
                                        "apt_id": apt_id,
                                        "start": start_time,
                                        "modified": True,
                                    },
                                )
                            )

            # Update state
            known_schedule[apt_id] = {
                "vak": subject,
                "fingerprint": fingerprint,
                "was_cancelled": is_cancelled,
                "seen_at": datetime.now(timezone.utc).isoformat(),
            }

        state["schedule"] = known_schedule
        self._save_state(state)
        return changes

    def check_homework(
        self, homework_items: list[dict[str, Any]], reminder_hours: int = 24
    ) -> list[StateChange]:
        """Check for homework due within reminder window.

        Args:
            homework_items: List of homework dicts with 'deadline', 'subject', 'description'
            reminder_hours: Hours before deadline to send reminder

        Returns:
            List of StateChange objects for homework reminders
        """
        state = self._load_state()
        notified_homework = state.get("homework", {})
        changes: list[StateChange] = []

        now = datetime.now(timezone.utc)

        for item in homework_items:
            item_id = str(item.get("id", hash(f"{item.get('subject')}:{item.get('deadline')}")))
            subject = item.get("subject", "Onbekend")
            deadline_str = item.get("deadline", "")

            try:
                deadline = datetime.fromisoformat(deadline_str.replace("Z", "+00:00"))
                # Ensure deadline is timezone-aware
                if deadline.tzinfo is None:
                    deadline = deadline.replace(tzinfo=timezone.utc)
            except (ValueError, AttributeError):
                continue

            # Calculate hours until deadline
            hours_until = (deadline - now).total_seconds() / 3600

            # Check if within reminder window and not yet notified
            notification_key = f"{item_id}:{reminder_hours}h"
            if 0 < hours_until <= reminder_hours and notification_key not in notified_homework:
                if state.get("initialized", False):
                    description_text = item.get("description", "")
                    if len(description_text) > 50:
                        description_text = description_text[:50] + "..."

                    changes.append(
                        StateChange(
                            change_type="homework_due",
                            subject=subject,
                            description=f"Deadline over {int(hours_until)} uur",
                            details={
                                "item_id": item_id,
                                "deadline": deadline_str,
                                "homework_description": description_text,
                            },
                        )
                    )

                # Mark as notified
                notified_homework[notification_key] = {
                    "subject": subject,
                    "deadline": deadline_str,
                    "notified_at": now.isoformat(),
                }

        state["homework"] = notified_homework
        self._save_state(state)
        return changes

    def clear_state(self) -> None:
        """Clear all tracked state."""
        if self.state_file.exists():
            self.state_file.unlink()

    def get_stats(self) -> dict[str, Any]:
        """Get statistics about tracked state."""
        state = self._load_state()
        return {
            "initialized": state.get("initialized", False),
            "last_check": state.get("last_check"),
            "tracked_grades": len(state.get("grades", {})),
            "tracked_appointments": len(state.get("schedule", {})),
            "notified_homework": len(state.get("homework", {})),
        }
