"""CLI utility functions and decorators."""

from functools import wraps
from typing import Callable, TypeVar

import typer
from rich.console import Console

from magister_cli.api.exceptions import (
    MagisterAPIError,
    NotAuthenticatedError,
    TokenExpiredError,
)
from magister_cli.cli.errors import format_error

console = Console()

F = TypeVar("F", bound=Callable)


def _check_token_expiry_warning(school_code: str | None) -> None:
    """Check if token is expiring soon and warn the user."""
    if not school_code:
        return

    from magister_cli.auth.token_manager import get_token_manager

    manager = get_token_manager(school_code)
    remaining = manager.get_time_until_expiry()

    if remaining is None:
        return

    minutes_left = int(remaining.total_seconds() / 60)

    # Warn if less than 15 minutes remaining
    if 0 < minutes_left <= 15:
        console.print(
            f"[yellow]Let op:[/yellow] Je sessie verloopt over {minutes_left} minuten. "
            f"[dim]Hernieuw met: magister login[/dim]"
        )
        console.print()


def handle_api_errors(f: F) -> F:
    """Decorator to handle common API errors in CLI commands.

    This decorator catches and handles:
    - TokenExpiredError: Shows re-authentication message
    - NotAuthenticatedError: Shows auth required message
    - RuntimeError with "Not authenticated": Shows auth message
    - MagisterAPIError: Shows formatted API error with suggestions

    It also proactively warns users when their token is about to expire.

    Usage:
        @app.command()
        @handle_api_errors
        def my_command(school: str):
            ...
    """

    @wraps(f)
    def wrapper(*args, **kwargs):
        # Extract school_code from kwargs if present
        school_code = kwargs.get("school") or kwargs.get("school_code")

        # Warn if token is expiring soon (but still valid)
        _check_token_expiry_warning(school_code)

        try:
            return f(*args, **kwargs)
        except (TokenExpiredError, NotAuthenticatedError, MagisterAPIError) as e:
            format_error(e, console, school=school_code)
            raise typer.Exit(1)
        except RuntimeError as e:
            if "Not authenticated" in str(e):
                format_error(
                    NotAuthenticatedError(school_code),
                    console,
                    school=school_code,
                )
            else:
                console.print(f"[red]Fout:[/red] {e}")
            raise typer.Exit(1)

    return wrapper  # type: ignore
