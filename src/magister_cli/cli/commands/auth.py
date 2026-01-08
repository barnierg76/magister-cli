"""Authentication CLI commands."""

from typing import Annotated

import typer
from rich.console import Console

from magister_cli.auth import get_current_token, login, logout
from magister_cli.cli.progress import print_error, print_success, print_warning
from magister_cli.config import get_settings

console = Console()
app = typer.Typer(help="Authentication commands")


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

    if token is None:
        console.print(f"[red]Not authenticated[/red] for school: {school_code}")
        console.print("\nRun [cyan]magister login --school {school_code}[/cyan] to authenticate.")
        raise typer.Exit(1)

    if token.person_name:
        console.print(f"[green]Authenticated[/green] as [bold]{token.person_name}[/bold]")
    else:
        console.print("[green]Authenticated[/green]")

    console.print(f"School: [cyan]{token.school}[/cyan]")

    if token.expires_at:
        console.print(f"Token expires: {token.expires_at.strftime('%Y-%m-%d %H:%M')}")


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
