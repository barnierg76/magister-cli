---
status: complete
priority: p3
issue_id: "013"
tags: [code-review, security]
dependencies: []
---

# State File World-Readable Permissions

## Problem Statement

State files created in `~/.config/magister-cli/state_{school}.json` may have default permissions (0644), making them readable by other users on multi-user systems.

**Why it matters:** State data contains grade IDs and schedule info (PII).

## Findings

**Location:** `services/state_tracker.py:63-64`

```python
with open(self.state_file, "w") as f:
    json.dump(state, f, indent=2, default=str)
```

**Issue:** No explicit permission setting. Inherits umask (often 0022 = world-readable).

## Proposed Solutions

### Option A: Set Restrictive Permissions (Recommended)
```python
import os

# Before writing
os.chmod(self.state_file, 0o600)  # Owner read/write only
with open(self.state_file, "w") as f:
    json.dump(state, f)
```

**Pros:** Protects PII on shared systems
**Cons:** Minor code change
**Effort:** Small (30 min)
**Risk:** Low

## Recommended Action
<!-- To be filled during triage -->

## Technical Details

**Affected files:**
- `services/state_tracker.py:63-64`
- `config.py:32-33` (if writing config files)

## Acceptance Criteria

- [ ] State files have 0600 permissions
- [ ] Config files have restrictive permissions

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-01-08 | Created from code review | Security best practice |

## Resources

- Security analysis report
