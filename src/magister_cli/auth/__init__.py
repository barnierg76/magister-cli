"""Authentication module for Magister CLI."""

from magister_cli.auth.browser_auth import get_current_token, login, logout
from magister_cli.auth.token_manager import TokenData, TokenManager, get_token_manager
from magister_cli.auth.async_browser_auth import (
    async_login,
    is_gui_available,
    AsyncBrowserAuthenticator,
)
from magister_cli.auth.token_refresh import (
    refresh_access_token,
    refresh_access_token_sync,
    auto_refresh_if_needed,
)
from magister_cli.auth.credential_store import (
    store_credentials,
    get_credentials,
    clear_credentials,
    has_stored_credentials,
)
from magister_cli.auth.headless_login import (
    headless_login,
    try_headless_reauth,
    HeadlessLoginError,
    CredentialsInvalidError,
    TwoFactorRequiredError,
    LoginTimeoutError,
)

__all__ = [
    # Token management
    "TokenData",
    "TokenManager",
    "get_token_manager",
    # Browser auth
    "login",
    "logout",
    "get_current_token",
    "async_login",
    "is_gui_available",
    "AsyncBrowserAuthenticator",
    # Token refresh
    "refresh_access_token",
    "refresh_access_token_sync",
    "auto_refresh_if_needed",
    # Credential storage (headless auth)
    "store_credentials",
    "get_credentials",
    "clear_credentials",
    "has_stored_credentials",
    # Headless login
    "headless_login",
    "try_headless_reauth",
    "HeadlessLoginError",
    "CredentialsInvalidError",
    "TwoFactorRequiredError",
    "LoginTimeoutError",
]
