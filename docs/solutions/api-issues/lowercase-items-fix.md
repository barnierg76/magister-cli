# Magister API: Lowercase Field Names Fix

## Problem

The Magister API returns data with **lowercase** field names (e.g., `items`, `waarde`, `ingevoerdOp`), but our code was expecting **PascalCase** field names (e.g., `Items`, `CijferStr`, `DatumIngevoerd`).

This caused issues where API calls would succeed but return empty results because:
1. `data.get("Items", [])` returned `[]` when the actual key was `items`
2. Pydantic models expected aliases like `CijferStr` but received `waarde`

## Root Cause

The Magister API has been updated to use camelCase field names in responses, but our code was written for an older API format with PascalCase naming.

## Solution

### 1. Response Item Extraction

Changed all item extraction to check lowercase first:

```python
# Before (broken)
items = data.get("Items", [])

# After (works with both formats)
items = data.get("items", data.get("Items", []))
```

### 2. Pydantic Model Aliases

Updated model field aliases to match actual API field names:

```python
# Before (old API format)
class Cijfer(MagisterModel):
    id: int = Field(alias="Id")
    cijfer_str: str = Field(alias="CijferStr")
    datum_ingevoerd: datetime = Field(alias="DatumIngevoerd")

# After (new API format)
class Cijfer(MagisterModel):
    id: int = Field(alias="kolomId")
    cijfer_str: str = Field(alias="waarde")
    datum_ingevoerd: datetime = Field(alias="ingevoerdOp")
```

## Files Modified

| File | Change |
|------|--------|
| `api/base.py` | Updated `_extract_items()` method |
| `api/resources/grades.py` | Fixed `enrollments()`, `all_grades()`, `subjects()` |
| `api/resources/appointments.py` | Fixed `list()` method |
| `api/resources/messages.py` | Fixed `inbox()`, `sent()`, `deleted()` |
| `api/resources/account.py` | Fixed `get_children()` |
| `api/client.py` | Fixed `get_children()` |
| `services/async_magister.py` | Fixed `_get_children()`, `get_homework()`, `get_recent_grades()`, `get_schedule()` |
| `api/models/grades.py` | Completely rewrote with correct field aliases |

## Debugging Tips

If you encounter similar issues:

1. **Use the raw command** to see actual API response:
   ```bash
   magister grades raw --limit 5
   ```

2. **Enable debug logging**:
   ```bash
   magister grades recent --debug
   ```

3. **Check field names** in the raw JSON response - the API may have changed

## Lesson Learned

Always check **both** lowercase and uppercase variants when extracting data from APIs that may change their naming conventions. The pattern `data.get("items", data.get("Items", []))` is defensive and handles both cases.
