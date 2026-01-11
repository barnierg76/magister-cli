# Magister CLI

A command-line tool for retrieving data from Magister, the Dutch student tracking system used by many schools in the Netherlands.

## Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Commands](#commands)
  - [Authentication](#authentication)
  - [Homework](#homework)
  - [Tests](#tests)
  - [Grades](#grades)
  - [Schedule](#schedule)
  - [Messages](#messages)
  - [Download](#download)
  - [Export](#export)
  - [Notifications](#notifications)
  - [Configuration](#configuration)
  - [Shell Completion](#shell-completion)
- [MCP Server (Claude Integration)](#mcp-server-claude-integration)
- [Configuration Options](#configuration-options)
- [Architecture](#architecture)
- [Development](#development)

## Installation

```bash
# Clone the repository
git clone https://github.com/your-username/magister-cli.git
cd magister-cli

# Create virtual environment and install (recommended)
uv venv
source .venv/bin/activate
uv pip install -e .

# Or with pip
pip install -e .

# Install Playwright browser for authentication
playwright install chromium
```

## Quick Start

```bash
# 1. Login to your school
magister login --school jouwschool

# 2. View homework for the next 7 days
magister homework

# 3. View upcoming tests
magister tests --days 14

# 4. View today's schedule
magister schedule today

# 5. Check your recent grades
magister grades recent
```

---

## Commands

### Authentication

Magister CLI uses browser-based OAuth authentication. Your token is securely stored in the system keychain.

#### `magister login`

Authenticate with Magister by opening a browser window.

```bash
magister login --school <schoolcode>
```

| Option | Short | Description |
|--------|-------|-------------|
| `--school` | `-s` | School code (e.g., `jouwschool`) |
| `--headless/--no-headless` | | Run browser in headless mode |

**Examples:**
```bash
magister login --school jouwschool
magister login --school jouwschool --headless
```

#### `magister logout`

Remove stored authentication token.

```bash
magister logout [--school <schoolcode>]
```

| Option | Short | Description |
|--------|-------|-------------|
| `--school` | `-s` | School code |

#### `magister status`

Show current authentication status including session expiry time.

```bash
magister status [--school <schoolcode>]
```

| Option | Short | Description |
|--------|-------|-------------|
| `--school` | `-s` | School code |

---

### Homework

#### `magister homework`

Show upcoming homework assignments.

```bash
magister homework [OPTIONS]
```

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--days` | `-d` | Number of days to look ahead | `7` |
| `--subject` | `-s` | Filter by subject (partial match) | - |
| `--school` | | School code | - |
| `--completed` | `-c` | Include completed homework | `false` |
| `--table` | `-t` | Show as table format | `false` |
| `--download` | | Download all attachments | `false` |
| `--output` | `-o` | Output directory for downloads | `./magister_bijlagen` |

**Examples:**
```bash
# View homework for next 7 days
magister homework

# View homework for next 14 days
magister homework --days 14

# Filter by subject
magister homework --subject wiskunde

# Show in table format
magister homework --table

# Include completed homework
magister homework --completed

# Download attachments
magister homework --download
magister homework --download --output ./bijlagen
```

---

### Tests

#### `magister tests`

Show upcoming tests and exams.

```bash
magister tests [OPTIONS]
```

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--days` | `-d` | Number of days to look ahead | `14` |
| `--school` | | School code | - |

**Examples:**
```bash
# View tests for next 14 days
magister tests

# View tests for next 30 days
magister tests --days 30
```

---

### Grades

The `grades` command group provides comprehensive access to your grades.

#### `magister grades recent` / `magister grades list`

Show recent grades.

```bash
magister grades recent [OPTIONS]
```

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--top` | `-n` | Number of grades to show | `15` |
| `--school` | `-s` | School code | - |
| `--debug` | `-d` | Show debug information | `false` |

**Examples:**
```bash
magister grades recent
magister grades recent --top 25
magister grades list --debug
```

#### `magister grades overview`

Show grade overview with averages per subject.

```bash
magister grades overview [--school <schoolcode>]
```

**Output includes:**
- Average grade per subject
- Pass/fail status
- Summary of passing vs failing subjects

#### `magister grades subject`

Show all grades for a specific subject.

```bash
magister grades subject <subject_name> [--school <schoolcode>]
```

| Argument | Description |
|----------|-------------|
| `subject` | Subject name (partial match supported) |

**Examples:**
```bash
magister grades subject wiskunde
magister grades subject "ne"
magister grades subject engels
```

#### `magister grades subjects`

List all subjects.

```bash
magister grades subjects [--school <schoolcode>]
```

**Output includes:**
- Subject name
- Subject code
- Main teacher

#### `magister grades enrollments`

Show all enrollments (school years).

```bash
magister grades enrollments [--school <schoolcode>]
```

#### `magister grades trends`

Analyze grade trends over time.

```bash
magister grades trends [OPTIONS]
```

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--period` | `-p` | Analysis period in days | `90` |
| `--school` | `-s` | School code | - |

**Output includes:**
- Current average per subject
- Trend indicator (↑ improving, ↓ declining, → stable)
- Number of grades
- Min-Max range

**Examples:**
```bash
magister grades trends
magister grades trends --period 30
magister grades trends --period 180
```

#### `magister grades stats`

Show detailed grade statistics.

```bash
magister grades stats [--school <schoolcode>]
```

**Output includes:**
- Average, median, standard deviation per subject
- Highest and lowest grades
- Total grade count

#### `magister grades raw`

Debug command showing raw API response.

```bash
magister grades raw [OPTIONS]
```

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--school` | `-s` | School code | - |
| `--limit` | `-n` | Number of grades | `10` |

---

### Schedule

The `schedule` command group shows your class timetable.

#### `magister schedule today` / `magister schedule dag`

Show today's schedule.

```bash
magister schedule today [--school <schoolcode>]
```

#### `magister schedule tomorrow` / `magister schedule morgen`

Show tomorrow's schedule.

```bash
magister schedule tomorrow [--school <schoolcode>]
```

#### `magister schedule week`

Show this week's schedule.

```bash
magister schedule week [--school <schoolcode>]
```

#### `magister schedule date`

Show schedule for a specific date.

```bash
magister schedule date <date> [--school <schoolcode>]
```

| Argument | Description |
|----------|-------------|
| `date` | Date in format `DD-MM-YYYY` or `DD-MM` |

**Examples:**
```bash
magister schedule date 15-01-2026
magister schedule date 15-01
```

#### `magister schedule changes`

Show only schedule changes (cancellations and modifications).

```bash
magister schedule changes [OPTIONS]
```

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--days` | `-d` | Number of days ahead | `7` |
| `--school` | `-s` | School code | - |

**Examples:**
```bash
magister schedule changes
magister schedule changes --days 14
```

---

### Messages

The `messages` command group manages your Magister inbox.

#### `magister messages inbox` / `magister messages list`

Show inbox messages.

```bash
magister messages inbox [OPTIONS]
```

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--top` | `-n` | Number of messages to show | `25` |
| `--unread` | `-u` | Show only unread messages | `false` |
| `--school` | `-s` | School code | - |

**Examples:**
```bash
magister messages inbox
magister messages inbox --unread
magister messages inbox --top 50
```

#### `magister messages sent`

Show sent messages.

```bash
magister messages sent [OPTIONS]
```

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--top` | `-n` | Number of messages to show | `25` |
| `--school` | `-s` | School code | - |

#### `magister messages read`

Read a specific message.

```bash
magister messages read <message_id> [OPTIONS]
```

| Argument | Description |
|----------|-------------|
| `message_id` | Message ID |

| Option | Description | Default |
|--------|-------------|---------|
| `--mark-read/--no-mark-read` | Mark message as read | `true` |
| `--school` | School code | - |

**Examples:**
```bash
magister messages read 12345
magister messages read 12345 --no-mark-read
```

#### `magister messages mark-read`

Mark a message as read.

```bash
magister messages mark-read <message_id> [--school <schoolcode>]
```

#### `magister messages delete`

Delete a message.

```bash
magister messages delete <message_id> [OPTIONS]
```

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--force` | `-f` | Skip confirmation prompt | `false` |
| `--school` | `-s` | School code | - |

**Examples:**
```bash
magister messages delete 12345
magister messages delete 12345 --force
```

#### `magister messages count`

Show number of unread messages.

```bash
magister messages count [--school <schoolcode>]
```

---

### Download

#### `magister download`

Download all homework attachments.

```bash
magister download [OPTIONS]
```

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--days` | `-d` | Number of days to look ahead | `7` |
| `--subject` | `-s` | Filter by subject (partial match) | - |
| `--output` | `-o` | Output directory | `./magister_bijlagen` |
| `--school` | | School code | - |

Attachments are organized in subdirectories by subject.

**Examples:**
```bash
# Download all attachments
magister download

# Download for next 14 days
magister download --days 14

# Filter by subject
magister download --subject engels

# Custom output directory
magister download --output ./studiematerialen
```

---

### Export

The `export` command group exports data to iCal format for use with calendar apps.

#### `magister export schedule`

Export schedule to iCal format.

```bash
magister export schedule [OPTIONS]
```

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--days` | `-d` | Number of days to export | `14` |
| `--output` | `-o` | Output file (.ics) | `./magister_rooster.ics` |
| `--school` | | School code | - |

**Compatible with:**
- Google Calendar
- Apple Calendar
- Microsoft Outlook
- Other iCal-compatible apps

**Examples:**
```bash
magister export schedule
magister export schedule --days 30 --output rooster.ics
```

#### `magister export homework`

Export homework to iCal format (as all-day events on deadline dates).

```bash
magister export homework [OPTIONS]
```

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--days` | `-d` | Number of days ahead | `14` |
| `--output` | `-o` | Output file (.ics) | `./magister_huiswerk.ics` |
| `--school` | | School code | - |
| `--completed` | `-c` | Include completed homework | `false` |

**Examples:**
```bash
magister export homework
magister export homework --days 30 --output huiswerk.ics
```

#### `magister export all`

Export both schedule and homework to iCal files.

```bash
magister export all [OPTIONS]
```

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--days` | `-d` | Number of days ahead | `14` |
| `--output` | `-o` | Output directory | Current directory |
| `--school` | | School code | - |

Creates two files:
- `magister_rooster.ics`
- `magister_huiswerk.ics`

**Examples:**
```bash
magister export all
magister export all --days 30 --output ./exports
```

---

### Notifications

The `notify` command group manages desktop notifications for Magister changes.

#### `magister notify setup`

Interactive setup wizard for notifications.

```bash
magister notify setup [--school <schoolcode>]
```

Steps through:
1. Testing desktop notifications
2. Initializing baseline data
3. Instructions for automation

#### `magister notify check`

Check for changes and send notifications.

```bash
magister notify check [OPTIONS]
```

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--school` | | School code | - |
| `--quiet` | `-q` | Only show changes, no notifications | `false` |

On first run, saves current state as baseline. Subsequent runs detect and notify about:
- New grades
- Schedule changes (cancellations, modifications)
- Upcoming homework deadlines

**Examples:**
```bash
magister notify check
magister notify check --quiet
```

#### `magister notify test`

Send a test notification.

```bash
magister notify test [--school <schoolcode>]
```

#### `magister notify status`

Show notification status and configuration.

```bash
magister notify status [--school <schoolcode>]
```

**Shows:**
- Initialization status
- Last check time
- Enabled notification types
- Quiet hours
- Tracked items count

#### `magister notify reset`

Reset notification state (triggers re-initialization).

```bash
magister notify reset [OPTIONS]
```

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--force` | `-f` | Skip confirmation prompt | `false` |
| `--school` | | School code | - |

**Automation with cron:**
```bash
# Check every 30 minutes
*/30 * * * * cd /path/to/magister-cli && source .venv/bin/activate && magister notify check --quiet
```

**Default Configuration:**
- Quiet hours: 22:00 - 07:00 (no notifications)
- Homework reminder: 24 hours before deadline
- All notification types enabled (grades, schedule, homework)

---

### Configuration

The `config` command group manages CLI settings.

#### `magister config show`

Show all configuration settings.

```bash
magister config show
```

**Displays:**
- Current value for each setting
- Source (config file, environment variable, or default)
- Description

#### `magister config set`

Set a configuration value.

```bash
magister config set <key> <value>
```

**Available settings:**

| Key | Type | Description | Example |
|-----|------|-------------|---------|
| `school` | string | Default school code | `jouwschool` |
| `username` | string | Username hint for login | `jan.jansen` |
| `timeout` | int | HTTP timeout in seconds (5-120) | `30` |
| `headless` | bool | Run browser in headless mode | `true` |
| `oauth_callback_port` | int | Port for OAuth callback (1024-65535) | `8080` |
| `oauth_timeout` | int | OAuth flow timeout in seconds (30-600) | `300` |

**Examples:**
```bash
magister config set school jouwschool
magister config set timeout 60
magister config set headless false
```

#### `magister config get`

Get a specific configuration value.

```bash
magister config get <key>
```

**Examples:**
```bash
magister config get school
```

#### `magister config reset`

Reset all configuration to defaults.

```bash
magister config reset [--force]
```

| Option | Short | Description |
|--------|-------|-------------|
| `--force` | `-f` | Skip confirmation prompt |

#### `magister config edit`

Open configuration file in default editor.

```bash
magister config edit
```

#### `magister config path`

Show path to configuration file.

```bash
magister config path
```

**Config file location:** `~/.config/magister-cli/config.yaml`

---

### Shell Completion

The `completion` command group manages shell autocompletion.

#### `magister completion install`

Install shell completion.

```bash
magister completion install [--shell <shell>]
```

| Option | Short | Description |
|--------|-------|-------------|
| `--shell` | `-s` | Shell type: `bash`, `zsh`, or `fish` |

Auto-detects shell if not specified.

**Examples:**
```bash
magister completion install
magister completion install --shell zsh
```

#### `magister completion show`

Show completion script for your shell.

```bash
magister completion show [--shell <shell>]
```

#### `magister completion status`

Show shell completion status.

```bash
magister completion status
```

**Alternative method:**
```bash
# Use Typer's built-in completion
magister --install-completion bash
magister --install-completion zsh
magister --install-completion fish
```

---

## MCP Server (Claude Integration)

Magister CLI includes an MCP (Model Context Protocol) server that allows Claude and other AI agents to access Magister data directly. The server is designed with **agent-native architecture**: agents have full parity with users and can persist context across sessions.

### Configuration in Claude Desktop

Add to your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "magister": {
      "command": "magister-mcp"
    }
  }
}
```

### Available MCP Tools

#### Data Access Tools

| Tool | Description |
|------|-------------|
| `get_student_summary` | Complete daily overview (homework, grades, schedule) |
| `get_homework` | Retrieve homework with filters |
| `search_homework` | Search homework by text query |
| `get_upcoming_tests` | Upcoming tests |
| `get_recent_grades` | Recent grades with average |
| `get_grade_overview` | Per-subject grade averages |
| `get_grade_trends` | Identify improving/declining subjects |
| `get_grades_by_subject` | Grades for a specific subject |
| `get_today_schedule` | Today's schedule |
| `get_schedule` | Schedule for a date range |
| `get_messages` | Read inbox messages |
| `read_message` | Read full message content |
| `get_study_guides` | List study guides |
| `get_study_guide_details` | Full study guide with sections |
| `get_assignments` | ELO assignments |
| `get_learning_materials` | Digital textbooks and resources |

#### Agent Primitives (Low-Level)

| Tool | Description |
|------|-------------|
| `list_attachments` | List attachments from homework, messages, or study guides |
| `download_attachment` | Download a single attachment by ID |
| `check_notifications` | Check for new grades, schedule changes, homework |
| `export_schedule_ical` | Export schedule to .ics file |
| `export_homework_ical` | Export homework to .ics file |

#### Context & Memory

| Tool | Description |
|------|-------------|
| `read_context` | Read agent context file (preferences, activity, cached data) |
| `update_context` | Update preferences, cache data, or session notes |
| `discover_capabilities` | Discover available tools and authentication status |

#### Authentication

| Tool | Description |
|------|-------------|
| `check_auth_status` | Check if authenticated for a school |
| `authenticate` | Launch browser authentication |
| `refresh_token` | Silent token refresh |
| `refresh_authentication` | Try silent refresh, fallback to browser |

#### Configuration

| Tool | Description |
|------|-------------|
| `get_config` | Get current CLI configuration |
| `set_config` | Set a configuration value |

### MCP Resources

The server also exposes read-only resources:

| Resource URI | Description |
|--------------|-------------|
| `magister://context/{school_code}` | Agent context file content |
| `magister://capabilities` | Available capabilities |
| `magister://status` | Authentication status for configured school |

### Agent-Native Features

**Context Persistence**: Agents can save preferences, cache summaries, and maintain session notes using `update_context`. Context is stored per-school in `~/.config/magister-cli/{school}/context.md`.

**Capability Discovery**: The `discover_capabilities` tool lets agents understand what's available before making requests, enabling autonomous planning.

**Low-Level Primitives**: Agents can compose complex operations from primitives like `list_attachments` + `download_attachment` for fine-grained control.

### Example Claude Prompts

- "What homework do I have today?"
- "What tests do I have in the next 2 weeks?"
- "How are my grades looking? Are there any subjects I should focus on?"
- "Download all attachments for math"
- "Search for homework about 'Pythagoras'"
- "Check if I have any new grades or schedule changes"
- "Remember that I prefer 14 days lookahead for homework"

---

## Configuration Options

### Environment Variables

```bash
# School code (optional, can use --school flag instead)
export MAGISTER_SCHOOL=jouwschool

# OAuth timeout in seconds (default: 120)
export MAGISTER_OAUTH_TIMEOUT=180

# Headless browser mode (default: false)
export MAGISTER_HEADLESS=true
```

### Config File

Location: `~/.config/magister-cli/config.yaml`

```yaml
school: jouwschool
headless: false
timeout: 30
oauth_timeout: 120
```

---

## Architecture

```
magister-cli/
├── src/magister_cli/
│   ├── api/              # Magister API client
│   ├── auth/             # OAuth authentication
│   ├── cli/              # CLI commands and formatters
│   │   ├── commands/     # Typer subcommands
│   │   ├── formatters.py # Rich output formatting
│   │   └── progress.py   # Progress indicators
│   ├── mcp/              # MCP server for Claude
│   │   └── server.py     # FastMCP tools
│   ├── services/         # Business logic
│   │   ├── core.py       # I/O agnostic domain objects
│   │   ├── async_magister.py  # Async service
│   │   └── sync_magister.py   # Sync wrapper
│   └── config.py         # Settings
└── tests/
```

### Design Principles

- **Async-first**: Primary implementation is async for parallel API calls
- **I/O agnostic core**: Business logic separated from I/O
- **MCP-ready**: All CLI functionality available as MCP tools
- **Rich progress**: Clear feedback via spinners and progress bars

---

## Development

```bash
# Install dev dependencies
uv pip install -e ".[dev]"

# Run tests
pytest

# Linting
ruff check .
ruff format .

# Test MCP server
mcp dev magister_cli/mcp/server.py
```

---

## License

MIT

## Contributing

Pull requests welcome! Please ensure tests pass and code is formatted with ruff.
