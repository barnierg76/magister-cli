"""Core business logic for Magister services (I/O agnostic).

This module contains pure business logic that can be reused by both
sync and async service implementations.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import List, Optional


@dataclass
class AttachmentInfo:
    """Attachment information for display."""

    id: int
    name: str
    size: str
    content_type: str
    download_url: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "size": self.size,
            "content_type": self.content_type,
            "download_url": self.download_url,
        }


@dataclass
class HomeworkItem:
    """A homework assignment with context."""

    subject: str
    subject_abbr: Optional[str]
    description: str
    deadline: datetime
    lesson_number: Optional[int]
    location: Optional[str]
    teacher: Optional[str]
    is_test: bool
    is_completed: bool
    afspraak_id: Optional[int] = None
    attachments: List[AttachmentInfo] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "subject": self.subject,
            "subject_abbr": self.subject_abbr,
            "description": self.description,
            "deadline": self.deadline.isoformat(),
            "lesson_number": self.lesson_number,
            "location": self.location,
            "teacher": self.teacher,
            "is_test": self.is_test,
            "is_completed": self.is_completed,
            "afspraak_id": self.afspraak_id,
            "attachments": [a.to_dict() for a in self.attachments],
        }


@dataclass
class HomeworkDay:
    """Homework items grouped by day."""

    date: date
    items: List[HomeworkItem]

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
            "jan", "feb", "mrt", "apr", "mei", "jun",
            "jul", "aug", "sep", "okt", "nov", "dec",
        ]
        return months[self.date.month - 1]

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "date": self.date.isoformat(),
            "day_label": self.day_label,
            "items": [i.to_dict() for i in self.items],
        }


@dataclass
class GradeInfo:
    """Grade information for display."""

    subject: str
    grade: str
    weight: Optional[float]
    date: Optional[datetime]
    description: Optional[str]
    is_sufficient: bool

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "subject": self.subject,
            "grade": self.grade,
            "weight": self.weight,
            "date": self.date.isoformat() if self.date else None,
            "description": self.description,
            "is_sufficient": self.is_sufficient,
        }


@dataclass
class ScheduleItem:
    """Schedule item for display."""

    start: datetime
    end: datetime
    subject: str
    location: Optional[str]
    teacher: Optional[str]
    lesson_number: Optional[int]
    has_homework: bool
    is_cancelled: bool

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "subject": self.subject,
            "location": self.location,
            "teacher": self.teacher,
            "lesson_number": self.lesson_number,
            "has_homework": self.has_homework,
            "is_cancelled": self.is_cancelled,
        }


class MagisterCore:
    """I/O agnostic business logic for Magister data processing."""

    @staticmethod
    def filter_by_subject(items: List[HomeworkItem], subject: str) -> List[HomeworkItem]:
        """Filter homework by subject (case-insensitive partial match)."""
        subject_lower = subject.lower()
        return [
            i for i in items
            if subject_lower in i.subject.lower()
            or (i.subject_abbr and subject_lower in i.subject_abbr.lower())
        ]

    @staticmethod
    def filter_incomplete(items: List[HomeworkItem]) -> List[HomeworkItem]:
        """Filter to incomplete homework only."""
        return [i for i in items if not i.is_completed]

    @staticmethod
    def filter_tests(items: List[HomeworkItem]) -> List[HomeworkItem]:
        """Filter to tests only."""
        return [i for i in items if i.is_test]

    @staticmethod
    def group_by_date(items: List[HomeworkItem]) -> List[HomeworkDay]:
        """Group homework by deadline date."""
        # Sort by deadline first
        items = sorted(items, key=lambda i: (i.deadline, i.subject))

        # Group by date
        grouped: dict[date, List[HomeworkItem]] = {}
        for item in items:
            day = item.deadline.date()
            if day not in grouped:
                grouped[day] = []
            grouped[day].append(item)

        # Create HomeworkDay objects
        return [
            HomeworkDay(date=d, items=day_items)
            for d, day_items in sorted(grouped.items())
        ]

    @staticmethod
    def calculate_average(grades: List[GradeInfo]) -> Optional[float]:
        """Calculate weighted average of grades."""
        if not grades:
            return None

        total_weighted = 0.0
        total_weight = 0.0

        for grade in grades:
            try:
                value = float(grade.grade.replace(",", "."))
                weight = grade.weight or 1.0
                total_weighted += value * weight
                total_weight += weight
            except (ValueError, AttributeError):
                continue

        if total_weight == 0:
            return None

        return round(total_weighted / total_weight, 2)

    @staticmethod
    def parse_homework_from_api(api_data: dict) -> HomeworkItem:
        """Parse homework item from Magister API response."""
        # Extract subject info
        vakken = api_data.get("Vakken", [])
        vak = vakken[0] if vakken else {}

        # Extract teacher info
        docenten = api_data.get("Docenten", [])
        docent = docenten[0] if docenten else {}

        # Extract location
        lokalen = api_data.get("Lokalen", [])
        lokaal = lokalen[0] if lokalen else {}

        # Parse attachments
        attachments = []
        for bijlage in api_data.get("Bijlagen", []):
            attachments.append(AttachmentInfo(
                id=bijlage.get("Id", 0),
                name=bijlage.get("Naam", ""),
                size=bijlage.get("GrootteLeesbaar", ""),
                content_type=bijlage.get("ContentType", ""),
                download_url=bijlage.get("Uri"),
            ))

        # Parse datetime
        start_str = api_data.get("Start") or api_data.get("Einde", "")
        try:
            deadline = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            deadline = datetime.now()

        return HomeworkItem(
            subject=vak.get("Naam", "Onbekend"),
            subject_abbr=vak.get("Afkorting"),
            description=api_data.get("Inhoud") or api_data.get("Huiswerk", ""),
            deadline=deadline,
            lesson_number=api_data.get("LesuurVan"),
            location=lokaal.get("Naam"),
            teacher=docent.get("Naam"),
            is_test=api_data.get("InfoType", 0) == 2,  # InfoType 2 = toets
            is_completed=api_data.get("Afgerond", False),
            afspraak_id=api_data.get("Id"),
            attachments=attachments,
        )

    @staticmethod
    def parse_grade_from_api(api_data: dict) -> GradeInfo:
        """Parse grade from Magister API response."""
        # Extract subject
        vak = api_data.get("Vak", {})

        # Parse date
        date_str = api_data.get("DatumIngevoerd", "")
        try:
            grade_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            grade_date = None

        # Determine if sufficient (>= 5.5 for Dutch grades)
        grade_value = api_data.get("CijferStr", "")
        try:
            numeric = float(grade_value.replace(",", "."))
            is_sufficient = numeric >= 5.5
        except (ValueError, AttributeError):
            is_sufficient = True  # Assume sufficient if can't parse

        return GradeInfo(
            subject=vak.get("Omschrijving", "Onbekend"),
            grade=grade_value,
            weight=api_data.get("Weging"),
            date=grade_date,
            description=api_data.get("KolomOmschrijving"),
            is_sufficient=is_sufficient,
        )

    @staticmethod
    def parse_schedule_from_api(api_data: dict) -> ScheduleItem:
        """Parse schedule item from Magister API response."""
        # Extract subject info
        vakken = api_data.get("Vakken", [])
        vak = vakken[0] if vakken else {}

        # Extract teacher info
        docenten = api_data.get("Docenten", [])
        docent = docenten[0] if docenten else {}

        # Extract location
        lokalen = api_data.get("Lokalen", [])
        lokaal = lokalen[0] if lokalen else {}

        # Parse times
        try:
            start = datetime.fromisoformat(api_data.get("Start", "").replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            start = datetime.now()

        try:
            end = datetime.fromisoformat(api_data.get("Einde", "").replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            end = datetime.now()

        return ScheduleItem(
            start=start,
            end=end,
            subject=vak.get("Naam", "Onbekend"),
            location=lokaal.get("Naam"),
            teacher=docent.get("Naam"),
            lesson_number=api_data.get("LesuurVan"),
            has_homework=bool(api_data.get("Inhoud") or api_data.get("Huiswerk")),
            is_cancelled=api_data.get("Status", 0) == 5,  # Status 5 = cancelled
        )
