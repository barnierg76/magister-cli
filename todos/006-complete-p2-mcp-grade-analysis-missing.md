---
status: complete
priority: p2
issue_id: "006"
tags: [code-review, agent-native, mcp]
dependencies: []
---

# MCP Server Missing Grade Analysis Tools

## Problem Statement

Agents can fetch raw grades via `get_recent_grades` but cannot perform analysis that users can do via CLI: per-subject averages, trends, statistics. This severely limits agent utility for academic insights.

**Why it matters:** "How am I doing in Math?" - Agent can show raw grades but not average or trend.

## Findings

**Location:** `grades.py` lines 151-680 vs `mcp/server.py` (only `get_recent_grades`)

**Missing Capabilities:**
| CLI Command | MCP Tool | Status |
|-------------|----------|--------|
| `grades overview` | None | MISSING |
| `grades trends` | None | MISSING |
| `grades stats` | None | MISSING |
| `grades --subject <name>` | None | MISSING |

**User Experience Gap:**
- CLI: Rich analysis with averages, trends, min/max
- Agent: Raw list of grades only

## Proposed Solutions

### Option A: Add Analysis Tools (Recommended)
```python
@mcp.tool()
async def get_grade_overview(school_code: str) -> dict:
    """Per-subject averages and counts."""

@mcp.tool()
async def get_grade_trends(school_code: str, period_days: int = 90) -> dict:
    """Identifying improving/declining subjects."""

@mcp.tool()
async def get_grades_by_subject(school_code: str, subject: str) -> dict:
    """Filter grades by subject name."""
```

**Pros:** Enables meaningful academic insights
**Cons:** Additional maintenance
**Effort:** Medium (3-4 hours)
**Risk:** Low

## Recommended Action
<!-- To be filled during triage -->

## Technical Details

**Files to modify:**
- `mcp/server.py` - Add 3 new tools
- Reuse logic from `grades.py` commands

## Acceptance Criteria

- [ ] `get_grade_overview` returns per-subject averages
- [ ] `get_grade_trends` identifies improving/declining subjects
- [ ] `get_grades_by_subject` filters by subject name
- [ ] Tools use existing business logic from grades.py

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-01-08 | Created from code review | Agent-native gap |

## Resources

- Agent-native review report
