"""Headless login using stored credentials.

This module enables automatic re-authentication without browser popups
by using securely stored credentials to perform automated login.

The login flow mimics human behavior with realistic delays to avoid
bot detection. If login fails (wrong password, 2FA required, etc.),
credentials are automatically cleared to prevent account lockout.

IMPORTANT: This only works for schools that don't require 2FA/MFA.
Schools with mandatory 2FA will always fail headless login.
"""

import asyncio
import logging
import random
from datetime import datetime, timedelta

from magister_cli.auth.constants import (
    OIDC_TOKEN_EXTRACTION_JS,
    PAGE_LOAD_DELAY_MS,
    auth_file_lock,
    get_browser_data_dir,
    get_storage_state_path,
    secure_storage_state_file,
)
from magister_cli.auth.credential_store import clear_credentials, get_credentials
from magister_cli.auth.token_manager import TokenData, get_token_manager
from magister_cli.config import validate_school_code

logger = logging.getLogger(__name__)

# Human-like delay ranges (in seconds)
MIN_TYPING_DELAY = 0.3
MAX_TYPING_DELAY = 0.8
MIN_ACTION_DELAY = 0.5
MAX_ACTION_DELAY = 1.5

# Realistic user agent (updated regularly)
HEADLESS_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


async def _human_delay(min_sec: float = MIN_TYPING_DELAY, max_sec: float = MAX_TYPING_DELAY) -> None:
    """Add a human-like random delay."""
    await asyncio.sleep(random.uniform(min_sec, max_sec))


class HeadlessLoginError(Exception):
    """Base exception for headless login errors."""

    pass


class CredentialsInvalidError(HeadlessLoginError):
    """Raised when stored credentials are invalid (wrong password, etc.)."""

    pass


class TwoFactorRequiredError(HeadlessLoginError):
    """Raised when school requires 2FA which cannot be automated."""

    pass


class LoginTimeoutError(HeadlessLoginError):
    """Raised when login times out."""

    pass


async def headless_login(school: str, timeout: int = 60) -> TokenData | None:
    """Perform headless login using stored credentials.

    This function:
    1. Retrieves stored credentials from keyring
    2. Launches a headless browser
    3. Fills in the login form automatically
    4. Waits for redirect to dashboard
    5. Extracts the OAuth token

    Args:
        school: School code (e.g., 'vsvonh')
        timeout: Max seconds to wait for login to complete

    Returns:
        TokenData if successful, None if no credentials stored

    Raises:
        CredentialsInvalidError: If login fails due to wrong password
        TwoFactorRequiredError: If school requires 2FA
        LoginTimeoutError: If login times out
        HeadlessLoginError: For other login failures
    """
    school = validate_school_code(school)

    creds = get_credentials(school)
    if not creds:
        logger.debug(f"No stored credentials for school: {school}")
        return None

    username, password = creds

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        raise HeadlessLoginError(
            "Playwright is not installed. Install with: pip install playwright && playwright install chromium"
        )

    user_data_dir = get_browser_data_dir(school)
    storage_state_path = get_storage_state_path(school)

    with auth_file_lock(school):
        async with async_playwright() as p:
            # Use persistent context for session continuity
            context = await p.chromium.launch_persistent_context(
                user_data_dir=str(user_data_dir),
                headless=True,
                user_agent=HEADLESS_USER_AGENT,
            )
            page = context.pages[0] if context.pages else await context.new_page()

            try:
                login_url = f"https://{school}.magister.net"
                logger.info(f"Starting headless login for {school}")
                await page.goto(login_url)
                await page.wait_for_timeout(PAGE_LOAD_DELAY_MS)

                # Check if already logged in (session still valid)
                current_url = page.url
                if "/magister" in current_url or "/today" in current_url:
                    logger.info("Session still valid, extracting token")
                    token = await _extract_token(page, school)
                    if token:
                        await context.close()
                        return token

                # Wait for login form to appear
                try:
                    await page.wait_for_selector(
                        'input[type="text"], input[type="email"], input[name="username"]',
                        timeout=10000,
                    )
                except Exception:
                    # Might already be logged in or page structure changed
                    logger.warning("Could not find login form")

                await _human_delay(MIN_ACTION_DELAY, MAX_ACTION_DELAY)

                # Fill username
                username_input = page.locator(
                    'input[type="text"], input[type="email"], input[name="username"]'
                ).first
                await username_input.fill("")  # Clear first
                await username_input.fill(username)
                logger.debug("Filled username")

                await _human_delay()

                # Click next/continue button (Magister uses "Doorgaan")
                next_button = page.get_by_role("button", name="Doorgaan")
                if await next_button.count() > 0:
                    await next_button.click()
                    logger.debug("Clicked next button")

                    # Wait for password field
                    await page.wait_for_selector('input[type="password"]', timeout=10000)
                    await _human_delay()

                # Fill password
                password_input = page.locator('input[type="password"]')
                await password_input.fill(password)
                logger.debug("Filled password")

                await _human_delay()

                # Submit login (Magister uses "Doorgaan" for both steps)
                submit_button = page.get_by_role("button", name="Doorgaan")
                if await submit_button.count() > 0:
                    await submit_button.click()
                    logger.debug("Clicked submit button")

                # Wait for navigation result
                timeout_ms = timeout * 1000
                try:
                    # Wait for either dashboard or error
                    await page.wait_for_function(
                        """() => {
                            const url = window.location.href;
                            // Success patterns
                            if (url.includes('/magister') || url.includes('/today') ||
                                url.includes('/#/today') || url.includes('/#/agenda')) {
                                return true;
                            }
                            // Error patterns - check for error messages on page
                            const errorEl = document.querySelector('.error, .alert-error, [class*="error"]');
                            if (errorEl && errorEl.textContent) {
                                return 'error:' + errorEl.textContent;
                            }
                            return false;
                        }""",
                        timeout=timeout_ms,
                    )
                except asyncio.TimeoutError:
                    # Check if 2FA is required
                    if await _check_for_2fa(page):
                        logger.warning("2FA required - cannot complete headless login")
                        raise TwoFactorRequiredError(
                            f"School {school} requires 2FA. Headless login not possible."
                        )
                    raise LoginTimeoutError(
                        f"Login timed out after {timeout} seconds"
                    )

                # Check final URL
                current_url = page.url
                if "/login" in current_url.lower() or "error" in current_url.lower():
                    # Login failed - check for error message
                    error_text = await _get_error_message(page)
                    logger.warning(f"Login failed: {error_text}")

                    # Clear credentials on auth failure
                    clear_credentials(school)
                    logger.info(f"Cleared invalid credentials for {school}")

                    raise CredentialsInvalidError(
                        f"Login failed for {school}: {error_text}. Credentials cleared."
                    )

                # Success - extract token
                await page.wait_for_timeout(PAGE_LOAD_DELAY_MS)
                token = await _extract_token(page, school)

                if not token:
                    raise HeadlessLoginError("Could not extract token after login")

                # Save storage state for future sessions
                try:
                    await context.storage_state(path=str(storage_state_path))
                    secure_storage_state_file(storage_state_path)
                    logger.debug("Saved storage state")
                except Exception as e:
                    logger.warning(f"Could not save storage state: {e}")

                logger.info(f"Headless login successful for {school}")
                return token

            except (CredentialsInvalidError, TwoFactorRequiredError, LoginTimeoutError):
                raise
            except Exception as e:
                error_msg = str(e).lower()
                # Don't clear credentials for network/timeout issues
                if "invalid" in error_msg or "incorrect" in error_msg or "wrong" in error_msg:
                    clear_credentials(school)
                    logger.info("Cleared credentials due to auth error")
                raise HeadlessLoginError(f"Headless login failed: {e}") from e
            finally:
                await context.close()


async def _extract_token(page, school: str) -> TokenData | None:
    """Extract OAuth token from browser session."""
    try:
        token_data = await page.evaluate(OIDC_TOKEN_EXTRACTION_JS)

        if not token_data or not token_data.get("access_token"):
            return None

        expires_at = None
        if token_data.get("expires_at"):
            try:
                expires_at = datetime.fromtimestamp(token_data["expires_at"])
            except (ValueError, TypeError):
                pass

        if expires_at is None:
            expires_at = datetime.now() + timedelta(hours=2)

        return TokenData(
            access_token=token_data["access_token"],
            school=school,
            expires_at=expires_at,
            refresh_token=token_data.get("refresh_token"),
        )
    except Exception as e:
        logger.warning(f"Failed to extract token: {e}")
        return None


async def _check_for_2fa(page) -> bool:
    """Check if the page is showing a 2FA/MFA prompt."""
    try:
        # Common 2FA elements
        selectors = [
            'input[type="tel"]',  # SMS code input
            'input[name*="otp"]',
            'input[name*="code"]',
            'input[name*="2fa"]',
            '[class*="authenticator"]',
            '[class*="two-factor"]',
            'text=verification code',
            'text=verificatiecode',  # Dutch
        ]
        for selector in selectors:
            if await page.locator(selector).count() > 0:
                return True
        return False
    except Exception:
        return False


async def _get_error_message(page) -> str:
    """Try to extract error message from the page."""
    try:
        error_selectors = [
            ".error",
            ".alert-error",
            ".error-message",
            '[class*="error"]',
            '[role="alert"]',
        ]
        for selector in error_selectors:
            el = page.locator(selector).first
            if await el.count() > 0:
                text = await el.text_content()
                if text and text.strip():
                    return text.strip()
        return "Unknown error"
    except Exception:
        return "Unknown error"


async def try_headless_reauth(school: str, timeout: int = 60) -> TokenData | None:
    """Attempt headless re-authentication if credentials are stored.

    This is the main entry point for automatic token refresh.
    It should be called when:
    - Token is expired
    - Refresh token failed or not available
    - Browser session is invalid

    Args:
        school: School code
        timeout: Max seconds for login

    Returns:
        TokenData if successful, None if no credentials or headless failed
    """
    try:
        token = await headless_login(school, timeout)
        if token:
            # Store the new token
            token_manager = get_token_manager(school)
            token_manager.save_token(token)
            logger.info("Headless re-auth successful, token stored")
        return token
    except TwoFactorRequiredError:
        # 2FA schools can't use headless - log but don't clear credentials
        logger.warning("School requires 2FA - headless login not possible")
        return None
    except HeadlessLoginError as e:
        logger.warning(f"Headless re-auth failed: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in headless re-auth: {e}")
        return None
