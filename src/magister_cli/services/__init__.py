"""Services module for Magister CLI.

This module provides two sets of domain objects:

1. **core.py**: I/O agnostic domain objects (AttachmentInfo, HomeworkItem, etc.)
   - Used by MagisterAsyncService for MCP tools and async operations
   - JSON serializable via to_dict() methods
   - No dependencies on raw API models

2. **homework.py**: CLI-specific domain objects (with same names but different fields)
   - Used by HomeworkService for CLI commands
   - Contains raw Bijlage/Afspraak references for full API access
   - Designed for interactive CLI workflows

The separation is intentional: MCP tools need clean, serializable objects while
CLI commands benefit from raw API access for features like downloads.
"""

# Core domain objects (I/O agnostic) - for async/MCP use
from magister_cli.services.core import (
    AttachmentInfo,
    GradeInfo,
    HomeworkDay,
    HomeworkItem,
    MagisterCore,
    ScheduleItem,
)

# Async service (primary implementation)
from magister_cli.services.async_magister import MagisterAsyncService

# Sync service (wrapper for backward compatibility)
from magister_cli.services.sync_magister import MagisterSyncService

# CLI homework service (has raw API references)
from magister_cli.services.homework import HomeworkService

__all__ = [
    # Core domain objects
    "AttachmentInfo",
    "GradeInfo",
    "HomeworkDay",
    "HomeworkItem",
    "MagisterCore",
    "ScheduleItem",
    # Services
    "MagisterAsyncService",
    "MagisterSyncService",
    "HomeworkService",  # Legacy
]
