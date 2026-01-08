"""Tests for homework service."""

import json
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from magister_cli.api.models import Afspraak
from magister_cli.services.homework import HomeworkDay, HomeworkItem, HomeworkService


FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestHomeworkItem:
    """Tests for HomeworkItem."""

    def test_from_afspraak(self):
        """Create HomeworkItem from Afspraak."""
        afspraak = Afspraak.model_validate({
            "Id": 1,
            "Start": "2026-01-09T09:00:00",
            "Einde": "2026-01-09T09:50:00",
            "Omschrijving": "Wiskunde",
            "Inhoud": "Maak opgaven 4.1-4.15",
            "InfoType": 1,
            "Vakken": [{"Id": 101, "Naam": "Wiskunde", "Afkorting": "WIS"}],
            "LesuurVan": 2,
            "Toets": False,
        })

        item = HomeworkItem.from_afspraak(afspraak)

        assert item.subject == "Wiskunde"
        assert item.subject_abbr == "WIS"
        assert item.description == "Maak opgaven 4.1-4.15"
        assert item.lesson_number == 2
        assert not item.is_test

    def test_from_afspraak_test(self):
        """Create HomeworkItem for test."""
        afspraak = Afspraak.model_validate({
            "Id": 1,
            "Start": "2026-01-09T09:00:00",
            "Einde": "2026-01-09T09:50:00",
            "Omschrijving": "Geschiedenis",
            "Inhoud": "Toets H6-7",
            "InfoType": 1,
            "Vakken": [{"Id": 103, "Naam": "Geschiedenis"}],
            "Toets": True,
        })

        item = HomeworkItem.from_afspraak(afspraak)

        assert item.is_test
        assert item.subject == "Geschiedenis"


class TestHomeworkDay:
    """Tests for HomeworkDay."""

    def test_is_today(self):
        """Check if day is today."""
        today = date.today()
        day = HomeworkDay(date=today, items=[])

        assert day.is_today
        assert not day.is_tomorrow

    def test_is_tomorrow(self):
        """Check if day is tomorrow."""
        tomorrow = date.today() + timedelta(days=1)
        day = HomeworkDay(date=tomorrow, items=[])

        assert not day.is_today
        assert day.is_tomorrow

    def test_day_label_today(self):
        """Day label for today."""
        today = date.today()
        day = HomeworkDay(date=today, items=[])

        assert day.day_label == "Vandaag"

    def test_day_label_tomorrow(self):
        """Day label for tomorrow."""
        tomorrow = date.today() + timedelta(days=1)
        day = HomeworkDay(date=tomorrow, items=[])

        assert day.day_label == "Morgen"

    def test_day_label_other(self):
        """Day label for other days."""
        future = date.today() + timedelta(days=3)
        day = HomeworkDay(date=future, items=[])

        label = day.day_label
        assert str(future.day) in label


class TestHomeworkService:
    """Tests for HomeworkService."""

    @pytest.fixture
    def mock_token(self):
        """Mock get_current_token."""
        with patch("magister_cli.services.homework.get_current_token") as mock:
            token = MagicMock()
            token.school = "vsvonh"
            token.access_token = "test_token"
            mock.return_value = token
            yield mock

    @pytest.fixture
    def mock_client(self):
        """Mock MagisterClient."""
        with patch("magister_cli.services.homework.MagisterClient") as mock:
            yield mock

    @pytest.fixture
    def sample_afspraken(self):
        """Sample afspraken with homework."""
        with open(FIXTURES_DIR / "afspraken.json") as f:
            data = json.load(f)
        return [Afspraak.model_validate(item) for item in data["Items"]]

    def test_get_homework_not_authenticated(self, mock_token):
        """Error when not authenticated."""
        mock_token.return_value = None

        service = HomeworkService(school="vsvonh")

        with pytest.raises(RuntimeError, match="Not authenticated"):
            service.get_homework()

    def test_get_homework_filters_items(self, mock_token, mock_client, sample_afspraken):
        """Only return items with homework."""
        client_instance = MagicMock()
        client_instance.__enter__ = MagicMock(return_value=client_instance)
        client_instance.__exit__ = MagicMock(return_value=False)
        hw_items = [a for a in sample_afspraken if a.heeft_huiswerk]
        client_instance.get_homework.return_value = hw_items
        client_instance.get_homework_with_attachments.return_value = hw_items
        mock_client.return_value = client_instance

        service = HomeworkService(school="vsvonh")
        days = service.get_homework(days=7)

        assert len(days) > 0
        for day in days:
            for item in day.items:
                assert item.description

    def test_get_homework_by_subject(self, mock_token, mock_client, sample_afspraken):
        """Filter homework by subject."""
        client_instance = MagicMock()
        client_instance.__enter__ = MagicMock(return_value=client_instance)
        client_instance.__exit__ = MagicMock(return_value=False)
        hw_items = [a for a in sample_afspraken if a.heeft_huiswerk]
        client_instance.get_homework.return_value = hw_items
        client_instance.get_homework_with_attachments.return_value = hw_items
        mock_client.return_value = client_instance

        service = HomeworkService(school="vsvonh")
        days = service.get_homework(days=7, subject="wiskunde")

        for day in days:
            for item in day.items:
                assert "wiskunde" in item.subject.lower() or (
                    item.subject_abbr and "wis" in item.subject_abbr.lower()
                )

    def test_get_upcoming_tests(self, mock_token, mock_client, sample_afspraken):
        """Get only test items."""
        client_instance = MagicMock()
        client_instance.__enter__ = MagicMock(return_value=client_instance)
        client_instance.__exit__ = MagicMock(return_value=False)
        hw_items = [a for a in sample_afspraken if a.heeft_huiswerk]
        client_instance.get_homework.return_value = hw_items
        client_instance.get_homework_with_attachments.return_value = hw_items
        mock_client.return_value = client_instance

        service = HomeworkService(school="vsvonh")
        tests = service.get_upcoming_tests(days=14)

        assert len(tests) == 1
        assert tests[0].is_test
        assert tests[0].subject == "Geschiedenis"

    def test_get_homework_sorted_by_date(self, mock_token, mock_client, sample_afspraken):
        """Homework days are sorted by date."""
        client_instance = MagicMock()
        client_instance.__enter__ = MagicMock(return_value=client_instance)
        client_instance.__exit__ = MagicMock(return_value=False)
        hw_items = [a for a in sample_afspraken if a.heeft_huiswerk]
        client_instance.get_homework.return_value = hw_items
        client_instance.get_homework_with_attachments.return_value = hw_items
        mock_client.return_value = client_instance

        service = HomeworkService(school="vsvonh")
        days = service.get_homework(days=7)

        if len(days) > 1:
            dates = [d.date for d in days]
            assert dates == sorted(dates)
