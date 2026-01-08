"""Main CLI entry point for Magister CLI."""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from magister_cli.api import MagisterAPIError, MagisterClient
from magister_cli.auth import get_current_token
from magister_cli.cli.commands import auth, completion, config, export, grades, messages, notify, schedule
from magister_cli.cli.errors import format_error
from magister_cli.cli.formatters import (
    format_homework_list,
    format_homework_table,
    strip_html,
)
from magister_cli.cli.progress import (
    DownloadProgress,
    api_spinner,
    print_error,
    print_success,
)
from magister_cli.cli.utils import handle_api_errors
from magister_cli.config import get_settings
from magister_cli.services.homework import HomeworkService

console = Console()

app = typer.Typer(
    name="magister",
    help="CLI tool voor Magister data ophalen en quiz generatie",
    no_args_is_help=True,
)

app.command("login")(auth.do_login)
app.command("logout")(auth.do_logout)
app.command("status")(auth.status)

# Add subcommand groups
app.add_typer(messages.app, name="messages", help="Berichten beheren")
app.add_typer(grades.app, name="grades", help="Cijfers bekijken")
app.add_typer(schedule.app, name="schedule", help="Rooster bekijken")
app.add_typer(config.app, name="config", help="Configuratie beheren")
app.add_typer(completion.app, name="completion", help="Shell completion beheren")
app.add_typer(export.app, name="export", help="Exporteer naar iCal en andere formaten")
app.add_typer(notify.app, name="notify", help="Notificaties beheren")


@app.command("homework")
@handle_api_errors
def homework(
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
    download: Annotated[
        bool,
        typer.Option("--download", help="Download all attachments"),
    ] = False,
    output_dir: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Output directory for downloads"),
    ] = None,
):
    """
    Show upcoming homework.

    Examples:
        magister homework --days 7
        magister homework --subject wiskunde
        magister homework --table
        magister homework --download
        magister homework --download --output ./bijlagen
    """
    settings = get_settings()
    school_code = school or settings.school

    service = HomeworkService(school=school_code)

    with api_spinner("Huiswerk ophalen..."):
        homework_days = service.get_homework(
            days=days,
            subject=subject,
            include_completed=include_completed,
        )

    if table_format:
        format_homework_table(homework_days, console)
    else:
        format_homework_list(homework_days, console)

    # Download attachments if requested
    if download:
        # Collect all attachments
        attachments_to_download = []
        for day in homework_days:
            for item in day.items:
                for att in item.attachments:
                    attachments_to_download.append((item, att))

        if not attachments_to_download:
            console.print("\n[yellow]Geen bijlagen om te downloaden.[/yellow]")
        else:
            # Get token for download
            from magister_cli.api.exceptions import NotAuthenticatedError

            token_data = get_current_token(school_code)
            if token_data is None:
                raise NotAuthenticatedError(school_code)

            # Default output directory
            if output_dir is None:
                download_dir = Path.cwd() / "magister_bijlagen"
            else:
                download_dir = output_dir

            console.print(f"\n[bold]📎 {len(attachments_to_download)} bijlage(n) downloaden...[/bold]")

            with MagisterClient(token_data.school, token_data.access_token) as client:
                with DownloadProgress(len(attachments_to_download)) as progress:
                    for item, att in attachments_to_download:
                        progress.update_file(att.name)
                        subject_dir = download_dir / item.subject.replace("/", "-")
                        try:
                            client.download_attachment(att.raw, subject_dir)
                            progress.complete_file(success=True)
                        except MagisterAPIError as e:
                            progress.complete_file(success=False)
                            print_error(f"{att.name}: {e}")

            print_success(f"Opgeslagen in: {download_dir}")


@app.command("tests")
@handle_api_errors
def tests(
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
        magister tests --days 14
    """
    settings = get_settings()
    school_code = school or settings.school

    service = HomeworkService(school=school_code)

    with api_spinner("Toetsen ophalen..."):
        test_items = service.get_upcoming_tests(days=days)

    if not test_items:
        console.print(
            f"[green]Geen toetsen in de komende {days} dagen.[/green]"
        )
        return

    console.print(f"[bold red]Toetsen komende {days} dagen[/bold red]")
    console.print()

    for test in test_items:
        date_str = test.deadline.strftime("%a %d %b")
        time_str = test.deadline.strftime("%H:%M")
        console.print(
            f"  [red]TOETS[/red] [cyan]{date_str} {time_str}[/cyan] - [bold]{test.subject}[/bold]"
        )
        if test.description:
            clean_desc = strip_html(test.description)
            for line in clean_desc.strip().split("\n"):
                if line.strip():
                    console.print(f"         {line.strip()}")
        console.print()


@app.command("download")
@handle_api_errors
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
        magister download
        magister download --days 14 --output ./bijlagen
        magister download --subject engels
    """
    from magister_cli.api.exceptions import NotAuthenticatedError

    settings = get_settings()
    school_code = school or settings.school

    # Get token
    token_data = get_current_token(school_code)
    if token_data is None:
        raise NotAuthenticatedError(school_code)

    # Default output directory
    if output_dir is None:
        output_dir = Path.cwd() / "magister_bijlagen"

    service = HomeworkService(school=school_code)

    with api_spinner("Bijlagen zoeken..."):
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

    # Download each attachment with progress
    with MagisterClient(token_data.school, token_data.access_token) as client:
        with DownloadProgress(len(attachments_to_download)) as progress:
            for item, att in attachments_to_download:
                progress.update_file(att.name)
                # Create subject subfolder
                subject_dir = output_dir / item.subject.replace("/", "-")

                try:
                    client.download_attachment(att.raw, subject_dir)
                    progress.complete_file(success=True)
                except MagisterAPIError as e:
                    progress.complete_file(success=False)
                    print_error(f"{att.name}: {e}")

    console.print()
    print_success(f"Downloads opgeslagen in: {output_dir}")


if __name__ == "__main__":
    app()
