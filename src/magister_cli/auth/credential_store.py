"""Secure credential storage for headless re-authentication.

WARNING: Storing credentials is a security risk. Only enable with
explicit user consent. Credentials are stored in the OS keyring.

This module enables automatic headless re-authentication when the
OAuth token expires (~2 hours). Instead of requiring a browser popup,
the system can automatically log in using stored credentials.

Security considerations:
- Credentials are stored in the OS keyring (macOS Keychain, Windows
  Credential Manager, GNOME Keyring / KWallet on Linux)
- Keyring access may require user unlock (OS-dependent)
- Credentials are cleared automatically on failed login attempts
- User must explicitly opt-in with security warnings displayed
"""

import logging

import keyring

logger = logging.getLogger(__name__)

# Separate service name from token storage to avoid confusion
CREDENTIAL_SERVICE = "magister-cli-credentials"


def store_credentials(school: str, username: str, password: str) -> None:
    """Store credentials in OS keyring.

    The credentials are stored separately from the OAuth tokens,
    using a dedicated keyring service name.

    Args:
        school: School code (e.g., 'vsvonh')
        username: Magister username
        password: Magister password
    """
    # Store username and password separately
    keyring.set_password(CREDENTIAL_SERVICE, f"{school}:username", username)
    keyring.set_password(CREDENTIAL_SERVICE, f"{school}:password", password)
    logger.debug(f"Credentials stored for school: {school}")


def get_credentials(school: str) -> tuple[str, str] | None:
    """Retrieve stored credentials.

    Returns:
        Tuple of (username, password) or None if not stored
    """
    username = keyring.get_password(CREDENTIAL_SERVICE, f"{school}:username")
    password = keyring.get_password(CREDENTIAL_SERVICE, f"{school}:password")

    if username and password:
        return (username, password)
    return None


def clear_credentials(school: str) -> bool:
    """Remove stored credentials.

    Args:
        school: School code

    Returns:
        True if credentials were cleared, False if they didn't exist
    """
    cleared = False
    try:
        keyring.delete_password(CREDENTIAL_SERVICE, f"{school}:username")
        cleared = True
    except keyring.errors.PasswordDeleteError:
        pass

    try:
        keyring.delete_password(CREDENTIAL_SERVICE, f"{school}:password")
        cleared = True
    except keyring.errors.PasswordDeleteError:
        pass

    if cleared:
        logger.debug(f"Credentials cleared for school: {school}")

    return cleared


def has_stored_credentials(school: str) -> bool:
    """Check if credentials are stored for a school.

    Args:
        school: School code

    Returns:
        True if both username and password are stored
    """
    return get_credentials(school) is not None
