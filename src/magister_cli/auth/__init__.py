"""Authentication module for Magister CLI."""

from magister_cli.auth.browser_auth import get_current_token, login, logout
from magister_cli.auth.token_manager import TokenData, TokenManager, get_token_manager

__all__ = [
    "TokenData",
    "TokenManager",
    "get_token_manager",
    "login",
    "logout",
    "get_current_token",
]
