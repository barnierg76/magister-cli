"""Tests for token manager."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from magister_cli.auth.token_manager import TokenData, TokenManager


class TestTokenData:
    """Tests for TokenData dataclass."""

    def test_is_expired_no_expiry(self):
        """Token without expiry is never expired."""
        token = TokenData(
            access_token="test_token",
            school="vsvonh",
        )
        assert not token.is_expired()

    def test_is_expired_future(self):
        """Token expiring in future is not expired."""
        token = TokenData(
            access_token="test_token",
            school="vsvonh",
            expires_at=datetime.now() + timedelta(hours=1),
        )
        assert not token.is_expired()

    def test_is_expired_past(self):
        """Token that expired in past is expired."""
        token = TokenData(
            access_token="test_token",
            school="vsvonh",
            expires_at=datetime.now() - timedelta(hours=1),
        )
        assert token.is_expired()

    def test_is_expired_within_buffer(self):
        """Token expiring within 5 minute buffer is considered expired."""
        token = TokenData(
            access_token="test_token",
            school="vsvonh",
            expires_at=datetime.now() + timedelta(minutes=3),
        )
        assert token.is_expired()

    def test_to_dict_and_from_dict(self):
        """Token can be serialized and deserialized."""
        original = TokenData(
            access_token="test_token",
            school="vsvonh",
            person_id=12345,
            person_name="Jan Jansen",
            expires_at=datetime(2026, 1, 8, 16, 0, 0),
        )

        data = original.to_dict()
        restored = TokenData.from_dict(data)

        assert restored.access_token == original.access_token
        assert restored.school == original.school
        assert restored.person_id == original.person_id
        assert restored.person_name == original.person_name
        assert restored.expires_at == original.expires_at

    def test_from_dict_minimal(self):
        """Token can be restored from minimal data."""
        data = {"access_token": "test", "school": "test_school"}
        token = TokenData.from_dict(data)

        assert token.access_token == "test"
        assert token.school == "test_school"
        assert token.person_id is None
        assert token.person_name is None
        assert token.expires_at is None


class TestTokenManager:
    """Tests for TokenManager."""

    @pytest.fixture
    def mock_keyring(self):
        """Mock keyring module."""
        import keyring.errors

        with patch("magister_cli.auth.token_manager.keyring") as mock:
            mock.errors = keyring.errors
            yield mock

    @pytest.fixture
    def mock_settings(self):
        """Mock settings."""
        with patch("magister_cli.auth.token_manager.get_settings") as mock:
            settings = MagicMock()
            settings.school = None
            settings.cache_dir = "/tmp/magister-test"
            mock.return_value = settings
            yield settings

    def test_save_and_get_token(self, mock_keyring, mock_settings):
        """Token can be saved and retrieved."""
        manager = TokenManager(school="vsvonh")

        token = TokenData(
            access_token="test_token",
            school="vsvonh",
            person_id=123,
        )
        manager.save_token(token)

        mock_keyring.set_password.assert_called_once()
        call_args = mock_keyring.set_password.call_args
        assert call_args[0][0] == "magister-cli"
        assert "vsvonh" in call_args[0][1]
        assert "test_token" in call_args[0][2]

    def test_get_token_not_found(self, mock_keyring, mock_settings):
        """Returns None when no token stored."""
        mock_keyring.get_password.return_value = None

        manager = TokenManager(school="vsvonh")
        token = manager.get_token()

        assert token is None

    def test_get_token_invalid_json(self, mock_keyring, mock_settings):
        """Returns None when stored data is invalid JSON."""
        mock_keyring.get_password.return_value = "not valid json"

        manager = TokenManager(school="vsvonh")
        token = manager.get_token()

        assert token is None

    def test_delete_token_success(self, mock_keyring, mock_settings):
        """Delete returns True on success."""
        manager = TokenManager(school="vsvonh")
        result = manager.delete_token()

        assert result is True
        mock_keyring.delete_password.assert_called_once()

    def test_delete_token_not_found(self, mock_keyring, mock_settings):
        """Delete returns False when no token to delete."""
        import keyring.errors

        mock_keyring.delete_password.side_effect = keyring.errors.PasswordDeleteError()

        manager = TokenManager(school="vsvonh")
        result = manager.delete_token()

        assert result is False

    def test_get_valid_token_expired(self, mock_keyring, mock_settings):
        """Returns None for expired token."""
        import json

        expired_token = {
            "access_token": "test",
            "school": "vsvonh",
            "expires_at": (datetime.now() - timedelta(hours=1)).isoformat(),
        }
        mock_keyring.get_password.return_value = json.dumps(expired_token)

        manager = TokenManager(school="vsvonh")
        token = manager.get_valid_token()

        assert token is None

    def test_get_valid_token_valid(self, mock_keyring, mock_settings):
        """Returns token when valid."""
        import json

        valid_token = {
            "access_token": "test",
            "school": "vsvonh",
            "expires_at": (datetime.now() + timedelta(hours=1)).isoformat(),
        }
        mock_keyring.get_password.return_value = json.dumps(valid_token)

        manager = TokenManager(school="vsvonh")
        token = manager.get_valid_token()

        assert token is not None
        assert token.access_token == "test"

    def test_school_from_settings(self, mock_keyring, mock_settings):
        """School can come from settings if not provided."""
        mock_settings.school = "fromconfig"

        manager = TokenManager()
        assert manager.school == "fromconfig"

    def test_school_override(self, mock_keyring, mock_settings):
        """Explicit school overrides settings."""
        mock_settings.school = "fromconfig"

        manager = TokenManager(school="explicit")
        assert manager.school == "explicit"
