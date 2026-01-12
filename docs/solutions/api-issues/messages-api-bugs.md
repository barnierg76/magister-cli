# Magister Messages API: Multiple Bug Fixes

---
category: api-issues
severity: high
apis_affected:
  - /berichten/berichten
  - /berichten/berichten/{id}
  - /berichten/berichten/{id}/bijlagen
symptoms:
  - Messages return null/empty fields
  - Delete message fails with internal_error
  - Mark as read fails with internal_error
  - Attachments not found despite heeftBijlagen=true
  - Attachment downloads fail
root_causes:
  - Lowercase field names in /berichten/ API (not PascalCase)
  - Wrong endpoint paths
  - Missing separate endpoint calls for attachments
  - Missing redirect handling for downloads
date_fixed: 2025-01-12
commits:
  - 7d6ab30
  - 253450d
  - c102cff
  - 1677295
  - 7034015
related_docs:
  - lowercase-items-fix.md
  - parent-accounts-and-attachments.md
---

## Problem Summary

Six related bugs in the messages API functionality that caused MCP tools to fail when working with Magister messages.

## Bug 1: Messages Returning Null Fields

### Symptom
`get_messages` returned all null fields:
```json
{
  "id": null,
  "subject": null,
  "sender_name": null,
  "sent_at": null,
  "is_read": null
}
```

### Root Cause
The `/berichten/` API uses **lowercase** field names (`id`, `onderwerp`, `afzender`), while other APIs use PascalCase. The code expected PascalCase.

### Fix
Use lowercase with PascalCase fallback:
```python
# Before
"id": item.get("Id"),
"subject": item.get("Onderwerp"),

# After
"id": item.get("id", item.get("Id")),
"subject": item.get("onderwerp", item.get("Onderwerp")),
```

---

## Bug 2: Delete Message Failing

### Symptom
```
Error: internal_error - 404 Not Found
```

### Root Cause
Wrong endpoint path. The API uses a doubled path pattern:
- Wrong: `/berichten/{id}`
- Correct: `/berichten/berichten/{id}`

### Fix
```python
# Before
response = await client.delete(f"/berichten/{message_id}")

# After
response = await client.delete(f"/berichten/berichten/{message_id}")
```

---

## Bug 3: Mark as Read Failing

### Symptom
```
Error: internal_error - 404 Not Found
```

### Root Cause
No dedicated endpoint exists for marking messages as read. Tried `/berichten/berichten/{id}/gelezen` but it returns 404.

### Fix
Implement GET-modify-PUT pattern:
```python
async def mark_message_as_read(self, message_id: int) -> None:
    client = self._ensure_client()
    # GET full message
    response = await client.get(f"/berichten/berichten/{message_id}")
    response.raise_for_status()

    data = response.json()
    data["isGelezen"] = True  # Modify

    # PUT back
    response = await client.put(f"/berichten/berichten/{message_id}", json=data)
    response.raise_for_status()
```

---

## Bug 4: Attachments Not Found

### Symptom
`list_attachments` returned empty list despite message having `heeftBijlagen: true`.

### Root Cause
Attachments are NOT included in the message response. They must be fetched from a separate endpoint: `/berichten/berichten/{id}/bijlagen`

### Fix
Fetch attachments separately when `heeftBijlagen=true`:
```python
bijlagen = []
if data.get("heeftBijlagen", data.get("HeeftBijlagen", False)):
    att_response = await client.get(f"/berichten/berichten/{message_id}/bijlagen")
    if att_response.status_code == 200:
        att_data = att_response.json()
        for b in att_data.get("items", att_data.get("Items", [])):
            bijlagen.append({
                "id": b.get("id", b.get("Id")),
                "name": b.get("naam", b.get("Naam")),
                "mime_type": b.get("contentType", b.get("ContentType")),
                "size": b.get("grootte", b.get("Grootte")),
            })
```

---

## Bug 5: Attachment Downloads Failing

### Symptom
```
Error: internal_error - Failed to download attachment
```

### Root Causes
1. httpx client didn't have `follow_redirects=True` - download URLs return 302 redirects
2. Fallback URL pattern `/personen/{id}/bijlagen/{id}` doesn't work for message attachments

### Fix
1. Enable redirect following in httpx client:
```python
self._client = httpx.AsyncClient(
    # ... other config ...
    follow_redirects=True,  # Required for attachment downloads
)
```

2. Try multiple URL patterns:
```python
if attachment.download_url:
    urls_to_try = [attachment.download_url]
else:
    urls_to_try = [
        f"/berichten/bijlagen/{attachment.id}/download",  # Message attachments
        f"/personen/{self._person_id}/bijlagen/{attachment.id}",  # Homework
        f"/leerlingen/{self._person_id}/bijlagen/{attachment.id}/download",  # Alt
    ]

for url in urls_to_try:
    try:
        response = await client.get(url)
        if response.status_code == 200:
            break
    except Exception:
        continue
```

---

## API Naming Convention Summary

| API Path | Field Names | Example |
|----------|-------------|---------|
| `/berichten/` | lowercase | `id`, `onderwerp`, `afzender`, `isGelezen` |
| `/personen/` | PascalCase | `Id`, `Titel`, `Bijlagen` |
| `/leerlingen/` | PascalCase | `Id`, `Naam`, `Adres` |
| `/aanwezigheid/` | PascalCase | `Id`, `Afwezigheid`, `Periode` |

**Key insight**: The `/berichten/` API is inconsistent with other Magister APIs.

---

## Prevention Strategies

### 1. Always Use Dual-Case Extraction
```python
# Defensive pattern for any Magister API
value = data.get("lowercase", data.get("PascalCase", default))
```

### 2. Verify Endpoint Paths with Raw Requests
Before implementing, test endpoints directly:
```bash
curl -H "Authorization: Bearer $TOKEN" \
  "https://school.magister.net/api/berichten/berichten/123"
```

### 3. Check for Nested Resources
When an object has `hasX=true`, look for separate endpoint `/parent/{id}/x`

### 4. Enable Redirects for Downloads
Always configure HTTP clients with redirect handling for file downloads.

### 5. Test All CRUD Operations
Don't assume standard REST patterns. Test each operation:
- GET (read)
- POST (create)
- PUT (update)
- DELETE (delete)

---

## Files Modified

| File | Changes |
|------|---------|
| `services/async_magister.py` | All message-related methods fixed |
| `mcp/__main__.py` | Created (MCP server entry point) |

## Commits

- `7d6ab30` - Fix MCP entry point and message field names
- `253450d` - Fix delete_message endpoint path
- `c102cff` - Fix mark_message_as_read with GET-PUT pattern
- `1677295` - Fix attachments with separate endpoint
- `7034015` - Fix downloads with redirects and URL patterns
