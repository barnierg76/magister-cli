"""Token storage and management using keyring for secure storage."""

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Self

import keyring

from magister_cli.config import get_settings

SERVICE_NAME = "magister-cli"


@dataclass
class TokenData:
    """Stored token data."""

    access_token: str
    school: str
    person_id: int | None = None
    person_name: str | None = None
    expires_at: datetime | None = None

    def is_expired(self) -> bool:
        """Check if token is expired or will expire soon (5 min buffer)."""
        if self.expires_at is None:
            return False
        return datetime.now() >= (self.expires_at - timedelta(minutes=5))

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "access_token": self.access_token,
            "school": self.school,
            "person_id": self.person_id,
            "person_name": self.person_name,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        """Create from dictionary."""
        expires_at = None
        if data.get("expires_at"):
            expires_at = datetime.fromisoformat(data["expires_at"])
        return cls(
            access_token=data["access_token"],
            school=data["school"],
            person_id=data.get("person_id"),
            person_name=data.get("person_name"),
            expires_at=expires_at,
        )


class TokenManager:
    """Manages token storage using keyring for secure storage."""

    def __init__(self, school: str | None = None):
        self.settings = get_settings()
        self._school = school

    @property
    def school(self) -> str | None:
        """Get the school code."""
        return self._school or self.settings.school

    def _get_keyring_key(self) -> str:
        """Get the keyring key for this school."""
        school = self.school
        if not school:
            return f"{SERVICE_NAME}:default"
        return f"{SERVICE_NAME}:{school}"

    def save_token(self, token_data: TokenData) -> None:
        """Save token securely using keyring."""
        key = self._get_keyring_key()
        data_json = json.dumps(token_data.to_dict())
        keyring.set_password(SERVICE_NAME, key, data_json)

    def get_token(self) -> TokenData | None:
        """Retrieve stored token from keyring."""
        key = self._get_keyring_key()
        data_json = keyring.get_password(SERVICE_NAME, key)
        if not data_json:
            return None
        try:
            data = json.loads(data_json)
            return TokenData.from_dict(data)
        except (json.JSONDecodeError, KeyError):
            return None

    def delete_token(self) -> bool:
        """Delete stored token from keyring."""
        key = self._get_keyring_key()
        try:
            keyring.delete_password(SERVICE_NAME, key)
            return True
        except keyring.errors.PasswordDeleteError:
            return False

    def get_valid_token(self) -> TokenData | None:
        """Get token only if it's valid and not expired."""
        token = self.get_token()
        if token is None:
            return None
        if token.is_expired():
            return None
        return token

    def is_token_expiring_soon(self, minutes: int = 10) -> bool:
        """Check if token will expire within the given minutes.

        Args:
            minutes: Number of minutes to check ahead

        Returns:
            True if token will expire soon or is already expired
        """
        token = self.get_token()
        if token is None or token.expires_at is None:
            return False
        return datetime.now() >= (token.expires_at - timedelta(minutes=minutes))

    def get_time_until_expiry(self) -> timedelta | None:
        """Get time remaining until token expires.

        Returns:
            Time until expiry, or None if no token or no expiry time
        """
        token = self.get_token()
        if token is None or token.expires_at is None:
            return None
        remaining = token.expires_at - datetime.now()
        return remaining if remaining.total_seconds() > 0 else timedelta(0)

    def update_person_info(self, person_id: int, person_name: str) -> None:
        """Update person info in stored token."""
        token = self.get_token()
        if token:
            token.person_id = person_id
            token.person_name = person_name
            self.save_token(token)


def get_token_manager(school: str | None = None) -> TokenManager:
    """Get a token manager instance."""
    return TokenManager(school)
