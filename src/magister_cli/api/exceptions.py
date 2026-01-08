"""Exceptions for Magister API."""


class MagisterAPIError(Exception):
    """Base exception for Magister API errors."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class TokenExpiredError(MagisterAPIError):
    """Token has expired and needs refresh."""


class RateLimitError(MagisterAPIError):
    """Rate limit exceeded."""

    def __init__(self, message: str, retry_after: int = 60):
        super().__init__(message, 429)
        self.retry_after = retry_after


class NotAuthenticatedError(MagisterAPIError):
    """User is not authenticated."""

    def __init__(self, school: str | None = None):
        msg = "Not authenticated"
        if school:
            msg += f" for school '{school}'"
        msg += ". Run 'magister login' first."
        super().__init__(msg)
