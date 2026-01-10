"""Shared authentication constants and utilities.

This module contains constants and helper functions shared between
sync (browser_auth.py) and async (async_browser_auth.py) authentication modules.
"""

import fcntl
import logging
import os
import stat
from contextlib import contextmanager
from pathlib import Path

logger = logging.getLogger(__name__)

# OAuth constants
OAUTH_CLIENT_ID = "M6LOAPP"
TOKEN_ENDPOINT = "https://accounts.magister.net/connect/token"

# Timeouts
PAGE_LOAD_DELAY_MS = 2000
DEFAULT_AUTH_TIMEOUT_SEC = 300

# Storage paths
BROWSER_DATA_DIR_NAME = "browser_data"
STORAGE_STATE_FILENAME = "storage_state.json"

# JavaScript for extracting OIDC tokens from browser storage
# This is shared between sync and async implementations
OIDC_TOKEN_EXTRACTION_JS = """() => {
    // First check for OIDC user storage (Magister's primary token storage)
    // Keys look like: oidc.user:https://accounts.magister.net:M6LOAPP
    for (let i = 0; i < sessionStorage.length; i++) {
        const key = sessionStorage.key(i);
        if (key && key.startsWith('oidc.user:')) {
            const value = sessionStorage.getItem(key);
            try {
                const parsed = JSON.parse(value);
                if (parsed.access_token) {
                    return {
                        access_token: parsed.access_token,
                        refresh_token: parsed.refresh_token || null,
                        expires_at: parsed.expires_at || null,
                        id_token: parsed.id_token || null
                    };
                }
            } catch (e) {
                console.error('Failed to parse OIDC user data:', e);
            }
        }
    }

    // Also check localStorage for OIDC data
    for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        if (key && key.startsWith('oidc.user:')) {
            const value = localStorage.getItem(key);
            try {
                const parsed = JSON.parse(value);
                if (parsed.access_token) {
                    return {
                        access_token: parsed.access_token,
                        refresh_token: parsed.refresh_token || null,
                        expires_at: parsed.expires_at || null,
                        id_token: parsed.id_token || null
                    };
                }
            } catch (e) {
                console.error('Failed to parse OIDC user data:', e);
            }
        }
    }

    // Fallback: Check for any key containing access_token
    for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        const value = localStorage.getItem(key);
        if (value && value.includes('access_token')) {
            try {
                const parsed = JSON.parse(value);
                if (parsed.access_token) {
                    return {
                        access_token: parsed.access_token,
                        refresh_token: parsed.refresh_token || null,
                        expires_at: parsed.expires_at || null
                    };
                }
            } catch (e) {}
        }
    }

    // Check sessionStorage as last fallback
    for (let i = 0; i < sessionStorage.length; i++) {
        const key = sessionStorage.key(i);
        const value = sessionStorage.getItem(key);
        if (value && value.includes('access_token')) {
            try {
                const parsed = JSON.parse(value);
                if (parsed.access_token) {
                    return {
                        access_token: parsed.access_token,
                        refresh_token: parsed.refresh_token || null,
                        expires_at: parsed.expires_at || null
                    };
                }
            } catch (e) {}
        }
    }

    return null;
}"""


def get_browser_data_dir(school: str) -> Path:
    """Get browser data directory for persistent sessions.

    Creates the directory with secure permissions (0700) if it doesn't exist.
    """
    config_dir = Path.home() / ".config" / "magister-cli" / BROWSER_DATA_DIR_NAME / school
    config_dir.mkdir(parents=True, exist_ok=True)

    # Ensure secure permissions (owner-only access)
    try:
        os.chmod(config_dir, stat.S_IRWXU)  # 0700
    except OSError:
        pass  # May fail on some systems, but directory is still created

    return config_dir


def get_storage_state_path(school: str) -> Path:
    """Get path for storing browser storage state (cookies + localStorage)."""
    return get_browser_data_dir(school) / STORAGE_STATE_FILENAME


def secure_storage_state_file(path: Path) -> None:
    """Set secure permissions on storage state file (contains session cookies)."""
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)  # 0600
    except OSError:
        pass  # May fail on some systems


def clear_browser_data(school: str) -> bool:
    """Clear all browser session data for a school.

    Returns True if any data was cleared.
    """
    import shutil

    browser_data_dir = get_browser_data_dir(school)
    storage_state_path = get_storage_state_path(school)

    cleared = False

    # Remove storage state file
    if storage_state_path.exists():
        try:
            storage_state_path.unlink()
            cleared = True
        except OSError:
            pass

    # Remove browser data directory
    if browser_data_dir.exists():
        try:
            shutil.rmtree(browser_data_dir)
            cleared = True
        except OSError:
            pass

    return cleared


# File locking
AUTH_LOCK_FILENAME = ".auth.lock"
AUTH_LOCK_TIMEOUT_SEC = 30


def get_auth_lock_path(school: str) -> Path:
    """Get path for the authentication lock file."""
    return get_browser_data_dir(school) / AUTH_LOCK_FILENAME


@contextmanager
def auth_file_lock(school: str, timeout: int = AUTH_LOCK_TIMEOUT_SEC):
    """Context manager for exclusive access to authentication files.

    Prevents race conditions when multiple CLI processes access browser data.

    Usage:
        with auth_file_lock(school):
            # Access browser data exclusively
            ...

    Args:
        school: School code for namespacing
        timeout: Maximum seconds to wait for lock (default: 30)

    Raises:
        TimeoutError: If lock cannot be acquired within timeout
    """
    import time

    lock_path = get_auth_lock_path(school)
    lock_file = None

    try:
        # Create lock file if it doesn't exist
        lock_file = open(lock_path, "w")

        # Try to acquire exclusive lock with timeout
        start_time = time.time()
        while True:
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                logger.debug(f"Acquired auth lock for {school}")
                break
            except BlockingIOError:
                elapsed = time.time() - start_time
                if elapsed >= timeout:
                    raise TimeoutError(
                        f"Could not acquire auth lock for {school} after {timeout}s. "
                        "Another process may be authenticating."
                    )
                time.sleep(0.1)

        yield

    finally:
        if lock_file:
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                logger.debug(f"Released auth lock for {school}")
            except Exception:
                pass
            lock_file.close()
