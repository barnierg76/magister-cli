"""Grades CLI commands."""

import logging
from datetime import datetime, timedelta, timezone
from statistics import mean, median, stdev
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from magister_cli.api import MagisterAPIError, MagisterClient, NotAuthenticatedError, TokenExpiredError
from magister_cli.api.models import Cijfer
from magister_cli.auth import get_current_token
from magister_cli.cli.errors import format_error
from magister_cli.cli.utils import handle_api_errors
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
        format_error(NotAuthenticatedError(school_code), console, school=school_code)
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
    debug: Annotated[
        bool,
        typer.Option("--debug", "-d", help="Toon debug info"),
    ] = False,
):
    """
    Toon recente cijfers.

    Voorbeelden:
        magister grades recent
        magister grades recent --top 25
        magister grades recent --debug
    """
    if debug:
        logging.basicConfig(level=logging.DEBUG)
        console.print("[dim]Debug mode enabled[/dim]")

    client, school_code = _get_client(school)

    try:
        with client:
            if debug:
                console.print(f"[dim]Person ID: {client._person_id}[/dim]")
                console.print(f"[dim]Fetching {top} recent grades...[/dim]")

            grades = client.grades.recent(limit=top)

            if debug:
                console.print(f"[dim]Retrieved {len(grades)} grades[/dim]")

            if not grades:
                console.print("[yellow]Geen cijfers gevonden.[/yellow]")
                if not debug:
                    console.print("[dim]Tip: Gebruik --debug voor meer informatie[/dim]")
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

    except TokenExpiredError as e:
        format_error(e, console, school=school_code)
        raise typer.Exit(1)
    except MagisterAPIError as e:
        format_error(e, console, school=school_code)
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

    except TokenExpiredError as e:
        format_error(e, console, school=school_code)
        raise typer.Exit(1)
    except MagisterAPIError as e:
        format_error(e, console, school=school_code)
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

    except TokenExpiredError as e:
        format_error(e, console, school=school_code)
        raise typer.Exit(1)
    except MagisterAPIError as e:
        format_error(e, console, school=school_code)
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
            table.add_column("Code", width=10)
            table.add_column("Docent", width=30)

            for subject in sorted(subjects, key=lambda s: s.vak_naam):
                table.add_row(
                    subject.vak_naam,
                    subject.vak_code or "-",
                    subject.hoofd_docent or "-",
                )

            console.print(table)

    except TokenExpiredError as e:
        format_error(e, console, school=school_code)
        raise typer.Exit(1)
    except MagisterAPIError as e:
        format_error(e, console, school=school_code)
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

    except TokenExpiredError as e:
        format_error(e, console, school=school_code)
        raise typer.Exit(1)
    except MagisterAPIError as e:
        format_error(e, console, school=school_code)
        raise typer.Exit(1)


@app.command("raw")
def raw_grades(
    school: Annotated[
        str | None,
        typer.Option("--school", "-s", help="School code"),
    ] = None,
    limit: Annotated[
        int,
        typer.Option("--limit", "-n", help="Aantal cijfers"),
    ] = 10,
):
    """
    Debug: Toon ruwe API response voor cijfers.

    Gebruik dit om te zien wat de API daadwerkelijk teruggeeft.
    """
    import json

    client, school_code = _get_client(school)

    try:
        with client:
            # Get student ID (triggers account fetch if needed)
            student_id = client._ensure_student_id()

            console.print(f"[bold]Student ID:[/bold] {student_id}")
            console.print(f"[bold]School:[/bold] {school_code}")
            console.print(f"[bold]Is Parent:[/bold] {client._is_parent}")
            console.print(f"[bold]Person Name:[/bold] {client._person_name}")
            console.print()

            # Make raw API call
            endpoint = f"/personen/{student_id}/cijfers/laatste"
            console.print(f"[bold]Endpoint:[/bold] {endpoint}?top={limit}")
            console.print()

            response = client._client.get(endpoint, params={"top": limit})
            console.print(f"[bold]Status:[/bold] {response.status_code}")
            console.print()

            if response.status_code == 200:
                data = response.json()
                console.print("[bold]Response:[/bold]")
                console.print(json.dumps(data, indent=2, default=str)[:2000])

                if isinstance(data, dict):
                    console.print(f"\n[bold]Keys:[/bold] {list(data.keys())}")
                    if "Items" in data:
                        console.print(f"[bold]Items count:[/bold] {len(data['Items'])}")
                        if data["Items"]:
                            console.print("\n[bold]First item keys:[/bold]")
                            console.print(list(data["Items"][0].keys()))
            else:
                console.print(f"[red]Error response:[/red] {response.text[:500]}")

    except TokenExpiredError:
        from magister_cli.api.exceptions import TokenExpiredError as TE
        format_error(TE("Token expired"), console, school=school_code)
        raise typer.Exit(1)
    except MagisterAPIError as e:
        format_error(e, console, school=school_code)
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


def _calculate_trend(grades: list[Cijfer], period_days: int = 30) -> str:
    """Calculate grade trend indicator based on recent vs older grades.

    Returns: ↑ (improving), ↓ (declining), → (stable)
    """
    if len(grades) < 4:
        return "→"  # Not enough data

    # Split grades into recent and older
    cutoff = datetime.now(timezone.utc) - timedelta(days=period_days // 2)

    recent = [g.cijfer_numeriek for g in grades if g.datum_ingevoerd >= cutoff and g.cijfer_numeriek]
    older = [g.cijfer_numeriek for g in grades if g.datum_ingevoerd < cutoff and g.cijfer_numeriek]

    if not recent or not older:
        return "→"

    recent_avg = mean(recent)
    older_avg = mean(older)

    diff = recent_avg - older_avg

    if diff > 0.3:
        return "[green]↑[/green]"
    elif diff < -0.3:
        return "[red]↓[/red]"
    else:
        return "[dim]→[/dim]"


@app.command("trends")
@handle_api_errors
def grade_trends(
    period: Annotated[
        int,
        typer.Option("--period", "-p", help="Periode in dagen om te analyseren"),
    ] = 90,
    school: Annotated[
        str | None,
        typer.Option("--school", "-s", help="School code"),
    ] = None,
):
    """
    Toon cijfer trends per vak.

    Analyseert cijfers over de opgegeven periode en toont:
    - Huidige gemiddelde
    - Trend indicator (↑ verbetering, ↓ achteruitgang, → stabiel)
    - Aantal cijfers

    Voorbeelden:
        magister grades trends
        magister grades trends --period 30
        magister grades trends --period 180
    """
    client, school_code = _get_client(school)

    try:
        with client:
            # Get all grades
            grades = client.grades.recent(limit=200)

            if not grades:
                console.print("[yellow]Geen cijfers gevonden.[/yellow]")
                return

            # Filter to period
            cutoff = datetime.now(timezone.utc) - timedelta(days=period)
            period_grades = [g for g in grades if g.datum_ingevoerd >= cutoff]

            if not period_grades:
                console.print(f"[yellow]Geen cijfers in de afgelopen {period} dagen.[/yellow]")
                return

            # Group by subject
            by_subject: dict[str, list[Cijfer]] = {}
            for g in period_grades:
                if g.vak_naam not in by_subject:
                    by_subject[g.vak_naam] = []
                by_subject[g.vak_naam].append(g)

            console.print(Panel(
                f"Cijfer trends - afgelopen {period} dagen",
                border_style="blue",
            ))

            table = Table(show_header=True, header_style="bold")
            table.add_column("Vak", width=25)
            table.add_column("Gemiddelde", justify="center", width=12)
            table.add_column("Trend", justify="center", width=8)
            table.add_column("Cijfers", justify="center", width=10)
            table.add_column("Min-Max", justify="center", width=12)

            for subject in sorted(by_subject.keys()):
                subject_grades = by_subject[subject]
                numeric = [g.cijfer_numeriek for g in subject_grades if g.cijfer_numeriek is not None]

                if not numeric:
                    continue

                avg = mean(numeric)
                trend = _calculate_trend(subject_grades, period)
                count = len(numeric)
                min_max = f"{min(numeric):.1f} - {max(numeric):.1f}"

                table.add_row(
                    subject,
                    _format_average(avg),
                    trend,
                    str(count),
                    min_max,
                )

            console.print(table)

            # Overall summary
            all_numeric = [g.cijfer_numeriek for g in period_grades if g.cijfer_numeriek]
            if all_numeric:
                console.print()
                overall_avg = mean(all_numeric)
                console.print(f"[bold]Totaal gemiddelde:[/bold] {_format_average(overall_avg)}")
                console.print(f"[dim]{len(period_grades)} cijfers van {len(by_subject)} vakken[/dim]")

    except TokenExpiredError:
        from magister_cli.api.exceptions import TokenExpiredError as TE
        format_error(TE("Token expired"), console, school=school_code)
        raise typer.Exit(1)
    except MagisterAPIError as e:
        format_error(e, console, school=school_code)
        raise typer.Exit(1)


@app.command("stats")
@handle_api_errors
def grade_stats(
    school: Annotated[
        str | None,
        typer.Option("--school", "-s", help="School code"),
    ] = None,
):
    """
    Toon gedetailleerde cijferstatistieken.

    Toont voor elk vak:
    - Gemiddelde, mediaan, standaarddeviatie
    - Hoogste en laagste cijfer
    - Totaal aantal cijfers

    Voorbeelden:
        magister grades stats
    """
    client, school_code = _get_client(school)

    try:
        with client:
            grades = client.grades.recent(limit=300)

            if not grades:
                console.print("[yellow]Geen cijfers gevonden.[/yellow]")
                return

            # Group by subject
            by_subject: dict[str, list[float]] = {}
            for g in grades:
                if g.cijfer_numeriek is not None:
                    if g.vak_naam not in by_subject:
                        by_subject[g.vak_naam] = []
                    by_subject[g.vak_naam].append(g.cijfer_numeriek)

            console.print(Panel(
                "Cijferstatistieken",
                border_style="blue",
            ))

            table = Table(show_header=True, header_style="bold")
            table.add_column("Vak", width=20)
            table.add_column("Gem", justify="center", width=6)
            table.add_column("Med", justify="center", width=6)
            table.add_column("SD", justify="center", width=6)
            table.add_column("Min", justify="center", width=6)
            table.add_column("Max", justify="center", width=6)
            table.add_column("N", justify="center", width=4)

            all_grades = []
            for subject in sorted(by_subject.keys()):
                grades_list = by_subject[subject]
                all_grades.extend(grades_list)

                avg_val = mean(grades_list)
                med_val = median(grades_list)
                sd_val = stdev(grades_list) if len(grades_list) > 1 else 0
                min_val = min(grades_list)
                max_val = max(grades_list)

                table.add_row(
                    subject[:20],
                    _format_average(avg_val),
                    f"{med_val:.1f}",
                    f"{sd_val:.1f}",
                    f"{min_val:.1f}",
                    f"{max_val:.1f}",
                    str(len(grades_list)),
                )

            console.print(table)

            # Overall statistics
            if all_grades:
                console.print()
                console.print("[bold]Totaal overzicht:[/bold]")
                console.print(f"  Gemiddelde: {_format_average(mean(all_grades))}")
                console.print(f"  Mediaan: {median(all_grades):.1f}")
                console.print(f"  Spreiding: {stdev(all_grades):.1f}" if len(all_grades) > 1 else "")
                console.print(f"  Hoogste: [green]{max(all_grades):.1f}[/green]")
                console.print(f"  Laagste: [red]{min(all_grades):.1f}[/red]")
                console.print(f"  Totaal: {len(all_grades)} cijfers")

    except TokenExpiredError:
        from magister_cli.api.exceptions import TokenExpiredError as TE
        format_error(TE("Token expired"), console, school=school_code)
        raise typer.Exit(1)
    except MagisterAPIError as e:
        format_error(e, console, school=school_code)
        raise typer.Exit(1)
