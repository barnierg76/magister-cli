"""Tests for MagisterCore business logic."""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from magister_cli.services.core import (
    AttachmentInfo,
    GradeInfo,
    HomeworkDay,
    HomeworkItem,
    MagisterCore,
    ScheduleItem,
    to_dutch_time,
)

DUTCH_TZ = ZoneInfo("Europe/Amsterdam")


class TestAttachmentInfo:
    """Tests for AttachmentInfo dataclass."""

    def test_creation_with_all_fields(self):
        """Test creating AttachmentInfo with all fields."""
        att = AttachmentInfo(
            id=123,
            name="homework.pdf",
            size="2.5 MB",
            content_type="application/pdf",
            download_url="https://example.com/file.pdf",
        )
        assert att.id == 123
        assert att.name == "homework.pdf"
        assert att.size == "2.5 MB"
        assert att.content_type == "application/pdf"
        assert att.download_url == "https://example.com/file.pdf"

    def test_to_dict_serialization(self):
        """Test that to_dict returns correct structure."""
        att = AttachmentInfo(
            id=456,
            name="test.docx",
            size="1.2 MB",
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            download_url="https://example.com/test.docx",
        )
        result = att.to_dict()

        assert isinstance(result, dict)
        assert result["id"] == 456
        assert result["name"] == "test.docx"
        assert result["size"] == "1.2 MB"
        assert result["content_type"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        assert result["download_url"] == "https://example.com/test.docx"


class TestHomeworkItem:
    """Tests for HomeworkItem dataclass."""

    def test_creation_with_required_fields(self):
        """Test creating HomeworkItem with all fields."""
        deadline = datetime(2026, 1, 15, 9, 0)
        item = HomeworkItem(
            subject="Wiskunde",
            subject_abbr="WIS",
            description="Maak opgaven 4.1-4.15",
            deadline=deadline,
            lesson_number=2,
            location="A101",
            teacher="Dhr. Jansen",
            is_test=False,
            is_completed=False,
            afspraak_id=12345,
            attachments=[],
        )

        assert item.subject == "Wiskunde"
        assert item.subject_abbr == "WIS"
        assert item.description == "Maak opgaven 4.1-4.15"
        assert item.deadline == deadline
        assert item.lesson_number == 2
        assert item.location == "A101"
        assert item.teacher == "Dhr. Jansen"
        assert not item.is_test
        assert not item.is_completed
        assert item.afspraak_id == 12345

    def test_to_dict_serialization(self):
        """Test that to_dict returns correct structure."""
        deadline = datetime(2026, 1, 15, 9, 0)
        attachments = [
            AttachmentInfo(
                id=1,
                name="homework.pdf",
                size="1 MB",
                content_type="application/pdf",
            )
        ]

        item = HomeworkItem(
            subject="Math",
            subject_abbr="MAT",
            description="Homework",
            deadline=deadline,
            lesson_number=3,
            location="B202",
            teacher="Mr. Smith",
            is_test=True,
            is_completed=False,
            afspraak_id=999,
            attachments=attachments,
        )

        result = item.to_dict()

        assert isinstance(result, dict)
        assert result["subject"] == "Math"
        assert result["subject_abbr"] == "MAT"
        assert result["description"] == "Homework"
        # to_dict converts to Dutch timezone, so compare with converted value
        assert result["deadline"] == to_dutch_time(deadline).isoformat()
        assert result["lesson_number"] == 3
        assert result["location"] == "B202"
        assert result["teacher"] == "Mr. Smith"
        assert result["is_test"] is True
        assert result["is_completed"] is False
        assert result["afspraak_id"] == 999
        assert len(result["attachments"]) == 1
        assert result["attachments"][0]["name"] == "homework.pdf"


class TestHomeworkDay:
    """Tests for HomeworkDay dataclass."""

    def test_creation_with_items(self):
        """Test creating HomeworkDay with items."""
        deadline = datetime(2026, 1, 8, 9, 0)
        items = [
            HomeworkItem(
                subject="Math",
                subject_abbr="MAT",
                description="Test",
                deadline=deadline,
                lesson_number=1,
                location=None,
                teacher=None,
                is_test=False,
                is_completed=False,
                attachments=[],
            )
        ]
        day = HomeworkDay(
            date=date(2026, 1, 8),
            items=items,
        )

        assert day.date == date(2026, 1, 8)
        assert len(day.items) == 1
        assert day.items[0].subject == "Math"

    def test_is_today(self):
        """Test is_today property."""
        today = date.today()
        day = HomeworkDay(date=today, items=[])

        assert day.is_today is True

    def test_is_not_today(self):
        """Test is_today property for other days."""
        tomorrow = date.today() + timedelta(days=1)
        day = HomeworkDay(date=tomorrow, items=[])

        assert day.is_today is False

    def test_is_tomorrow(self):
        """Test is_tomorrow property."""
        tomorrow = date.today() + timedelta(days=1)
        day = HomeworkDay(date=tomorrow, items=[])

        assert day.is_tomorrow is True

    def test_is_not_tomorrow(self):
        """Test is_tomorrow property for other days."""
        today = date.today()
        day = HomeworkDay(date=today, items=[])

        assert day.is_tomorrow is False

    def test_day_label_today(self):
        """Test day_label for today."""
        today = date.today()
        day = HomeworkDay(date=today, items=[])

        assert day.day_label == "Vandaag"

    def test_day_label_tomorrow(self):
        """Test day_label for tomorrow."""
        tomorrow = date.today() + timedelta(days=1)
        day = HomeworkDay(date=tomorrow, items=[])

        assert day.day_label == "Morgen"

    def test_day_label_other_day(self):
        """Test day_label for other days includes date."""
        future = date.today() + timedelta(days=3)
        day = HomeworkDay(date=future, items=[])

        label = day.day_label
        # Should contain day number
        assert str(future.day) in label

    def test_to_dict_serialization(self):
        """Test to_dict serialization."""
        deadline = datetime(2026, 1, 8, 9, 0)
        items = [
            HomeworkItem(
                subject="Test",
                subject_abbr="TST",
                description="Test homework",
                deadline=deadline,
                lesson_number=1,
                location=None,
                teacher=None,
                is_test=False,
                is_completed=False,
                attachments=[],
            )
        ]
        day = HomeworkDay(date=date(2026, 1, 8), items=items)
        result = day.to_dict()

        assert isinstance(result, dict)
        assert result["date"] == "2026-01-08"
        assert "day_label" in result
        assert len(result["items"]) == 1


class TestGradeInfo:
    """Tests for GradeInfo dataclass."""

    def test_creation(self):
        """Test creating GradeInfo."""
        grade_date = datetime(2026, 1, 8, 12, 0)
        grade = GradeInfo(
            subject="Wiskunde",
            grade="8.5",
            weight=2.0,
            date=grade_date,
            description="Toets hoofdstuk 4",
            is_sufficient=True,
        )

        assert grade.subject == "Wiskunde"
        assert grade.grade == "8.5"
        assert grade.weight == 2.0
        assert grade.date == grade_date
        assert grade.description == "Toets hoofdstuk 4"
        assert grade.is_sufficient is True

    def test_to_dict_serialization(self):
        """Test to_dict serialization."""
        grade_date = datetime(2026, 1, 8, 12, 0)
        grade = GradeInfo(
            subject="Math",
            grade="7.0",
            weight=1.5,
            date=grade_date,
            description="Test",
            is_sufficient=True,
        )

        result = grade.to_dict()

        assert isinstance(result, dict)
        assert result["subject"] == "Math"
        assert result["grade"] == "7.0"
        assert result["weight"] == 1.5
        # to_dict converts to Dutch timezone
        assert result["date"] == to_dutch_time(grade_date).isoformat()
        assert result["description"] == "Test"
        assert result["is_sufficient"] is True


class TestScheduleItem:
    """Tests for ScheduleItem dataclass."""

    def test_creation(self):
        """Test creating ScheduleItem."""
        start = datetime(2026, 1, 8, 9, 0)
        end = datetime(2026, 1, 8, 9, 50)

        item = ScheduleItem(
            start=start,
            end=end,
            subject="Wiskunde",
            location="A101",
            teacher="Dhr. Jansen",
            lesson_number=2,
            has_homework=True,
            is_cancelled=False,
        )

        assert item.start == start
        assert item.end == end
        assert item.subject == "Wiskunde"
        assert item.location == "A101"
        assert item.teacher == "Dhr. Jansen"
        assert item.lesson_number == 2
        assert item.has_homework is True
        assert item.is_cancelled is False

    def test_to_dict_serialization(self):
        """Test to_dict serialization."""
        start = datetime(2026, 1, 8, 10, 0)
        end = datetime(2026, 1, 8, 10, 50)

        item = ScheduleItem(
            start=start,
            end=end,
            subject="Science",
            location="Lab 1",
            teacher="Dr. Jones",
            lesson_number=3,
            has_homework=False,
            is_cancelled=True,
        )

        result = item.to_dict()

        assert isinstance(result, dict)
        # to_dict converts to Dutch timezone
        assert result["start"] == to_dutch_time(start).isoformat()
        assert result["end"] == to_dutch_time(end).isoformat()
        assert result["subject"] == "Science"
        assert result["location"] == "Lab 1"
        assert result["teacher"] == "Dr. Jones"
        assert result["lesson_number"] == 3
        assert result["has_homework"] is False
        assert result["is_cancelled"] is True


class TestMagisterCore:
    """Tests for MagisterCore static methods (pure functions)."""

    def test_filter_by_subject_case_insensitive(self):
        """Test subject filtering is case-insensitive."""
        deadline = datetime(2026, 1, 15, 9, 0)
        items = [
            HomeworkItem(
                subject="Wiskunde",
                subject_abbr="WIS",
                description="Test 1",
                deadline=deadline,
                lesson_number=1,
                location=None,
                teacher=None,
                is_test=False,
                is_completed=False,
                attachments=[],
            ),
            HomeworkItem(
                subject="Engels",
                subject_abbr="ENG",
                description="Test 2",
                deadline=deadline,
                lesson_number=2,
                location=None,
                teacher=None,
                is_test=False,
                is_completed=False,
                attachments=[],
            ),
        ]

        result = MagisterCore.filter_by_subject(items, "wiskunde")

        assert len(result) == 1
        assert result[0].subject == "Wiskunde"

    def test_filter_by_subject_abbreviation(self):
        """Test filtering by subject abbreviation."""
        deadline = datetime(2026, 1, 15, 9, 0)
        items = [
            HomeworkItem(
                subject="Wiskunde",
                subject_abbr="WIS",
                description="Test 1",
                deadline=deadline,
                lesson_number=1,
                location=None,
                teacher=None,
                is_test=False,
                is_completed=False,
                attachments=[],
            ),
            HomeworkItem(
                subject="Engels",
                subject_abbr="ENG",
                description="Test 2",
                deadline=deadline,
                lesson_number=2,
                location=None,
                teacher=None,
                is_test=False,
                is_completed=False,
                attachments=[],
            ),
        ]

        result = MagisterCore.filter_by_subject(items, "wis")

        assert len(result) == 1
        assert result[0].subject_abbr == "WIS"

    def test_filter_incomplete(self):
        """Test filtering incomplete homework."""
        deadline = datetime(2026, 1, 15, 9, 0)
        items = [
            HomeworkItem(
                subject="Math",
                subject_abbr="MAT",
                description="Done",
                deadline=deadline,
                lesson_number=1,
                location=None,
                teacher=None,
                is_test=False,
                is_completed=True,
                attachments=[],
            ),
            HomeworkItem(
                subject="Science",
                subject_abbr="SCI",
                description="Not done",
                deadline=deadline,
                lesson_number=2,
                location=None,
                teacher=None,
                is_test=False,
                is_completed=False,
                attachments=[],
            ),
        ]

        result = MagisterCore.filter_incomplete(items)

        assert len(result) == 1
        assert result[0].description == "Not done"
        assert result[0].is_completed is False

    def test_filter_tests(self):
        """Test filtering tests only."""
        deadline = datetime(2026, 1, 15, 9, 0)
        items = [
            HomeworkItem(
                subject="Math",
                subject_abbr="MAT",
                description="Homework",
                deadline=deadline,
                lesson_number=1,
                location=None,
                teacher=None,
                is_test=False,
                is_completed=False,
                attachments=[],
            ),
            HomeworkItem(
                subject="Science",
                subject_abbr="SCI",
                description="Test",
                deadline=deadline,
                lesson_number=2,
                location=None,
                teacher=None,
                is_test=True,
                is_completed=False,
                attachments=[],
            ),
        ]

        result = MagisterCore.filter_tests(items)

        assert len(result) == 1
        assert result[0].is_test is True
        assert result[0].description == "Test"

    def test_group_by_date(self):
        """Test grouping homework by deadline date."""
        date1 = datetime(2026, 1, 15, 9, 0)
        date2 = datetime(2026, 1, 16, 10, 0)
        date3 = datetime(2026, 1, 15, 14, 0)  # Same day as date1

        items = [
            HomeworkItem(
                subject="Math",
                subject_abbr="MAT",
                description="Day 1 - Item 1",
                deadline=date1,
                lesson_number=1,
                location=None,
                teacher=None,
                is_test=False,
                is_completed=False,
                attachments=[],
            ),
            HomeworkItem(
                subject="Science",
                subject_abbr="SCI",
                description="Day 2",
                deadline=date2,
                lesson_number=2,
                location=None,
                teacher=None,
                is_test=False,
                is_completed=False,
                attachments=[],
            ),
            HomeworkItem(
                subject="English",
                subject_abbr="ENG",
                description="Day 1 - Item 2",
                deadline=date3,
                lesson_number=3,
                location=None,
                teacher=None,
                is_test=False,
                is_completed=False,
                attachments=[],
            ),
        ]

        result = MagisterCore.group_by_date(items)

        assert len(result) == 2  # Two different days
        assert result[0].date == date(2026, 1, 15)
        assert len(result[0].items) == 2  # Two items on same day
        assert result[1].date == date(2026, 1, 16)
        assert len(result[1].items) == 1

    def test_group_by_date_sorting(self):
        """Test that grouped days are sorted by date."""
        date1 = datetime(2026, 1, 20, 9, 0)
        date2 = datetime(2026, 1, 15, 10, 0)

        items = [
            HomeworkItem(
                subject="Math",
                subject_abbr="MAT",
                description="Later",
                deadline=date1,
                lesson_number=1,
                location=None,
                teacher=None,
                is_test=False,
                is_completed=False,
                attachments=[],
            ),
            HomeworkItem(
                subject="Science",
                subject_abbr="SCI",
                description="Earlier",
                deadline=date2,
                lesson_number=2,
                location=None,
                teacher=None,
                is_test=False,
                is_completed=False,
                attachments=[],
            ),
        ]

        result = MagisterCore.group_by_date(items)

        # Should be sorted with earlier date first
        assert result[0].date == date(2026, 1, 15)
        assert result[1].date == date(2026, 1, 20)

    def test_calculate_average_basic(self):
        """Test calculating weighted average of grades."""
        grades = [
            GradeInfo(
                subject="Math",
                grade="8.0",
                weight=1.0,
                date=None,
                description=None,
                is_sufficient=True,
            ),
            GradeInfo(
                subject="Science",
                grade="6.0",
                weight=1.0,
                date=None,
                description=None,
                is_sufficient=True,
            ),
        ]

        result = MagisterCore.calculate_average(grades)

        assert result == 7.0

    def test_calculate_average_weighted(self):
        """Test weighted average calculation."""
        grades = [
            GradeInfo(
                subject="Math",
                grade="8.0",
                weight=2.0,
                date=None,
                description=None,
                is_sufficient=True,
            ),
            GradeInfo(
                subject="Science",
                grade="6.0",
                weight=1.0,
                date=None,
                description=None,
                is_sufficient=True,
            ),
        ]

        result = MagisterCore.calculate_average(grades)

        # (8.0 * 2 + 6.0 * 1) / (2 + 1) = 22 / 3 = 7.33...
        assert result == 7.33

    def test_calculate_average_comma_decimal(self):
        """Test average calculation with comma decimal separator."""
        grades = [
            GradeInfo(
                subject="Math",
                grade="7,5",
                weight=1.0,
                date=None,
                description=None,
                is_sufficient=True,
            ),
            GradeInfo(
                subject="Science",
                grade="8,5",
                weight=1.0,
                date=None,
                description=None,
                is_sufficient=True,
            ),
        ]

        result = MagisterCore.calculate_average(grades)

        assert result == 8.0

    def test_calculate_average_empty_list(self):
        """Test average calculation with empty list."""
        result = MagisterCore.calculate_average([])

        assert result is None

    def test_calculate_average_invalid_grades(self):
        """Test average calculation skips invalid grades."""
        grades = [
            GradeInfo(
                subject="Math",
                grade="8.0",
                weight=1.0,
                date=None,
                description=None,
                is_sufficient=True,
            ),
            GradeInfo(
                subject="Science",
                grade="vrij",  # Invalid grade
                weight=1.0,
                date=None,
                description=None,
                is_sufficient=True,
            ),
        ]

        result = MagisterCore.calculate_average(grades)

        # Should only use valid grades
        assert result == 8.0

    def test_parse_homework_from_api(self):
        """Test parsing homework from API response."""
        api_data = {
            "Id": 12345,
            "Start": "2026-01-15T09:00:00Z",
            "Vakken": [{"Naam": "Wiskunde", "Afkorting": "WIS"}],
            "Docenten": [{"Naam": "Dhr. Jansen"}],
            "Lokalen": [{"Naam": "A101"}],
            "Inhoud": "Maak opgaven 4.1-4.15",
            "LesuurVan": 2,
            "InfoType": 1,
            "Afgerond": False,
            "Bijlagen": [
                {
                    "Id": 999,
                    "Naam": "opgaven.pdf",
                    "GrootteLeesbaar": "2.5 MB",
                    "ContentType": "application/pdf",
                    "Uri": "https://example.com/opgaven.pdf",
                }
            ],
        }

        result = MagisterCore.parse_homework_from_api(api_data)

        assert isinstance(result, HomeworkItem)
        assert result.subject == "Wiskunde"
        assert result.subject_abbr == "WIS"
        assert result.description == "Maak opgaven 4.1-4.15"
        assert result.lesson_number == 2
        assert result.location == "A101"
        assert result.teacher == "Dhr. Jansen"
        assert result.is_test is False
        assert result.is_completed is False
        assert result.afspraak_id == 12345
        assert len(result.attachments) == 1
        assert result.attachments[0].name == "opgaven.pdf"

    def test_parse_homework_from_api_test(self):
        """Test parsing test from API response."""
        api_data = {
            "Id": 12345,
            "Start": "2026-01-15T09:00:00Z",
            "Vakken": [{"Naam": "Geschiedenis"}],
            "Docenten": [],
            "Lokalen": [],
            "Inhoud": "Toets H6-7",
            "InfoType": 2,  # InfoType 2 = toets
            "Afgerond": False,
            "Bijlagen": [],
        }

        result = MagisterCore.parse_homework_from_api(api_data)

        assert result.is_test is True
        assert result.subject == "Geschiedenis"

    def test_parse_grade_from_api(self):
        """Test parsing grade from API response."""
        api_data = {
            "Vak": {"Omschrijving": "Wiskunde"},
            "CijferStr": "8,5",
            "Weging": 2.0,
            "DatumIngevoerd": "2026-01-08T12:00:00Z",
            "KolomOmschrijving": "Toets hoofdstuk 4",
        }

        result = MagisterCore.parse_grade_from_api(api_data)

        assert isinstance(result, GradeInfo)
        assert result.subject == "Wiskunde"
        assert result.grade == "8,5"
        assert result.weight == 2.0
        assert result.description == "Toets hoofdstuk 4"
        assert result.is_sufficient is True

    def test_parse_grade_insufficient(self):
        """Test parsing insufficient grade."""
        api_data = {
            "Vak": {"Omschrijving": "Math"},
            "CijferStr": "4.5",
            "DatumIngevoerd": "2026-01-08T12:00:00Z",
        }

        result = MagisterCore.parse_grade_from_api(api_data)

        assert result.is_sufficient is False

    def test_parse_schedule_from_api(self):
        """Test parsing schedule item from API response."""
        api_data = {
            "Start": "2026-01-08T09:00:00Z",
            "Einde": "2026-01-08T09:50:00Z",
            "Vakken": [{"Naam": "Wiskunde"}],
            "Docenten": [{"Naam": "Dhr. Jansen"}],
            "Lokalen": [{"Naam": "A101"}],
            "LesuurVan": 2,
            "Inhoud": "Huiswerk bespreken",
            "Status": 0,
        }

        result = MagisterCore.parse_schedule_from_api(api_data)

        assert isinstance(result, ScheduleItem)
        assert result.subject == "Wiskunde"
        assert result.location == "A101"
        assert result.teacher == "Dhr. Jansen"
        assert result.lesson_number == 2
        assert result.has_homework is True
        assert result.is_cancelled is False

    def test_parse_schedule_cancelled(self):
        """Test parsing cancelled schedule item."""
        api_data = {
            "Start": "2026-01-08T09:00:00Z",
            "Einde": "2026-01-08T09:50:00Z",
            "Vakken": [{"Naam": "Science"}],
            "Docenten": [],
            "Lokalen": [],
            "Status": 5,  # Status 5 = cancelled
        }

        result = MagisterCore.parse_schedule_from_api(api_data)

        assert result.is_cancelled is True
