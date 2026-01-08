"""Magister API facade with resource accessors."""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from magister_cli.api.exceptions import (
    MagisterAPIError,
    RateLimitError,
    TokenExpiredError,
)
from magister_cli.api.models import Account, Afspraak, Bijlage, Cijfer, Kind
from magister_cli.api.resources import (
    AccountResource,
    AppointmentsResource,
    AttachmentsResource,
    GradesResource,
    MessagesResource,
)
from magister_cli.config import get_settings, validate_school_code


class MagisterClient:
    """Facade for Magister API with lazy-loaded resources.

    This client provides two ways to interact with the API:

    1. Direct methods (backward compatible):
       ```
       with MagisterClient(school, token) as client:
           homework = client.get_homework(start, end)
       ```

    2. Resource accessors (new pattern):
       ```
       with MagisterClient(school, token) as client:
           homework = client.appointments.with_homework(start, end)
       ```

    The resource pattern is preferred for new code as it provides better
    organization and makes it easy to add new endpoints.
    """

    def __init__(self, school: str, token: str, timeout: int | None = None):
        # Validate school code to prevent SSRF
        self.school = validate_school_code(school)
        self.token = token
        self._timeout = timeout or get_settings().timeout
        self._client: httpx.Client | None = None

        # State
        self._account_id: int | None = None
        self._student_id: int | None = None
        self._person_name: str | None = None
        self._is_parent: bool = False
        self._children: list[Kind] | None = None

        # Resources (lazy initialized)
        self._account_resource: AccountResource | None = None
        self._appointments_resource: AppointmentsResource | None = None
        self._grades_resource: GradesResource | None = None
        self._attachments_resource: AttachmentsResource | None = None
        self._messages_resource: MessagesResource | None = None

    @property
    def base_url(self) -> str:
        """Get the base URL for this school's Magister API."""
        return f"https://{self.school}.magister.net/api"

    def __enter__(self) -> MagisterClient:
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
        # Reset resources
        self._account_resource = None
        self._appointments_resource = None
        self._grades_resource = None
        self._attachments_resource = None
        self._messages_resource = None

    def _ensure_client(self) -> httpx.Client:
        """Ensure client is initialized."""
        if self._client is None:
            raise RuntimeError("Client not initialized - use 'with' context manager")
        return self._client

    def _ensure_student_id(self) -> int:
        """Ensure student_id is available, fetching account if needed."""
        if self._student_id is None:
            self.get_account()
        assert self._student_id is not None
        return self._student_id

    # -------------------------------------------------------------------------
    # Resource accessors (new pattern)
    # -------------------------------------------------------------------------

    @property
    def account(self) -> AccountResource:
        """Access account-related API methods."""
        if self._account_resource is None:
            self._account_resource = AccountResource(self._ensure_client(), 0)
        return self._account_resource

    @property
    def appointments(self) -> AppointmentsResource:
        """Access appointment-related API methods."""
        if self._appointments_resource is None:
            self._appointments_resource = AppointmentsResource(
                self._ensure_client(), self._ensure_student_id()
            )
        return self._appointments_resource

    @property
    def grades(self) -> GradesResource:
        """Access grade-related API methods."""
        if self._grades_resource is None:
            self._grades_resource = GradesResource(
                self._ensure_client(), self._ensure_student_id()
            )
        return self._grades_resource

    @property
    def attachments(self) -> AttachmentsResource:
        """Access attachment download methods."""
        if self._attachments_resource is None:
            self._attachments_resource = AttachmentsResource(
                self._ensure_client(),
                self._ensure_student_id(),
                self.base_url,
                self.token,
                self._timeout,
            )
        return self._attachments_resource

    @property
    def messages(self) -> MessagesResource:
        """Access message-related API methods."""
        if self._messages_resource is None:
            self._messages_resource = MessagesResource(
                self._ensure_client(), self._ensure_student_id()
            )
        return self._messages_resource

    # -------------------------------------------------------------------------
    # Direct methods (backward compatible)
    # -------------------------------------------------------------------------

    def _handle_response(self, response: httpx.Response) -> Any:
        """Handle API response, raising appropriate errors."""
        if response.status_code == 401:
            raise TokenExpiredError("Access token has expired", 401)

        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", "60"))
            raise RateLimitError("Rate limit exceeded", retry_after)

        if response.status_code >= 400:
            # Log detailed error for debugging, but don't expose raw response to users
            logger.error(f"API error: {response.status_code} - {response.text}")
            raise MagisterAPIError(
                f"API request failed ({response.status_code})",
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
        client = self._ensure_client()
        response = client.request(method, endpoint, **kwargs)
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
            if isinstance(data, dict):
                items = data.get("items", data.get("Items", []))
                self._children = [Kind.model_validate(item) for item in items]
            elif isinstance(data, list):
                self._children = [Kind.model_validate(item) for item in data]
            else:
                self._children = []
            return self._children
        except MagisterAPIError:
            # Not a parent account or no children
            return []

    def get_appointments(self, start: date, end: date) -> list[Afspraak]:
        """Get appointments for a date range."""
        return self.appointments.list(start, end)

    def get_homework(self, start: date, end: date) -> list[Afspraak]:
        """Get appointments that have homework."""
        return self.appointments.with_homework(start, end)

    def get_homework_with_attachments(self, start: date, end: date) -> list[Afspraak]:
        """Get homework with attachments populated for items that have them."""
        return self.appointments.with_attachments(start, end)

    def get_appointment(self, afspraak_id: int) -> Afspraak:
        """Get a single appointment with full details including attachments."""
        return self.appointments.get(afspraak_id)

    def get_recent_grades(self, limit: int = 10) -> list[Cijfer]:
        """Get recent grades."""
        return self.grades.recent(limit)

    def get_schedule(self, date_: date) -> list[Afspraak]:
        """Get schedule for a specific date."""
        return self.appointments.for_date(date_)

    def download_attachment(self, bijlage: Bijlage, output_dir: Path | None = None) -> Path:
        """Download an attachment to the specified directory."""
        return self.attachments.download(bijlage, output_dir)

    # -------------------------------------------------------------------------
    # Properties (backward compatible)
    # -------------------------------------------------------------------------

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
