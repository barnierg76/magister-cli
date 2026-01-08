"""Tests for API client."""

import json
from pathlib import Path

import httpx
import pytest
import respx

from magister_cli.api.client import (
    MagisterAPIError,
    MagisterClient,
    RateLimitError,
    TokenExpiredError,
)


FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def account_response():
    """Load account fixture."""
    with open(FIXTURES_DIR / "account.json") as f:
        return json.load(f)


@pytest.fixture
def afspraken_response():
    """Load afspraken fixture."""
    with open(FIXTURES_DIR / "afspraken.json") as f:
        return json.load(f)


@pytest.fixture
def cijfers_response():
    """Load cijfers fixture."""
    with open(FIXTURES_DIR / "cijfers.json") as f:
        return json.load(f)


class TestMagisterClient:
    """Tests for MagisterClient."""

    def test_context_manager(self):
        """Client can be used as context manager."""
        client = MagisterClient("test", "token123")

        assert client._client is None

        with client:
            assert client._client is not None

        assert client._client is None

    @respx.mock
    def test_get_account(self, account_response):
        """Fetch account info."""
        respx.get("https://test.magister.net/api/account").mock(
            return_value=httpx.Response(200, json=account_response)
        )

        with MagisterClient("test", "token123") as client:
            account = client.get_account()

        assert account.persoon_id == 12345
        assert account.naam == "Jan Jansen"
        assert client.person_id == 12345

    @respx.mock
    def test_get_homework(self, account_response, afspraken_response):
        """Fetch homework."""
        from datetime import date

        respx.get("https://test.magister.net/api/account").mock(
            return_value=httpx.Response(200, json=account_response)
        )
        respx.get("https://test.magister.net/api/personen/12345/afspraken").mock(
            return_value=httpx.Response(200, json=afspraken_response)
        )

        with MagisterClient("test", "token123") as client:
            homework = client.get_homework(date(2026, 1, 9), date(2026, 1, 15))

        assert len(homework) == 3
        assert all(a.heeft_huiswerk for a in homework)

    @respx.mock
    def test_get_recent_grades(self, account_response, cijfers_response):
        """Fetch recent grades."""
        respx.get("https://test.magister.net/api/account").mock(
            return_value=httpx.Response(200, json=account_response)
        )
        respx.get("https://test.magister.net/api/personen/12345/cijfers/laatste").mock(
            return_value=httpx.Response(200, json=cijfers_response)
        )

        with MagisterClient("test", "token123") as client:
            grades = client.get_recent_grades(limit=10)

        assert len(grades) == 3
        assert grades[0].cijfer_numeriek == 7.5

    @respx.mock
    def test_token_expired_error(self):
        """Handle 401 response."""
        respx.get("https://test.magister.net/api/account").mock(
            return_value=httpx.Response(401, json={"error": "Unauthorized"})
        )

        with pytest.raises(TokenExpiredError) as exc_info:
            with MagisterClient("test", "token123") as client:
                client.get_account()

        assert exc_info.value.status_code == 401

    @respx.mock
    def test_rate_limit_error(self):
        """Handle 429 response."""
        respx.get("https://test.magister.net/api/account").mock(
            return_value=httpx.Response(429, headers={"Retry-After": "120"})
        )

        with pytest.raises(RateLimitError) as exc_info:
            with MagisterClient("test", "token123") as client:
                client.get_account()

        assert exc_info.value.retry_after == 120

    @respx.mock
    def test_generic_api_error(self):
        """Handle other error responses."""
        respx.get("https://test.magister.net/api/account").mock(
            return_value=httpx.Response(500, text="Internal Server Error")
        )

        with pytest.raises(MagisterAPIError) as exc_info:
            with MagisterClient("test", "token123") as client:
                client.get_account()

        assert exc_info.value.status_code == 500

    def test_client_not_initialized_error(self):
        """Error when using client outside context manager."""
        client = MagisterClient("test", "token123")

        with pytest.raises(RuntimeError, match="not initialized"):
            client.get_account()

    @respx.mock
    def test_authorization_header(self, account_response):
        """Client sends authorization header."""
        route = respx.get("https://test.magister.net/api/account").mock(
            return_value=httpx.Response(200, json=account_response)
        )

        with MagisterClient("test", "my_secret_token") as client:
            client.get_account()

        request = route.calls[0].request
        assert request.headers["Authorization"] == "Bearer my_secret_token"

    @respx.mock
    def test_person_id_cached(self, account_response, afspraken_response):
        """Person ID is fetched once and cached."""
        from datetime import date

        account_route = respx.get("https://test.magister.net/api/account").mock(
            return_value=httpx.Response(200, json=account_response)
        )
        respx.get("https://test.magister.net/api/personen/12345/afspraken").mock(
            return_value=httpx.Response(200, json=afspraken_response)
        )

        with MagisterClient("test", "token123") as client:
            client.get_account()
            client.get_homework(date(2026, 1, 9), date(2026, 1, 15))
            client.get_homework(date(2026, 1, 9), date(2026, 1, 15))

        assert len(account_route.calls) == 1
