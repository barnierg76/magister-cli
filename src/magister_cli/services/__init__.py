"""Services module for Magister CLI."""

from magister_cli.services.homework import HomeworkDay, HomeworkItem, HomeworkService

__all__ = [
    "HomeworkService",
    "HomeworkItem",
    "HomeworkDay",
]
