"""Browser-based OAuth authentication using Playwright with persistent sessions.

Uses Playwright's persistent context to maintain browser sessions across CLI runs.
This allows users to authenticate once and stay logged in for weeks/months without
re-authentication, bypassing the limitation of implicit grant (no refresh tokens).

The browser data (cookies, localStorage) is stored in:
  ~/.config/magister-cli/browser_data/{school}/
"""

import html
import json
import logging
import socket
import threading
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import Page, Response, sync_playwright

from magister_cli.auth.token_manager import TokenData, get_token_manager
from magister_cli.config import get_settings, validate_school_code

logger = logging.getLogger(__name__)


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """Handle OAuth callback requests."""

    token: str | None = None
    error: str | None = None
    received = threading.Event()

    def do_GET(self):
        """Handle GET request with OAuth callback."""
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        if "access_token" in params:
            OAuthCallbackHandler.token = params["access_token"][0]
            self._send_success_response()
        elif "error" in params:
            OAuthCallbackHandler.error = params.get("error_description", ["Unknown error"])[0]
            self._send_error_response(OAuthCallbackHandler.error)
        else:
            self._send_error_response("No token in callback")

        OAuthCallbackHandler.received.set()

    def _send_success_response(self):
        """Send success HTML response."""
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        response_html = """
        <!DOCTYPE html>
        <html>
        <head><title>Magister CLI - Login Successful</title></head>
        <body style="font-family: system-ui; text-align: center; padding: 50px;">
            <h1>Login Successful!</h1>
            <p>You can close this window and return to the terminal.</p>
        </body>
        </html>
        """
        self.wfile.write(response_html.encode())

    def _send_error_response(self, error: str):
        """Send error HTML response."""
        self.send_response(400)
        self.send_header("Content-type", "text/html")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        # Escape error message to prevent XSS
        safe_error = html.escape(error)
        response_html = f"""
        <!DOCTYPE html>
        <html>
        <head><title>Magister CLI - Login Failed</title></head>
        <body style="font-family: system-ui; text-align: center; padding: 50px;">
            <h1>Login Failed</h1>
            <p>Error: {safe_error}</p>
            <p>Please close this window and try again.</p>
        </body>
        </html>
        """
        self.wfile.write(response_html.encode())

    def log_message(self, format, *args):
        """Suppress HTTP server logging."""
        pass


def find_available_port(start_port: int, max_attempts: int = 3) -> int:
    """Find an available port starting from start_port."""
    for offset in range(max_attempts):
        port = start_port + offset
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("localhost", port))
                return port
        except OSError:
            continue
    raise RuntimeError(f"No available port found in range {start_port}-{start_port + max_attempts}")


def extract_token_from_page(page: Page) -> dict | None:
    """Try to extract access token and refresh token from page state or storage.

    Magister stores OIDC tokens in sessionStorage with keys like:
    - oidc.user:https://accounts.magister.net:M6LOAPP

    Returns:
        Dictionary with 'access_token' and optionally 'refresh_token', or None if not found.
    """
    try:
        result = page.evaluate(
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


def debug_storage(page: Page) -> dict:
    """Debug helper to dump all storage contents."""
    try:
        return page.evaluate(
            """() => {
            const result = {
                localStorage: {},
                sessionStorage: {}
            };

            for (let i = 0; i < localStorage.length; i++) {
                const key = localStorage.key(i);
                result.localStorage[key] = localStorage.getItem(key);
            }

            for (let i = 0; i < sessionStorage.length; i++) {
                const key = sessionStorage.key(i);
                result.sessionStorage[key] = sessionStorage.getItem(key);
            }

            return result;
        }"""
        )
    except Exception:
        return {}


def get_browser_data_dir(school: str) -> Path:
    """Get browser data directory for persistent sessions."""
    config_dir = Path.home() / ".config" / "magister-cli" / "browser_data" / school
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_storage_state_path(school: str) -> Path:
    """Get path for storing browser storage state (cookies + localStorage)."""
    return get_browser_data_dir(school) / "storage_state.json"


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

        Uses storage state to maintain sessions across CLI runs.
        On subsequent runs with valid session, login completes automatically.

        Returns TokenData with access token on success.
        Raises RuntimeError on failure.
        """
        user_data_dir = get_browser_data_dir(self.school)
        storage_state_path = get_storage_state_path(self.school)

        with sync_playwright() as p:
            # Use persistent context with storage state for session persistence
            context_options = {
                "user_data_dir": str(user_data_dir),
                "headless": self.headless,
            }

            context = p.chromium.launch_persistent_context(**context_options)
            page = context.pages[0] if context.pages else context.new_page()

            try:
                # Restore storage state if it exists (for localStorage/sessionStorage)
                if storage_state_path.exists():
                    try:
                        import json
                        with open(storage_state_path) as f:
                            state = json.load(f)
                        # Add cookies from storage state
                        if state.get("cookies"):
                            context.add_cookies(state["cookies"])
                        logger.debug("Restored storage state from previous session")
                    except Exception as e:
                        logger.debug(f"Could not restore storage state: {e}")

                page.goto(self.login_url)

                page.wait_for_timeout(2000)

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

                page.wait_for_timeout(2000)

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
                    # Debug: log what's in storage
                    storage = debug_storage(page)
                    logger.debug(f"Storage keys: localStorage={list(storage.get('localStorage', {}).keys())}, "
                                f"sessionStorage={list(storage.get('sessionStorage', {}).keys())}")
                    raise RuntimeError(
                        "Could not extract access token. "
                        "Please ensure you completed the login process."
                    )

                # Default expiry if not provided
                if expires_at is None:
                    expires_at = datetime.now() + timedelta(hours=2)

                # Save storage state for future sessions (cookies from all domains)
                try:
                    context.storage_state(path=str(storage_state_path))
                    logger.debug(f"Saved storage state to {storage_state_path}")
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
    Remove stored token for the school.

    Args:
        school: School code (None uses config default)

    Returns:
        True if token was deleted, False if no token existed
    """
    token_manager = get_token_manager(school)
    return token_manager.delete_token()


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
