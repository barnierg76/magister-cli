---
date: 2026-01-08
problem_type: feature_implementation
component: cli_commands
severity: moderate
tags: [wave2, config, notifications, ical, grades, completion, errors]
features_implemented: 7
---

# Wave 2 CLI Enhancements - 7 New Features

## Overview

Major feature release adding 7 new capabilities to the Magister CLI, improving user experience, adding export functionality, and enabling proactive notifications.

## Features Implemented

### 1. Config Command (`magister config`)

**Purpose:** YAML-based configuration management replacing environment variables.

**Files Created:**
- `src/magister_cli/cli/commands/config.py` - CLI commands
- Modified `src/magister_cli/config.py` - YAML settings source

**Commands:**
```bash
magister config show      # Show all settings
magister config set KEY VALUE  # Set a value
magister config get KEY   # Get specific value
magister config reset     # Reset to defaults
magister config edit      # Open in editor
magister config path      # Show config file path
```

**Key Implementation:**
```python
class YamlConfigSettingsSource(PydanticBaseSettingsSource):
    """Custom settings source that reads from YAML config file."""

    def get_field_value(self, field: Any, field_name: str) -> tuple[Any, str, bool]:
        config = self._load_config()
        if field_name in config:
            return config[field_name], field_name, False
        return None, field_name, False
```

**Config Location:** `~/.config/magister-cli/config.yaml`

---

### 2. Better Error Messages (`errors.py`)

**Purpose:** User-friendly Dutch error messages with actionable suggestions.

**Files Created:**
- `src/magister_cli/cli/errors.py` - Error taxonomy and formatting

**Error Types Handled:**
- `auth_expired` - Session expired
- `auth_required` - Not logged in
- `network_timeout` - Connection failed
- `rate_limit` - Too many requests
- `school_not_found` - Invalid school code
- `api_error` - Generic API errors

**Key Implementation:**
```python
ERROR_MESSAGES = {
    "auth_expired": ErrorInfo(
        title="Sessie verlopen",
        message="Je sessie is verlopen.",
        suggestion="Log opnieuw in met: magister login",
        exit_code=1,
    ),
    # ... more error types
}

def format_error(error: Exception, school: str | None = None) -> None:
    """Format and display error with Rich panel."""
```

---

### 3. Token Expiry Handling

**Purpose:** Proactive warnings before session expires.

**Files Modified:**
- `src/magister_cli/auth/token_manager.py` - Added expiry methods
- `src/magister_cli/cli/commands/auth.py` - Enhanced status display
- `src/magister_cli/cli/utils.py` - Added expiry check decorator

**Key Implementation:**
```python
def is_token_expiring_soon(self, threshold_minutes: int = 15) -> bool:
    """Check if token expires within threshold."""
    remaining = self.get_time_until_expiry()
    if remaining is None:
        return False
    return remaining.total_seconds() <= threshold_minutes * 60

def get_time_until_expiry(self) -> timedelta | None:
    """Get time remaining until token expires."""
```

**Proactive Warning:** Shows warning when <15 minutes remaining.

---

### 4. Shell Completion (`magister completion`)

**Purpose:** Tab completion for commands, options, and dynamic values.

**Files Created:**
- `src/magister_cli/cli/commands/completion.py` - CLI commands
- `src/magister_cli/cli/completers.py` - Custom completers

**Commands:**
```bash
magister completion install [SHELL]  # Install completion
magister completion show [SHELL]     # Show completion script
magister completion status           # Check installation status
```

**Custom Completers:**
- School code completion from config
- Subject completion from cached grades

---

### 5. iCal Export (`magister export`)

**Purpose:** Export schedule and homework to calendar apps.

**Files Created:**
- `src/magister_cli/cli/commands/export.py` - CLI commands
- `src/magister_cli/services/ical_export.py` - iCal generation

**Commands:**
```bash
magister export schedule --days 14   # Export schedule
magister export homework --days 14   # Export homework
magister export all --days 14        # Export both
```

**Key Implementation:**
```python
def appointment_to_event(afspraak: Afspraak) -> Event:
    """Convert Magister appointment to iCal event."""
    event = Event()
    event.add("uid", _generate_uid("appointment", afspraak.id, afspraak.start))
    event.add("summary", afspraak.vak_naam)
    event.add("dtstart", afspraak.start.replace(tzinfo=NL_TZ))
    event.add("dtend", afspraak.einde.replace(tzinfo=NL_TZ))
    # ... location, description, categories
    return event
```

**Dependencies Added:** `icalendar>=5.0.0`

---

### 6. Grade Trends (`magister grades trends/stats`)

**Purpose:** Statistical analysis of grade progression.

**Files Modified:**
- `src/magister_cli/cli/commands/grades.py` - Added trends and stats commands

**Commands:**
```bash
magister grades trends --days 90     # Show trends per subject
magister grades stats                # Detailed statistics
```

**Key Implementation:**
```python
def _calculate_trend(grades: list[Cijfer], period_days: int = 30) -> str:
    """Calculate trend indicator for grades."""
    if len(grades) < 4:
        return "→"
    # Split into recent vs older, calculate averages
    diff = recent_avg - older_avg
    if diff > 0.3:
        return "[green]↑[/green]"
    elif diff < -0.3:
        return "[red]↓[/red]"
    return "[dim]→[/dim]"
```

**Statistics Provided:** Mean, median, standard deviation, min/max per subject.

---

### 7. Desktop Notifications (`magister notify`)

**Purpose:** Proactive alerts for new grades, schedule changes, homework deadlines.

**Files Created:**
- `src/magister_cli/cli/commands/notify.py` - CLI commands
- `src/magister_cli/services/notifications.py` - Notification service
- `src/magister_cli/services/state_tracker.py` - Change detection

**Commands:**
```bash
magister notify test     # Send test notification
magister notify check    # Check for changes
magister notify status   # Show notification status
magister notify reset    # Reset state
magister notify setup    # Interactive setup wizard
```

**Key Implementation:**
```python
class StateTracker:
    """Tracks state changes between API calls."""

    def check_grades(self, grades: list[dict]) -> list[StateChange]:
        """Detect new grades since last check."""

    def check_schedule(self, appointments: list[dict]) -> list[StateChange]:
        """Detect schedule changes."""

    def check_homework(self, items: list[dict], reminder_hours: int) -> list[StateChange]:
        """Detect homework due within reminder window."""

class NotificationService:
    """Service for sending desktop notifications."""

    async def send_notification(self, title: str, message: str) -> bool:
        """Send desktop notification via desktop-notifier."""
```

**Dependencies Added:** `desktop-notifier>=5.0.0`

**State Storage:** `~/.config/magister-cli/state_{school}.json`

---

## Architecture Decisions

### Why desktop-notifier over plyer?
- Better async API
- Cross-platform (macOS, Windows, Linux)
- More reliable on macOS with rubicon-objc

### Why YAML config over .env?
- Human-readable and editable
- Supports nested config (future: notifications.quiet_hours)
- Integrates with pydantic-settings via custom source

### Why state tracking for notifications?
- Prevents notification flood on first run (baseline initialization)
- Tracks what's been notified to avoid duplicates
- Persistent across CLI invocations

---

## Dependencies Added

```toml
pyyaml>=6.0.0           # YAML config support
icalendar>=5.0.0        # iCal export
desktop-notifier>=5.0.0 # Desktop notifications
```

---

## Testing

**Verified working:**
- `magister --help` shows all new commands
- `magister notify --help` shows all notify subcommands
- `magister config show` displays settings table
- `magister grades --help` shows trends/stats commands

**Architecture Note:** Required `arch -arm64` prefix due to terminal running in Rosetta (x86_64) while packages were arm64.

---

## Related Files

- Plan document: `plans/feat-magister-cli-enhancements.md`
- Main entry point: `src/magister_cli/main.py`
- Config: `src/magister_cli/config.py`

---

## Commit Reference

```
f396cb0 feat: Add Wave 2 enhancements - 7 new features
```
