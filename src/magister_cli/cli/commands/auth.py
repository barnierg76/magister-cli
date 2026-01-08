"""Authentication CLI commands."""

from typing import Annotated

import typer
from rich.console import Console

from magister_cli.auth import get_current_token, login, logout
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

    if headless:
        console.print("[yellow]Warning:[/yellow] Running in headless mode - you won't see the browser.")

    try:
        token = login(school_code, headless=headless)
        console.print("\n[green]Login successful![/green]")
        console.print(f"Token saved for school: [cyan]{token.school}[/cyan]")

        if token.expires_at:
            console.print(f"[dim]Token expires: {token.expires_at.strftime('%Y-%m-%d %H:%M')}[/dim]")

    except RuntimeError as e:
        console.print(f"\n[red]Login failed:[/red] {e}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"\n[red]Unexpected error:[/red] {e}")
        console.print("\n[dim]If Playwright browser is not installed, run:[/dim]")
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
        console.print("[green]Logged out successfully.[/green]")
    else:
        console.print("[yellow]No token found to remove.[/yellow]")
