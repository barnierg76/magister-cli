"""Progress indicators for CLI operations.

This module provides Rich-based progress utilities for consistent
user feedback across all CLI commands.
"""

from contextlib import contextmanager
from typing import Generator, Optional

from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
)
from rich.status import Status

# Shared console instance
console = Console()


@contextmanager
def api_spinner(message: str) -> Generator[Status, None, None]:
    """Spinner for API calls with unknown duration.

    Usage:
        with api_spinner("Huiswerk ophalen..."):
            data = service.get_homework()

    Args:
        message: Status message to display during operation

    Yields:
        Rich Status object for updating the message if needed
    """
    with console.status(f"[bold green]{message}", spinner="dots") as status:
        yield status


@contextmanager
def oauth_progress(school: str) -> Generator[Status, None, None]:
    """Progress indicator for OAuth browser authentication.

    Shows a spinner while waiting for the user to complete browser login.

    Args:
        school: School code being authenticated

    Yields:
        Rich Status object
    """
    with console.status(
        f"[bold blue]Wacht op login via browser voor {school}.magister.net...",
        spinner="dots",
    ) as status:
        yield status


class DownloadProgress:
    """Progress bar for file downloads.

    Usage:
        with DownloadProgress(total_files=5) as progress:
            for file in files:
                progress.update_file(file.name)
                # ... download file ...
                progress.complete_file()
    """

    def __init__(self, total_files: int, description: str = "Downloaden"):
        """Initialize download progress.

        Args:
            total_files: Total number of files to download
            description: Description shown in progress bar
        """
        self.total_files = total_files
        self.description = description
        self._progress: Optional[Progress] = None
        self._task_id: Optional[TaskID] = None
        self._current_file: str = ""

    def __enter__(self) -> "DownloadProgress":
        """Start the progress display."""
        self._progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            console=console,
        )
        self._progress.__enter__()
        self._task_id = self._progress.add_task(
            self.description,
            total=self.total_files,
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Clean up progress display."""
        if self._progress:
            self._progress.__exit__(exc_type, exc_val, exc_tb)

    def update_file(self, filename: str) -> None:
        """Update progress with current file being downloaded.

        Args:
            filename: Name of file currently being downloaded
        """
        self._current_file = filename
        if self._progress and self._task_id is not None:
            self._progress.update(
                self._task_id,
                description=f"[cyan]{filename}[/cyan]",
            )

    def complete_file(self, success: bool = True) -> None:
        """Mark current file as complete and advance progress.

        Args:
            success: Whether the download succeeded
        """
        if self._progress and self._task_id is not None:
            self._progress.advance(self._task_id)


class MultiStepProgress:
    """Progress for multi-step operations like student summary.

    Usage:
        steps = ["Huiswerk", "Cijfers", "Rooster"]
        with MultiStepProgress(steps) as progress:
            progress.start_step("Huiswerk")
            # ... fetch homework ...
            progress.complete_step()
    """

    def __init__(self, steps: list[str]):
        """Initialize multi-step progress.

        Args:
            steps: List of step names
        """
        self.steps = steps
        self._progress: Optional[Progress] = None
        self._task_id: Optional[TaskID] = None
        self._current_step = 0

    def __enter__(self) -> "MultiStepProgress":
        """Start the progress display."""
        self._progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=console,
        )
        self._progress.__enter__()
        self._task_id = self._progress.add_task(
            f"[bold]{self.steps[0]}...",
            total=len(self.steps),
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Clean up progress display."""
        if self._progress:
            self._progress.__exit__(exc_type, exc_val, exc_tb)

    def start_step(self, step_name: str) -> None:
        """Mark a step as starting.

        Args:
            step_name: Name of step being started
        """
        if self._progress and self._task_id is not None:
            self._progress.update(
                self._task_id,
                description=f"[bold cyan]{step_name}...[/bold cyan]",
            )

    def complete_step(self) -> None:
        """Mark current step as complete."""
        if self._progress and self._task_id is not None:
            self._current_step += 1
            self._progress.advance(self._task_id)

            # Update description to next step if available
            if self._current_step < len(self.steps):
                self._progress.update(
                    self._task_id,
                    description=f"[bold]{self.steps[self._current_step]}...",
                )


def print_success(message: str) -> None:
    """Print a success message with checkmark.

    Args:
        message: Success message to display
    """
    console.print(f"[green]✓[/green] {message}")


def print_error(message: str) -> None:
    """Print an error message with X mark.

    Args:
        message: Error message to display
    """
    console.print(f"[red]✗[/red] {message}")


def print_warning(message: str) -> None:
    """Print a warning message.

    Args:
        message: Warning message to display
    """
    console.print(f"[yellow]⚠[/yellow] {message}")


def print_info(message: str) -> None:
    """Print an info message.

    Args:
        message: Info message to display
    """
    console.print(f"[blue]ℹ[/blue] {message}")
