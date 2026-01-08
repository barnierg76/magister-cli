---
status: complete
priority: p2
issue_id: "011"
tags: [code-review, data-integrity]
dependencies: []
---

# Timezone-Naive Datetime Comparisons

## Problem Statement

Deadline calculations compare timezone-naive datetimes, leading to incorrect notifications during DST transitions or for users in different timezones.

**Why it matters:** Notifications may be 1 hour early/late during DST, or completely wrong for non-local timezones.

## Findings

**Location:** `services/state_tracker.py:229-235`

```python
deadline = datetime.fromisoformat(deadline_str.replace("Z", "+00:00"))
# ...
hours_until = (deadline - now).total_seconds() / 3600
```

**Issue:** `now = datetime.now()` is timezone-naive local time. Comparing with UTC deadline causes errors.

**Scenario:**
1. API returns: `2026-01-09T08:00:00Z` (UTC)
2. User in UTC+1 (Netherlands), system time 09:00 local (08:00 UTC)
3. Naive comparison thinks deadline passed
4. User gets notification 1 hour late (or never)

## Proposed Solutions

### Option A: Timezone-Aware Comparisons (Recommended)
```python
from datetime import timezone

deadline = datetime.fromisoformat(deadline_str.replace("Z", "+00:00"))
if deadline.tzinfo is None:
    deadline = deadline.replace(tzinfo=timezone.utc)
now = datetime.now(timezone.utc)
hours_until = (deadline - now).total_seconds() / 3600
```

**Pros:** Correct across all timezones
**Cons:** Minor code change
**Effort:** Small (1 hour)
**Risk:** Low

## Recommended Action
<!-- To be filled during triage -->

## Technical Details

**Affected files:**
- `services/state_tracker.py:229-235`
- Line 82, 129, 199 (similar issues)

## Acceptance Criteria

- [ ] All datetime comparisons use timezone-aware objects
- [ ] Correct behavior during DST transitions
- [ ] Test for timezone edge cases

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-01-08 | Created from code review | Data integrity issue |

## Resources

- Data integrity analysis report
