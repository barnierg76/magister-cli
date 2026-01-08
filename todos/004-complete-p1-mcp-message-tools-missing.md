---
status: complete
priority: p1
issue_id: "004"
tags: [code-review, agent-native, mcp]
dependencies: []
---

# MCP Server Missing Message System Tools

## Problem Statement

The MCP server exposes only 18% of CLI functionality to AI agents. Most critically, the entire message system (inbox, sent, unread count) has ZERO agent access, making the CLI useless for agent-assisted message management.

**Why it matters:** Agents cannot help users with "Check if I have any new messages from my teacher" or any message-related tasks.

## Findings

**Location:** `mcp/server.py` - No message tools defined

**Evidence:**
- `messages.py` has 361 lines of message functionality
- MCP server has 0 message-related tools
- User can: list inbox, read message, mark as read, delete, count unread
- Agent can: NONE of the above

**Capability Gap:**
| CLI Command | MCP Tool | Status |
|-------------|----------|--------|
| `messages inbox` | None | MISSING |
| `messages read <id>` | None | MISSING |
| `messages unread` | None | MISSING |
| `messages mark-read <id>` | None | MISSING |

## Proposed Solutions

### Option A: Add Core Message Tools (Recommended)
```python
@mcp.tool()
async def get_messages(
    school_code: str,
    folder: str = "inbox",  # inbox, sent
    limit: int = 25,
    unread_only: bool = False,
) -> dict

@mcp.tool()
async def read_message(school_code: str, message_id: int) -> dict

@mcp.tool()
async def get_unread_count(school_code: str) -> dict

@mcp.tool()
async def mark_message_read(school_code: str, message_id: int) -> dict
```

**Pros:** Covers most common use cases
**Cons:** Doesn't cover delete (safer)
**Effort:** Medium (3-4 hours)
**Risk:** Low

### Option B: Full Message Parity
Add all message operations including delete.

**Pros:** Complete feature parity
**Cons:** Delete is risky for agents to have
**Effort:** Medium-Large
**Risk:** Medium (delete capability)

## Recommended Action
<!-- To be filled during triage -->

## Technical Details

**Files to modify:**
- `mcp/server.py` - Add 4 new tools
- `services/async_magister.py` - Add async message methods (may already exist)

**Related issues:**
- #005 (grade analysis tools missing)
- #006 (schedule changes tools missing)

## Acceptance Criteria

- [ ] `get_messages` tool returns inbox/sent messages
- [ ] `read_message` tool returns full message content
- [ ] `get_unread_count` tool returns count
- [ ] `mark_message_read` tool marks messages as read
- [ ] Error handling follows existing MCP patterns

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-01-08 | Created from code review | Agent-native gap analysis |

## Resources

- Agent-native review report
- Existing message implementation in `messages.py`
