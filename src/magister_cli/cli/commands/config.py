"""Config CLI commands for managing settings."""

from typing import Annotated

import typer
import yaml
from rich.console import Console
from rich.table import Table

from magister_cli.config import CONFIG_PATH, Settings, get_settings

console = Console()
app = typer.Typer(help="Configuratie beheren")

# Settings that can be configured via the config command
CONFIGURABLE_KEYS = {
    "school": {
        "description": "Default school code",
        "type": "str",
        "example": "vsvonh",
    },
    "username": {
        "description": "Username hint for login",
        "type": "str",
        "example": "jan.jansen",
    },
    "timeout": {
        "description": "HTTP timeout in seconds (5-120)",
        "type": "int",
        "example": "30",
    },
    "headless": {
        "description": "Run browser in headless mode",
        "type": "bool",
        "example": "true",
    },
    "oauth_callback_port": {
        "description": "Port for OAuth callback (1024-65535)",
        "type": "int",
        "example": "8080",
    },
    "oauth_timeout": {
        "description": "OAuth flow timeout in seconds (30-600)",
        "type": "int",
        "example": "300",
    },
}


def load_config() -> dict:
    """Load config from YAML file."""
    if not CONFIG_PATH.exists():
        return {}
    try:
        with open(CONFIG_PATH) as f:
            return yaml.safe_load(f) or {}
    except yaml.YAMLError:
        return {}


def save_config(config: dict) -> None:
    """Save config to YAML file."""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)


def parse_value(key: str, value: str) -> str | int | bool:
    """Parse string value to appropriate type based on key."""
    key_info = CONFIGURABLE_KEYS.get(key)
    if not key_info:
        return value

    value_type = key_info["type"]

    if value_type == "bool":
        return value.lower() in ("true", "1", "yes", "ja")
    elif value_type == "int":
        try:
            return int(value)
        except ValueError:
            raise typer.BadParameter(f"'{value}' is geen geldig nummer")
    return value


def validate_value(key: str, value: str | int | bool) -> None:
    """Validate a config value."""
    if key == "timeout":
        if not isinstance(value, int) or not (5 <= value <= 120):
            raise typer.BadParameter("timeout moet tussen 5 en 120 zijn")
    elif key == "oauth_callback_port":
        if not isinstance(value, int) or not (1024 <= value <= 65535):
            raise typer.BadParameter("oauth_callback_port moet tussen 1024 en 65535 zijn")
    elif key == "oauth_timeout":
        if not isinstance(value, int) or not (30 <= value <= 600):
            raise typer.BadParameter("oauth_timeout moet tussen 30 en 600 zijn")


@app.command("show")
def config_show():
    """
    Toon alle configuratie-instellingen.

    Voorbeelden:
        magister config show
    """
    config = load_config()
    settings = get_settings()

    table = Table(title="Magister CLI Configuratie", show_header=True)
    table.add_column("Instelling", style="cyan", width=20)
    table.add_column("Waarde", style="green", width=20)
    table.add_column("Bron", style="dim", width=15)
    table.add_column("Omschrijving", style="dim", width=35)

    for key, info in CONFIGURABLE_KEYS.items():
        # Get value from config file
        file_value = config.get(key)
        # Get effective value from settings (includes env vars)
        effective_value = getattr(settings, key, None)

        if file_value is not None:
            source = "config.yaml"
            display_value = str(file_value)
        elif effective_value is not None and effective_value != getattr(Settings(), key, None):
            source = "env var"
            display_value = str(effective_value)
        elif effective_value is not None:
            source = "standaard"
            display_value = f"[dim]{effective_value}[/dim]"
        else:
            source = "-"
            display_value = "[dim]niet ingesteld[/dim]"

        table.add_row(key, display_value, source, info["description"])

    console.print(table)
    console.print()
    console.print(f"[dim]Config bestand: {CONFIG_PATH}[/dim]")


@app.command("set")
def config_set(
    key: Annotated[str, typer.Argument(help="Instelling naam")],
    value: Annotated[str, typer.Argument(help="Nieuwe waarde")],
):
    """
    Stel een configuratiewaarde in.

    Voorbeelden:
        magister config set school vsvonh
        magister config set timeout 60
        magister config set headless false
    """
    if key not in CONFIGURABLE_KEYS:
        console.print(f"[red]Onbekende instelling:[/red] {key}")
        console.print()
        console.print("[bold]Beschikbare instellingen:[/bold]")
        for k, info in CONFIGURABLE_KEYS.items():
            console.print(f"  [cyan]{k}[/cyan] - {info['description']}")
        raise typer.Exit(1)

    # Parse and validate
    parsed_value = parse_value(key, value)
    validate_value(key, parsed_value)

    # Save
    config = load_config()
    config[key] = parsed_value
    save_config(config)

    console.print(f"[green]✓[/green] {key} = {parsed_value}")


@app.command("get")
def config_get(
    key: Annotated[str, typer.Argument(help="Instelling naam")],
):
    """
    Haal een specifieke configuratiewaarde op.

    Voorbeelden:
        magister config get school
    """
    if key not in CONFIGURABLE_KEYS:
        console.print(f"[red]Onbekende instelling:[/red] {key}")
        raise typer.Exit(1)

    config = load_config()
    settings = get_settings()

    file_value = config.get(key)
    effective_value = getattr(settings, key, None)

    if file_value is not None:
        console.print(f"{key} = {file_value} [dim](config.yaml)[/dim]")
    elif effective_value is not None:
        console.print(f"{key} = {effective_value} [dim](standaard/env)[/dim]")
    else:
        console.print(f"{key} = [dim]niet ingesteld[/dim]")


@app.command("reset")
def config_reset(
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Bevestig reset zonder prompt"),
    ] = False,
):
    """
    Reset alle configuratie naar standaardwaarden.

    Voorbeelden:
        magister config reset
        magister config reset --force
    """
    if not CONFIG_PATH.exists():
        console.print("[yellow]Geen config bestand gevonden.[/yellow]")
        return

    if not force:
        confirm = typer.confirm("Weet je zeker dat je alle instellingen wilt resetten?")
        if not confirm:
            console.print("[dim]Geannuleerd.[/dim]")
            return

    CONFIG_PATH.unlink()
    console.print("[green]✓[/green] Configuratie gereset naar standaardwaarden.")


@app.command("edit")
def config_edit():
    """
    Open het configuratiebestand in de standaard editor.

    Voorbeelden:
        magister config edit
    """
    import os
    import subprocess

    # Ensure config file exists
    if not CONFIG_PATH.exists():
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        # Create with example values
        example_config = {
            "# Magister CLI configuratie": None,
            "# Beschikbare instellingen:": None,
            "school": None,
            "username": None,
            "timeout": 30,
            "headless": True,
        }
        # Write a clean example
        with open(CONFIG_PATH, "w") as f:
            f.write("# Magister CLI configuratie\n")
            f.write("# Uncomment en pas aan naar wens\n\n")
            f.write("# school: vsvonh\n")
            f.write("# username: jan.jansen\n")
            f.write("# timeout: 30\n")
            f.write("# headless: true\n")

    # Get editor from env or use default
    editor = os.environ.get("EDITOR", os.environ.get("VISUAL", "nano"))

    try:
        subprocess.run([editor, str(CONFIG_PATH)])
        console.print(f"[dim]Bestand bewerkt: {CONFIG_PATH}[/dim]")
    except FileNotFoundError:
        console.print(f"[red]Editor niet gevonden:[/red] {editor}")
        console.print(f"[dim]Je kunt het bestand handmatig bewerken: {CONFIG_PATH}[/dim]")


@app.command("path")
def config_path():
    """
    Toon het pad naar het configuratiebestand.

    Voorbeelden:
        magister config path
    """
    console.print(str(CONFIG_PATH))
