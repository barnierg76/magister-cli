"""State tracking service for notification change detection."""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class StateChange:
    """Represents a detected change."""

    change_type: str  # "new_grade", "schedule_change", "homework_due"
    subject: str
    description: str
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


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
        """Ensure config directory exists."""
        self.state_dir.mkdir(parents=True, exist_ok=True)

    def _load_state(self) -> dict[str, Any]:
        """Load existing state from file."""
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
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {
                "grades": {},
                "schedule": {},
                "homework": {},
                "last_check": None,
                "initialized": False,
            }

    def _save_state(self, state: dict[str, Any]) -> None:
        """Save state to file."""
        state["last_check"] = datetime.now().isoformat()
        with open(self.state_file, "w") as f:
            json.dump(state, f, indent=2, default=str)

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
                    "seen_at": datetime.now().isoformat(),
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
                "seen_at": datetime.now().isoformat(),
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

        now = datetime.now()

        for item in homework_items:
            item_id = str(item.get("id", hash(f"{item.get('subject')}:{item.get('deadline')}")))
            subject = item.get("subject", "Onbekend")
            deadline_str = item.get("deadline", "")

            try:
                deadline = datetime.fromisoformat(deadline_str.replace("Z", "+00:00"))
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
