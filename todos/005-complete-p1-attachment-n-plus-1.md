---
status: complete
priority: p1
issue_id: "005"
tags: [code-review, performance]
dependencies: []
---

# N+1 Query Pattern in Attachment Fetching

## Problem Statement

The `with_attachments()` method fetches attachment details sequentially for each appointment, causing N+1 API calls. 10 appointments with attachments = 11 API calls = 2+ seconds latency.

**Why it matters:** User-facing operations become unusably slow with many attachments. 50 appointments = 10+ seconds.

## Findings

**Location:** `api/resources/appointments.py:56-77`

```python
def with_attachments(self, start: date, end: date) -> list[Afspraak]:
    appointments = self.with_homework(start, end)
    result = []
    for afspraak in appointments:
        if afspraak.heeft_bijlagen:
            full = self.get(afspraak.id)  # Sequential API call!
            result.append(full)
        else:
            result.append(afspraak)
    return result
```

**Performance Impact:**
- 10 appointments with attachments = 11 API calls
- ~200ms per API call = 2+ seconds total
- 50 appointments = 10+ seconds
- 100 appointments = 20+ seconds

## Proposed Solutions

### Option A: Concurrent Fetching with asyncio.gather (Recommended)
```python
async def with_attachments(self, start: date, end: date) -> list[Afspraak]:
    appointments = await self.with_homework(start, end)

    # Batch fetch concurrently
    attachment_tasks = [
        self.get_async(a.id) for a in appointments if a.heeft_bijlagen
    ]
    detailed = await asyncio.gather(*attachment_tasks)

    # Merge results
    detailed_map = {d.id: d for d in detailed}
    return [detailed_map.get(a.id, a) for a in appointments]
```

**Pros:** 10-20x performance improvement
**Cons:** Requires async context
**Effort:** Medium (2-4 hours)
**Risk:** Low - purely optimization

### Option B: Batch API Endpoint (If Available)
Check if Magister API has batch fetch endpoint.

**Pros:** Single API call
**Cons:** Depends on API supporting batch
**Effort:** Small if exists, N/A if not
**Risk:** Low

## Recommended Action
<!-- To be filled during triage -->

## Technical Details

**Affected files:**
- `api/resources/appointments.py:56-77`
- `services/async_magister.py` (should use concurrent pattern)

**Expected Performance Gain:** 10-20x (2s → 200ms for 10 attachments)

## Acceptance Criteria

- [ ] Attachment details fetched concurrently
- [ ] Semaphore limits concurrent requests (avoid rate limiting)
- [ ] Performance test showing improvement
- [ ] No regression in functionality

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-01-08 | Created from code review | Critical performance bottleneck |

## Resources

- Performance analysis report
