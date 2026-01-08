---
status: complete
priority: p3
issue_id: "014"
tags: [code-review, security]
dependencies: []
---

# Token May Be Exposed in Debug Output

## Problem Statement

The `TokenData` class has no `__repr__` or `__str__` override, meaning if accidentally printed or logged, the full access token will be exposed.

**Why it matters:** Developers debugging could accidentally expose tokens in logs or terminal.

## Findings

**Location:** `auth/token_manager.py:16-53`

**Evidence:**
- TokenData is a dataclass with `access_token: str` field
- Default dataclass repr includes all fields
- `console.print(token)` would expose the token

## Proposed Solutions

### Option A: Add Redacting __repr__ (Recommended)
```python
@dataclass
class TokenData:
    access_token: str
    # ...

    def __repr__(self) -> str:
        return f"TokenData(school={self.school!r}, person_name={self.person_name!r}, expires_at={self.expires_at!r}, access_token='***')"
```

**Pros:** Prevents accidental exposure
**Cons:** Minor code addition
**Effort:** Small (15 min)
**Risk:** Low

## Recommended Action
<!-- To be filled during triage -->

## Technical Details

**Affected files:**
- `auth/token_manager.py:16-53`

## Acceptance Criteria

- [ ] TokenData.__repr__ redacts access_token
- [ ] Token never appears in logs
- [ ] Audit all print/log statements for token refs

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-01-08 | Created from code review | Security best practice |

## Resources

- Security analysis report
