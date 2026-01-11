"""Tests for credential storage module."""

from unittest.mock import MagicMock, patch

import pytest

# Import the module directly to avoid import chain issues
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "credential_store",
    Path(__file__).parent.parent / "src" / "magister_cli" / "auth" / "credential_store.py"
)
credential_store = importlib.util.module_from_spec(spec)
spec.loader.exec_module(credential_store)

store_credentials = credential_store.store_credentials
get_credentials = credential_store.get_credentials
clear_credentials = credential_store.clear_credentials
has_stored_credentials = credential_store.has_stored_credentials
CREDENTIAL_SERVICE = credential_store.CREDENTIAL_SERVICE


class TestStoreCredentials:
    """Tests for store_credentials function."""

    @patch("keyring.set_password")
    def test_stores_username_and_password(self, mock_set):
        """Should store both username and password in keyring."""
        store_credentials("testschool", "testuser", "testpass")

        assert mock_set.call_count == 2
        mock_set.assert_any_call(CREDENTIAL_SERVICE, "testschool:username", "testuser")
        mock_set.assert_any_call(CREDENTIAL_SERVICE, "testschool:password", "testpass")

    @patch("keyring.set_password")
    def test_stores_with_special_characters(self, mock_set):
        """Should handle special characters in credentials."""
        store_credentials("school-2024", "user@example.com", "p@$$w0rd!")

        mock_set.assert_any_call(CREDENTIAL_SERVICE, "school-2024:username", "user@example.com")
        mock_set.assert_any_call(CREDENTIAL_SERVICE, "school-2024:password", "p@$$w0rd!")


class TestGetCredentials:
    """Tests for get_credentials function."""

    @patch("keyring.get_password")
    def test_returns_tuple_when_both_exist(self, mock_get):
        """Should return (username, password) tuple when both are stored."""
        mock_get.side_effect = lambda service, key: {
            "testschool:username": "user123",
            "testschool:password": "pass456",
        }.get(key)

        result = get_credentials("testschool")

        assert result == ("user123", "pass456")

    @patch("keyring.get_password")
    def test_returns_none_when_username_missing(self, mock_get):
        """Should return None if username is not stored."""
        mock_get.side_effect = lambda service, key: {
            "testschool:password": "pass456",
        }.get(key)

        result = get_credentials("testschool")

        assert result is None

    @patch("keyring.get_password")
    def test_returns_none_when_password_missing(self, mock_get):
        """Should return None if password is not stored."""
        mock_get.side_effect = lambda service, key: {
            "testschool:username": "user123",
        }.get(key)

        result = get_credentials("testschool")

        assert result is None

    @patch("keyring.get_password")
    def test_returns_none_when_both_missing(self, mock_get):
        """Should return None if neither is stored."""
        mock_get.return_value = None

        result = get_credentials("testschool")

        assert result is None


class TestClearCredentials:
    """Tests for clear_credentials function."""

    @patch("keyring.delete_password")
    def test_clears_both_username_and_password(self, mock_delete):
        """Should delete both username and password."""
        result = clear_credentials("testschool")

        assert result is True
        mock_delete.assert_any_call(CREDENTIAL_SERVICE, "testschool:username")
        mock_delete.assert_any_call(CREDENTIAL_SERVICE, "testschool:password")

    @patch("keyring.delete_password")
    def test_returns_true_on_partial_clear(self, mock_delete):
        """Should return True even if only one credential exists."""
        import keyring.errors

        def side_effect(service, key):
            if "password" in key:
                raise keyring.errors.PasswordDeleteError("Not found")

        mock_delete.side_effect = side_effect

        result = clear_credentials("testschool")

        assert result is True

    @patch("keyring.delete_password")
    def test_returns_false_when_nothing_to_clear(self, mock_delete):
        """Should return False if no credentials exist."""
        import keyring.errors

        mock_delete.side_effect = keyring.errors.PasswordDeleteError("Not found")

        result = clear_credentials("testschool")

        assert result is False


class TestHasStoredCredentials:
    """Tests for has_stored_credentials function."""

    @patch("keyring.get_password")
    def test_returns_true_when_credentials_exist(self, mock_get):
        """Should return True when both username and password are stored."""
        mock_get.side_effect = lambda service, key: {
            "testschool:username": "user",
            "testschool:password": "pass",
        }.get(key)

        result = has_stored_credentials("testschool")

        assert result is True

    @patch("keyring.get_password")
    def test_returns_false_when_credentials_missing(self, mock_get):
        """Should return False when credentials are not stored."""
        mock_get.return_value = None

        result = has_stored_credentials("testschool")

        assert result is False

    @patch("keyring.get_password")
    def test_returns_false_when_partial_credentials(self, mock_get):
        """Should return False when only username is stored."""
        mock_get.side_effect = lambda service, key: {
            "testschool:username": "user",
        }.get(key)

        result = has_stored_credentials("testschool")

        assert result is False


class TestCredentialIsolation:
    """Tests for credential isolation between schools."""

    @patch("keyring.get_password")
    def test_credentials_isolated_by_school(self, mock_get):
        """Credentials for one school should not affect another."""
        mock_get.side_effect = lambda service, key: {
            "school1:username": "user1",
            "school1:password": "pass1",
        }.get(key)

        result1 = get_credentials("school1")
        result2 = get_credentials("school2")

        assert result1 == ("user1", "pass1")
        assert result2 is None

    @patch("keyring.set_password")
    def test_stores_credentials_with_school_prefix(self, mock_set):
        """Should use school code as prefix in keyring key."""
        store_credentials("myschool", "user", "pass")

        # Verify the key format includes school code
        calls = [call[0] for call in mock_set.call_args_list]
        assert any("myschool:" in call[1] for call in calls)
