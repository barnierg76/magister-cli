"""Tests for API models."""

import json
from pathlib import Path


from magister_cli.api.models import (
    Account,
    Afspraak,
    AfspraakResponse,
    Cijfer,
    CijferResponse,
    Vak,
)


FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestVak:
    """Tests for Vak model."""

    def test_parse_from_api(self):
        """Parse Vak from API response."""
        data = {"Id": 101, "Naam": "Wiskunde", "Afkorting": "WIS"}
        vak = Vak.model_validate(data)

        assert vak.id == 101
        assert vak.naam == "Wiskunde"
        assert vak.afkorting == "WIS"

    def test_optional_afkorting(self):
        """Afkorting is optional."""
        data = {"Id": 102, "Naam": "Engels"}
        vak = Vak.model_validate(data)

        assert vak.afkorting is None


class TestAfspraak:
    """Tests for Afspraak model."""

    def test_parse_from_fixture(self):
        """Parse Afspraak from fixture data."""
        with open(FIXTURES_DIR / "afspraken.json") as f:
            data = json.load(f)

        response = AfspraakResponse.model_validate(data)
        assert len(response.items) == 4

        homework_item = response.items[0]
        assert homework_item.id == 1001
        assert homework_item.vak_naam == "Wiskunde"
        assert homework_item.heeft_huiswerk
        assert "4.1" in homework_item.huiswerk_tekst

    def test_geen_huiswerk(self):
        """Item without homework."""
        data = {
            "Id": 1,
            "Start": "2026-01-09T09:00:00",
            "Einde": "2026-01-09T09:50:00",
            "Omschrijving": "Gym",
            "Inhoud": None,
            "Huiswerk": None,
            "InfoType": 1,
            "Vakken": [],
        }
        afspraak = Afspraak.model_validate(data)

        assert not afspraak.heeft_huiswerk
        assert afspraak.huiswerk_tekst == ""
        assert afspraak.vak_naam == "Gym"

    def test_toets_flag(self):
        """Test identification."""
        with open(FIXTURES_DIR / "afspraken.json") as f:
            data = json.load(f)

        response = AfspraakResponse.from_response(data)
        tests = [a for a in response.items if a.is_toets]

        assert len(tests) == 1
        assert tests[0].vak_naam == "Geschiedenis"


class TestCijfer:
    """Tests for Cijfer model."""

    def test_parse_from_fixture(self):
        """Parse Cijfer from fixture data."""
        with open(FIXTURES_DIR / "cijfers.json") as f:
            data = json.load(f)

        response = CijferResponse.from_response(data)
        assert len(response.items) == 3

        grade = response.items[0]
        assert grade.id == 5001
        assert grade.vak_naam == "Wiskunde"
        assert grade.cijfer_str == "7,5"
        assert grade.cijfer_numeriek == 7.5

    def test_numeric_conversion(self):
        """Grade string is converted to numeric."""
        data = {
            "CijferId": 1,
            "Vak": {"Id": 1, "Naam": "Test"},
            "CijferStr": "8,5",
            "DatumIngevoerd": "2026-01-08T12:00:00",
        }
        grade = Cijfer.model_validate(data)

        assert grade.cijfer_numeriek == 8.5

    def test_non_numeric_grade(self):
        """Non-numeric grade returns None for numeric."""
        data = {
            "CijferId": 1,
            "Vak": {"Id": 1, "Naam": "Test"},
            "CijferStr": "voldoende",
            "DatumIngevoerd": "2026-01-08T12:00:00",
        }
        grade = Cijfer.model_validate(data)

        assert grade.cijfer_str == "voldoende"
        assert grade.cijfer_numeriek is None


class TestAccount:
    """Tests for Account model."""

    def test_parse_from_fixture(self):
        """Parse Account from fixture data."""
        with open(FIXTURES_DIR / "account.json") as f:
            data = json.load(f)

        account = Account.model_validate(data)

        assert account.persoon_id == 12345
        assert account.naam == "Jan Jansen"

    def test_with_tussenvoegsel(self):
        """Name includes tussenvoegsel."""
        data = {
            "Persoon": {
                "Id": 1,
                "Voornaam": "Jan",
                "Achternaam": "Berg",
                "Tussenvoegsel": "van den",
            }
        }
        account = Account.model_validate(data)

        assert account.naam == "Jan van den Berg"


class TestResponseWrappers:
    """Tests for response wrapper classes."""

    def test_afspraak_response_from_wrapped(self):
        """Parse from Items wrapper."""
        data = {"Items": [{"Id": 1, "Start": "2026-01-09T09:00:00", "Einde": "2026-01-09T09:50:00", "Omschrijving": "Test", "InfoType": 1}]}
        response = AfspraakResponse.from_response(data)

        assert len(response.items) == 1

    def test_afspraak_response_from_list(self):
        """Parse from unwrapped list."""
        data = [{"Id": 1, "Start": "2026-01-09T09:00:00", "Einde": "2026-01-09T09:50:00", "Omschrijving": "Test", "InfoType": 1}]
        response = AfspraakResponse.from_response(data)

        assert len(response.items) == 1

    def test_cijfer_response_from_wrapped(self):
        """Parse grades from Items wrapper."""
        data = {"Items": [{"CijferId": 1, "Vak": {"Id": 1, "Naam": "Test"}, "CijferStr": "8", "DatumIngevoerd": "2026-01-08T12:00:00"}]}
        response = CijferResponse.from_response(data)

        assert len(response.items) == 1

    def test_empty_response(self):
        """Handle empty response."""
        response = AfspraakResponse.from_response({})
        assert len(response.items) == 0
