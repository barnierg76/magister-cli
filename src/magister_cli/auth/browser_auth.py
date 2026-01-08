"""Browser-based OAuth authentication using Playwright."""

import html
import socket
import threading
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import Page, sync_playwright

from magister_cli.auth.token_manager import TokenData, get_token_manager
from magister_cli.config import get_settings, validate_school_code


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


def extract_token_from_page(page: Page) -> str | None:
    """Try to extract access token from page state or storage."""
    try:
        token = page.evaluate(
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


class BrowserAuthenticator:
    """Handle browser-based OAuth authentication for Magister."""

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

        Returns TokenData with access token on success.
        Raises RuntimeError on failure.
        """
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            context = browser.new_context()
            page = context.new_page()

            try:
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

                token = extract_token_from_page(page)

                if not token:
                    cookies = context.cookies()
                    for cookie in cookies:
                        if "token" in cookie["name"].lower():
                            token = cookie["value"]
                            break

                if not token:
                    raise RuntimeError(
                        "Could not extract access token. "
                        "Please ensure you completed the login process."
                    )

                expires_at = datetime.now() + timedelta(hours=2)

                return TokenData(
                    access_token=token,
                    school=self.school,
                    expires_at=expires_at,
                )

            finally:
                browser.close()


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
