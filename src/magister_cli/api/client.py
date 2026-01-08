"""HTTP client for Magister API with retry logic and rate limiting."""

from datetime import date
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from pathlib import Path

from magister_cli.api.models import (
    Account,
    Afspraak,
    AfspraakResponse,
    Bijlage,
    Cijfer,
    CijferResponse,
    Kind,
    KindResponse,
)
from magister_cli.config import get_settings


class MagisterAPIError(Exception):
    """Base exception for Magister API errors."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class TokenExpiredError(MagisterAPIError):
    """Token has expired and needs refresh."""

    pass


class RateLimitError(MagisterAPIError):
    """Rate limit exceeded."""

    def __init__(self, message: str, retry_after: int = 60):
        super().__init__(message, 429)
        self.retry_after = retry_after


class MagisterClient:
    """Synchronous HTTP client for Magister API."""

    def __init__(self, school: str, token: str, timeout: int | None = None):
        self.school = school
        self.token = token
        self._client: httpx.Client | None = None
        self._timeout = timeout or get_settings().timeout
        self._account_id: int | None = None  # The logged-in account's ID
        self._student_id: int | None = None  # The student's ID (may differ for parents)
        self._person_name: str | None = None
        self._is_parent: bool = False
        self._children: list[Kind] | None = None

    @property
    def base_url(self) -> str:
        """Get the base URL for this school's Magister API."""
        return f"https://{self.school}.magister.net/api"

    def __enter__(self) -> "MagisterClient":
        """Enter context manager, creating HTTP client."""
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/json",
                "User-Agent": "Magister-CLI/0.1.0",
            },
            timeout=self._timeout,
        )
        return self

    def __exit__(self, *args) -> None:
        """Exit context manager, closing HTTP client."""
        if self._client:
            self._client.close()
            self._client = None

    def _check_client(self) -> None:
        """Ensure client is initialized."""
        if self._client is None:
            raise RuntimeError("Client not initialized - use 'with' context manager")

    def _handle_response(self, response: httpx.Response) -> Any:
        """Handle API response, raising appropriate errors."""
        if response.status_code == 401:
            raise TokenExpiredError("Access token has expired", 401)

        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", "60"))
            raise RateLimitError("Rate limit exceeded", retry_after)

        if response.status_code >= 400:
            raise MagisterAPIError(
                f"API error: {response.status_code} - {response.text}",
                response.status_code,
            )

        return response.json()

    @retry(
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    def _request(self, method: str, endpoint: str, **kwargs) -> Any:
        """Make an API request with retry logic."""
        self._check_client()
        assert self._client is not None

        response = self._client.request(method, endpoint, **kwargs)
        return self._handle_response(response)

    def get_account(self) -> Account:
        """Get account info and determine if this is a parent or student account."""
        data = self._request("GET", "/account")
        account = Account.model_validate(data)
        self._account_id = account.persoon_id
        self._person_name = account.naam

        # Check if this is a parent account by looking for "Ouder" group
        self._is_parent = account.is_parent

        if self._is_parent:
            # For parent accounts, get children and use first child's ID
            children = self.get_children()
            if children:
                self._student_id = children[0].id
                self._person_name = children[0].volledige_naam
            else:
                # No children found, fall back to account ID
                self._student_id = self._account_id
        else:
            # Student account - use own ID
            self._student_id = self._account_id

        return account

    def get_children(self) -> list[Kind]:
        """Get children for a parent account."""
        if self._account_id is None:
            self.get_account()

        try:
            data = self._request("GET", f"/personen/{self._account_id}/kinderen")
            response = KindResponse.from_response(data)
            self._children = response.items
            return self._children
        except MagisterAPIError:
            # Not a parent account or no children
            return []

    def _ensure_student_id(self) -> int:
        """Ensure student_id is available, fetching account if needed."""
        if self._student_id is None:
            self.get_account()
        assert self._student_id is not None
        return self._student_id

    def get_appointments(self, start: date, end: date) -> list[Afspraak]:
        """Get appointments for a date range."""
        student_id = self._ensure_student_id()

        data = self._request(
            "GET",
            f"/personen/{student_id}/afspraken",
            params={"van": start.isoformat(), "tot": end.isoformat()},
        )

        response = AfspraakResponse.from_response(data)
        return response.items

    def get_homework(self, start: date, end: date) -> list[Afspraak]:
        """Get appointments that have homework."""
        appointments = self.get_appointments(start, end)
        return [a for a in appointments if a.heeft_huiswerk]

    def get_recent_grades(self, limit: int = 10) -> list[Cijfer]:
        """Get recent grades."""
        student_id = self._ensure_student_id()

        data = self._request(
            "GET",
            f"/personen/{student_id}/cijfers/laatste",
            params={"top": limit},
        )

        response = CijferResponse.from_response(data)
        return response.items

    def get_schedule(self, date_: date) -> list[Afspraak]:
        """Get schedule for a specific date."""
        return self.get_appointments(date_, date_)

    def get_appointment(self, afspraak_id: int) -> Afspraak:
        """Get a single appointment with full details including attachments."""
        student_id = self._ensure_student_id()

        data = self._request(
            "GET",
            f"/personen/{student_id}/afspraken/{afspraak_id}",
        )

        return Afspraak.model_validate(data)

    def get_homework_with_attachments(self, start: date, end: date) -> list[Afspraak]:
        """Get homework with attachments populated for items that have them."""
        appointments = self.get_homework(start, end)

        # For items with attachments, fetch full details
        result = []
        for afspraak in appointments:
            if afspraak.heeft_bijlagen:
                # Fetch full appointment to get bijlagen
                full_afspraak = self.get_appointment(afspraak.id)
                result.append(full_afspraak)
            else:
                result.append(afspraak)

        return result

    def download_attachment(self, bijlage: Bijlage, output_dir: Path | None = None) -> Path:
        """Download an attachment to the specified directory."""
        self._check_client()
        assert self._client is not None

        download_path = bijlage.download_path
        if not download_path:
            raise MagisterAPIError(f"No download path for attachment: {bijlage.naam}")

        # The download path from API includes /api/ prefix, but our base_url already ends with /api
        # So we need to strip the /api prefix from the download path
        if download_path.startswith("/api/"):
            download_path = download_path[4:]  # Remove "/api" prefix

        # Build full URL and use a new client with redirect support for downloads
        full_url = f"{self.base_url}{download_path}"
        with httpx.Client(
            headers={"Authorization": f"Bearer {self.token}"},
            timeout=self._timeout,
            follow_redirects=True,
        ) as download_client:
            response = download_client.get(full_url)

        if response.status_code >= 400:
            raise MagisterAPIError(
                f"Failed to download attachment: {response.status_code}",
                response.status_code,
            )

        # Determine output path
        if output_dir is None:
            output_dir = Path.cwd()
        output_dir.mkdir(parents=True, exist_ok=True)

        output_path = output_dir / bijlage.naam

        # Handle duplicate filenames
        if output_path.exists():
            stem = output_path.stem
            suffix = output_path.suffix
            counter = 1
            while output_path.exists():
                output_path = output_dir / f"{stem}_{counter}{suffix}"
                counter += 1

        output_path.write_bytes(response.content)
        return output_path

    @property
    def person_id(self) -> int | None:
        """Get the student's ID (for API calls)."""
        return self._student_id

    @property
    def person_name(self) -> str | None:
        """Get the student's name."""
        return self._person_name

    @property
    def is_parent_account(self) -> bool:
        """Check if this is a parent account."""
        return self._is_parent
