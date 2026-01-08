"""Schedule CLI commands."""

from datetime import date, timedelta
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from magister_cli.api import MagisterAPIError, MagisterClient, TokenExpiredError
from magister_cli.api.models import Afspraak
from magister_cli.auth import get_current_token
from magister_cli.cli.formatters import format_api_error, format_no_auth_error, strip_html
from magister_cli.config import get_settings

console = Console()
app = typer.Typer(help="Rooster commando's")

# Dutch day names
DAY_NAMES = ["Maandag", "Dinsdag", "Woensdag", "Donderdag", "Vrijdag", "Zaterdag", "Zondag"]


def _get_client(school: str | None) -> tuple[MagisterClient, str]:
    """Get authenticated client and school code."""
    settings = get_settings()
    school_code = school or settings.school

    if not school_code:
        console.print("[red]Geen school opgegeven.[/red]")
        console.print("Gebruik --school of stel MAGISTER_SCHOOL in.")
        raise typer.Exit(1)

    token_data = get_current_token(school_code)
    if token_data is None:
        format_no_auth_error(console, school_code)
        raise typer.Exit(1)

    return MagisterClient(token_data.school, token_data.access_token), school_code


def _format_time_range(afspraak: Afspraak) -> str:
    """Format start-end time."""
    start = afspraak.start.strftime("%H:%M")
    end = afspraak.einde.strftime("%H:%M")
    return f"{start}-{end}"


def _format_lesson_status(afspraak: Afspraak) -> str:
    """Format lesson status indicators."""
    status = []
    if afspraak.is_vervallen:
        status.append("[red]UITVAL[/red]")
    if afspraak.is_gewijzigd:
        status.append("[yellow]WIJZIGING[/yellow]")
    if afspraak.is_test_or_exam():
        status.append("[red]TOETS[/red]")
    if afspraak.heeft_huiswerk:
        status.append("[cyan]HW[/cyan]")
    return " ".join(status)


def _get_day_label(d: date) -> str:
    """Get a label for a date (Vandaag, Morgen, or weekday)."""
    today = date.today()
    if d == today:
        return "Vandaag"
    elif d == today + timedelta(days=1):
        return "Morgen"
    else:
        return DAY_NAMES[d.weekday()]


def _display_day_schedule(appointments: list[Afspraak], day: date) -> None:
    """Display schedule for a single day."""
    label = _get_day_label(day)
    date_str = day.strftime("%d-%m-%Y")

    if day == date.today():
        header_style = "bold green"
    elif day == date.today() + timedelta(days=1):
        header_style = "bold yellow"
    else:
        header_style = "bold"

    console.print(f"[{header_style}]{label}[/{header_style}] [dim]{date_str}[/dim]")
    console.print()

    if not appointments:
        console.print("  [dim]Geen lessen[/dim]")
        console.print()
        return

    # Sort by lesson hour then start time
    appointments.sort(key=lambda a: (a.les_uur or 99, a.start))

    for afspraak in appointments:
        time_str = _format_time_range(afspraak)
        lesson_num = f"Les {afspraak.les_uur}" if afspraak.les_uur else ""
        status = _format_lesson_status(afspraak)

        # Main lesson info
        subject = afspraak.vak_naam or afspraak.omschrijving or "Onbekend"
        location = afspraak.lokaal_naam or ""
        teacher = afspraak.docent_naam or ""

        # Format main line
        if afspraak.is_vervallen:
            subject = f"[strike]{subject}[/strike]"

        line = f"  [cyan]{time_str}[/cyan] [dim]{lesson_num:6}[/dim] [bold]{subject}[/bold]"
        if location:
            line += f" [dim]({location})[/dim]"
        if status:
            line += f" {status}"

        console.print(line)

        # Teacher info
        if teacher:
            console.print(f"             [dim]Docent: {teacher}[/dim]")

        # Homework preview
        if afspraak.heeft_huiswerk and afspraak.huiswerk_tekst:
            hw_clean = strip_html(afspraak.huiswerk_tekst)
            # Replace newlines with spaces for single-line preview
            hw_oneline = hw_clean.replace("\n", " ").strip()
            hw_preview = hw_oneline[:60]
            if len(hw_oneline) > 60:
                hw_preview += "..."
            console.print(f"             [cyan]↳ {hw_preview}[/cyan]")

    console.print()


@app.command("today")
@app.command("dag")
def today_schedule(
    school: Annotated[
        str | None,
        typer.Option("--school", "-s", help="School code"),
    ] = None,
):
    """
    Toon rooster van vandaag.

    Voorbeelden:
        magister schedule today
    """
    client, school_code = _get_client(school)

    try:
        with client:
            today = date.today()
            appointments = client.appointments.for_date(today)
            _display_day_schedule(appointments, today)

    except TokenExpiredError:
        format_no_auth_error(console, school_code)
        raise typer.Exit(1)
    except MagisterAPIError as e:
        format_api_error(console, e)
        raise typer.Exit(1)


@app.command("tomorrow")
@app.command("morgen")
def tomorrow_schedule(
    school: Annotated[
        str | None,
        typer.Option("--school", "-s", help="School code"),
    ] = None,
):
    """
    Toon rooster van morgen.

    Voorbeelden:
        magister schedule tomorrow
    """
    client, school_code = _get_client(school)

    try:
        with client:
            tomorrow = date.today() + timedelta(days=1)
            appointments = client.appointments.for_date(tomorrow)
            _display_day_schedule(appointments, tomorrow)

    except TokenExpiredError:
        format_no_auth_error(console, school_code)
        raise typer.Exit(1)
    except MagisterAPIError as e:
        format_api_error(console, e)
        raise typer.Exit(1)


@app.command("week")
def week_schedule(
    school: Annotated[
        str | None,
        typer.Option("--school", "-s", help="School code"),
    ] = None,
):
    """
    Toon rooster van deze week.

    Voorbeelden:
        magister schedule week
    """
    client, school_code = _get_client(school)

    try:
        with client:
            today = date.today()
            # Get start of week (Monday)
            start_of_week = today - timedelta(days=today.weekday())
            end_of_week = start_of_week + timedelta(days=6)

            appointments = client.appointments.list(start_of_week, end_of_week)

            # Group by date
            by_date: dict[date, list[Afspraak]] = {}
            for a in appointments:
                d = a.start.date()
                if d not in by_date:
                    by_date[d] = []
                by_date[d].append(a)

            console.print(Panel(
                f"Week van {start_of_week.strftime('%d-%m')} t/m {end_of_week.strftime('%d-%m-%Y')}",
                border_style="blue",
            ))
            console.print()

            # Display each day
            for i in range(7):
                day = start_of_week + timedelta(days=i)
                day_appointments = by_date.get(day, [])
                _display_day_schedule(day_appointments, day)

    except TokenExpiredError:
        format_no_auth_error(console, school_code)
        raise typer.Exit(1)
    except MagisterAPIError as e:
        format_api_error(console, e)
        raise typer.Exit(1)


@app.command("date")
def date_schedule(
    target_date: Annotated[
        str,
        typer.Argument(help="Datum (formaat: DD-MM-YYYY of DD-MM)"),
    ],
    school: Annotated[
        str | None,
        typer.Option("--school", "-s", help="School code"),
    ] = None,
):
    """
    Toon rooster voor een specifieke datum.

    Voorbeelden:
        magister schedule date 15-01-2026
        magister schedule date 15-01
    """
    client, school_code = _get_client(school)

    # Parse date
    try:
        parts = target_date.split("-")
        if len(parts) == 2:
            day, month = int(parts[0]), int(parts[1])
            year = date.today().year
        elif len(parts) == 3:
            day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
        else:
            raise ValueError("Ongeldig formaat")

        target = date(year, month, day)
    except (ValueError, IndexError):
        console.print("[red]Ongeldig datumformaat.[/red] Gebruik DD-MM-YYYY of DD-MM")
        raise typer.Exit(1)

    try:
        with client:
            appointments = client.appointments.for_date(target)
            _display_day_schedule(appointments, target)

    except TokenExpiredError:
        format_no_auth_error(console, school_code)
        raise typer.Exit(1)
    except MagisterAPIError as e:
        format_api_error(console, e)
        raise typer.Exit(1)


@app.command("changes")
def schedule_changes(
    days: Annotated[
        int,
        typer.Option("--days", "-d", help="Aantal dagen vooruit"),
    ] = 7,
    school: Annotated[
        str | None,
        typer.Option("--school", "-s", help="School code"),
    ] = None,
):
    """
    Toon alleen roosterwijzigingen.

    Voorbeelden:
        magister schedule changes
        magister schedule changes --days 14
    """
    client, school_code = _get_client(school)

    try:
        with client:
            start = date.today()
            end = start + timedelta(days=days)

            appointments = client.appointments.list(start, end)

            # Filter to only changed/cancelled
            changes = [a for a in appointments if a.is_gewijzigd or a.is_vervallen]

            if not changes:
                console.print(f"[green]Geen roosterwijzigingen in de komende {days} dagen.[/green]")
                return

            console.print(Panel(
                f"Roosterwijzigingen ({len(changes)} stuks)",
                border_style="yellow",
            ))
            console.print()

            # Sort by date
            changes.sort(key=lambda a: a.start)

            table = Table(show_header=True, header_style="bold")
            table.add_column("Datum", style="cyan", width=12)
            table.add_column("Tijd", width=12)
            table.add_column("Les", width=5)
            table.add_column("Vak", width=20)
            table.add_column("Status", width=15)
            table.add_column("Lokaal", width=10)

            for afspraak in changes:
                date_str = afspraak.start.strftime("%a %d-%m")
                time_str = _format_time_range(afspraak)
                les = str(afspraak.les_uur) if afspraak.les_uur else "-"
                subject = afspraak.vak_naam or afspraak.omschrijving or "?"

                if afspraak.is_vervallen:
                    status = "[red]Uitval[/red]"
                    subject = f"[strike]{subject}[/strike]"
                else:
                    status = "[yellow]Wijziging[/yellow]"

                location = afspraak.lokaal_naam or "-"

                table.add_row(date_str, time_str, les, subject, status, location)

            console.print(table)

    except TokenExpiredError:
        format_no_auth_error(console, school_code)
        raise typer.Exit(1)
    except MagisterAPIError as e:
        format_api_error(console, e)
        raise typer.Exit(1)
