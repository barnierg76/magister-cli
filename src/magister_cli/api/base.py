"""Base resource for API endpoints."""

import logging
from typing import Any

import httpx

from magister_cli.api.exceptions import (
    MagisterAPIError,
    RateLimitError,
    TokenExpiredError,
)

logger = logging.getLogger(__name__)


class BaseResource:
    """Base class for API resources.

    All resource classes should inherit from this to get:
    - Access to the HTTP client
    - Common request/response handling
    - Consistent error handling
    """

    def __init__(self, client: httpx.Client, person_id: int):
        """Initialize the resource.

        Args:
            client: HTTP client instance
            person_id: The student's person ID for API calls
        """
        self._client = client
        self._person_id = person_id

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

    def _extract_items(self, data: Any) -> list:
        """Extract items array from Magister API response.

        The Magister API wraps lists in {"items": [...]} or {"Items": [...]} objects.
        Note: API uses lowercase "items" in newer endpoints.
        """
        if isinstance(data, dict):
            return data.get("items", data.get("Items", []))
        return data

    def _request(self, method: str, endpoint: str, **kwargs) -> Any:
        """Make an API request."""
        response = self._client.request(method, endpoint, **kwargs)
        return self._handle_response(response)

    def _get(self, endpoint: str, **kwargs) -> Any:
        """Convenience method for GET requests."""
        return self._request("GET", endpoint, **kwargs)

    def _post(self, endpoint: str, **kwargs) -> Any:
        """Convenience method for POST requests."""
        return self._request("POST", endpoint, **kwargs)

    def _put(self, endpoint: str, **kwargs) -> Any:
        """Convenience method for PUT requests."""
        return self._request("PUT", endpoint, **kwargs)

    def _delete(self, endpoint: str, **kwargs) -> Any:
        """Convenience method for DELETE requests."""
        return self._request("DELETE", endpoint, **kwargs)
