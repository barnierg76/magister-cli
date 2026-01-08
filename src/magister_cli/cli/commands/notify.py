"""Notification CLI commands for Magister CLI."""

from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from magister_cli.cli.progress import api_spinner, print_error, print_success
from magister_cli.cli.utils import handle_api_errors
from magister_cli.config import get_settings
from magister_cli.services.notifications import NotificationConfig, NotificationService

console = Console()
app = typer.Typer(help="Notificaties beheren")


def _get_config_from_settings() -> NotificationConfig:
    """Load notification config from settings."""
    # Default config - could be extended to read from YAML config
    return NotificationConfig(
        grades_enabled=True,
        schedule_enabled=True,
        homework_enabled=True,
        homework_reminder_hours=24,
        quiet_hours_start=22,
        quiet_hours_end=7,
    )


@app.command("test")
def test_notification(
    school: Annotated[
        str | None,
        typer.Option("--school", help="School code"),
    ] = None,
):
    """
    Stuur een test notificatie.

    Gebruik dit om te controleren of desktop notificaties werken.

    Voorbeeld:
        magister notify test
    """
    settings = get_settings()
    school_code = school or settings.school

    if not school_code:
        print_error("Geen school opgegeven. Gebruik --school of stel een default in.")
        raise typer.Exit(1)

    config = _get_config_from_settings()
    service = NotificationService(school_code, config)

    console.print("Test notificatie versturen...")

    success = service.send_test_notification_sync()

    if success:
        print_success("Test notificatie verstuurd!")
        console.print("[dim]Je zou nu een notificatie moeten zien.[/dim]")
    else:
        print_error("Kon geen notificatie versturen.")
        console.print("[dim]Dit kan komen door quiet hours of systeeminstellingen.[/dim]")


@app.command("check")
@handle_api_errors
def check_notifications(
    school: Annotated[
        str | None,
        typer.Option("--school", help="School code"),
    ] = None,
    quiet: Annotated[
        bool,
        typer.Option("--quiet", "-q", help="Alleen wijzigingen tonen, geen notificaties"),
    ] = False,
):
    """
    Controleer op nieuwe cijfers, roosterwijzigingen en huiswerk.

    Dit commando controleert Magister op wijzigingen en stuurt notificaties.
    Bij eerste gebruik wordt de huidige status opgeslagen als baseline.

    Voorbeelden:
        magister notify check
        magister notify check --quiet
    """
    settings = get_settings()
    school_code = school or settings.school

    if not school_code:
        print_error("Geen school opgegeven. Gebruik --school of stel een default in.")
        raise typer.Exit(1)

    config = _get_config_from_settings()
    service = NotificationService(school_code, config)

    # Check if first run
    is_first_run = not service.state_tracker.is_initialized()

    with api_spinner("Controleren op wijzigingen..."):
        changes = service.check_and_notify_sync()

    if is_first_run:
        console.print(
            Panel(
                "[green]Eerste controle voltooid![/green]\n\n"
                "De huidige status is opgeslagen als baseline.\n"
                "Toekomstige controles zullen wijzigingen detecteren.",
                title="Initialisatie",
            )
        )
        return

    if not changes:
        console.print("[green]✓[/green] Geen nieuwe wijzigingen gevonden.")
        return

    # Show detected changes
    console.print(f"\n[bold]{len(changes)} wijziging(en) gevonden:[/bold]\n")

    for change in changes:
        if change.change_type == "new_grade":
            emoji = "📊"
            color = "cyan"
            value = change.details.get("value", "?")
            console.print(f"  {emoji} [bold {color}]{change.subject}[/bold {color}]: {value}")
            if change.details.get("description"):
                console.print(f"      [dim]{change.details['description']}[/dim]")

        elif change.change_type == "schedule_change":
            emoji = "📅" if not change.details.get("cancelled") else "❌"
            color = "yellow" if not change.details.get("cancelled") else "red"
            console.print(
                f"  {emoji} [bold {color}]{change.subject}[/bold {color}]: {change.description}"
            )

        elif change.change_type == "homework_due":
            emoji = "📚"
            color = "magenta"
            console.print(
                f"  {emoji} [bold {color}]{change.subject}[/bold {color}]: {change.description}"
            )
            if change.details.get("homework_description"):
                console.print(f"      [dim]{change.details['homework_description']}[/dim]")

    if not quiet:
        console.print("\n[dim]Notificaties zijn verstuurd.[/dim]")


@app.command("status")
def notification_status(
    school: Annotated[
        str | None,
        typer.Option("--school", help="School code"),
    ] = None,
):
    """
    Toon notificatie status en configuratie.

    Voorbeeld:
        magister notify status
    """
    settings = get_settings()
    school_code = school or settings.school

    if not school_code:
        print_error("Geen school opgegeven. Gebruik --school of stel een default in.")
        raise typer.Exit(1)

    config = _get_config_from_settings()
    service = NotificationService(school_code, config)
    status = service.get_status()

    # Status table
    table = Table(title="Notificatie Status", show_header=False, box=None)
    table.add_column("Key", style="dim")
    table.add_column("Value")

    table.add_row("School", status["school"])
    table.add_row(
        "Geïnitialiseerd",
        "[green]Ja[/green]" if status["initialized"] else "[yellow]Nee[/yellow]",
    )
    table.add_row("Laatste controle", status["last_check"] or "[dim]Nooit[/dim]")

    console.print(table)
    console.print()

    # Config table
    config_table = Table(title="Configuratie", show_header=False, box=None)
    config_table.add_column("Setting", style="dim")
    config_table.add_column("Status")

    cfg = status["config"]
    config_table.add_row(
        "Cijfers",
        "[green]Aan[/green]" if cfg["grades"] else "[red]Uit[/red]",
    )
    config_table.add_row(
        "Rooster",
        "[green]Aan[/green]" if cfg["schedule"] else "[red]Uit[/red]",
    )
    config_table.add_row(
        "Huiswerk",
        "[green]Aan[/green]" if cfg["homework"] else "[red]Uit[/red]",
    )
    config_table.add_row("Huiswerk reminder", f"{cfg['homework_reminder_hours']} uur")
    config_table.add_row("Stille uren", cfg["quiet_hours"])

    console.print(config_table)
    console.print()

    # Tracked items
    tracked = status["tracked"]
    console.print("[dim]Bijgehouden items:[/dim]")
    console.print(f"  Cijfers: {tracked['grades']}")
    console.print(f"  Rooster: {tracked['appointments']}")
    console.print(f"  Huiswerk notificaties: {tracked['homework_notifications']}")


@app.command("reset")
def reset_notifications(
    school: Annotated[
        str | None,
        typer.Option("--school", help="School code"),
    ] = None,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Bevestig reset zonder prompt"),
    ] = False,
):
    """
    Reset notificatie status.

    Dit wist alle bijgehouden staat. De volgende controle zal
    de huidige data als nieuwe baseline gebruiken.

    Voorbeeld:
        magister notify reset
        magister notify reset --force
    """
    settings = get_settings()
    school_code = school or settings.school

    if not school_code:
        print_error("Geen school opgegeven. Gebruik --school of stel een default in.")
        raise typer.Exit(1)

    if not force:
        confirm = typer.confirm("Weet je zeker dat je de notificatie status wilt resetten?")
        if not confirm:
            console.print("Geannuleerd.")
            raise typer.Exit(0)

    config = _get_config_from_settings()
    service = NotificationService(school_code, config)
    service.reset()

    print_success("Notificatie status gereset.")
    console.print("[dim]De volgende controle zal de huidige data als baseline gebruiken.[/dim]")


@app.command("setup")
def setup_notifications(
    school: Annotated[
        str | None,
        typer.Option("--school", help="School code"),
    ] = None,
):
    """
    Interactieve setup voor notificaties.

    Dit commando helpt je om notificaties in te stellen en te testen.

    Voorbeeld:
        magister notify setup
    """
    settings = get_settings()
    school_code = school or settings.school

    if not school_code:
        school_code = typer.prompt("Voer je school code in")

    console.print(
        Panel(
            "[bold]Magister Notificaties Setup[/bold]\n\n"
            "Dit helpt je om notificaties in te stellen voor:\n"
            "• Nieuwe cijfers\n"
            "• Roosterwijzigingen\n"
            "• Huiswerk deadlines",
            title="Setup",
        )
    )

    # Test notifications
    console.print("\n[bold]Stap 1:[/bold] Test notificaties")
    if typer.confirm("Wil je een test notificatie versturen?", default=True):
        config = _get_config_from_settings()
        service = NotificationService(school_code, config)
        success = service.send_test_notification_sync()

        if success:
            print_success("Test notificatie verstuurd!")
            if not typer.confirm("Heb je de notificatie gezien?", default=True):
                console.print(
                    "\n[yellow]Controleer je systeeminstellingen:[/yellow]\n"
                    "• macOS: Systeemvoorkeuren → Meldingen → Terminal/iTerm\n"
                    "• Windows: Instellingen → Systeem → Meldingen\n"
                    "• Linux: Controleer je notification daemon"
                )
        else:
            print_error("Kon geen notificatie versturen.")

    # Initialize baseline
    console.print("\n[bold]Stap 2:[/bold] Baseline initialiseren")
    console.print(
        "[dim]Dit haalt de huidige data op zodat alleen nieuwe wijzigingen worden gemeld.[/dim]"
    )

    if typer.confirm("Wil je de baseline nu initialiseren?", default=True):
        config = _get_config_from_settings()
        service = NotificationService(school_code, config)

        with api_spinner("Baseline initialiseren..."):
            service.check_and_notify_sync()

        print_success("Baseline geïnitialiseerd!")

    # Instructions for periodic checking
    console.print(
        Panel(
            "[bold]Setup voltooid![/bold]\n\n"
            "Om notificaties te ontvangen, voer periodiek dit commando uit:\n\n"
            "  [cyan]magister notify check[/cyan]\n\n"
            "Je kunt dit automatiseren met cron (Linux/macOS) of Task Scheduler (Windows):\n\n"
            "[dim]# Elke 30 minuten controleren (cron):\n"
            "*/30 * * * * magister notify check --quiet[/dim]",
            title="Klaar",
        )
    )
