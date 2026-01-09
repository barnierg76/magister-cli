"""Async browser-based authentication using Playwright for MCP server.

This module provides async authentication that can be called from the MCP server
to launch a browser for user login when not authenticated.
"""

import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta

from magister_cli.auth.token_manager import TokenData, get_token_manager
from magister_cli.config import get_settings, validate_school_code

logger = logging.getLogger(__name__)


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


async def extract_token_from_page_async(page) -> str | None:
    """Try to extract access token from page state or storage (async version)."""
    try:
        token = await page.evaluate(
            """() => {
            // Check localStorage for token
            for (let i = 0; i < localStorage.length; i++) {
                const key = localStorage.key(i);
                const value = localStorage.getItem(key);
                if (value && value.includes('access_token')) {
                    try {
                        const parsed = JSON.parse(value);
                        if (parsed.access_token) return parsed.access_token;
                    } catch (e) {}
                }
            }
            // Check sessionStorage
            for (let i = 0; i < sessionStorage.length; i++) {
                const key = sessionStorage.key(i);
                const value = sessionStorage.getItem(key);
                if (value && value.includes('access_token')) {
                    try {
                        const parsed = JSON.parse(value);
                        if (parsed.access_token) return parsed.access_token;
                    } catch (e) {}
                }
            }
            return null;
        }"""
        )
        return token
    except Exception:
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

        This method launches a visible browser window where the user
        can complete the Magister login process. Once logged in,
        the token is extracted and returned.

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

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            context = await browser.new_context()
            page = await context.new_page()

            try:
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
                token = await extract_token_from_page_async(page)

                if not token:
                    # Try cookies as fallback
                    cookies = await context.cookies()
                    for cookie in cookies:
                        if "token" in cookie["name"].lower():
                            token = cookie["value"]
                            break

                if not token:
                    raise RuntimeError(
                        "Could not extract access token. "
                        "Please ensure you completed the login process."
                    )

                # Token expires in approximately 2 hours
                expires_at = datetime.now() + timedelta(hours=2)

                logger.info("Authentication successful!")
                return TokenData(
                    access_token=token,
                    school=self.school,
                    expires_at=expires_at,
                )

            except asyncio.TimeoutError:
                raise RuntimeError(
                    f"Login timed out after {self.timeout_seconds} seconds. "
                    "Please try again and complete the login process."
                )
            finally:
                await browser.close()


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
