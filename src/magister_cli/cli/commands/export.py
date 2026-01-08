"""Export CLI commands for iCal and other formats."""

from datetime import date, timedelta
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from magister_cli.api import MagisterClient
from magister_cli.auth import get_current_token
from magister_cli.cli.progress import api_spinner, print_success
from magister_cli.cli.utils import handle_api_errors
from magister_cli.config import get_settings
from magister_cli.services.homework import HomeworkService
from magister_cli.services.ical_export import (
    export_homework_to_ical,
    export_schedule_to_ical,
)

console = Console()
app = typer.Typer(help="Exporteer data naar verschillende formaten")


@app.command("schedule")
@handle_api_errors
def export_schedule(
    days: Annotated[
        int,
        typer.Option("--days", "-d", help="Aantal dagen te exporteren"),
    ] = 14,
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Output bestand (.ics)"),
    ] = None,
    school: Annotated[
        str | None,
        typer.Option("--school", help="School code"),
    ] = None,
):
    """
    Exporteer rooster naar iCal formaat.

    Het bestand kan worden geïmporteerd in agenda apps zoals:
    - Google Calendar
    - Apple Calendar
    - Outlook
    - Andere iCal-compatibele apps

    Voorbeelden:
        magister export schedule
        magister export schedule --days 30 --output rooster.ics
    """
    from magister_cli.api.exceptions import NotAuthenticatedError

    settings = get_settings()
    school_code = school or settings.school

    token_data = get_current_token(school_code)
    if token_data is None:
        raise NotAuthenticatedError(school_code)

    # Default output path
    if output is None:
        output = Path.cwd() / "magister_rooster.ics"

    start = date.today()
    end = start + timedelta(days=days)

    with api_spinner(f"Rooster ophalen ({days} dagen)..."):
        with MagisterClient(token_data.school, token_data.access_token) as client:
            appointments = client.appointments.list(start, end)

    if not appointments:
        console.print("[yellow]Geen lessen gevonden in deze periode.[/yellow]")
        return

    # Export to iCal
    export_schedule_to_ical(appointments, output)

    print_success(f"Rooster geëxporteerd naar: {output}")
    console.print(f"  [dim]{len(appointments)} lessen[/dim]")
    console.print()
    console.print("[dim]Importeer dit bestand in je agenda-app.[/dim]")


@app.command("homework")
@handle_api_errors
def export_homework(
    days: Annotated[
        int,
        typer.Option("--days", "-d", help="Aantal dagen vooruit"),
    ] = 14,
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Output bestand (.ics)"),
    ] = None,
    school: Annotated[
        str | None,
        typer.Option("--school", help="School code"),
    ] = None,
    include_completed: Annotated[
        bool,
        typer.Option("--completed", "-c", help="Inclusief afgerond huiswerk"),
    ] = False,
):
    """
    Exporteer huiswerk naar iCal formaat.

    Huiswerk wordt als hele-dag gebeurtenissen getoond op de deadline datum.

    Voorbeelden:
        magister export homework
        magister export homework --days 30 --output huiswerk.ics
    """
    settings = get_settings()
    school_code = school or settings.school

    # Default output path
    if output is None:
        output = Path.cwd() / "magister_huiswerk.ics"

    service = HomeworkService(school=school_code)

    with api_spinner(f"Huiswerk ophalen ({days} dagen)..."):
        homework_days = service.get_homework(
            days=days,
            include_completed=include_completed,
        )

    # Flatten to list of items
    all_items = []
    for day in homework_days:
        all_items.extend(day.items)

    if not all_items:
        console.print("[yellow]Geen huiswerk gevonden in deze periode.[/yellow]")
        return

    # Export to iCal
    export_homework_to_ical(all_items, output)

    tests_count = sum(1 for i in all_items if i.is_test)

    print_success(f"Huiswerk geëxporteerd naar: {output}")
    console.print(f"  [dim]{len(all_items)} opdrachten[/dim]")
    if tests_count:
        console.print(f"  [red]{tests_count} toetsen[/red]")
    console.print()
    console.print("[dim]Importeer dit bestand in je agenda-app.[/dim]")


@app.command("all")
@handle_api_errors
def export_all(
    days: Annotated[
        int,
        typer.Option("--days", "-d", help="Aantal dagen vooruit"),
    ] = 14,
    output_dir: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Output directory"),
    ] = None,
    school: Annotated[
        str | None,
        typer.Option("--school", help="School code"),
    ] = None,
):
    """
    Exporteer rooster én huiswerk naar iCal bestanden.

    Maakt twee bestanden aan:
    - magister_rooster.ics
    - magister_huiswerk.ics

    Voorbeelden:
        magister export all
        magister export all --days 30 --output ./exports
    """
    from magister_cli.api.exceptions import NotAuthenticatedError

    settings = get_settings()
    school_code = school or settings.school

    token_data = get_current_token(school_code)
    if token_data is None:
        raise NotAuthenticatedError(school_code)

    # Default output directory
    if output_dir is None:
        output_dir = Path.cwd()

    output_dir.mkdir(parents=True, exist_ok=True)

    start = date.today()
    end = start + timedelta(days=days)

    with api_spinner(f"Data ophalen ({days} dagen)..."):
        # Get schedule
        with MagisterClient(token_data.school, token_data.access_token) as client:
            appointments = client.appointments.list(start, end)

        # Get homework
        service = HomeworkService(school=school_code)
        homework_days = service.get_homework(days=days)
        homework_items = []
        for day in homework_days:
            homework_items.extend(day.items)

    # Export schedule
    schedule_path = output_dir / "magister_rooster.ics"
    if appointments:
        export_schedule_to_ical(appointments, schedule_path)
        console.print(f"[green]✓[/green] Rooster: {schedule_path} ({len(appointments)} lessen)")
    else:
        console.print("[yellow]![/yellow] Geen rooster gevonden")

    # Export homework
    homework_path = output_dir / "magister_huiswerk.ics"
    if homework_items:
        export_homework_to_ical(homework_items, homework_path)
        console.print(f"[green]✓[/green] Huiswerk: {homework_path} ({len(homework_items)} items)")
    else:
        console.print("[yellow]![/yellow] Geen huiswerk gevonden")

    console.print()
    console.print("[dim]Importeer deze bestanden in je agenda-app.[/dim]")
