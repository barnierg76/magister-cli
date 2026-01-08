---
status: complete
priority: p1
issue_id: "002"
tags: [code-review, data-integrity, concurrency]
dependencies: []
---

# No File Locking for Concurrent State Access

## Problem Statement

Multiple processes can read/write the state file simultaneously with zero synchronization. This leads to race conditions and data loss when multiple CLI instances or cron jobs run concurrently.

**Why it matters:** Users running notification checks via cron while also using CLI manually will experience unpredictable data loss.

## Findings

**Location:** `services/state_tracker.py` (entire file)

**Evidence:**
- No `fcntl.flock()` or similar locking mechanism
- Read at line 49-50, write at line 63-64 are separate operations
- Classic "lost update" problem possible

**Data Corruption Scenario:**
1. User runs `magister notify check` in terminal (Process A)
2. Cron job runs same command simultaneously (Process B)
3. Both load state at T=0 (both see 10 tracked grades)
4. Process A detects 2 new grades → writes 12 grades at T=1
5. Process B detects 1 new grade → writes 11 grades at T=2
6. Process B overwrites Process A's changes
7. Result: 11 grades instead of 12 - one grade permanently lost

## Proposed Solutions

### Option A: POSIX File Locking (Recommended)
```python
import fcntl

def _load_state(self) -> dict[str, Any]:
    with open(self.state_file, 'r') as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_SH)  # Shared lock
        try:
            return json.load(f)
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)

def _save_state(self, state: dict[str, Any]) -> None:
    with open(self.state_file, 'w') as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)  # Exclusive lock
        try:
            json.dump(state, f, indent=2, default=str)
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
```

**Pros:** Standard POSIX pattern, works on macOS/Linux
**Cons:** Doesn't work on Windows (needs different approach)
**Effort:** Small (1 hour)
**Risk:** Low on POSIX, medium on Windows

### Option B: Lock File Pattern
Use separate `.lock` file with `filelock` library.

**Pros:** Cross-platform
**Cons:** External dependency
**Effort:** Small
**Risk:** Low

## Recommended Action
<!-- To be filled during triage -->

## Technical Details

**Affected files:**
- `services/state_tracker.py:37-64`

**Dependencies:**
- #001 (atomic writes) should be implemented together

## Acceptance Criteria

- [ ] File locking implemented for state file access
- [ ] Works on macOS and Linux
- [ ] Graceful handling if lock cannot be acquired
- [ ] Test for concurrent access scenario

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-01-08 | Created from code review | Critical for multi-process usage |

## Resources

- Python fcntl docs: https://docs.python.org/3/library/fcntl.html
