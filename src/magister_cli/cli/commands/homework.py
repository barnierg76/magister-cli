"""Homework CLI command."""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from magister_cli.api import MagisterAPIError, MagisterClient, TokenExpiredError
from magister_cli.auth import get_current_token
from magister_cli.cli.formatters import (
    format_api_error,
    format_homework_list,
    format_homework_table,
    format_no_auth_error,
    strip_html,
)
from magister_cli.config import get_settings
from magister_cli.services.homework import HomeworkService

console = Console()
app = typer.Typer(help="Homework commands")


@app.command("list")
def homework_list(
    days: Annotated[
        int,
        typer.Option("--days", "-d", help="Number of days to look ahead"),
    ] = 7,
    subject: Annotated[
        str | None,
        typer.Option("--subject", "-s", help="Filter by subject (partial match)"),
    ] = None,
    school: Annotated[
        str | None,
        typer.Option("--school", help="School code"),
    ] = None,
    include_completed: Annotated[
        bool,
        typer.Option("--completed", "-c", help="Include completed homework"),
    ] = False,
    table_format: Annotated[
        bool,
        typer.Option("--table", "-t", help="Show as table"),
    ] = False,
):
    """
    Show upcoming homework.

    Examples:
        magister homework list --days 7
        magister homework list --subject wiskunde
        magister homework list --table
    """
    settings = get_settings()
    school_code = school or settings.school

    service = HomeworkService(school=school_code)

    try:
        homework_days = service.get_homework(
            days=days,
            subject=subject,
            include_completed=include_completed,
        )

        if table_format:
            format_homework_table(homework_days, console)
        else:
            format_homework_list(homework_days, console)

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


@app.command("tests")
def upcoming_tests(
    days: Annotated[
        int,
        typer.Option("--days", "-d", help="Number of days to look ahead"),
    ] = 14,
    school: Annotated[
        str | None,
        typer.Option("--school", help="School code"),
    ] = None,
):
    """
    Show upcoming tests.

    Example:
        magister homework tests --days 14
    """
    settings = get_settings()
    school_code = school or settings.school

    service = HomeworkService(school=school_code)

    try:
        tests = service.get_upcoming_tests(days=days)

        if not tests:
            console.print(
                f"[green]Geen toetsen in de komende {days} dagen.[/green]"
            )
            return

        console.print(f"[bold red]Toetsen komende {days} dagen[/bold red]")
        console.print()

        for test in tests:
            date_str = test.deadline.strftime("%a %d %b")
            time_str = test.deadline.strftime("%H:%M")
            console.print(
                f"  [red]TOETS[/red] [cyan]{date_str} {time_str}[/cyan] - [bold]{test.subject}[/bold]"
            )
            if test.description:
                for line in test.description.strip().split("\n"):
                    if line.strip():
                        console.print(f"         {line.strip()}")
            console.print()

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


@app.command("download")
def download_attachments(
    days: Annotated[
        int,
        typer.Option("--days", "-d", help="Number of days to look ahead"),
    ] = 7,
    subject: Annotated[
        str | None,
        typer.Option("--subject", "-s", help="Filter by subject (partial match)"),
    ] = None,
    output_dir: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Output directory for downloads"),
    ] = None,
    school: Annotated[
        str | None,
        typer.Option("--school", help="School code"),
    ] = None,
):
    """
    Download all homework attachments.

    Examples:
        magister homework download
        magister homework download --days 14 --output ./bijlagen
        magister homework download --subject engels
    """
    settings = get_settings()
    school_code = school or settings.school

    # Get token
    token_data = get_current_token(school_code)
    if token_data is None:
        format_no_auth_error(console, school_code)
        raise typer.Exit(1)

    # Default output directory
    if output_dir is None:
        output_dir = Path.cwd() / "magister_bijlagen"

    service = HomeworkService(school=school_code)

    try:
        homework_days = service.get_homework(
            days=days,
            subject=subject,
            include_attachments=True,
        )

        # Collect all attachments
        attachments_to_download = []
        for day in homework_days:
            for item in day.items:
                for att in item.attachments:
                    attachments_to_download.append((item, att))

        if not attachments_to_download:
            console.print("[yellow]Geen bijlagen gevonden.[/yellow]")
            return

        console.print(f"[bold]📎 {len(attachments_to_download)} bijlage(n) gevonden[/bold]")
        console.print()

        # Download each attachment
        with MagisterClient(token_data.school, token_data.access_token) as client:
            for item, att in attachments_to_download:
                # Create subject subfolder
                subject_dir = output_dir / item.subject.replace("/", "-")

                console.print(f"  Downloaden: [cyan]{att.name}[/cyan] ({att.size})")

                try:
                    output_path = client.download_attachment(att.raw, subject_dir)
                    console.print(f"    ✓ Opgeslagen: [dim]{output_path}[/dim]")
                except MagisterAPIError as e:
                    console.print(f"    [red]✗ Fout: {e}[/red]")

        console.print()
        console.print(f"[green]✓ Downloads opgeslagen in: {output_dir}[/green]")

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
