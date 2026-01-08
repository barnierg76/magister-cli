"""Shell completion commands."""

import subprocess
import sys
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel

console = Console()
app = typer.Typer(help="Shell completion beheren")


def _detect_shell() -> str | None:
    """Detect the current shell."""
    import os

    shell = os.environ.get("SHELL", "")
    if "zsh" in shell:
        return "zsh"
    elif "bash" in shell:
        return "bash"
    elif "fish" in shell:
        return "fish"
    return None


@app.command("install")
def install_completion(
    shell: Annotated[
        str | None,
        typer.Option("--shell", "-s", help="Shell type (bash, zsh, fish)"),
    ] = None,
):
    """
    Installeer shell completion voor magister commando's.

    Voorbeelden:
        magister completion install
        magister completion install --shell zsh
    """
    detected = shell or _detect_shell()

    if not detected:
        console.print("[red]Kon shell niet detecteren.[/red]")
        console.print("Gebruik --shell om je shell op te geven (bash, zsh, fish)")
        raise typer.Exit(1)

    console.print(f"Installeer completion voor [cyan]{detected}[/cyan]...")

    try:
        # Use Typer's built-in completion installation
        result = subprocess.run(
            [sys.executable, "-m", "magister_cli.main", "--install-completion", detected],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            console.print("[green]Completion geïnstalleerd![/green]")
            console.print()
            console.print("[dim]Herstart je terminal of voer uit:[/dim]")
            if detected == "zsh":
                console.print("  [cyan]source ~/.zshrc[/cyan]")
            elif detected == "bash":
                console.print("  [cyan]source ~/.bashrc[/cyan]")
            elif detected == "fish":
                console.print("  [cyan]source ~/.config/fish/config.fish[/cyan]")
        else:
            # Try fallback approach
            console.print("[yellow]Probeer alternatieve methode...[/yellow]")
            _show_manual_instructions(detected)

    except Exception as e:
        console.print(f"[red]Fout:[/red] {e}")
        _show_manual_instructions(detected)


def _show_manual_instructions(shell: str) -> None:
    """Show manual completion installation instructions."""
    if shell == "zsh":
        instructions = """\
# Voeg toe aan ~/.zshrc:
autoload -Uz compinit
compinit

# Of voer dit eenmalig uit:
magister --install-completion zsh
"""
    elif shell == "bash":
        instructions = """\
# Voeg toe aan ~/.bashrc:
eval "$(magister --show-completion bash)"
"""
    elif shell == "fish":
        instructions = """\
# Voeg toe aan ~/.config/fish/completions/magister.fish:
magister --show-completion fish > ~/.config/fish/completions/magister.fish
"""
    else:
        instructions = "Gebruik: magister --install-completion <shell>"

    console.print(Panel(
        instructions,
        title="Handmatige installatie",
        border_style="yellow",
    ))


@app.command("show")
def show_completion(
    shell: Annotated[
        str | None,
        typer.Option("--shell", "-s", help="Shell type (bash, zsh, fish)"),
    ] = None,
):
    """
    Toon completion script voor je shell.

    Voorbeelden:
        magister completion show
        magister completion show --shell bash
    """
    detected = shell or _detect_shell()

    if not detected:
        console.print("[red]Kon shell niet detecteren.[/red]")
        console.print("Gebruik --shell om je shell op te geven (bash, zsh, fish)")
        raise typer.Exit(1)

    try:
        result = subprocess.run(
            [sys.executable, "-m", "magister_cli.main", "--show-completion", detected],
            capture_output=True,
            text=True,
        )
        if result.stdout:
            print(result.stdout)
        else:
            console.print(f"[red]Geen completion script beschikbaar voor {detected}[/red]")
    except Exception as e:
        console.print(f"[red]Fout:[/red] {e}")
        raise typer.Exit(1)


@app.command("status")
def completion_status():
    """
    Toon status van shell completion.
    """
    detected = _detect_shell()

    console.print("[bold]Shell Completion Status[/bold]")
    console.print()

    if detected:
        console.print(f"Gedetecteerde shell: [cyan]{detected}[/cyan]")
    else:
        console.print("Gedetecteerde shell: [yellow]onbekend[/yellow]")

    console.print()
    console.print("[dim]Om completion te installeren:[/dim]")
    console.print("  [cyan]magister completion install[/cyan]")
    console.print()
    console.print("[dim]Of gebruik Typer's ingebouwde optie:[/dim]")
    console.print("  [cyan]magister --install-completion[/cyan]")
