"""Context management for agent memory and preferences.

This module implements the context.md pattern for agent-native architecture,
allowing agents to persist preferences, activity logs, and cached data
across sessions.
"""

import fcntl
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


@dataclass
class ContextData:
    """Parsed context data with frontmatter and body."""

    frontmatter: dict[str, Any]
    body: str


class ContextManager:
    """Manages context.md files for agent memory.

    Context files use YAML frontmatter + markdown body format:

    ```
    ---
    schema_version: "1.0"
    school_code: vsvonh
    preferences:
      default_days_ahead: 7
    ---

    ## Session Notes

    Agent notes here...
    ```
    """

    SCHEMA_VERSION = "1.0"

    def __init__(self, school_code: str):
        """Initialize the context manager.

        Args:
            school_code: The Magister school code
        """
        self.school_code = school_code
        self.context_dir = Path.home() / ".config" / "magister-cli" / school_code
        self.context_file = self.context_dir / "context.md"
        self.lock_file = self.context_dir / ".context.lock"

    def _ensure_dir(self) -> None:
        """Ensure context directory exists with proper permissions."""
        if not self.context_dir.exists():
            # Set umask to ensure directory is created with 0o700
            old_umask = os.umask(0o077)
            try:
                self.context_dir.mkdir(parents=True, exist_ok=True)
            finally:
                os.umask(old_umask)
        else:
            # Verify existing directory has correct permissions
            current_mode = self.context_dir.stat().st_mode & 0o777
            if current_mode != 0o700:
                self.context_dir.chmod(0o700)

    def read(self) -> ContextData:
        """Read context.md, returning parsed frontmatter and body.

        Returns:
            ContextData with frontmatter dict and body string
        """
        if not self.context_file.exists():
            return self._default_context()

        try:
            content = self.context_file.read_text()

            # Parse YAML frontmatter using regex for robustness
            match = re.match(r"^---\s*\n(.*?\n)---\s*\n(.*)$", content, re.DOTALL)
            if not match:
                return self._default_context()

            frontmatter_yaml = match.group(1)
            body = match.group(2).strip()

            frontmatter = yaml.safe_load(frontmatter_yaml)
            if frontmatter is None:
                return self._default_context()

            return ContextData(frontmatter=frontmatter, body=body)

        except (yaml.YAMLError, OSError):
            # Return default on any parsing error
            return self._default_context()

    def write(self, frontmatter: dict[str, Any], body: str = "") -> None:
        """Write context.md with file locking for concurrent safety.

        Args:
            frontmatter: YAML frontmatter dictionary
            body: Markdown body content
        """
        self._ensure_dir()

        # Update metadata
        frontmatter["schema_version"] = self.SCHEMA_VERSION
        frontmatter["school_code"] = self.school_code
        frontmatter["last_updated"] = datetime.now().isoformat()

        # Format content
        yaml_content = yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True)
        content = f"---\n{yaml_content}---\n\n{body}"

        # Atomic write with file locking
        with open(self.lock_file, "w") as lock_f:
            fcntl.flock(lock_f.fileno(), fcntl.LOCK_EX)
            try:
                temp_file = self.context_file.with_suffix(".tmp")
                temp_file.write_text(content)

                # Set restrictive permissions before moving
                temp_file.chmod(0o600)

                # Atomic rename
                temp_file.replace(self.context_file)
            finally:
                fcntl.flock(lock_f.fileno(), fcntl.LOCK_UN)

    def update_preferences(self, updates: dict[str, Any]) -> None:
        """Update specific preference values (merge semantics).

        Args:
            updates: Dictionary of preference updates to merge
        """
        ctx = self.read()
        fm = ctx.frontmatter

        if "preferences" not in fm:
            fm["preferences"] = {}

        fm["preferences"].update(updates)
        self.write(fm, ctx.body)

    def update_cached_data(self, updates: dict[str, Any]) -> None:
        """Update cached data values (merge semantics).

        Args:
            updates: Dictionary of cached data updates to merge
        """
        ctx = self.read()
        fm = ctx.frontmatter

        if "cached_data" not in fm:
            fm["cached_data"] = {}

        fm["cached_data"].update(updates)
        self.write(fm, ctx.body)

    def log_activity(self, query: str) -> None:
        """Log agent activity for context tracking.

        Args:
            query: The query or action to log
        """
        ctx = self.read()
        fm = ctx.frontmatter

        if "recent_activity" not in fm:
            fm["recent_activity"] = {}

        activity = fm["recent_activity"]
        activity["last_query"] = query
        activity["last_query_time"] = datetime.now().isoformat()
        activity["queries_today"] = activity.get("queries_today", 0) + 1

        self.write(fm, ctx.body)

    def update_notes(self, notes: str) -> None:
        """Replace the session notes body.

        Args:
            notes: New markdown body content
        """
        ctx = self.read()
        self.write(ctx.frontmatter, notes)

    def get_preferences(self) -> dict[str, Any]:
        """Get current preferences.

        Returns:
            Preferences dictionary (empty dict if not set)
        """
        ctx = self.read()
        return ctx.frontmatter.get("preferences", {})

    def get_cached_data(self) -> dict[str, Any]:
        """Get cached data.

        Returns:
            Cached data dictionary (empty dict if not set)
        """
        ctx = self.read()
        return ctx.frontmatter.get("cached_data", {})

    def clear(self) -> None:
        """Clear all context data, resetting to default."""
        if self.context_file.exists():
            self.context_file.unlink()

    def _default_context(self) -> ContextData:
        """Return default context structure.

        Returns:
            ContextData with default values
        """
        return ContextData(
            frontmatter={
                "schema_version": self.SCHEMA_VERSION,
                "school_code": self.school_code,
                "preferences": {},
                "recent_activity": {},
                "cached_data": {},
            },
            body="## Session Notes\n\nAgent-maintained notes about this student.\n\n## Recent Changes\n\nRecent updates tracked here.\n",
        )
