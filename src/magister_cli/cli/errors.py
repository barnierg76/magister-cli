"""User-friendly error messages with actionable suggestions."""

from dataclasses import dataclass

from rich.console import Console
from rich.panel import Panel

from magister_cli.api.exceptions import (
    MagisterAPIError,
    NotAuthenticatedError,
    RateLimitError,
    TokenExpiredError,
)


@dataclass
class ErrorInfo:
    """Structured error information for display."""

    title: str
    message: str
    suggestion: str
    command: str | None = None


# Error taxonomy with Dutch messages
ERROR_MESSAGES = {
    "auth_expired": ErrorInfo(
        title="Sessie verlopen",
        message="Je sessie is verlopen.",
        suggestion="Log opnieuw in",
        command="magister login",
    ),
    "auth_required": ErrorInfo(
        title="Niet ingelogd",
        message="Je moet eerst inloggen om deze actie uit te voeren.",
        suggestion="Log in met je Magister account",
        command="magister login --school {school}",
    ),
    "network_timeout": ErrorInfo(
        title="Verbinding mislukt",
        message="Kon geen verbinding maken met Magister.",
        suggestion="Controleer je internetverbinding en probeer opnieuw.",
        command=None,
    ),
    "network_error": ErrorInfo(
        title="Netwerkfout",
        message="Er is een fout opgetreden bij het verbinden met Magister.",
        suggestion="Controleer je internetverbinding of probeer later opnieuw.",
        command=None,
    ),
    "rate_limit": ErrorInfo(
        title="Te veel verzoeken",
        message="Je hebt te veel verzoeken gestuurd.",
        suggestion="Wacht {retry_after} seconden en probeer opnieuw.",
        command=None,
    ),
    "server_error": ErrorInfo(
        title="Magister serverfout",
        message="De Magister server heeft een fout gemeld.",
        suggestion="Dit is waarschijnlijk een tijdelijk probleem. Probeer later opnieuw.",
        command=None,
    ),
    "not_found": ErrorInfo(
        title="Niet gevonden",
        message="De gevraagde gegevens konden niet worden gevonden.",
        suggestion="Controleer of je de juiste school en gegevens hebt opgegeven.",
        command=None,
    ),
    "forbidden": ErrorInfo(
        title="Geen toegang",
        message="Je hebt geen toegang tot deze gegevens.",
        suggestion="Controleer of je account de juiste rechten heeft.",
        command=None,
    ),
    "invalid_school": ErrorInfo(
        title="Ongeldige school",
        message="De opgegeven schoolcode is ongeldig.",
        suggestion="Controleer de schoolcode op de Magister website van je school.",
        command=None,
    ),
    "unknown": ErrorInfo(
        title="Onverwachte fout",
        message="Er is een onverwachte fout opgetreden.",
        suggestion="Als dit blijft gebeuren, probeer uit te loggen en opnieuw in te loggen.",
        command="magister logout && magister login",
    ),
}


def get_error_type(error: Exception) -> str:
    """Determine error type from exception."""
    if isinstance(error, TokenExpiredError):
        return "auth_expired"
    elif isinstance(error, NotAuthenticatedError):
        return "auth_required"
    elif isinstance(error, RateLimitError):
        return "rate_limit"
    elif isinstance(error, MagisterAPIError):
        status = getattr(error, "status_code", None)
        if status == 401:
            return "auth_expired"
        elif status == 403:
            return "forbidden"
        elif status == 404:
            return "not_found"
        elif status == 429:
            return "rate_limit"
        elif status and status >= 500:
            return "server_error"

    # Check for network errors
    error_str = str(error).lower()
    if "timeout" in error_str:
        return "network_timeout"
    elif "connect" in error_str or "network" in error_str:
        return "network_error"

    return "unknown"


def format_error(
    error: Exception,
    console: Console,
    school: str | None = None,
    verbose: bool = False,
) -> None:
    """Format and display a user-friendly error message."""
    error_type = get_error_type(error)
    info = ERROR_MESSAGES.get(error_type, ERROR_MESSAGES["unknown"])

    # Format the message with any available context
    message = info.message
    suggestion = info.suggestion
    command = info.command

    # Handle dynamic substitutions
    if "{school}" in (command or ""):
        command = command.format(school=school or "<jouw_school>")

    if "{retry_after}" in suggestion:
        retry_after = getattr(error, "retry_after", 60)
        suggestion = suggestion.format(retry_after=retry_after)

    # Build the panel content
    content_lines = [
        f"[white]{message}[/white]",
        "",
        f"[yellow]Suggestie:[/yellow] {suggestion}",
    ]

    if command:
        content_lines.append("")
        content_lines.append(f"[cyan]{command}[/cyan]")

    # Show technical details in verbose mode
    if verbose:
        content_lines.append("")
        content_lines.append("[dim]─" * 40 + "[/dim]")
        content_lines.append(f"[dim]Type: {type(error).__name__}[/dim]")
        content_lines.append(f"[dim]Details: {error}[/dim]")

    content = "\n".join(content_lines)

    console.print()
    console.print(Panel(
        content,
        title=f"[red bold]Fout: {info.title}[/red bold]",
        border_style="red",
        padding=(1, 2),
    ))
    console.print()


def format_success(
    message: str,
    console: Console,
    details: str | None = None,
) -> None:
    """Format a success message."""
    content = f"[white]{message}[/white]"
    if details:
        content += f"\n\n[dim]{details}[/dim]"

    console.print(Panel(
        content,
        title="[green bold]Gelukt[/green bold]",
        border_style="green",
        padding=(0, 2),
    ))


def format_warning(
    message: str,
    console: Console,
    suggestion: str | None = None,
) -> None:
    """Format a warning message."""
    content = f"[white]{message}[/white]"
    if suggestion:
        content += f"\n\n[yellow]Tip:[/yellow] {suggestion}"

    console.print(Panel(
        content,
        title="[yellow bold]Let op[/yellow bold]",
        border_style="yellow",
        padding=(0, 2),
    ))
