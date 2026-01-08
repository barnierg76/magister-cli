---
status: complete
priority: p1
issue_id: "001"
tags: [code-review, security, data-integrity]
dependencies: []
---

# Non-Atomic State File Writes - Data Corruption Risk

## Problem Statement

The StateTracker writes state files using non-atomic operations. If the process crashes, power fails, or disk fills during the write, the state file becomes corrupted (partial JSON), leading to permanent data loss of all tracked grades, schedule entries, and homework notifications.

**Why it matters:** Users will lose notification history and receive duplicate or missing notifications. All tracked state (potentially years of data) can be lost in a single crash.

## Findings

**Location:** `services/state_tracker.py:60-64`

```python
def _save_state(self, state: dict[str, Any]) -> None:
    """Save state to file."""
    state["last_check"] = datetime.now().isoformat()
    with open(self.state_file, "w") as f:  # Truncates immediately!
        json.dump(state, f, indent=2, default=str)
```

**Evidence:**
1. File opened in write mode truncates existing content immediately
2. If crash occurs mid-write, file contains invalid JSON
3. Next read catches `JSONDecodeError` and returns empty state
4. All previously tracked entries are lost

**Data Corruption Scenario:**
1. User has 100 tracked grades in state file
2. System calls `_save_state()` to add grade #101
3. Halfway through `json.dump()`, process crashes
4. State file now contains: `{"grades": {"1": {"vak": "Mat`
5. All 100 grades lost - user gets flooded with 100 "new grade" notifications

## Proposed Solutions

### Option A: Atomic Write with Temp File + Rename (Recommended)
```python
def _save_state(self, state: dict[str, Any]) -> None:
    state["last_check"] = datetime.now().isoformat()
    temp_file = self.state_file.with_suffix('.tmp')
    with open(temp_file, 'w') as f:
        json.dump(state, f, indent=2, default=str)
        f.flush()
        os.fsync(f.fileno())  # Ensure written to disk
    temp_file.replace(self.state_file)  # Atomic on POSIX
```

**Pros:** Truly atomic, crash-safe, standard pattern
**Cons:** Requires import os, slightly more code
**Effort:** Small (30 min)
**Risk:** Low

### Option B: Write to Backup First
Write to backup file, then write to main file.

**Pros:** Simple recovery path
**Cons:** Not truly atomic, still has race window
**Effort:** Small
**Risk:** Medium - still vulnerable to crashes

## Recommended Action
<!-- To be filled during triage -->

## Technical Details

**Affected files:**
- `services/state_tracker.py:60-64` - Main save method
- Called from lines 133, 203, 266 (grades, schedule, homework tracking)

**Related issues:**
- #002 (file locking for concurrent access)
- #003 (unbounded state file growth)

## Acceptance Criteria

- [ ] State file writes use atomic temp file + rename pattern
- [ ] `os.fsync()` called before rename to ensure data on disk
- [ ] Existing state preserved if write fails
- [ ] Unit test for crash recovery scenario

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-01-08 | Created from code review | Critical data integrity issue |

## Resources

- PR: N/A (code review of entire codebase)
- Similar pattern: https://stackoverflow.com/questions/2333872/atomic-writing-to-file-with-python
