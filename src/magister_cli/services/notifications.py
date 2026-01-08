"""Desktop notification service for Magister CLI."""

import asyncio
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from desktop_notifier import DesktopNotifier, Urgency

from magister_cli.api import MagisterClient
from magister_cli.auth import get_current_token
from magister_cli.services.homework import HomeworkService
from magister_cli.services.state_tracker import StateChange, StateTracker


@dataclass
class NotificationConfig:
    """Configuration for notifications."""

    grades_enabled: bool = True
    schedule_enabled: bool = True
    homework_enabled: bool = True
    homework_reminder_hours: int = 24
    quiet_hours_start: int | None = 22  # 22:00
    quiet_hours_end: int | None = 7  # 07:00


class NotificationService:
    """Service for sending desktop notifications about Magister changes."""

    APP_NAME = "Magister CLI"
    ICON_PATH: Path | None = None  # Can be set to app icon path

    def __init__(self, school: str, config: NotificationConfig | None = None):
        self.school = school
        self.config = config or NotificationConfig()
        self.state_tracker = StateTracker(school)
        self._notifier: DesktopNotifier | None = None

    async def _get_notifier(self) -> DesktopNotifier:
        """Get or create the desktop notifier instance."""
        if self._notifier is None:
            self._notifier = DesktopNotifier(
                app_name=self.APP_NAME,
                app_icon=str(self.ICON_PATH) if self.ICON_PATH else None,
            )
        return self._notifier

    def _is_quiet_hours(self) -> bool:
        """Check if currently in quiet hours."""
        if self.config.quiet_hours_start is None or self.config.quiet_hours_end is None:
            return False

        from datetime import datetime

        now = datetime.now()
        hour = now.hour

        start = self.config.quiet_hours_start
        end = self.config.quiet_hours_end

        # Handle overnight quiet hours (e.g., 22:00 - 07:00)
        if start > end:
            return hour >= start or hour < end
        else:
            return start <= hour < end

    async def send_notification(
        self,
        title: str,
        message: str,
        urgency: Urgency = Urgency.Normal,
    ) -> bool:
        """Send a desktop notification.

        Args:
            title: Notification title
            message: Notification body text
            urgency: Notification urgency level

        Returns:
            True if notification was sent, False if skipped (e.g., quiet hours)
        """
        if self._is_quiet_hours():
            return False

        try:
            notifier = await self._get_notifier()
            await notifier.send(
                title=title,
                message=message,
                urgency=urgency,
            )
            return True
        except Exception:
            # Silently fail - notifications are non-critical
            return False

    async def notify_change(self, change: StateChange) -> bool:
        """Send notification for a state change.

        Args:
            change: The detected state change

        Returns:
            True if notification was sent
        """
        title: str
        message: str
        urgency = Urgency.Normal

        if change.change_type == "new_grade":
            if not self.config.grades_enabled:
                return False
            value = change.details.get("value", "?")
            title = f"📊 Nieuw cijfer: {change.subject}"
            message = f"{value} - {change.details.get('description', '')}"
            # Make it urgent if it's a low grade
            try:
                if float(str(value).replace(",", ".")) < 5.5:
                    urgency = Urgency.Critical
            except (ValueError, TypeError):
                pass

        elif change.change_type == "schedule_change":
            if not self.config.schedule_enabled:
                return False
            title = f"📅 {change.description}"
            message = f"{change.subject}"
            if change.details.get("cancelled"):
                title = f"❌ Les uitgevallen: {change.subject}"
                urgency = Urgency.Normal

        elif change.change_type == "homework_due":
            if not self.config.homework_enabled:
                return False
            title = f"📚 Huiswerk deadline: {change.subject}"
            message = change.description
            hw_desc = change.details.get("homework_description", "")
            if hw_desc:
                message += f"\n{hw_desc}"
            urgency = Urgency.Normal

        else:
            return False

        return await self.send_notification(title, message, urgency)

    async def check_and_notify(self) -> list[StateChange]:
        """Check for changes and send notifications.

        Returns:
            List of detected changes
        """
        all_changes: list[StateChange] = []

        # Get authentication
        token_data = get_current_token(self.school)
        if token_data is None:
            return all_changes

        try:
            with MagisterClient(token_data.school, token_data.access_token) as client:
                # Check grades
                if self.config.grades_enabled:
                    try:
                        grades = client.grades.recent(limit=20)
                        grade_dicts = [
                            {
                                "id": g.id,
                                "vak": g.vak,
                                "waarde": g.waarde,
                                "omschrijving": g.omschrijving,
                            }
                            for g in grades
                        ]
                        changes = self.state_tracker.check_grades(grade_dicts)
                        all_changes.extend(changes)
                    except Exception:
                        pass

                # Check schedule (next 7 days)
                if self.config.schedule_enabled:
                    try:
                        start = date.today()
                        end = start + timedelta(days=7)
                        appointments = client.appointments.list(start, end)
                        apt_dicts = [
                            {
                                "id": a.id,
                                "vak_naam": a.vak_naam,
                                "omschrijving": a.omschrijving,
                                "is_vervallen": a.is_vervallen,
                                "is_gewijzigd": a.is_gewijzigd,
                                "start": a.start.isoformat() if a.start else "",
                            }
                            for a in appointments
                        ]
                        changes = self.state_tracker.check_schedule(apt_dicts)
                        all_changes.extend(changes)
                    except Exception:
                        pass

            # Check homework (uses HomeworkService)
            if self.config.homework_enabled:
                try:
                    service = HomeworkService(school=self.school)
                    homework_days = service.get_homework(days=7)
                    hw_items = []
                    for day in homework_days:
                        for item in day.items:
                            hw_items.append(
                                {
                                    "id": item.raw.id if item.raw else None,
                                    "subject": item.subject,
                                    "deadline": item.deadline.isoformat(),
                                    "description": item.description,
                                }
                            )
                    changes = self.state_tracker.check_homework(
                        hw_items,
                        reminder_hours=self.config.homework_reminder_hours,
                    )
                    all_changes.extend(changes)
                except Exception:
                    pass

        except Exception:
            pass

        # Initialize state if first run
        if not self.state_tracker.is_initialized():
            self.state_tracker.mark_initialized()

        # Send notifications for all changes
        for change in all_changes:
            await self.notify_change(change)

        return all_changes

    def check_and_notify_sync(self) -> list[StateChange]:
        """Synchronous wrapper for check_and_notify."""
        return asyncio.run(self.check_and_notify())

    async def send_test_notification(self) -> bool:
        """Send a test notification to verify setup works."""
        return await self.send_notification(
            title="🎓 Magister CLI",
            message="Notificaties werken correct!",
            urgency=Urgency.Normal,
        )

    def send_test_notification_sync(self) -> bool:
        """Synchronous wrapper for send_test_notification."""
        return asyncio.run(self.send_test_notification())

    def get_status(self) -> dict:
        """Get notification service status."""
        stats = self.state_tracker.get_stats()
        return {
            "school": self.school,
            "initialized": stats["initialized"],
            "last_check": stats["last_check"],
            "config": {
                "grades": self.config.grades_enabled,
                "schedule": self.config.schedule_enabled,
                "homework": self.config.homework_enabled,
                "homework_reminder_hours": self.config.homework_reminder_hours,
                "quiet_hours": f"{self.config.quiet_hours_start}:00 - {self.config.quiet_hours_end}:00"
                if self.config.quiet_hours_start
                else "disabled",
            },
            "tracked": {
                "grades": stats["tracked_grades"],
                "appointments": stats["tracked_appointments"],
                "homework_notifications": stats["notified_homework"],
            },
        }

    def reset(self) -> None:
        """Reset notification state (triggers re-initialization)."""
        self.state_tracker.clear_state()
