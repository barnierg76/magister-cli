---
status: complete
priority: p2
issue_id: "007"
tags: [code-review, performance]
dependencies: []
---

# Sequential Download in Async Service

## Problem Statement

`download_all_attachments()` downloads files sequentially despite using async infrastructure, severely underutilizing network bandwidth.

**Why it matters:** 5 attachments × 500ms each = 2.5 seconds. Large files = minutes of waiting.

## Findings

**Location:** `services/async_magister.py:415-459`

```python
for item in homework:
    for att in item.attachments:
        try:
            path = await self.download_attachment(att, subject_dir)  # Sequential!
```

**Performance Impact:**
- 5 attachments × 500ms = 2.5 seconds
- 20 attachments = 10 seconds
- Large files = minutes

## Proposed Solutions

### Option A: Parallel Downloads with Semaphore (Recommended)
```python
async def download_all_attachments(...):
    semaphore = asyncio.Semaphore(5)  # Max 5 concurrent

    async def download_with_limit(item, att, dir):
        async with semaphore:
            return await self.download_attachment(att, dir)

    tasks = [
        download_with_limit(item, att, subject_dir)
        for item in homework
        for att in item.attachments
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
```

**Pros:** 5-10x performance improvement
**Cons:** Need to handle partial failures
**Effort:** Small (1-2 hours)
**Risk:** Low

## Recommended Action
<!-- To be filled during triage -->

## Technical Details

**Affected files:**
- `services/async_magister.py:415-459`

**Expected Performance Gain:** 5-10x with bandwidth-limited ceiling

## Acceptance Criteria

- [ ] Downloads run concurrently with semaphore limit
- [ ] Partial failures don't stop other downloads
- [ ] Progress reporting still works

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-01-08 | Created from code review | Performance bottleneck |

## Resources

- Performance analysis report
