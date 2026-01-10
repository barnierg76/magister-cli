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

__all__ = [
    "TokenData",
    "TokenManager",
    "get_token_manager",
    "login",
    "logout",
    "get_current_token",
    "async_login",
    "is_gui_available",
    "AsyncBrowserAuthenticator",
    "refresh_access_token",
    "refresh_access_token_sync",
    "auto_refresh_if_needed",
]
