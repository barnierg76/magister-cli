"""Browser-based OAuth authentication using Playwright with persistent sessions.

Uses Playwright's persistent context to maintain browser sessions across CLI runs.
This allows users to authenticate once and stay logged in for weeks/months without
re-authentication, bypassing the limitation of implicit grant (no refresh tokens).

The browser data (cookies, localStorage) is stored in:
  ~/.config/magister-cli/browser_data/{school}/
"""

import logging
from datetime import datetime, timedelta

from playwright.sync_api import Page, sync_playwright

from magister_cli.auth.constants import (
    OIDC_TOKEN_EXTRACTION_JS,
    PAGE_LOAD_DELAY_MS,
    auth_file_lock,
    clear_browser_data,
    get_browser_data_dir,
    get_storage_state_path,
    secure_storage_state_file,
)
from magister_cli.auth.token_manager import TokenData, get_token_manager
from magister_cli.config import get_settings, validate_school_code

logger = logging.getLogger(__name__)


def extract_token_from_page(page: Page) -> dict | None:
    """Try to extract access token and refresh token from page state or storage.

    Magister stores OIDC tokens in sessionStorage with keys like:
    - oidc.user:https://accounts.magister.net:M6LOAPP

    Returns:
        Dictionary with 'access_token' and optionally 'refresh_token', or None if not found.
    """
    try:
        result = page.evaluate(OIDC_TOKEN_EXTRACTION_JS)
        return result
    except Exception as e:
        logger.warning(f"Failed to extract token from page: {e}")
        return None


class BrowserAuthenticator:
    """Handle browser-based OAuth authentication for Magister with persistent sessions."""

    def __init__(self, school: str, headless: bool | None = None):
        # Validate school code to prevent SSRF
        self.school = validate_school_code(school)
        self.settings = get_settings()
        self.headless = headless if headless is not None else self.settings.headless

    @property
    def login_url(self) -> str:
        """Get the Magister login URL for the school."""
        return f"https://{self.school}.magister.net"

    def authenticate(self) -> TokenData:
        """
        Open browser for user to authenticate and capture the token.

        Uses persistent context to maintain sessions across CLI runs.
        On subsequent runs with valid session, login completes automatically.

        Returns TokenData with access token on success.
        Raises RuntimeError on failure.
        Raises TimeoutError if another process is already authenticating.
        """
        user_data_dir = get_browser_data_dir(self.school)
        storage_state_path = get_storage_state_path(self.school)

        # Use file lock to prevent concurrent authentication attempts
        with auth_file_lock(self.school), sync_playwright() as p:
            # Use persistent context for session persistence
            context = p.chromium.launch_persistent_context(
                user_data_dir=str(user_data_dir),
                headless=self.headless,
            )
            page = context.pages[0] if context.pages else context.new_page()

            try:
                page.goto(self.login_url)
                page.wait_for_timeout(PAGE_LOAD_DELAY_MS)

                dashboard_patterns = [
                    f"https://{self.school}.magister.net/magister",
                    f"https://{self.school}.magister.net/today",
                    f"https://{self.school}.magister.net/#/today",
                    f"https://{self.school}.magister.net/#/agenda",
                ]

                timeout = self.settings.oauth_timeout * 1000

                page.wait_for_function(
                    f"""() => {{
                        const url = window.location.href;
                        const patterns = {dashboard_patterns};
                        return patterns.some(p => url.includes(p.replace('https://{self.school}.magister.net', '')));
                    }}""",
                    timeout=timeout,
                )

                page.wait_for_timeout(PAGE_LOAD_DELAY_MS)

                token_data = extract_token_from_page(page)
                access_token = None
                refresh_token = None
                expires_at = None

                if token_data:
                    access_token = token_data.get("access_token")
                    refresh_token = token_data.get("refresh_token")
                    # expires_at from OIDC is Unix timestamp
                    if token_data.get("expires_at"):
                        try:
                            expires_at = datetime.fromtimestamp(token_data["expires_at"])
                        except (ValueError, TypeError):
                            pass

                    if refresh_token:
                        logger.info("Refresh token captured successfully")
                    else:
                        logger.debug("No refresh token (expected for implicit grant)")

                if not access_token:
                    # Fallback to cookies
                    cookies = context.cookies()
                    for cookie in cookies:
                        if "token" in cookie["name"].lower():
                            access_token = cookie["value"]
                            break

                if not access_token:
                    raise RuntimeError(
                        "Could not extract access token. "
                        "Please ensure you completed the login process."
                    )

                # Default expiry if not provided
                if expires_at is None:
                    expires_at = datetime.now() + timedelta(hours=2)

                # Save storage state for future sessions with secure permissions
                try:
                    context.storage_state(path=str(storage_state_path))
                    secure_storage_state_file(storage_state_path)
                    logger.debug(f"Saved storage state to {storage_state_path.name}")
                except Exception as e:
                    logger.warning(f"Could not save storage state: {e}")

                return TokenData(
                    access_token=access_token,
                    school=self.school,
                    expires_at=expires_at,
                    refresh_token=refresh_token,
                )

            finally:
                context.close()


def login(school: str, headless: bool | None = None) -> TokenData:
    """
    Perform browser-based login and store the token.

    Args:
        school: School code (e.g., 'vsvonh')
        headless: Override headless setting (None uses config)

    Returns:
        TokenData with the access token

    Raises:
        RuntimeError: If login fails
    """
    auth = BrowserAuthenticator(school, headless)
    token_data = auth.authenticate()

    token_manager = get_token_manager(school)
    token_manager.save_token(token_data)

    return token_data


def logout(school: str | None = None) -> bool:
    """
    Remove stored token and browser session data for the school.

    Clears:
    - Token from system keyring
    - Browser persistent context data
    - Storage state file (cookies)

    Args:
        school: School code (None uses config default)

    Returns:
        True if any data was deleted, False if nothing existed
    """
    settings = get_settings()
    school = validate_school_code(school or settings.school)

    # Clear keyring token
    token_manager = get_token_manager(school)
    token_deleted = token_manager.delete_token()

    # Clear browser session data
    browser_data_cleared = clear_browser_data(school)

    return token_deleted or browser_data_cleared


def get_current_token(school: str | None = None) -> TokenData | None:
    """
    Get the current valid token if one exists.

    Args:
        school: School code (None uses config default)

    Returns:
        TokenData if valid token exists, None otherwise
    """
    token_manager = get_token_manager(school)
    return token_manager.get_valid_token()
