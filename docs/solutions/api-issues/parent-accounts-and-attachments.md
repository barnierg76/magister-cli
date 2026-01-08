---
title: Parent Account Support and Attachment Downloads
category: api-issues
severity: high
date: 2026-01-08
tags: [magister-api, parent-accounts, attachments, downloads, httpx]
---

# Parent Account Support and Attachment Downloads

## Problem Summary

Two related issues were discovered when building the Magister CLI:

1. **Parent accounts** have a different ID structure than student accounts - API calls need to use the child's ID, not the parent's account ID
2. **Attachment downloads** required multiple fixes:
   - `Bijlagen` field can be `null` in list responses
   - Download paths include `/api/` prefix that conflicts with base URL
   - API returns 302 redirects that must be followed

## Root Causes

### Parent Account Issue
The Magister API uses different IDs depending on account type:
- **Student accounts**: `persoon_id` from `/account` endpoint works directly
- **Parent accounts**: Must fetch children via `/personen/{id}/kinderen` and use child's ID for homework/appointment calls

### Attachment Issues
1. **Null Bijlagen**: List endpoint returns `HeeftBijlagen: true` but `Bijlagen: null`. Must fetch individual appointment to get attachment details.
2. **Path prefix**: Download URLs from API include `/api/` but our base URL already ends with `/api`, causing 404s
3. **Redirects**: Magister serves attachments via redirect (302) but httpx doesn't follow redirects by default

## Solutions

### Parent Account Detection

```python
# In api/models.py - Account model
@property
def is_parent(self) -> bool:
    """Check if this is a parent account."""
    for groep in self.groepen:
        if "ouder" in groep.naam.lower():
            return True
    return False

# In api/client.py - MagisterClient
def get_account(self) -> Account:
    """Get account info and determine if this is a parent or student account."""
    data = self._request("GET", "/account")
    account = Account.model_validate(data)
    self._account_id = account.persoon_id
    self._is_parent = account.is_parent

    if self._is_parent:
        # For parent accounts, get children and use first child's ID
        children = self.get_children()
        if children:
            self._student_id = children[0].id
        else:
            self._student_id = self._account_id
    else:
        # Student account - use own ID
        self._student_id = self._account_id

    return account
```

### Nullable Bijlagen Field

```python
# In api/models.py - Afspraak model
heeft_bijlagen: bool = Field(default=False, alias="HeeftBijlagen")
bijlagen: list[Bijlage] | None = Field(default=None, alias="Bijlagen")

@property
def bijlagen_lijst(self) -> list[Bijlage]:
    """Get attachments as a list, handling null case."""
    return self.bijlagen or []
```

### Download Path Prefix Fix

```python
# In api/client.py - download_attachment method
download_path = bijlage.download_path
if not download_path:
    raise MagisterAPIError(f"No download path for attachment: {bijlage.naam}")

# Strip /api prefix since base_url already includes it
if download_path.startswith("/api/"):
    download_path = download_path[4:]  # Remove "/api" prefix
```

### Following Redirects for Downloads

```python
# In api/client.py - download_attachment method
# Use separate client with redirect support for downloads
full_url = f"{self.base_url}{download_path}"
with httpx.Client(
    headers={"Authorization": f"Bearer {self.token}"},
    timeout=self._timeout,
    follow_redirects=True,  # Critical: API returns 302 redirects
) as download_client:
    response = download_client.get(full_url)
```

### HTML Stripping for Readable Output

```python
# In cli/formatters.py
import html
import re

def strip_html(text: str) -> str:
    """Strip HTML tags and decode entities from text."""
    if not text:
        return ""
    # Convert block elements to newlines
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</li>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<li[^>]*>", "• ", text, flags=re.IGNORECASE)
    # Remove remaining tags
    text = re.sub(r"<[^>]+>", "", text)
    # Decode HTML entities
    text = html.unescape(text)
    # Normalize whitespace
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n", "\n\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
```

## Prevention Strategies

1. **Always use Optional/Union types for nullable API fields** - Even if a field "should" have data, APIs often return null in list responses
2. **Check for URL prefix conflicts** when combining base URLs with paths from API responses
3. **Enable redirect following** when downloading files - many APIs use redirects for file serving
4. **Detect account type early** and store the correct ID for subsequent API calls
5. **Fetch detailed records** when list responses don't include all needed data (e.g., attachments)

## Testing Commands

```bash
# Test homework with attachments displayed
magister homework --school vsvonh

# Download all attachments
magister homework --school vsvonh --download

# Download to specific directory
magister homework --school vsvonh --download --output ./downloads

# Standalone download command
magister download --school vsvonh --days 14
```

## Files Modified

- `src/magister_cli/api/models.py` - Added Bijlage, BijlageLink, Kind models
- `src/magister_cli/api/client.py` - Added parent detection, attachment download
- `src/magister_cli/services/homework.py` - Added AttachmentInfo, attachment support
- `src/magister_cli/cli/formatters.py` - Added HTML stripping, attachment display
- `src/magister_cli/main.py` - Added --download flag and download command
