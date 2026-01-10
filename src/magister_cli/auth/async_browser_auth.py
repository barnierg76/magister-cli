"""Async browser-based authentication using Playwright for MCP server.

This module provides async authentication that can be called from the MCP server
to launch a browser for user login when not authenticated.

Uses Playwright's persistent context to maintain browser sessions across runs.
This allows users to authenticate once and stay logged in for weeks/months,
bypassing the limitation of implicit grant (no refresh tokens).

The browser data (cookies, localStorage) is stored in:
  ~/.config/magister-cli/browser_data/{school}/
"""

import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

from magister_cli.auth.token_manager import TokenData, get_token_manager
from magister_cli.config import get_settings, validate_school_code

logger = logging.getLogger(__name__)


def get_browser_data_dir(school: str) -> Path:
    """Get browser data directory for persistent sessions."""
    config_dir = Path.home() / ".config" / "magister-cli" / "browser_data" / school
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_storage_state_path(school: str) -> Path:
    """Get path for storing browser storage state (cookies + localStorage)."""
    return get_browser_data_dir(school) / "storage_state.json"


def is_gui_available() -> bool:
    """Check if a GUI environment is available for browser display.

    Returns:
        True if GUI is available, False otherwise
    """
    # macOS - check if we're in a GUI session
    if sys.platform == "darwin":
        # Check for WindowServer process or DISPLAY
        return os.environ.get("TERM_PROGRAM") is not None or os.path.exists(
            "/System/Library/CoreServices/WindowServer.app"
        )

    # Linux - check DISPLAY or WAYLAND_DISPLAY
    if sys.platform.startswith("linux"):
        return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))

    # Windows - assume GUI available
    if sys.platform == "win32":
        return True

    return False


async def extract_token_from_page_async(page) -> dict | None:
    """Try to extract access token and refresh token from page state or storage (async version).

    Magister stores OIDC tokens in sessionStorage with keys like:
    - oidc.user:https://accounts.magister.net:M6LOAPP

    Returns:
        Dictionary with 'access_token' and optionally 'refresh_token', or None if not found.
    """
    try:
        result = await page.evaluate(
            """() => {
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
        )
        return result
    except Exception as e:
        logger.warning(f"Failed to extract token from page: {e}")
        return None


class AsyncBrowserAuthenticator:
    """Handle async browser-based OAuth authentication for Magister."""

    def __init__(
        self,
        school: str,
        headless: bool = False,
        timeout_seconds: int = 300,
    ):
        """Initialize the authenticator.

        Args:
            school: School code (e.g., 'vsvonh')
            headless: Run browser in headless mode (default False for MCP)
            timeout_seconds: Max time to wait for user login
        """
        self.school = validate_school_code(school)
        self.settings = get_settings()
        self.headless = headless
        self.timeout_seconds = timeout_seconds

    @property
    def login_url(self) -> str:
        """Get the Magister login URL for the school."""
        return f"https://{self.school}.magister.net"

    async def authenticate(self) -> TokenData:
        """
        Open browser for user to authenticate and capture the token.

        Uses storage state to maintain sessions across CLI runs.
        On subsequent runs with valid session, login completes automatically.

        Returns:
            TokenData with access token on success.

        Raises:
            RuntimeError: If login fails or times out.
        """
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            raise RuntimeError(
                "Playwright is not installed. Install with: pip install playwright && playwright install chromium"
            )

        if not self.headless and not is_gui_available():
            raise RuntimeError(
                "No GUI environment available for browser authentication. "
                "Please run 'magister login --school {self.school}' from a terminal with GUI access."
            )

        user_data_dir = get_browser_data_dir(self.school)
        storage_state_path = get_storage_state_path(self.school)

        async with async_playwright() as p:
            # Use persistent context to maintain sessions across runs
            context = await p.chromium.launch_persistent_context(
                user_data_dir=str(user_data_dir),
                headless=self.headless,
            )
            page = context.pages[0] if context.pages else await context.new_page()

            try:
                # Restore storage state if it exists (for cookies)
                if storage_state_path.exists():
                    try:
                        import json
                        with open(storage_state_path) as f:
                            state = json.load(f)
                        # Add cookies from storage state
                        if state.get("cookies"):
                            await context.add_cookies(state["cookies"])
                        logger.debug("Restored storage state from previous session")
                    except Exception as e:
                        logger.debug(f"Could not restore storage state: {e}")

                logger.info(f"Opening browser for login at {self.login_url}")
                await page.goto(self.login_url)

                # Wait a moment for initial page load
                await page.wait_for_timeout(2000)

                # Dashboard patterns that indicate successful login
                dashboard_patterns = [
                    f"https://{self.school}.magister.net/magister",
                    f"https://{self.school}.magister.net/today",
                    f"https://{self.school}.magister.net/#/today",
                    f"https://{self.school}.magister.net/#/agenda",
                ]

                timeout_ms = self.timeout_seconds * 1000

                # Wait for user to complete login
                logger.info("Waiting for user to complete login...")
                await page.wait_for_function(
                    f"""() => {{
                        const url = window.location.href;
                        const patterns = {dashboard_patterns};
                        return patterns.some(p => url.includes(p.replace('https://{self.school}.magister.net', '')));
                    }}""",
                    timeout=timeout_ms,
                )

                # Give the page time to store the token
                await page.wait_for_timeout(2000)

                # Extract the token
                token_data = await extract_token_from_page_async(page)
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
                    # Try cookies as fallback
                    cookies = await context.cookies()
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

                # Save storage state for future sessions (cookies from all domains)
                try:
                    await context.storage_state(path=str(storage_state_path))
                    logger.debug(f"Saved storage state to {storage_state_path}")
                except Exception as e:
                    logger.warning(f"Could not save storage state: {e}")

                logger.info("Authentication successful!")
                return TokenData(
                    access_token=access_token,
                    school=self.school,
                    expires_at=expires_at,
                    refresh_token=refresh_token,
                )

            except asyncio.TimeoutError:
                raise RuntimeError(
                    f"Login timed out after {self.timeout_seconds} seconds. "
                    "Please try again and complete the login process."
                )
            finally:
                await context.close()


async def async_login(
    school: str,
    headless: bool = False,
    timeout_seconds: int = 300,
) -> TokenData:
    """
    Perform async browser-based login and store the token.

    This is the main entry point for MCP-triggered authentication.

    Args:
        school: School code (e.g., 'vsvonh')
        headless: Run browser in headless mode (default: False)
        timeout_seconds: Max time to wait for login (default: 300)

    Returns:
        TokenData with the access token

    Raises:
        RuntimeError: If login fails
    """
    auth = AsyncBrowserAuthenticator(school, headless, timeout_seconds)
    token_data = await auth.authenticate()

    # Store the token
    token_manager = get_token_manager(school)
    token_manager.save_token(token_data)

    return token_data
