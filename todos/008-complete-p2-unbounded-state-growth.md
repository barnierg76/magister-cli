---
status: complete
priority: p2
issue_id: "008"
tags: [code-review, data-integrity, performance]
dependencies: []
---

# Unbounded State File Growth

## Problem Statement

State files grow indefinitely with no cleanup mechanism. Grades, schedule entries, and homework notifications are never removed, leading to slow JSON parsing and disk space issues over time.

**Why it matters:** After 5 years: ~1 MB state file. JSON parsing becomes O(n) bottleneck.

## Findings

**Location:** `services/state_tracker.py:85-266`

**Evidence:**
```python
# Grades never removed (line 125-130)
known_grades[grade_id] = { "vak": ..., "seen_at": ... }

# Schedule entries never removed (line 194-200)
known_schedule[apt_id] = { ... }

# Homework notifications accumulate (line 258-263)
notified_homework[notification_key] = { ... }
```

**Growth Projection:**
- 10 grades/week × 40 weeks = 400 grades/year
- 20 appointments/week × 40 weeks = 800 entries/year
- ~1400 entries/year × 150 bytes = ~210 KB/year
- 5 years = ~1 MB state file

## Proposed Solutions

### Option A: Time-Based Cleanup (Recommended)
```python
def _cleanup_old_entries(self, state: dict) -> None:
    cutoff = datetime.now() - timedelta(days=90)

    state["grades"] = {
        k: v for k, v in state.get("grades", {}).items()
        if datetime.fromisoformat(v.get("seen_at", "")) > cutoff
    }
    # Same for schedule and homework
```

Call in `_save_state()` before writing.

**Pros:** Simple, automatic cleanup
**Cons:** 90 days may not be right for all users
**Effort:** Small (1 hour)
**Risk:** Low

## Recommended Action
<!-- To be filled during triage -->

## Technical Details

**Affected files:**
- `services/state_tracker.py`

## Acceptance Criteria

- [ ] Old entries (>90 days) automatically removed
- [ ] Retention period configurable
- [ ] Cleanup runs on save, not load

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-01-08 | Created from code review | Long-term maintenance issue |

## Resources

- Data integrity analysis report
