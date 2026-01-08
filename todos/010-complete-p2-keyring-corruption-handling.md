---
status: complete
priority: p2
issue_id: "010"
tags: [code-review, data-integrity, auth]
dependencies: []
---

# Keyring Corruption Not Handled

## Problem Statement

If keyring data becomes corrupted (malformed JSON, missing fields), the corrupt data remains indefinitely. Users cannot authenticate until they manually clear keyring.

**Why it matters:** Silent failure makes debugging difficult. Users stuck in auth loop.

## Findings

**Location:** `auth/token_manager.py:81-91`

```python
def get_token(self) -> TokenData | None:
    data_json = keyring.get_password(SERVICE_NAME, key)
    if not data_json:
        return None
    try:
        data = json.loads(data_json)
        return TokenData.from_dict(data)
    except (json.JSONDecodeError, KeyError):
        return None  # Silent failure - corrupted token stays!
```

**Issue:** Corrupt data never cleared, stays in keyring forever.

## Proposed Solutions

### Option A: Auto-Clear on Corruption (Recommended)
```python
except (json.JSONDecodeError, KeyError) as e:
    logger.warning(f"Corrupted token in keyring: {e}. Clearing...")
    try:
        keyring.delete_password(SERVICE_NAME, key)
    except Exception:
        pass
    return None
```

**Pros:** Self-healing, no manual intervention
**Cons:** May lose valid token in edge case
**Effort:** Small (30 min)
**Risk:** Low

## Recommended Action
<!-- To be filled during triage -->

## Technical Details

**Affected files:**
- `auth/token_manager.py:81-91`

## Acceptance Criteria

- [ ] Corrupted keyring entries auto-cleared
- [ ] Warning logged when corruption detected
- [ ] User can re-login after corruption

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-01-08 | Created from code review | Data integrity issue |

## Resources

- Data integrity analysis report
