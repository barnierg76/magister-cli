"""CLI utility functions and decorators."""

from functools import wraps
from typing import Callable, TypeVar

import typer
from rich.console import Console

from magister_cli.api.exceptions import MagisterAPIError, TokenExpiredError
from magister_cli.cli.formatters import format_api_error, format_no_auth_error

console = Console()

F = TypeVar("F", bound=Callable)


def handle_api_errors(f: F) -> F:
    """Decorator to handle common API errors in CLI commands.

    This decorator catches and handles:
    - TokenExpiredError: Shows re-authentication message
    - RuntimeError with "Not authenticated": Shows auth message
    - MagisterAPIError: Shows formatted API error

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

        try:
            return f(*args, **kwargs)
        except TokenExpiredError:
            format_no_auth_error(console, school_code)
            raise typer.Exit(1)
        except RuntimeError as e:
            if "Not authenticated" in str(e):
                format_no_auth_error(console, school_code)
            else:
                console.print(f"[red]Fout:[/red] {e}")
            raise typer.Exit(1)
        except MagisterAPIError as e:
            format_api_error(console, e)
            raise typer.Exit(1)

    return wrapper  # type: ignore
