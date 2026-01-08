# Code Review Fixes - Magister CLI

## Overview

Address critical findings from the comprehensive code review of the `feature/agent-native-improvements` branch. Prioritizes security vulnerabilities, then architectural issues, then agent-native improvements.

## Phase 1: Security Fixes (P1 - Required Before Merge)

### 1.1 Path Traversal Vulnerability
**Files:** `api/resources/attachments.py:79`, `services/async_magister.py:370`

**Problem:** Filenames from API responses used directly in file paths without sanitization.

**Fix:**
```python
# Add to api/resources/attachments.py
def _sanitize_filename(self, filename: str) -> str:
    """Sanitize filename to prevent path traversal."""
    safe_name = filename.replace('/', '_').replace('\\', '_').replace('..', '_')
    if len(safe_name) > 255:
        safe_name = safe_name[:255]
    return safe_name or "unnamed_file"

def download(self, bijlage: Bijlage, output_dir: Path | None = None) -> Path:
    # ... existing code ...
    safe_filename = self._sanitize_filename(bijlage.naam)
    output_path = (output_dir / safe_filename).resolve()

    # Validate path is within output_dir
    if not str(output_path).startswith(str(output_dir.resolve())):
        raise MagisterAPIError(f"Invalid filename: {bijlage.naam}", 400)
```

**Acceptance Criteria:**
- [ ] Filenames sanitized in `attachments.py`
- [ ] Filenames sanitized in `async_magister.py`
- [ ] Path validation ensures files stay within output directory

---

### 1.2 XSS in OAuth Callback
**File:** `auth/browser_auth.py:60-70`

**Problem:** Error messages rendered in HTML without escaping.

**Fix:**
```python
import html

def _send_error_response(self, error: str):
    """Send error HTML response."""
    self.send_response(400)
    self.send_header("Content-type", "text/html")
    self.send_header("X-Content-Type-Options", "nosniff")
    self.send_header("X-Frame-Options", "DENY")
    self.end_headers()

    safe_error = html.escape(error)  # Escape HTML entities
    # ... rest of HTML template using safe_error
```

**Acceptance Criteria:**
- [ ] Error messages HTML-escaped
- [ ] Security headers added (X-Content-Type-Options, X-Frame-Options)

---

### 1.3 School Code Validation
**Files:** `auth/browser_auth.py:137`, `api/client.py:77`, `mcp/server.py` (all tools)

**Problem:** School code used in URLs without validation, enabling SSRF/phishing.

**Fix:**
```python
# Add to config.py or a new validation.py
import re

def validate_school_code(school: str) -> str:
    """Validate school code format."""
    if not school:
        raise ValueError("School code cannot be empty")
    if not re.match(r'^[a-zA-Z0-9-]+$', school):
        raise ValueError(f"Invalid school code: {school}")
    if len(school) > 50:
        raise ValueError("School code too long")
    return school.lower()
```

**Apply to:**
- [ ] `BrowserAuthenticator.__init__`
- [ ] `MagisterClient.__init__`
- [ ] `MagisterAsyncService.__init__`
- [ ] All MCP tool functions

---

### 1.4 Sanitize Error Messages
**Files:** `api/base.py:44`, `mcp/server.py:64-71`

**Problem:** Raw exception details exposed to users.

**Fix:**
```python
# api/base.py - Log detailed error, return generic message
if response.status_code >= 400:
    import logging
    logging.getLogger(__name__).error(f"API error: {response.status_code} - {response.text}")
    raise MagisterAPIError(f"API request failed ({response.status_code})", response.status_code)

# mcp/server.py - Generic errors with structured hints
except Exception as e:
    import logging
    logging.getLogger(__name__).exception("Tool error")
    return {"error": "Operation failed", "error_type": "internal_error"}
```

**Acceptance Criteria:**
- [ ] Raw API responses not exposed to users
- [ ] Detailed errors logged server-side
- [ ] Generic messages returned to users

---

## Phase 2: Architecture Fixes (P2 - Should Fix)

### 2.1 Consolidate Domain Models
**Problem:** `HomeworkItem`, `AttachmentInfo` defined in both `services/core.py` and `services/homework.py`

**Fix:**
1. Keep models in `services/core.py` (the newer, more complete version)
2. Update `services/homework.py` to import from `core.py`
3. Remove duplicate definitions from `homework.py`

```python
# services/homework.py - Remove duplicate dataclasses, import from core
from magister_cli.services.core import AttachmentInfo, HomeworkItem, HomeworkDay
```

**Acceptance Criteria:**
- [ ] Single definition of each domain model
- [ ] `homework.py` imports from `core.py`
- [ ] All tests pass

---

### 2.2 Create Error Handler Decorator
**Problem:** Same try/except block repeated 19+ times across CLI commands.

**Fix:**
```python
# cli/utils.py (new file)
from functools import wraps
import typer
from magister_cli.api import MagisterAPIError, TokenExpiredError
from magister_cli.cli.formatters import format_api_error, format_no_auth_error

def handle_api_errors(school_code_param: str = "school_code"):
    """Decorator to handle common API errors in CLI commands."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            school_code = kwargs.get(school_code_param)
            try:
                return f(*args, **kwargs)
            except TokenExpiredError:
                format_no_auth_error(console, school_code)
                raise typer.Exit(1)
            except RuntimeError as e:
                if "Not authenticated" in str(e):
                    format_no_auth_error(console, school_code)
                else:
                    console.print(f"[red]Error:[/red] {e}")
                raise typer.Exit(1)
            except MagisterAPIError as e:
                format_api_error(console, e)
                raise typer.Exit(1)
        return wrapper
    return decorator
```

**Apply to:** All CLI commands in `main.py`, `grades.py`, `schedule.py`, `messages.py`

**Acceptance Criteria:**
- [ ] Error handler decorator created
- [ ] Applied to all CLI commands
- [ ] Duplicate try/except blocks removed

---

### 2.3 Extract Response Parsing to Base Class
**Problem:** `data.get("Items", [])` pattern repeated 8+ times.

**Fix:**
```python
# api/base.py
class BaseResource:
    def _extract_items(self, data: Any) -> list:
        """Extract Items array from Magister API response."""
        return data.get("Items", []) if isinstance(data, dict) else data
```

**Acceptance Criteria:**
- [ ] Method added to BaseResource
- [ ] All resources use `_extract_items()`

---

### 2.4 Document Sync Service as Legacy
**File:** `services/sync_magister.py`

**Fix:** Add docstring warning about performance implications and recommending async.

**Acceptance Criteria:**
- [ ] Docstring updated with legacy warning
- [ ] Performance implications documented
- [ ] Migration example provided

---

## Phase 3: Agent-Native Improvements (P2 - Recommended)

### 3.1 Add Missing MCP Tools
**File:** `mcp/server.py`

**Add tools for:**
- [ ] `get_messages(school_code, folder="inbox", limit=25)` - Get inbox/sent messages
- [ ] `get_grade_overview(school_code)` - Averages per subject
- [ ] `get_schedule(school_code, start_date, end_date)` - Flexible date range
- [ ] `check_auth_status(school_code)` - Structured auth status (not just resource)

**Acceptance Criteria:**
- [ ] Message tools added (at minimum inbox)
- [ ] Grade overview tool added
- [ ] Flexible schedule tool added
- [ ] Auth status tool added
- [ ] Action parity improved from 27% to 50%+

---

### 3.2 Improve MCP Error Responses
**File:** `mcp/server.py`

**Fix:**
```python
# Structured error responses
return {
    "success": False,
    "error_type": "not_authenticated",  # Machine-readable
    "message": "Authentication required",
    "resolution": {
        "action": "login_required",
        "user_instruction": f"Run: magister login --school {school_code}"
    }
}
```

**Acceptance Criteria:**
- [ ] All tools return structured errors
- [ ] Error types are machine-readable
- [ ] Resolution hints included

---

### 3.3 Create MCP Error Handler Decorator
**Problem:** Same try/except in every MCP tool (6 occurrences).

**Fix:**
```python
# mcp/server.py
def mcp_error_handler(f):
    @wraps(f)
    async def wrapper(*args, **kwargs):
        school_code = kwargs.get('school_code', 'unknown')
        try:
            return await f(*args, **kwargs)
        except RuntimeError as e:
            return {"success": False, "error_type": "auth_error", ...}
        except Exception as e:
            logging.exception("MCP tool error")
            return {"success": False, "error_type": "internal_error", ...}
    return wrapper
```

**Acceptance Criteria:**
- [ ] MCP error handler decorator created
- [ ] Applied to all MCP tools
- [ ] Duplicate try/except blocks removed

---

## Implementation Order

1. **Security (1-2 hours)**
   - Path traversal fix (30 min)
   - XSS fix (15 min)
   - School code validation (30 min)
   - Error message sanitization (30 min)

2. **Architecture (1-2 hours)**
   - Consolidate domain models (30 min)
   - Error handler decorator (45 min)
   - Response parsing extraction (15 min)
   - Sync service documentation (15 min)

3. **Agent-Native (2-3 hours)**
   - Add missing MCP tools (1.5 hours)
   - Improve error responses (30 min)
   - MCP error handler decorator (30 min)

**Total Estimated Time: 4-7 hours**

---

## Testing

After each phase:
- [ ] Run `uv run pytest` - All tests pass
- [ ] Run `uv run ruff check` - No linting errors
- [ ] Run `uv run magister --help` - CLI works
- [ ] Test MCP server imports: `python -c "from magister_cli.mcp import mcp"`

---

## Out of Scope (P3 - Future)

These items are noted but not included in this plan:
- Progress utility simplification
- Service layer simplification
- Resource pattern flattening
- Rate limiting implementation
- Token encryption enhancement
