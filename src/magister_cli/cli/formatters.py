"""Rich output formatters for CLI display."""

import html
import re

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from magister_cli.services.homework import HomeworkDay, HomeworkItem


def strip_html(text: str) -> str:
    """Strip HTML tags and decode entities from text."""
    if not text:
        return ""

    # Replace <br>, <br/>, </p>, </li> with newlines
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</li>", "\n", text, flags=re.IGNORECASE)

    # Replace <li> with bullet point
    text = re.sub(r"<li[^>]*>", "• ", text, flags=re.IGNORECASE)

    # Remove all other HTML tags
    text = re.sub(r"<[^>]+>", "", text)

    # Decode HTML entities (&nbsp; &amp; etc.)
    text = html.unescape(text)

    # Clean up whitespace: collapse multiple spaces, normalize newlines
    text = re.sub(r"[ \t]+", " ", text)  # Multiple spaces to single
    text = re.sub(r"\n\s*\n", "\n\n", text)  # Multiple newlines to double
    text = re.sub(r"\n{3,}", "\n\n", text)  # Max 2 newlines

    return text.strip()


def format_homework_item(item: HomeworkItem, console: Console) -> None:
    """Format and print a single homework item."""
    icon = "[red]TOETS[/red]" if item.is_test else "[cyan]Huiswerk[/cyan]"

    subject_text = f"[bold]{item.subject}[/bold]"
    if item.lesson_number:
        subject_text += f" [dim](les {item.lesson_number})[/dim]"

    console.print(f"  {icon} {subject_text}")

    # Clean HTML and format description
    clean_description = strip_html(item.description)
    for line in clean_description.split("\n"):
        line = line.strip()
        if line:
            console.print(f"     {line}")

    if item.teacher or item.location:
        details = []
        if item.teacher:
            details.append(f"Docent: {item.teacher}")
        if item.location:
            details.append(f"Lokaal: {item.location}")
        console.print(f"     [dim]{' | '.join(details)}[/dim]")

    # Show attachments if present
    if item.attachments:
        console.print(f"     [yellow]📎 {len(item.attachments)} bijlage(n):[/yellow]")
        for att in item.attachments:
            console.print(f"        • {att.name} [dim]({att.size})[/dim]")

    console.print()


def format_homework_day(day: HomeworkDay, console: Console) -> None:
    """Format and print homework for a single day."""
    label = day.day_label
    date_str = day.date.strftime("%d-%m-%Y")

    if day.is_today:
        header = f"[bold green]{label}[/bold green] [dim]({date_str})[/dim]"
    elif day.is_tomorrow:
        header = f"[bold yellow]{label}[/bold yellow] [dim]({date_str})[/dim]"
    else:
        header = f"[bold]{label}[/bold] [dim]({date_str})[/dim]"

    console.print(header)
    console.print()

    for item in day.items:
        format_homework_item(item, console)


def format_homework_list(days: list[HomeworkDay], console: Console) -> None:
    """Format and print the full homework list."""
    if not days:
        console.print("[yellow]Geen huiswerk gevonden voor de komende dagen.[/yellow]")
        return

    total_items = sum(len(d.items) for d in days)
    total_tests = sum(1 for d in days for i in d.items if i.is_test)

    header = "Huiswerk overzicht"
    subtitle = f"{total_items} opdracht{'en' if total_items != 1 else ''}"
    if total_tests:
        subtitle += f" | [red]{total_tests} toets{'en' if total_tests != 1 else ''}[/red]"

    console.print(Panel(subtitle, title=header, border_style="blue"))
    console.print()

    for day in days:
        format_homework_day(day, console)


def format_homework_table(days: list[HomeworkDay], console: Console) -> None:
    """Format homework as a table."""
    if not days:
        console.print("[yellow]Geen huiswerk gevonden.[/yellow]")
        return

    table = Table(title="Huiswerk", show_header=True, header_style="bold")
    table.add_column("Datum", style="cyan")
    table.add_column("Vak", style="green")
    table.add_column("Type")
    table.add_column("Opdracht", no_wrap=False)

    for day in days:
        for item in day.items:
            date_str = day.day_label
            type_str = "[red]TOETS[/red]" if item.is_test else "Huiswerk"
            description = strip_html(item.description)
            description = description.replace("\n", " ")
            if len(description) > 80:
                description = description[:80] + "..."

            table.add_row(date_str, item.subject, type_str, description)

    console.print(table)


def format_no_auth_error(console: Console, school: str | None = None) -> None:
    """Format authentication error message."""
    console.print("[red]Niet ingelogd.[/red]")
    if school:
        console.print(f"\nLogin met: [cyan]magister login --school {school}[/cyan]")
    else:
        console.print("\nLogin met: [cyan]magister login --school <jouw_school>[/cyan]")


def format_api_error(console: Console, error: Exception) -> None:
    """Format API error message."""
    console.print(f"[red]API fout:[/red] {error}")
    console.print("\n[dim]Als dit blijft gebeuren, probeer opnieuw in te loggen:[/dim]")
    console.print("[cyan]magister logout && magister login[/cyan]")
