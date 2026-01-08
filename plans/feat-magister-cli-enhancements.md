# feat: Magister CLI Enhancements - Wave 2

## Overview

Seven feature enhancements for the Magister CLI to improve user experience, add export capabilities, and enable proactive notifications. These features build on the existing authentication, schedule, homework, grades, and messages functionality.

## Features Summary

| # | Feature | Priority | Complexity | Dependencies |
|---|---------|----------|------------|--------------|
| 1 | Refresh Token Handling | High | Medium | None |
| 2 | Grade Features (trends, averages) | Medium | Medium | Feature 1 |
| 3 | Notifications/Alerts | Medium | High | Feature 1, 7 |
| 4 | Export Functionality (iCal) | Medium | Low | Feature 1 |
| 5 | Better Error Messages | High | Low | None |
| 6 | Shell Completion | Low | Low | None |
| 7 | Config Command | High | Low | None |

**Recommended Implementation Order:** 7 → 5 → 1 → 6 → 4 → 2 → 3

---

## Feature 1: Refresh Token Handling

### Problem Statement

Currently, when tokens expire (~2 hours), users must manually re-login via browser. This disrupts workflows and makes automation impossible.

### Technical Context

**Current Implementation:** `src/magister_cli/auth/token_manager.py:25-29`
- `TokenData.is_expired()` checks with 5-minute buffer
- `get_valid_token()` returns None if expired - no automatic refresh
- Magister API does NOT provide a refresh token endpoint (per CLAUDE.md)

**Key Finding:** Since Magister doesn't expose a refresh endpoint, we cannot implement true OAuth2 token refresh. Instead, we need:
1. Proactive token checking before API calls
2. Graceful prompting for re-authentication
3. Option for headless re-auth using stored credentials (if user opts in)

### Proposed Solution

```python
# src/magister_cli/auth/token_manager.py

class TokenManager:
    def get_valid_token_or_prompt(self, school: str) -> TokenData:
        """Get valid token or prompt for re-authentication."""
        token = self.get_valid_token(school)

        if token is None:
            console.print("[yellow]Session expired. Re-authentication required.[/yellow]")
            # Trigger browser auth flow
            from magister_cli.auth.browser_auth import BrowserAuthenticator
            auth = BrowserAuthenticator(school)
            new_token = auth.authenticate()
            self.save_token(new_token)
            return new_token

        return token
```

### Implementation Tasks

- [ ] Add `get_valid_token_or_prompt()` method to `TokenManager`
- [ ] Create `@ensure_authenticated` decorator for CLI commands
- [ ] Add proactive token check (refresh if <10 min remaining)
- [ ] Handle concurrent token refresh with threading lock
- [ ] Store credentials securely (opt-in) for headless re-auth
- [ ] Add `--no-browser` flag to fail instead of opening browser

### Files to Modify

| File | Changes |
|------|---------|
| `src/magister_cli/auth/token_manager.py` | Add `get_valid_token_or_prompt()`, threading lock |
| `src/magister_cli/cli/utils.py` | Add `@ensure_authenticated` decorator |
| `src/magister_cli/api/client.py` | Use new token validation before requests |

### Edge Cases

- Token expires mid-long-operation (export) → Refresh and retry
- Multiple concurrent CLI processes → File-based lock for refresh
- Browser unavailable (SSH, CI/CD) → `--no-browser` flag with clear error

---

## Feature 2: Grade Features (Trends & Averages)

### Problem Statement

Current grade display shows raw data without analysis. Parents want to see trends, subject averages, and visual indicators of academic progress.

### Technical Context

**Current Implementation:** `src/magister_cli/cli/commands/grades.py`
- `grades recent` - Shows last N grades with color coding
- `grades overview` - Shows averages per subject
- Color thresholds: green ≥8.0, cyan ≥5.5, red <5.5

**API Endpoints:** `src/magister_cli/api/resources/grades.py`
- `all_grades(enrollment_id)` - Historical grades available
- `averages_by_subject(enrollment_id)` - Calculated averages

### Proposed Solution

Add new subcommands for trend analysis:

```bash
# Show grade trends with ASCII chart
magister grades trends --subject wiskunde --period 90d

# Show detailed statistics
magister grades stats

# Compare periods
magister grades compare --from 2025-09 --to 2025-12
```

### MVP Implementation

```python
# src/magister_cli/cli/commands/grades.py

@app.command("trends")
def grade_trends(
    subject: str | None = None,
    period: int = typer.Option(90, help="Days to analyze"),
):
    """Show grade trends over time."""
    # Fetch historical grades
    # Calculate moving average
    # Display ASCII chart with trend indicator (↑ ↓ →)
```

### Implementation Tasks

- [ ] Add `grades trends` command with ASCII chart display
- [ ] Add `grades stats` command showing min/max/avg/median
- [ ] Implement trend calculation (simple moving average)
- [ ] Add trend indicators (↑ improving, ↓ declining, → stable)
- [ ] Cache historical grades locally for performance
- [ ] Add `--period` flag (30d, 90d, semester, year)

### Files to Create/Modify

| File | Changes |
|------|---------|
| `src/magister_cli/cli/commands/grades.py` | Add `trends`, `stats` commands |
| `src/magister_cli/services/grade_analysis.py` | NEW: Trend calculation logic |
| `src/magister_cli/cli/formatters.py` | Add ASCII chart formatter |

### Display Example

```
Grade Trend: Wiskunde (last 90 days)

 8.5 │    ╭─╮
 8.0 │ ╭──╯ ╰──╮      ↑ Improving
 7.5 │─╯       ╰──╮   Avg: 7.8
 7.0 │            ╰─  Min: 7.0 Max: 8.5
     └────────────────
      Sep   Oct   Nov
```

---

## Feature 3: Notifications/Alerts

### Problem Statement

Parents want proactive alerts for new grades, schedule changes, and homework deadlines without manually checking the CLI.

### Technical Context

**No existing notification system.** Need to build:
1. Background daemon for polling
2. State tracking (what changed since last check)
3. Desktop notification integration

**Recommended Library:** `desktop-notifier` for cross-platform support with async API.

### Proposed Solution

```bash
# Enable notifications
magister notify enable

# Check status
magister notify status

# Configure
magister config set notifications.grades true
magister config set notifications.schedule true
magister config set notifications.homework_reminder 24h
```

### Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Daemon Process │────▶│  State Tracking  │────▶│  Desktop Notify │
│  (polling loop) │     │  (JSON file)     │     │  (plyer/notifier)│
└─────────────────┘     └──────────────────┘     └─────────────────┘
        │                        │
        ▼                        ▼
┌─────────────────┐     ┌──────────────────┐
│  Magister API   │     │ ~/.config/       │
│  (grades, etc.) │     │ magister-cli/    │
└─────────────────┘     │ state.json       │
                        └──────────────────┘
```

### Implementation Tasks

- [ ] Create `magister notify` command group
- [ ] Implement daemon process with `--daemon` flag
- [ ] Add state tracking in `~/.config/magister-cli/state.json`
- [ ] Integrate `plyer` for cross-platform notifications
- [ ] Add polling intervals configuration
- [ ] Implement quiet hours support
- [ ] Add `notify status` to show daemon health
- [ ] Handle first-run baseline (don't flood with existing data)

### Files to Create

| File | Purpose |
|------|---------|
| `src/magister_cli/cli/commands/notify.py` | Notification commands |
| `src/magister_cli/services/notifications.py` | Daemon and polling logic |
| `src/magister_cli/services/state_tracker.py` | Change detection |

### Notification Types

| Type | Trigger | Example Message |
|------|---------|-----------------|
| New Grade | Grade added | "Nieuw cijfer: Wiskunde 7.5" |
| Schedule Change | Lesson modified/cancelled | "Roosterwijziging: Engels uitval morgen" |
| Homework Reminder | Due in <24h | "Huiswerk morgen: Nederlands opdracht 5" |

---

## Feature 4: Export Functionality (iCal)

### Problem Statement

Users want to sync their Magister schedule with external calendar apps (Google Calendar, Apple Calendar, Outlook).

### Technical Context

**Recommended Library:** `icalendar` - RFC 5545 compliant, well-maintained.

**Existing Pattern:** Download command in `main.py:209-303` provides file export pattern.

### Proposed Solution

```bash
# Export schedule to iCal
magister export schedule --from 2026-01-08 --to 2026-02-08 -o schedule.ics

# Export homework as calendar events
magister export homework --days 14 -o homework.ics

# Export to stdout for piping
magister export schedule --format ical | pbcopy
```

### MVP Implementation

```python
# src/magister_cli/cli/commands/export.py

from icalendar import Calendar, Event
import zoneinfo

TZ = zoneinfo.ZoneInfo('Europe/Amsterdam')

def create_schedule_ical(appointments: list[Afspraak]) -> Calendar:
    """Convert Magister appointments to iCal format."""
    cal = Calendar()
    cal.add('prodid', '-//Magister CLI//magister-cli//NL')
    cal.add('version', '2.0')
    cal.add('x-wr-calname', 'Magister Rooster')
    cal.add('x-wr-timezone', 'Europe/Amsterdam')

    for apt in appointments:
        event = Event()
        event.add('summary', apt.vak_naam)
        event.add('dtstart', apt.start.replace(tzinfo=TZ))
        event.add('dtend', apt.einde.replace(tzinfo=TZ))
        event.add('location', apt.lokaal_naam or '')
        event['uid'] = f"{apt.id}@magister-cli"

        if apt.is_vervallen:
            event.add('status', 'CANCELLED')

        cal.add_component(event)

    return cal
```

### Implementation Tasks

- [ ] Add `icalendar` to dependencies
- [ ] Create `export` command group
- [ ] Implement `export schedule` with date range
- [ ] Implement `export homework` as all-day events
- [ ] Handle timezone conversion (Europe/Amsterdam)
- [ ] Generate stable UIDs for event updates
- [ ] Mark cancelled lessons appropriately
- [ ] Add `--format` flag (ical, json, csv)
- [ ] Handle >30 day ranges with chunked API calls

### Files to Create

| File | Purpose |
|------|---------|
| `src/magister_cli/cli/commands/export.py` | Export commands |
| `src/magister_cli/services/ical_generator.py` | iCal generation logic |

---

## Feature 5: Better Error Messages

### Problem Statement

Current error messages are technical and don't guide users to solutions. Need user-friendly Dutch messages with actionable suggestions.

### Technical Context

**Current Implementation:** `src/magister_cli/cli/formatters.py:140-154`
- `format_no_auth_error()` - Basic auth error
- `format_api_error()` - Generic API error

**Error Classes:** `src/magister_cli/api/exceptions.py`
- `MagisterAPIError`, `TokenExpiredError`, `RateLimitError`, `NotAuthenticatedError`

### Proposed Solution

Create comprehensive error taxonomy with Dutch translations:

```python
# src/magister_cli/cli/errors.py

ERROR_MESSAGES = {
    "auth_expired": {
        "title": "Sessie verlopen",
        "message": "Je sessie is verlopen.",
        "suggestion": "Log opnieuw in met: magister login",
    },
    "network_timeout": {
        "title": "Verbinding mislukt",
        "message": "Kon geen verbinding maken met Magister.",
        "suggestion": "Controleer je internetverbinding en probeer opnieuw.",
    },
    "rate_limit": {
        "title": "Te veel verzoeken",
        "message": "Je hebt te veel verzoeken gestuurd.",
        "suggestion": "Wacht {retry_after} seconden en probeer opnieuw.",
    },
    # ... more errors
}
```

### Implementation Tasks

- [ ] Create `src/magister_cli/cli/errors.py` with error taxonomy
- [ ] Map HTTP status codes to error types
- [ ] Add context-aware error enhancement
- [ ] Implement `--verbose` flag for full tracebacks
- [ ] Add error logging to `~/.config/magister-cli/error.log`
- [ ] Create Rich panels for error display

### Error Display Example

```
╭─────────────────── Fout: Sessie verlopen ────────────────────╮
│                                                               │
│  Je sessie is verlopen.                                       │
│                                                               │
│  💡 Suggestie: Log opnieuw in met:                           │
│     magister login --school vsvonh                            │
│                                                               │
╰───────────────────────────────────────────────────────────────╯
```

---

## Feature 6: Shell Completion

### Problem Statement

Users want tab completion for commands, options, and dynamic values like school codes and subjects.

### Technical Context

**Already Available:** Typer provides built-in completion via `--install-completion`.

**Current Status:** Mentioned in README but not actively promoted or customized.

### Proposed Solution

Enhance with custom completers for dynamic data:

```python
# src/magister_cli/cli/completers.py

def complete_school(incomplete: str) -> list[str]:
    """Complete school codes from config or cache."""
    # Return schools starting with incomplete
    schools = ["vsvonh", "erasmiaans", "stedelijk"]
    return [s for s in schools if s.startswith(incomplete)]

def complete_subject(incomplete: str) -> list[str]:
    """Complete subject names from cached grades."""
    # Load from local cache (don't hit API during completion)
    subjects = load_cached_subjects()
    return [s for s in subjects if s.lower().startswith(incomplete.lower())]
```

### Implementation Tasks

- [ ] Add custom completers for `--school`
- [ ] Add completers for `--subject` using cached data
- [ ] Cache subject list after first grades fetch
- [ ] Document completion installation in README
- [ ] Test on bash, zsh, fish
- [ ] Add `magister completion install` alias command

### Files to Create

| File | Purpose |
|------|---------|
| `src/magister_cli/cli/completers.py` | Custom completion functions |

---

## Feature 7: Config Command

### Problem Statement

Users must use environment variables or `.env` files to configure the CLI. Need a `config` command for easier management.

### Technical Context

**Current Implementation:** `src/magister_cli/config.py:36-81`
- `Settings` class uses `pydantic-settings`
- Reads from env vars with `MAGISTER_` prefix
- Supports `.env` file
- No config file persistence

**Config Location:** `~/.config/magister-cli/`

### Proposed Solution

```bash
# Set default school
magister config set school vsvonh

# View all settings
magister config show

# Get specific value
magister config get school

# Reset to defaults
magister config reset

# Edit config file directly
magister config edit
```

### MVP Implementation

```python
# src/magister_cli/cli/commands/config.py

import typer
import yaml
from pathlib import Path

app = typer.Typer(help="Configuratie beheren")

CONFIG_PATH = Path.home() / ".config" / "magister-cli" / "config.yaml"

@app.command("set")
def config_set(key: str, value: str):
    """Set a configuration value."""
    config = load_config()
    config[key] = value
    save_config(config)
    console.print(f"[green]✓[/green] {key} = {value}")

@app.command("get")
def config_get(key: str):
    """Get a configuration value."""
    config = load_config()
    value = config.get(key, "[dim]niet ingesteld[/dim]")
    console.print(f"{key} = {value}")

@app.command("show")
def config_show():
    """Show all configuration."""
    config = load_config()
    syntax = Syntax(yaml.dump(config), "yaml")
    console.print(Panel(syntax, title="Configuratie"))
```

### Config Schema

```yaml
# ~/.config/magister-cli/config.yaml
school: vsvonh
username: null  # Optional, for login hint

# Display settings
color_output: true
date_format: "%d-%m-%Y"

# Notification settings (Feature 3)
notifications:
  enabled: false
  grades: true
  schedule: true
  homework_reminder: "24h"
  quiet_hours:
    start: "22:00"
    end: "07:00"

# Export settings (Feature 4)
export:
  default_format: ical
  timezone: Europe/Amsterdam

# Grade display (Feature 2)
grades:
  pass_threshold: 5.5
  trend_period: 90  # days
```

### Implementation Tasks

- [ ] Create `config` command group
- [ ] Implement `config set/get/show/reset/edit`
- [ ] Add YAML config file support
- [ ] Integrate with existing `Settings` class
- [ ] Define config priority: CLI flag > env var > config file > default
- [ ] Add config validation on `set`
- [ ] Create config on first CLI use if not exists

### Files to Create/Modify

| File | Changes |
|------|---------|
| `src/magister_cli/cli/commands/config.py` | NEW: Config commands |
| `src/magister_cli/config.py` | Add YAML loading, merge with env vars |
| `src/magister_cli/main.py` | Register config command group |

---

## Dependencies

```toml
# pyproject.toml additions

[project.dependencies]
# Existing...
icalendar = ">=6.0.0"  # Feature 4: iCal export
plyer = ">=2.1.0"      # Feature 3: Desktop notifications (or desktop-notifier)
pyyaml = ">=6.0"       # Feature 7: Config file
```

---

## Testing Strategy

### Unit Tests

```python
# tests/test_config.py
def test_config_set_and_get():
    """Config set should persist and get should retrieve."""

# tests/test_ical_export.py
def test_schedule_to_ical():
    """Schedule export should produce valid iCal."""

# tests/test_grade_trends.py
def test_trend_calculation():
    """Trend should correctly identify improving/declining."""
```

### Integration Tests

- [ ] Full login → fetch → export flow
- [ ] Config set → command uses default
- [ ] Token expiry → auto re-auth prompt

### Manual Test Checklist

- [ ] Tab completion works on bash/zsh/fish
- [ ] iCal imports correctly to Apple Calendar
- [ ] iCal imports correctly to Google Calendar
- [ ] Notifications appear on macOS
- [ ] Notifications appear on Windows
- [ ] Config persists across CLI restarts

---

## Rollout Plan

### Phase 1: Foundation (Features 7, 5)
- Config command for better UX
- Error messages for debugging
- No API changes needed

### Phase 2: Core Enhancements (Features 1, 6)
- Token handling for reliability
- Shell completion for discoverability

### Phase 3: Export & Analysis (Features 4, 2)
- iCal export for calendar integration
- Grade trends for academic insights

### Phase 4: Proactive Features (Feature 3)
- Notifications (most complex, needs daemon)
- Requires all other features working

---

## Open Questions

1. **Multi-child support:** Should config support profiles for multiple children?
2. **Rate limits:** What are actual Magister API rate limits?
3. **Class averages:** Does Magister API provide class averages for comparison?
4. **Daemon approach:** Simple process vs. systemd/launchd integration?

---

## References

### Internal Files
- Token management: `src/magister_cli/auth/token_manager.py:15-123`
- Grade commands: `src/magister_cli/cli/commands/grades.py:66-366`
- Error formatting: `src/magister_cli/cli/formatters.py:140-154`
- Configuration: `src/magister_cli/config.py:36-98`
- Download pattern: `src/magister_cli/main.py:209-303`

### External Documentation
- [Typer Shell Completion](https://typer.tiangolo.com/tutorial/options-autocompletion/)
- [icalendar Documentation](https://icalendar.readthedocs.io/)
- [desktop-notifier](https://github.com/samschott/desktop-notifier)
- [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
