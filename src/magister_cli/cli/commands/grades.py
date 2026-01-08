"""Grades CLI commands."""

from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from magister_cli.api import MagisterAPIError, MagisterClient, TokenExpiredError
from magister_cli.api.models import Cijfer
from magister_cli.auth import get_current_token
from magister_cli.cli.formatters import format_api_error, format_no_auth_error
from magister_cli.config import get_settings

console = Console()
app = typer.Typer(help="Cijfers commando's")


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


def _format_grade(grade: Cijfer) -> str:
    """Format a grade value with color."""
    numeric = grade.cijfer_numeriek
    if numeric is None:
        return grade.cijfer_str

    if numeric >= 8.0:
        return f"[green]{grade.cijfer_str}[/green]"
    elif numeric >= 5.5:
        return f"[cyan]{grade.cijfer_str}[/cyan]"
    else:
        return f"[red]{grade.cijfer_str}[/red]"


def _format_average(avg: float | None) -> str:
    """Format an average with color."""
    if avg is None:
        return "[dim]-[/dim]"

    formatted = f"{avg:.1f}"
    if avg >= 8.0:
        return f"[green]{formatted}[/green]"
    elif avg >= 5.5:
        return f"[cyan]{formatted}[/cyan]"
    else:
        return f"[red]{formatted}[/red]"


@app.command("recent")
@app.command("list")
def recent_grades(
    top: Annotated[
        int,
        typer.Option("--top", "-n", help="Aantal cijfers om te tonen"),
    ] = 15,
    school: Annotated[
        str | None,
        typer.Option("--school", "-s", help="School code"),
    ] = None,
):
    """
    Toon recente cijfers.

    Voorbeelden:
        magister grades recent
        magister grades recent --top 25
    """
    client, school_code = _get_client(school)

    try:
        with client:
            grades = client.grades.recent(limit=top)

            if not grades:
                console.print("[yellow]Geen cijfers gevonden.[/yellow]")
                return

            table = Table(
                title=f"Recente Cijfers ({len(grades)})",
                show_header=True,
                header_style="bold",
            )
            table.add_column("Datum", style="cyan", width=12)
            table.add_column("Vak", width=20)
            table.add_column("Cijfer", justify="center", width=8)
            table.add_column("Weging", justify="center", width=8)
            table.add_column("Omschrijving", no_wrap=False)

            for grade in grades:
                date_str = grade.datum_ingevoerd.strftime("%d-%m-%Y")
                weging = f"x{grade.weging:.0f}" if grade.weging else "-"
                omschrijving = grade.omschrijving[:40] + "..." if len(grade.omschrijving) > 40 else grade.omschrijving

                table.add_row(
                    date_str,
                    grade.vak_naam,
                    _format_grade(grade),
                    weging,
                    omschrijving,
                )

            console.print(table)

    except TokenExpiredError:
        format_no_auth_error(console, school_code)
        raise typer.Exit(1)
    except MagisterAPIError as e:
        format_api_error(console, e)
        raise typer.Exit(1)


@app.command("overview")
def grades_overview(
    school: Annotated[
        str | None,
        typer.Option("--school", "-s", help="School code"),
    ] = None,
):
    """
    Toon cijferoverzicht met gemiddeldes per vak.

    Voorbeelden:
        magister grades overview
    """
    client, school_code = _get_client(school)

    try:
        with client:
            # Get current enrollment info
            enrollment = client.grades.current_enrollment()
            if enrollment:
                console.print(Panel(
                    f"[bold]{enrollment.display_name}[/bold]",
                    border_style="blue",
                ))

            # Get averages by subject
            averages = client.grades.averages_by_subject()

            if not averages:
                console.print("[yellow]Geen cijfers gevonden.[/yellow]")
                return

            table = Table(
                title="Gemiddeldes per Vak",
                show_header=True,
                header_style="bold",
            )
            table.add_column("Vak", width=30)
            table.add_column("Gemiddelde", justify="center", width=12)
            table.add_column("Status", justify="center", width=10)

            # Sort by subject name
            for subject in sorted(averages.keys()):
                avg = averages[subject]
                avg_str = _format_average(avg)

                if avg is not None:
                    status = "[green]Voldoende[/green]" if avg >= 5.5 else "[red]Onvoldoende[/red]"
                else:
                    status = "[dim]-[/dim]"

                table.add_row(subject, avg_str, status)

            console.print(table)

            # Summary
            passing = sum(1 for avg in averages.values() if avg is not None and avg >= 5.5)
            failing = sum(1 for avg in averages.values() if avg is not None and avg < 5.5)
            console.print()
            console.print(f"[green]{passing} voldoende[/green] | [red]{failing} onvoldoende[/red]")

    except TokenExpiredError:
        format_no_auth_error(console, school_code)
        raise typer.Exit(1)
    except MagisterAPIError as e:
        format_api_error(console, e)
        raise typer.Exit(1)


@app.command("subject")
def grades_by_subject(
    subject: Annotated[
        str,
        typer.Argument(help="Vak naam (gedeeltelijke match)"),
    ],
    school: Annotated[
        str | None,
        typer.Option("--school", "-s", help="School code"),
    ] = None,
):
    """
    Toon alle cijfers voor een specifiek vak.

    Voorbeelden:
        magister grades subject wiskunde
        magister grades subject "ne"
    """
    client, school_code = _get_client(school)

    try:
        with client:
            grades = client.grades.by_subject(subject=subject)

            if not grades:
                console.print(f"[yellow]Geen cijfers gevonden voor '{subject}'.[/yellow]")
                return

            # Group by subject (in case multiple subjects match)
            subjects = set(g.vak_naam for g in grades)

            for subj in sorted(subjects):
                subj_grades = [g for g in grades if g.vak_naam == subj]
                subj_grades.sort(key=lambda g: g.datum_ingevoerd, reverse=True)

                # Calculate average
                numeric_grades = [g.cijfer_numeriek for g in subj_grades if g.cijfer_numeriek is not None]
                avg = sum(numeric_grades) / len(numeric_grades) if numeric_grades else None

                console.print(Panel(
                    f"[bold]{subj}[/bold] - Gemiddelde: {_format_average(avg)}",
                    border_style="blue",
                ))

                table = Table(show_header=True, header_style="bold")
                table.add_column("Datum", style="cyan", width=12)
                table.add_column("Cijfer", justify="center", width=8)
                table.add_column("Weging", justify="center", width=8)
                table.add_column("Omschrijving", no_wrap=False)

                for grade in subj_grades:
                    date_str = grade.datum_ingevoerd.strftime("%d-%m-%Y")
                    weging = f"x{grade.weging:.0f}" if grade.weging else "-"

                    table.add_row(
                        date_str,
                        _format_grade(grade),
                        weging,
                        grade.omschrijving,
                    )

                console.print(table)
                console.print()

    except TokenExpiredError:
        format_no_auth_error(console, school_code)
        raise typer.Exit(1)
    except MagisterAPIError as e:
        format_api_error(console, e)
        raise typer.Exit(1)


@app.command("subjects")
def list_subjects(
    school: Annotated[
        str | None,
        typer.Option("--school", "-s", help="School code"),
    ] = None,
):
    """
    Toon alle vakken.

    Voorbeelden:
        magister grades subjects
    """
    client, school_code = _get_client(school)

    try:
        with client:
            subjects = client.grades.subjects()

            if not subjects:
                console.print("[yellow]Geen vakken gevonden.[/yellow]")
                return

            table = Table(
                title=f"Vakken ({len(subjects)})",
                show_header=True,
                header_style="bold",
            )
            table.add_column("Vak", width=30)
            table.add_column("Afkorting", width=10)

            for subject in sorted(subjects, key=lambda s: s.naam):
                table.add_row(subject.naam, subject.afkorting or "-")

            console.print(table)

    except TokenExpiredError:
        format_no_auth_error(console, school_code)
        raise typer.Exit(1)
    except MagisterAPIError as e:
        format_api_error(console, e)
        raise typer.Exit(1)


@app.command("enrollments")
def list_enrollments(
    school: Annotated[
        str | None,
        typer.Option("--school", "-s", help="School code"),
    ] = None,
):
    """
    Toon alle inschrijvingen (schooljaren).

    Voorbeelden:
        magister grades enrollments
    """
    client, school_code = _get_client(school)

    try:
        with client:
            enrollments = client.grades.enrollments()

            if not enrollments:
                console.print("[yellow]Geen inschrijvingen gevonden.[/yellow]")
                return

            table = Table(
                title="Inschrijvingen",
                show_header=True,
                header_style="bold",
            )
            table.add_column("ID", style="dim", width=8)
            table.add_column("Studie", width=25)
            table.add_column("Leerjaar", justify="center", width=10)
            table.add_column("Groep", width=10)
            table.add_column("Status", width=10)

            for enrollment in enrollments:
                status = "[green]Actief[/green]" if enrollment.is_actief else "[dim]Afgelopen[/dim]"
                table.add_row(
                    str(enrollment.id),
                    enrollment.studie_naam,
                    str(enrollment.leerjaar),
                    enrollment.groep or "-",
                    status,
                )

            console.print(table)

    except TokenExpiredError:
        format_no_auth_error(console, school_code)
        raise typer.Exit(1)
    except MagisterAPIError as e:
        format_api_error(console, e)
        raise typer.Exit(1)
