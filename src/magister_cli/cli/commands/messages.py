"""Messages CLI commands."""

from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from magister_cli.api import MagisterAPIError, MagisterClient, TokenExpiredError
from magister_cli.api.models import Bericht, BerichtDetail
from magister_cli.auth import get_current_token
from magister_cli.cli.formatters import format_api_error, format_no_auth_error, strip_html
from magister_cli.config import get_settings

console = Console()
app = typer.Typer(help="Berichten commando's")


def _format_message_row(msg: Bericht) -> tuple[str, str, str, str]:
    """Format a message for table display."""
    date_str = msg.verzonden_op.strftime("%d-%m %H:%M")
    sender = msg.sender_name
    if len(sender) > 25:
        sender = sender[:22] + "..."

    subject = msg.onderwerp
    if len(subject) > 40:
        subject = subject[:37] + "..."

    # Status indicators
    status = ""
    if msg.is_unread:
        status = "[bold cyan]●[/bold cyan]"
    if msg.heeft_bijlagen:
        status += " 📎"
    if msg.heeft_prioriteit:
        status += " [red]![/red]"

    return (str(msg.id), date_str, sender, subject + f" {status}".strip())


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


@app.command("inbox")
@app.command("list")
def list_messages(
    top: Annotated[
        int,
        typer.Option("--top", "-n", help="Aantal berichten om te tonen"),
    ] = 25,
    unread: Annotated[
        bool,
        typer.Option("--unread", "-u", help="Alleen ongelezen berichten"),
    ] = False,
    school: Annotated[
        str | None,
        typer.Option("--school", "-s", help="School code"),
    ] = None,
):
    """
    Toon inbox berichten.

    Voorbeelden:
        magister messages inbox
        magister messages inbox --unread
        magister messages inbox --top 50
    """
    client, school_code = _get_client(school)

    try:
        with client:
            messages = client.messages.inbox(top=top)

            if unread:
                messages = [m for m in messages if m.is_unread]

            if not messages:
                if unread:
                    console.print("[green]Geen ongelezen berichten.[/green]")
                else:
                    console.print("[yellow]Geen berichten in inbox.[/yellow]")
                return

            unread_count = sum(1 for m in messages if m.is_unread)

            table = Table(
                title=f"Inbox ({len(messages)} berichten, {unread_count} ongelezen)",
                show_header=True,
                header_style="bold",
            )
            table.add_column("ID", style="dim", width=8)
            table.add_column("Datum", style="cyan", width=12)
            table.add_column("Afzender", width=25)
            table.add_column("Onderwerp", no_wrap=False)

            for msg in messages:
                row = _format_message_row(msg)
                style = "bold" if msg.is_unread else None
                table.add_row(*row, style=style)

            console.print(table)

    except TokenExpiredError:
        format_no_auth_error(console, school_code)
        raise typer.Exit(1)
    except MagisterAPIError as e:
        format_api_error(console, e)
        raise typer.Exit(1)


@app.command("sent")
def sent_messages(
    top: Annotated[
        int,
        typer.Option("--top", "-n", help="Aantal berichten om te tonen"),
    ] = 25,
    school: Annotated[
        str | None,
        typer.Option("--school", "-s", help="School code"),
    ] = None,
):
    """
    Toon verzonden berichten.

    Voorbeelden:
        magister messages sent
        magister messages sent --top 10
    """
    client, school_code = _get_client(school)

    try:
        with client:
            messages = client.messages.sent(top=top)

            if not messages:
                console.print("[yellow]Geen verzonden berichten.[/yellow]")
                return

            table = Table(
                title=f"Verzonden ({len(messages)} berichten)",
                show_header=True,
                header_style="bold",
            )
            table.add_column("ID", style="dim", width=8)
            table.add_column("Datum", style="cyan", width=12)
            table.add_column("Ontvanger", width=25)
            table.add_column("Onderwerp", no_wrap=False)

            for msg in messages:
                row = _format_message_row(msg)
                table.add_row(*row)

            console.print(table)

    except TokenExpiredError:
        format_no_auth_error(console, school_code)
        raise typer.Exit(1)
    except MagisterAPIError as e:
        format_api_error(console, e)
        raise typer.Exit(1)


@app.command("read")
def read_message(
    message_id: Annotated[
        int,
        typer.Argument(help="Bericht ID"),
    ],
    school: Annotated[
        str | None,
        typer.Option("--school", "-s", help="School code"),
    ] = None,
    mark_read: Annotated[
        bool,
        typer.Option("--mark-read/--no-mark-read", help="Markeer als gelezen"),
    ] = True,
):
    """
    Lees een specifiek bericht.

    Voorbeelden:
        magister messages read 12345
        magister messages read 12345 --no-mark-read
    """
    client, school_code = _get_client(school)

    try:
        with client:
            msg = client.messages.get(message_id)

            # Optionally mark as read
            if mark_read and msg.is_unread:
                client.messages.mark_as_read(message_id)

            _display_message(msg)

    except TokenExpiredError:
        format_no_auth_error(console, school_code)
        raise typer.Exit(1)
    except MagisterAPIError as e:
        format_api_error(console, e)
        raise typer.Exit(1)


def _display_message(msg: BerichtDetail) -> None:
    """Display a full message."""
    # Header info
    date_str = msg.verzonden_op.strftime("%d-%m-%Y %H:%M")
    console.print(Panel(
        f"[bold]{msg.onderwerp}[/bold]",
        subtitle=f"ID: {msg.id}",
        border_style="blue",
    ))

    console.print(f"[cyan]Van:[/cyan] {msg.sender_name}")
    console.print(f"[cyan]Datum:[/cyan] {date_str}")

    if msg.ontvangers:
        recipients = ", ".join(msg.recipient_names[:5])
        if len(msg.ontvangers) > 5:
            recipients += f" (+{len(msg.ontvangers) - 5} anderen)"
        console.print(f"[cyan]Aan:[/cyan] {recipients}")

    console.print()

    # Message body
    body = strip_html(msg.inhoud)
    console.print(body)

    # Attachments
    if msg.bijlagen:
        console.print()
        console.print(f"[yellow]📎 {len(msg.bijlagen)} bijlage(n):[/yellow]")
        for bijlage in msg.bijlagen:
            console.print(f"  • {bijlage.naam} [dim]({bijlage.grootte_leesbaar})[/dim]")


@app.command("mark-read")
def mark_as_read(
    message_id: Annotated[
        int,
        typer.Argument(help="Bericht ID"),
    ],
    school: Annotated[
        str | None,
        typer.Option("--school", "-s", help="School code"),
    ] = None,
):
    """
    Markeer bericht als gelezen.

    Voorbeelden:
        magister messages mark-read 12345
    """
    client, school_code = _get_client(school)

    try:
        with client:
            client.messages.mark_as_read(message_id)
            console.print(f"[green]Bericht {message_id} gemarkeerd als gelezen.[/green]")

    except TokenExpiredError:
        format_no_auth_error(console, school_code)
        raise typer.Exit(1)
    except MagisterAPIError as e:
        format_api_error(console, e)
        raise typer.Exit(1)


@app.command("delete")
def delete_message(
    message_id: Annotated[
        int,
        typer.Argument(help="Bericht ID"),
    ],
    school: Annotated[
        str | None,
        typer.Option("--school", "-s", help="School code"),
    ] = None,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Niet om bevestiging vragen"),
    ] = False,
):
    """
    Verwijder een bericht.

    Voorbeelden:
        magister messages delete 12345
        magister messages delete 12345 --force
    """
    client, school_code = _get_client(school)

    if not force:
        confirm = typer.confirm(f"Weet je zeker dat je bericht {message_id} wilt verwijderen?")
        if not confirm:
            console.print("[yellow]Geannuleerd.[/yellow]")
            raise typer.Exit(0)

    try:
        with client:
            client.messages.delete(message_id)
            console.print(f"[green]Bericht {message_id} verwijderd.[/green]")

    except TokenExpiredError:
        format_no_auth_error(console, school_code)
        raise typer.Exit(1)
    except MagisterAPIError as e:
        format_api_error(console, e)
        raise typer.Exit(1)


@app.command("count")
def unread_count(
    school: Annotated[
        str | None,
        typer.Option("--school", "-s", help="School code"),
    ] = None,
):
    """
    Toon aantal ongelezen berichten.

    Voorbeelden:
        magister messages count
    """
    client, school_code = _get_client(school)

    try:
        with client:
            count = client.messages.unread_count()

            if count == 0:
                console.print("[green]Geen ongelezen berichten.[/green]")
            elif count == 1:
                console.print("[cyan]1 ongelezen bericht.[/cyan]")
            else:
                console.print(f"[cyan]{count} ongelezen berichten.[/cyan]")

    except TokenExpiredError:
        format_no_auth_error(console, school_code)
        raise typer.Exit(1)
    except MagisterAPIError as e:
        format_api_error(console, e)
        raise typer.Exit(1)
