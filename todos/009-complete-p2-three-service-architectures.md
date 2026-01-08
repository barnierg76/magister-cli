---
status: complete
priority: p2
issue_id: "009"
tags: [code-review, architecture, simplification]
dependencies: ["003"]
---

# Three Competing Service Architectures

## Problem Statement

The codebase has THREE different ways to access Magister data:
1. MagisterClient (resource pattern)
2. HomeworkService (sync, direct API)
3. MagisterAsyncService (async)
4. MagisterSyncService (deprecated wrapper)

This creates confusion, maintenance burden, and inconsistent behavior.

**Why it matters:** Developers don't know which to use. Features added to one don't appear in others.

## Findings

**Evidence:**
- CLI commands: Mix of MagisterClient and HomeworkService
- MCP server: Uses MagisterAsyncService only
- Export commands: Uses HomeworkService

**Architecture Mismatch:**
```
DECLARED: CLI → Async Service → API
ACTUAL:   CLI → Legacy Sync Service → API
          MCP → Async Service → API
```

**LOC Waste:** ~800 lines of redundant code

## Proposed Solutions

### Option A: Consolidate to MagisterClient (Recommended)
1. Delete `HomeworkService`, `MagisterAsyncService`, `MagisterSyncService`
2. Add async support to `MagisterClient`
3. Update all consumers to use `MagisterClient`

**Pros:** Single source of truth, ~800 LOC reduction
**Cons:** Migration effort
**Effort:** Large (1-2 days)
**Risk:** Medium - need thorough testing

### Option B: Keep Async Service Only
Delete sync services, migrate CLI to use async with `asyncio.run()`.

**Pros:** Modern async architecture
**Cons:** Adds async complexity to CLI
**Effort:** Medium
**Risk:** Medium

## Recommended Action
<!-- To be filled during triage -->

## Technical Details

**Files to DELETE:**
- `services/homework.py` (~209 lines)
- `services/async_magister.py` (~462 lines)
- `services/sync_magister.py` (~232 lines)

**Files to UPDATE:**
- All CLI commands
- MCP server

## Acceptance Criteria

- [ ] Single service architecture
- [ ] All CLI commands work
- [ ] MCP tools work
- [ ] Performance maintained

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-01-08 | Created from code review | Major architecture issue |

## Resources

- Architecture analysis report
- Simplification analysis report
