"""Authentication CLI commands."""

from datetime import datetime
from typing import Annotated

import typer
from rich.console import Console

from magister_cli.auth import get_current_token, login, logout, refresh_access_token_sync
from magister_cli.auth.token_manager import get_token_manager
from magister_cli.cli.progress import print_error, print_success, print_warning
from magister_cli.config import get_settings

console = Console()
app = typer.Typer(help="Authentication commands")


def _format_time_remaining(minutes: int) -> str:
    """Format remaining time in a human-readable way."""
    if minutes < 1:
        return "minder dan een minuut"
    elif minutes < 60:
        return f"{minutes} minuut{'en' if minutes != 1 else ''}"
    else:
        hours = minutes // 60
        mins = minutes % 60
        parts = []
        if hours > 0:
            parts.append(f"{hours} uur")
        if mins > 0:
            parts.append(f"{mins} min")
        return " en ".join(parts)


@app.command()
def status(
    school: Annotated[
        str | None,
        typer.Option("--school", "-s", help="School code (e.g., vsvonh)"),
    ] = None,
):
    """Show current authentication status."""
    settings = get_settings()
    school_code = school or settings.school

    if not school_code:
        console.print(
            "[yellow]No school configured.[/yellow]\n"
            "Set MAGISTER_SCHOOL in .env or use --school flag."
        )
        raise typer.Exit(1)

    token = get_current_token(school_code)
    token_manager = get_token_manager(school_code)

    if token is None:
        console.print(f"[red]Niet ingelogd[/red] voor school: {school_code}")
        console.print(f"\nLog in met: [cyan]magister login --school {school_code}[/cyan]")
        raise typer.Exit(1)

    # Check if token is expired or expiring soon
    if token.is_expired():
        console.print("[red]Sessie verlopen[/red]")
        console.print(f"School: [cyan]{token.school}[/cyan]")
        console.print(f"\nLog opnieuw in met: [cyan]magister login --school {school_code}[/cyan]")
        raise typer.Exit(1)

    if token.person_name:
        console.print(f"[green]Ingelogd[/green] als [bold]{token.person_name}[/bold]")
    else:
        console.print("[green]Ingelogd[/green]")

    console.print(f"School: [cyan]{token.school}[/cyan]")

    # Show token expiry with time remaining
    if token.expires_at:
        remaining = token_manager.get_time_until_expiry()
        if remaining:
            minutes_left = int(remaining.total_seconds() / 60)
            time_str = _format_time_remaining(minutes_left)

            if minutes_left <= 10:
                console.print(f"Sessie verloopt over: [yellow]{time_str}[/yellow]")
                if token.has_refresh_token():
                    console.print("[dim]Tip: Gebruik 'magister refresh' om sessie te verlengen[/dim]")
                else:
                    console.print("[dim]Tip: Log opnieuw in voor een langere sessie[/dim]")
            elif minutes_left <= 30:
                console.print(f"Sessie verloopt over: [yellow]{time_str}[/yellow]")
            else:
                console.print(f"Sessie verloopt over: [green]{time_str}[/green]")

            console.print(f"[dim]({token.expires_at.strftime('%H:%M')})[/dim]")

    # Show refresh token status
    if token.has_refresh_token():
        console.print("[dim]Refresh token: beschikbaar (automatisch vernieuwen mogelijk)[/dim]")
    else:
        console.print("[dim]Refresh token: niet beschikbaar[/dim]")


@app.command("login")
def do_login(
    school: Annotated[
        str | None,
        typer.Option("--school", "-s", help="School code (e.g., vsvonh)"),
    ] = None,
    headless: Annotated[
        bool,
        typer.Option("--headless/--no-headless", help="Run browser in headless mode"),
    ] = False,
):
    """
    Authenticate with Magister.

    Opens a browser window for you to log in. Your token will be securely stored
    in the system keychain.
    """
    settings = get_settings()
    school_code = school or settings.school

    if not school_code:
        console.print("[red]Error:[/red] No school specified.")
        console.print("\nProvide school via:")
        console.print("  --school flag: [cyan]magister login --school vsvonh[/cyan]")
        console.print("  Environment: [cyan]export MAGISTER_SCHOOL=vsvonh[/cyan]")
        raise typer.Exit(1)

    console.print(f"Opening browser for login to [cyan]{school_code}.magister.net[/cyan]...")
    console.print("[dim]Complete the login process in the browser window.[/dim]")
    console.print()

    if headless:
        print_warning("Running in headless mode - you won't see the browser.")

    try:
        # Show spinner while waiting for OAuth
        with console.status(
            "[bold blue]Wacht op login via browser...",
            spinner="dots",
        ):
            token = login(school_code, headless=headless)

        print_success("Login gelukt!")
        console.print(f"  School: [cyan]{token.school}[/cyan]")

        if token.person_name:
            console.print(f"  Gebruiker: [bold]{token.person_name}[/bold]")

        if token.expires_at:
            console.print(f"  [dim]Token geldig tot: {token.expires_at.strftime('%Y-%m-%d %H:%M')}[/dim]")

    except RuntimeError as e:
        print_error(f"Login mislukt: {e}")
        raise typer.Exit(1)
    except Exception as e:
        print_error(f"Onverwachte fout: {e}")
        console.print("\n[dim]Als Playwright browser niet is geïnstalleerd, voer uit:[/dim]")
        console.print("[cyan]playwright install chromium[/cyan]")
        raise typer.Exit(1)


@app.command("logout")
def do_logout(
    school: Annotated[
        str | None,
        typer.Option("--school", "-s", help="School code (e.g., vsvonh)"),
    ] = None,
):
    """Remove stored authentication token."""
    settings = get_settings()
    school_code = school or settings.school

    if not school_code:
        console.print("[yellow]No school specified. Using default.[/yellow]")

    if logout(school_code):
        print_success("Uitgelogd.")
    else:
        print_warning("Geen token gevonden om te verwijderen.")


@app.command("refresh")
def do_refresh(
    school: Annotated[
        str | None,
        typer.Option("--school", "-s", help="School code (e.g., vsvonh)"),
    ] = None,
):
    """
    Refresh the access token using the stored refresh token.

    This silently refreshes your session without opening a browser.
    Only works if a refresh token was captured during initial login.
    """
    settings = get_settings()
    school_code = school or settings.school

    if not school_code:
        console.print("[red]Error:[/red] No school specified.")
        console.print("\nProvide school via:")
        console.print("  --school flag: [cyan]magister refresh --school vsvonh[/cyan]")
        console.print("  Environment: [cyan]export MAGISTER_SCHOOL=vsvonh[/cyan]")
        raise typer.Exit(1)

    token_manager = get_token_manager(school_code)

    # Check if we have a refresh token
    if not token_manager.has_refresh_token():
        print_warning("Geen refresh token beschikbaar.")
        console.print("\nLog opnieuw in om een refresh token te verkrijgen:")
        console.print(f"  [cyan]magister login --school {school_code}[/cyan]")
        raise typer.Exit(1)

    try:
        with console.status(
            "[bold blue]Token vernieuwen...",
            spinner="dots",
        ):
            token = refresh_access_token_sync(school_code)

        print_success("Token vernieuwd!")
        console.print(f"  School: [cyan]{token.school}[/cyan]")

        if token.person_name:
            console.print(f"  Gebruiker: [bold]{token.person_name}[/bold]")

        if token.expires_at:
            remaining = token_manager.get_time_until_expiry()
            if remaining:
                minutes_left = int(remaining.total_seconds() / 60)
                time_str = _format_time_remaining(minutes_left)
                console.print(f"  Geldig voor: [green]{time_str}[/green]")
            console.print(f"  [dim]Verloopt om: {token.expires_at.strftime('%H:%M')}[/dim]")

        if token.has_refresh_token():
            console.print("  [dim]Refresh token: beschikbaar[/dim]")

    except RuntimeError as e:
        print_error(f"Token vernieuwen mislukt: {e}")
        console.print("\nProbeer opnieuw in te loggen:")
        console.print(f"  [cyan]magister login --school {school_code}[/cyan]")
        raise typer.Exit(1)
    except Exception as e:
        print_error(f"Onverwachte fout: {e}")
        raise typer.Exit(1)
