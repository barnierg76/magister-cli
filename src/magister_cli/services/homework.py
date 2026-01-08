"""Homework service for fetching and organizing homework assignments."""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from magister_cli.api import Afspraak, MagisterClient
from magister_cli.api.models import Bijlage
from magister_cli.auth import get_current_token


@dataclass
class AttachmentInfo:
    """Attachment information for display."""

    id: int
    name: str
    size: str
    content_type: str
    raw: Bijlage

    @classmethod
    def from_bijlage(cls, bijlage: Bijlage) -> "AttachmentInfo":
        """Create AttachmentInfo from a Bijlage."""
        return cls(
            id=bijlage.id,
            name=bijlage.naam,
            size=bijlage.grootte_leesbaar,
            content_type=bijlage.content_type,
            raw=bijlage,
        )


@dataclass
class HomeworkItem:
    """A homework assignment with context."""

    subject: str
    subject_abbr: str | None
    description: str
    deadline: datetime
    lesson_number: int | None
    location: str | None
    teacher: str | None
    is_test: bool
    is_completed: bool
    attachments: list[AttachmentInfo] = field(default_factory=list)
    raw: Afspraak = field(default=None)  # type: ignore

    @classmethod
    def from_afspraak(cls, afspraak: Afspraak) -> "HomeworkItem":
        """Create a HomeworkItem from an Afspraak."""
        attachments = [
            AttachmentInfo.from_bijlage(b) for b in afspraak.bijlagen_lijst
        ]

        return cls(
            subject=afspraak.vak_naam,
            subject_abbr=afspraak.vak_afkorting,
            description=afspraak.huiswerk_tekst,
            deadline=afspraak.start,
            lesson_number=afspraak.les_uur,
            location=afspraak.lokaal_naam,
            teacher=afspraak.docent_naam,
            is_test=afspraak.is_toets,
            is_completed=afspraak.afgerond,
            attachments=attachments,
            raw=afspraak,
        )


@dataclass
class HomeworkDay:
    """Homework items grouped by day."""

    date: date
    items: list[HomeworkItem]

    @property
    def is_today(self) -> bool:
        """Check if this is today."""
        return self.date == date.today()

    @property
    def is_tomorrow(self) -> bool:
        """Check if this is tomorrow."""
        return self.date == date.today() + timedelta(days=1)

    @property
    def day_label(self) -> str:
        """Get a human-readable label for the day."""
        if self.is_today:
            return "Vandaag"
        if self.is_tomorrow:
            return "Morgen"

        day_names = [
            "maandag",
            "dinsdag",
            "woensdag",
            "donderdag",
            "vrijdag",
            "zaterdag",
            "zondag",
        ]
        day_name = day_names[self.date.weekday()]
        return f"{day_name.capitalize()} {self.date.day} {self._month_name()}"

    def _month_name(self) -> str:
        """Get abbreviated month name in Dutch."""
        months = [
            "jan",
            "feb",
            "mrt",
            "apr",
            "mei",
            "jun",
            "jul",
            "aug",
            "sep",
            "okt",
            "nov",
            "dec",
        ]
        return months[self.date.month - 1]


class HomeworkService:
    """Service for fetching and organizing homework."""

    def __init__(self, school: str | None = None):
        self.school = school

    def _get_client(self) -> MagisterClient:
        """Get an authenticated client."""
        token_data = get_current_token(self.school)
        if token_data is None:
            raise RuntimeError(
                "Not authenticated. Run 'magister login' first."
            )
        return MagisterClient(token_data.school, token_data.access_token)

    def get_homework(
        self,
        days: int = 7,
        subject: str | None = None,
        include_completed: bool = False,
        include_attachments: bool = True,
    ) -> list[HomeworkDay]:
        """
        Get homework for the next N days, grouped by day.

        Args:
            days: Number of days to look ahead
            subject: Filter by subject name (case-insensitive partial match)
            include_completed: Include completed homework items
            include_attachments: Fetch full attachment details (slower)

        Returns:
            List of HomeworkDay objects, sorted by date
        """
        start = date.today()
        end = start + timedelta(days=days)

        with self._get_client() as client:
            if include_attachments:
                appointments = client.get_homework_with_attachments(start, end)
            else:
                appointments = client.get_homework(start, end)

        items = [HomeworkItem.from_afspraak(a) for a in appointments]

        if not include_completed:
            items = [i for i in items if not i.is_completed]

        if subject:
            subject_lower = subject.lower()
            items = [
                i
                for i in items
                if subject_lower in i.subject.lower()
                or (i.subject_abbr and subject_lower in i.subject_abbr.lower())
            ]

        items.sort(key=lambda i: (i.deadline, i.subject))

        grouped: dict[date, list[HomeworkItem]] = {}
        for item in items:
            day = item.deadline.date()
            if day not in grouped:
                grouped[day] = []
            grouped[day].append(item)

        days_list = [
            HomeworkDay(date=d, items=items)
            for d, items in sorted(grouped.items())
        ]

        return days_list

    def get_upcoming_tests(self, days: int = 14) -> list[HomeworkItem]:
        """Get upcoming tests in the next N days."""
        homework_days = self.get_homework(days=days, include_completed=False)
        tests = []
        for day in homework_days:
            for item in day.items:
                if item.is_test:
                    tests.append(item)
        return tests
