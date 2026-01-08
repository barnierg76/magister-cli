---
status: complete
priority: p1
issue_id: "003"
tags: [code-review, architecture, duplication]
dependencies: []
---

# Critical Code Duplication - Multiple Class Definitions

## Problem Statement

The codebase has duplicate definitions of the same classes in different files, creating maintenance burden, potential for divergence, and confusion about which version to use.

**Why it matters:**
- Security-critical code (`_sanitize_filename`) is duplicated - fixes must be applied twice
- Different behavior between versions causes subtle bugs
- Developers don't know which class to import

## Findings

### Duplicate 1: HomeworkItem (2 implementations)

**Location 1:** `services/homework.py:34-68`
```python
@dataclass
class HomeworkItem:
    raw: Afspraak = field(default=None)  # API coupling
    attachments: list[AttachmentInfo]
```

**Location 2:** `services/core.py:34-63`
```python
@dataclass
class HomeworkItem:
    afspraak_id: Optional[int] = None  # Decoupled
    attachments: List[AttachmentInfo]
    def to_dict(self) -> dict:  # Has serialization
```

**Key Differences:**
- `homework.py` stores full `Afspraak` object (heavier, API-coupled)
- `core.py` stores only ID + has `to_dict()` method

### Duplicate 2: AttachmentInfo (2 implementations)

**Location 1:** `services/homework.py:12-30` (with `raw: Bijlage`)
**Location 2:** `services/core.py:13-30` (with `download_url: str`)

### Duplicate 3: HomeworkDay (2 implementations)

**Location 1:** `services/homework.py:72-124`
**Location 2:** `services/core.py:67-117`

### Duplicate 4: _sanitize_filename (SECURITY CRITICAL)

**Location 1:** `api/resources/attachments.py:16-32`
**Location 2:** `services/async_magister.py:26-42`

**Risk:** Security fix applied to one location leaves other vulnerable.

## Proposed Solutions

### Option A: Consolidate to core.py (Recommended)
1. Keep only `core.py` versions (I/O agnostic, has serialization)
2. Delete duplicates from `homework.py`
3. Update all imports to use `core.py`
4. Extract `_sanitize_filename` to `utils/files.py`

**Pros:** Single source of truth, cleaner architecture
**Cons:** Migration effort, need to update consumers
**Effort:** Medium (4-6 hours)
**Risk:** Low - mostly deletions

### Option B: Gradual Deprecation
Add deprecation warnings to `homework.py`, migrate consumers over time.

**Pros:** Lower immediate risk
**Cons:** Longer maintenance burden
**Effort:** Small now, medium later
**Risk:** Low

## Recommended Action
<!-- To be filled during triage -->

## Technical Details

**Files to modify:**
- DELETE: `services/homework.py` (or heavily refactor)
- KEEP: `services/core.py`
- CREATE: `utils/files.py` (for `_sanitize_filename`)
- UPDATE: All importers of `HomeworkItem`, `AttachmentInfo`, `HomeworkDay`

**LOC Reduction:** ~400 lines

## Acceptance Criteria

- [ ] Single definition of each class
- [ ] `_sanitize_filename` in one location only
- [ ] All consumers updated to use consolidated classes
- [ ] No duplicate Dutch month/day name arrays

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-01-08 | Created from code review | Critical architecture issue |

## Resources

- Pattern analysis report from review
