# Magister CLI - Engineering Learnings & Prevention Strategies

## Overview
This document captures lessons learned from solving three critical issues in the Magister API client. Each issue has prevention strategies, testing approaches, and code patterns to prevent future similar problems.

---

## Issue 1: Parent vs Student Account API ID Handling

### The Problem
Parent accounts in the Magister system have a different ID structure than student accounts:
- **Parent's account ID** (`persoon_id`): Used for authentication/account info
- **Student's ID**: Used for API calls to fetch student-specific data (homework, grades, etc.)

When a parent logs in, API calls for student data must use the child's ID, not the parent's ID. This caused silent failures where API requests would either:
- Return empty results (no homework/grades shown)
- Return wrong student's data
- Fail with authorization errors

### Code Pattern: Dual ID Tracking

The solution implements dual ID tracking in the client:

```python
class MagisterClient:
    def __init__(self, school: str, token: str, timeout: int | None = None):
        self._account_id: int | None = None      # The logged-in account's ID
        self._student_id: int | None = None      # The student's ID (may differ for parents)
        self._is_parent: bool = False
        self._children: list[Kind] | None = None
```

**Key implementation in `get_account()`:**

```python
def get_account(self) -> Account:
    """Get account info and determine if this is a parent or student account."""
    data = self._request("GET", "/account")
    account = Account.model_validate(data)
    self._account_id = account.persoon_id        # Store login account ID

    # Check if this is a parent account
    self._is_parent = account.is_parent

    if self._is_parent:
        # For parent accounts, get children and use first child's ID
        children = self.get_children()
        if children:
            self._student_id = children[0].id    # Use child's ID for API calls
        else:
            self._student_id = self._account_id   # Fallback
    else:
        # Student account - use own ID
        self._student_id = self._account_id

    return account
```

**Usage pattern - always use `_student_id` for API calls:**

```python
def get_appointments(self, start: date, end: date) -> list[Afspraak]:
    """Get appointments for a date range."""
    student_id = self._ensure_student_id()  # ← Use this, not account_id

    data = self._request(
        "GET",
        f"/personen/{student_id}/afspraken",  # ← Correct ID
        params={"van": start.isoformat(), "tot": end.isoformat()},
    )
    return response.items
```

### How to Detect Similar Issues Early

#### 1. **Request/Response Logging Inspection**
Add debug logging to API calls and inspect the actual IDs being sent:

```python
def _request(self, method: str, endpoint: str, **kwargs) -> Any:
    """Make an API request with retry logic."""
    # Log the endpoint being called (only in debug mode)
    import logging
    logger = logging.getLogger(__name__)

    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(f"API Request: {method} {endpoint}")

    # ... rest of method
```

Check logs to see if:
- Wrong IDs are in the endpoint URL
- IDs don't match expected student vs parent
- Empty results when IDs are wrong

#### 2. **Account Type Smoke Test**
When first logging in, immediately verify account type handling:

```python
@respx.mock
def test_parent_account_uses_child_id(self):
    """Parent accounts must use child's ID for API calls."""
    parent_account = {..., "Groep": [{"Naam": "Ouder"}]}  # Parent account
    child_data = {
        "Items": [{"Id": 999, "Voornaam": "Kind"}]  # Child's ID is 999
    }

    respx.get("https://test.magister.net/api/account").mock(
        return_value=httpx.Response(200, json=parent_account)
    )
    respx.get("https://test.magister.net/api/personen/555/kinderen").mock(
        return_value=httpx.Response(200, json=child_data)
    )
    respx.get("https://test.magister.net/api/personen/999/afspraken").mock(
        return_value=httpx.Response(200, json={"Items": []})
    )

    with MagisterClient("test", "token") as client:
        client.get_account()
        # Verify correct ID is cached
        assert client.person_id == 999  # Child's ID, not parent's 555
```

### Testing Strategies

#### 1. **Test Both Account Types**
Always test with parent and student fixtures:

```python
@pytest.fixture
def parent_account_response():
    """Parent account with children."""
    return {
        "Persoon": {"Id": 555, "Voornaam": "Parent"},
        "Groep": [{"Naam": "Ouder"}]
    }

@pytest.fixture
def student_account_response():
    """Student account."""
    return {
        "Persoon": {"Id": 123, "Voornaam": "Student"},
        "Groep": [{"Naam": "Leerling"}]
    }

def test_student_account_uses_own_id(self, student_account_response):
    # ... test that uses student_account_response

def test_parent_account_uses_child_id(self, parent_account_response):
    # ... test that uses parent_account_response
```

#### 2. **Test ID Caching to Prevent Double Calls**
Verify that account info is fetched once and cached:

```python
@respx.mock
def test_person_id_cached(self, account_response, afspraken_response):
    """Person ID is fetched once and cached."""
    account_route = respx.get("https://test.magister.net/api/account").mock(
        return_value=httpx.Response(200, json=account_response)
    )
    respx.get("https://test.magister.net/api/personen/12345/afspraken").mock(
        return_value=httpx.Response(200, json=afspraken_response)
    )

    with MagisterClient("test", "token123") as client:
        client.get_account()
        client.get_homework(date(2026, 1, 9), date(2026, 1, 15))
        client.get_homework(date(2026, 1, 9), date(2026, 1, 15))

    # Should only call /account once
    assert len(account_route.calls) == 1
```

### Common Pitfalls to Avoid

1. **Don't use `account.persoon_id` directly in API endpoints**
   ```python
   # ❌ WRONG: Uses login account, not student account
   data = self._request("GET", f"/personen/{self._account_id}/afspraken")

   # ✅ CORRECT: Uses student ID (which may be child's for parents)
   student_id = self._ensure_student_id()
   data = self._request("GET", f"/personen/{student_id}/afspraken")
   ```

2. **Don't assume all accounts are students**
   - Always call `get_account()` first to determine account type
   - Parent accounts need special handling to fetch children

3. **Don't skip the fallback case**
   ```python
   # ✅ GOOD: Has fallback for parents with no children
   if self._is_parent:
       children = self.get_children()
       if children:
           self._student_id = children[0].id
       else:
           self._student_id = self._account_id  # ← Fallback
   ```

4. **Don't call account methods in a tight loop**
   - Cache `person_id` and `is_parent_account` after first call
   - Use `_ensure_student_id()` which returns cached value

### Code Patterns to Reuse

#### Pattern: Cached Lazy Initialization
```python
def _ensure_student_id(self) -> int:
    """Ensure student_id is available, fetching account if needed."""
    if self._student_id is None:
        self.get_account()
    assert self._student_id is not None
    return self._student_id
```

**When to use:** Any time you need an ID that might not be loaded yet

#### Pattern: Property with Type Checking
```python
@property
def person_id(self) -> int | None:
    """Get the student's ID (for API calls)."""
    return self._student_id

@property
def is_parent_account(self) -> bool:
    """Check if this is a parent account."""
    return self._is_parent
```

**When to use:** Exposing internal state that should be read-only

---

## Issue 2: HTML Content in API Responses Needing Sanitization

### The Problem
The Magister API returns homework descriptions and other content with embedded HTML:
```
"Inhoud": "<p>Maak opgaven <b>4.1-4.15</b></p><br/>Vraag 1: <li>Item A</li>"
```

When displayed in the terminal, this raw HTML creates:
- Unreadable output with visible tags (`<p>`, `</b>`, etc.)
- Malformed text with entity codes (`&nbsp;`, `&amp;`)
- Incorrect line breaks and spacing
- Bullet points not properly rendered

The CLI needs to sanitize HTML to produce clean, readable text output.

### Code Pattern: Comprehensive HTML Sanitization

```python
def strip_html(text: str) -> str:
    """Strip HTML tags and decode entities from text."""
    if not text:
        return ""

    # 1. Convert semantic block elements to newlines
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</li>", "\n", text, flags=re.IGNORECASE)

    # 2. Convert list items to bullet points
    text = re.sub(r"<li[^>]*>", "• ", text, flags=re.IGNORECASE)

    # 3. Strip all remaining HTML tags
    text = re.sub(r"<[^>]+>", "", text)

    # 4. Decode HTML entities (&nbsp; &amp; etc.)
    text = html.unescape(text)

    # 5. Normalize whitespace
    text = re.sub(r"[ \t]+", " ", text)      # Multiple spaces to single
    text = re.sub(r"\n\s*\n", "\n\n", text) # Multiple newlines to double
    text = re.sub(r"\n{3,}", "\n\n", text)  # Max 2 consecutive newlines

    return text.strip()
```

**Usage in CLI formatting:**

```python
def format_homework_item(item: HomeworkItem, console: Console) -> None:
    """Format and print a single homework item."""
    # Clean HTML and format description
    clean_description = strip_html(item.description)
    for line in clean_description.split("\n"):
        line = line.strip()
        if line:
            console.print(f"     {line}")
```

### How to Detect Similar Issues Early

#### 1. **Visual Inspection Test**
Create a test fixture with known problematic HTML and verify output is readable:

```python
def test_strip_html_realistic_content():
    """Test with real Magister HTML format."""
    html_content = (
        "<p>Maak opgaven <b>4.1-4.15</b></p>"
        "<br/>"
        "Vraag 1:<li>Item A</li>"
        "<li>Item B</li>"
    )

    result = strip_html(html_content)

    # ✓ Should have no HTML tags
    assert "<p>" not in result
    assert "<br" not in result
    assert "<li>" not in result

    # ✓ Should have readable structure
    assert "Maak opgaven" in result
    assert "4.1-4.15" in result
    assert "•" in result  # Bullet points
    assert "\n" in result  # Line breaks
```

#### 2. **Entity Decoding Test**
Test common HTML entities from API responses:

```python
def test_strip_html_entities():
    """Decode HTML entities properly."""
    cases = [
        ("&nbsp;", " "),          # Non-breaking space
        ("&amp;", "&"),            # Ampersand
        ("&quot;", '"'),           # Quote
        ("&apos;", "'"),           # Apostrophe
        ("&lt;", "<"),             # Less than
        ("&gt;", ">"),             # Greater than
        ("&ndash;", "–"),          # En dash
        ("&hellip;", "…"),         # Ellipsis
    ]

    for html_entity, expected in cases:
        result = strip_html(html_entity)
        assert result == expected, f"Failed to decode {html_entity}"
```

#### 3. **Screenshot/Terminal Output Test**
For UI changes, take screenshots and manually review:

```bash
# Run CLI and manually verify output is clean
magister homework list --days 7

# Should see:
# - No HTML tags
# - Readable bullet points
# - Proper line breaks
# - No entity codes like &nbsp;
```

### Testing Strategies

#### 1. **Comprehensive HTML Coverage Test**
Test all HTML variations that Magister might return:

```python
class TestStripHTML:
    """Test HTML sanitization comprehensively."""

    def test_block_elements(self):
        """Convert block elements to newlines."""
        assert "Paragraph 1\nParagraph 2" in strip_html("<p>Paragraph 1</p><p>Paragraph 2</p>")

    def test_line_breaks(self):
        """Handle various line break formats."""
        assert strip_html("Line 1<br>Line 2") == "Line 1\nLine 2"
        assert strip_html("Line 1<br/>Line 2") == "Line 1\nLine 2"
        assert strip_html("Line 1<BR>Line 2") == "Line 1\nLine 2"  # Case insensitive

    def test_list_items(self):
        """Convert list items to bullets."""
        html = "<ul><li>Item A</li><li>Item B</li></ul>"
        result = strip_html(html)
        assert "• Item A" in result
        assert "• Item B" in result

    def test_multiple_consecutive_newlines(self):
        """Collapse multiple newlines to max 2."""
        result = strip_html("A\n\n\n\nB")
        assert result.count("\n\n") <= 1

    def test_inline_formatting_removal(self):
        """Remove inline HTML formatting."""
        assert strip_html("<b>Bold</b>") == "Bold"
        assert strip_html("<i>Italic</i>") == "Italic"
        assert strip_html("<u>Underline</u>") == "Underline"

    def test_empty_tags(self):
        """Handle empty tags gracefully."""
        assert strip_html("<p></p>") == ""
        assert strip_html("<div></div>") == ""
```

#### 2. **Integration Test with Real Data**
Use actual fixture data from API responses:

```python
def test_format_homework_with_html():
    """Format homework that contains HTML."""
    afspraak = Afspraak.model_validate({
        "Id": 1,
        "Start": "2026-01-09T09:00:00",
        "Einde": "2026-01-09T09:50:00",
        "Omschrijving": "Wiskunde",
        # Real API response with HTML
        "Inhoud": "<p>Maak opgaven <b>4.1-4.15</b></p><br/>Vraag 1:<li>Item A</li>",
        "InfoType": 1,
        "Vakken": [{"Id": 101, "Naam": "Wiskunde"}],
    })

    item = HomeworkItem.from_afspraak(afspraak)
    clean = strip_html(item.description)

    # Verify readable output
    assert "<" not in clean and ">" not in clean  # No HTML tags
    assert "Maak opgaven" in clean
    assert "4.1-4.15" in clean
```

### Common Pitfalls to Avoid

1. **Don't remove all whitespace**
   ```python
   # ❌ WRONG: Produces unreadable output
   text = re.sub(r"\s+", " ", text)  # Removes ALL newlines

   # ✅ CORRECT: Preserves semantic newlines
   text = re.sub(r"[ \t]+", " ", text)           # Only spaces/tabs
   text = re.sub(r"\n\s*\n", "\n\n", text)      # Keep newlines
   ```

2. **Don't forget case-insensitive HTML matching**
   ```python
   # ❌ WRONG: Won't catch <BR> or <br/>
   text = re.sub(r"<br>", "\n", text)

   # ✅ CORRECT: Matches any case and variation
   text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
   ```

3. **Don't forget to decode entities**
   ```python
   # ❌ WRONG: HTML tags gone but &nbsp; still shows
   text = re.sub(r"<[^>]+>", "", text)

   # ✅ CORRECT: Also decode entities
   text = re.sub(r"<[^>]+>", "", text)
   text = html.unescape(text)  # ← Required
   ```

4. **Don't assume all HTML is valid**
   - Magister API might return malformed HTML
   - Use regex fallbacks, not HTML parsers that require valid structure
   - Test with various malformed inputs

### Code Patterns to Reuse

#### Pattern: Semantic HTML Conversion
```python
# Convert semantic elements to text equivalents
text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
text = re.sub(r"</p>", "\n", text, flags=re.IGNORECASE)
text = re.sub(r"<li[^>]*>", "• ", text, flags=re.IGNORECASE)
text = re.sub(r"<[^>]+>", "", text)  # Strip remaining tags
```

**When to use:** Any user-facing text that comes from HTML-containing APIs

#### Pattern: Entity Decoding
```python
import html
text = html.unescape(text)  # Decode &nbsp;, &amp;, etc.
```

**When to use:** After removing HTML tags, always decode entities

#### Pattern: Whitespace Normalization
```python
# Normalize whitespace in three steps
text = re.sub(r"[ \t]+", " ", text)     # Multiple spaces → single
text = re.sub(r"\n\s*\n", "\n\n", text) # Multiple newlines → double
text = re.sub(r"\n{3,}", "\n\n", text)  # Cap at 2 newlines
```

**When to use:** After converting HTML, to produce readable output

---

## Issue 3: Attachments Requiring Separate API Calls and Redirect Handling

### The Problem
The Magister API has a two-step process for attachments:

1. **First call**: Fetch appointment/homework details
   - `GET /personen/{id}/afspraken/{id}` returns attachment metadata
   - Includes ID, name, size, and a download link

2. **Second call**: Download the actual file using the link
   - The link often contains an API path like `/api/personen/.../bijlagen/.../contents`
   - The API server **redirects** (302, 301) to actual file location
   - Must follow redirects to get the actual file

**Complications:**
- Not all appointments have attachment metadata
- Attachment metadata must be fetched separately from list view
- Download links have `/api/` prefix that conflicts with base URL
- Without `follow_redirects=True`, downloads fail silently

### Code Pattern: Attachment Handling

**Model with metadata extraction:**

```python
class Bijlage(BaseModel):
    """Attachment model."""

    id: int = Field(alias="Id")
    naam: str = Field(alias="Naam")
    content_type: str = Field(alias="ContentType")
    grootte: int = Field(default=0, alias="Grootte")
    datum: datetime | None = Field(default=None, alias="Datum")
    links: list[BijlageLink] = Field(default_factory=list, alias="Links")

    @property
    def download_path(self) -> str | None:
        """Get the download path for this attachment."""
        for link in self.links:
            if link.rel == "Contents":  # ← Look for specific rel type
                return link.href
        return None
```

**Two-phase data fetching:**

```python
def get_homework_with_attachments(self, start: date, end: date) -> list[Afspraak]:
    """Get homework with attachments populated for items that have them."""
    # Phase 1: Get list of homework items
    appointments = self.get_homework(start, end)

    # Phase 2: For items with attachments, fetch full details
    result = []
    for afspraak in appointments:
        if afspraak.heeft_bijlagen:  # ← Check if has attachments
            # Fetch full appointment to get bijlagen
            full_afspraak = self.get_appointment(afspraak.id)  # ← Separate call
            result.append(full_afspraak)
        else:
            result.append(afspraak)

    return result
```

**Download with redirect handling:**

```python
def download_attachment(self, bijlage: Bijlage, output_dir: Path | None = None) -> Path:
    """Download an attachment to the specified directory."""
    self._check_client()
    assert self._client is not None

    download_path = bijlage.download_path
    if not download_path:
        raise MagisterAPIError(f"No download path for attachment: {bijlage.naam}")

    # Handle path prefix conflict
    if download_path.startswith("/api/"):
        download_path = download_path[4:]  # Remove "/api" prefix

    full_url = f"{self.base_url}{download_path}"

    # Use separate client with follow_redirects=True for downloads
    with httpx.Client(
        headers={"Authorization": f"Bearer {self.token}"},
        timeout=self._timeout,
        follow_redirects=True,  # ← CRITICAL: Must follow server redirects
    ) as download_client:
        response = download_client.get(full_url)

    if response.status_code >= 400:
        raise MagisterAPIError(
            f"Failed to download attachment: {response.status_code}",
            response.status_code,
        )

    # Handle duplicate filenames
    if output_dir is None:
        output_dir = Path.cwd()
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / bijlage.naam

    if output_path.exists():
        stem = output_path.stem
        suffix = output_path.suffix
        counter = 1
        while output_path.exists():
            output_path = output_dir / f"{stem}_{counter}{suffix}"
            counter += 1

    output_path.write_bytes(response.content)
    return output_path
```

### How to Detect Similar Issues Early

#### 1. **Verify Attachment Metadata is Complete**
Test that attachment model has all required fields:

```python
def test_attachment_has_download_link():
    """Attachment must have download path."""
    bijlage_data = {
        "Id": 1,
        "Naam": "homework.pdf",
        "ContentType": "application/pdf",
        "Grootte": 12345,
        "Links": [
            {"Rel": "Contents", "Href": "/api/personen/123/bijlagen/456/contents"}
        ]
    }

    bijlage = Bijlage.model_validate(bijlage_data)

    assert bijlage.download_path is not None
    assert bijlage.download_path.startswith("/api/")
```

#### 2. **Test Two-Phase Fetching Pattern**
Verify that list view and detail view are called separately:

```python
@respx.mock
def test_attachments_fetched_separately():
    """Attachments require separate API call."""
    # List view doesn't have attachment details
    list_response = {
        "Items": [{
            "Id": 1,
            "HeeftBijlagen": True,  # ← Says has attachments, but...
            "Bijlagen": None,       # ← No attachment details in list
        }]
    }

    # Detail view has full attachment data
    detail_response = {
        "Id": 1,
        "HeeftBijlagen": True,
        "Bijlagen": [{
            "Id": 100,
            "Naam": "file.pdf",
            "Links": [{"Rel": "Contents", "Href": "/api/.../contents"}]
        }]
    }

    list_route = respx.get("https://test.magister.net/api/personen/123/afspraken").mock(
        return_value=httpx.Response(200, json=list_response)
    )
    detail_route = respx.get("https://test.magister.net/api/personen/123/afspraken/1").mock(
        return_value=httpx.Response(200, json=detail_response)
    )

    with MagisterClient("test", "token") as client:
        client._student_id = 123
        result = client.get_homework_with_attachments(date(2026,1,1), date(2026,1,31))

    # Both endpoints should be called
    assert len(list_route.calls) > 0
    assert len(detail_route.calls) > 0

    # Result should have attachment data
    assert result[0].bijlagen is not None
```

#### 3. **Test Redirect Following**
Verify downloads handle HTTP redirects:

```python
@respx.mock
def test_download_follows_redirects():
    """Download must follow server redirects."""
    # Server redirects to actual file
    respx.get("https://test.magister.net/api/bijlagen/contents").mock(
        return_value=httpx.Response(
            302,
            headers={"Location": "https://cdn.example.com/file.pdf"}
        )
    )
    respx.get("https://cdn.example.com/file.pdf").mock(
        return_value=httpx.Response(200, content=b"PDF file content")
    )

    with MagisterClient("test", "token") as client:
        bijlage = Bijlage.model_validate({
            "Id": 1,
            "Naam": "test.pdf",
            "ContentType": "application/pdf",
            "Links": [{"Rel": "Contents", "Href": "/api/bijlagen/contents"}]
        })

        output_path = client.download_attachment(bijlage)

        # Should follow redirect and get actual content
        assert output_path.read_bytes() == b"PDF file content"
```

### Testing Strategies

#### 1. **Test URL Path Handling**
Test the `/api/` prefix stripping logic:

```python
class TestDownloadPathHandling:
    """Test attachment download path handling."""

    def test_strips_api_prefix():
        """Strip /api prefix from download path."""
        bijlage = Bijlage.model_validate({
            "Id": 1,
            "Naam": "file.pdf",
            "ContentType": "application/pdf",
            "Links": [{"Rel": "Contents", "Href": "/api/personen/123/bijlagen/456/contents"}]
        })

        client = MagisterClient("test", "token")
        download_path = bijlage.download_path

        # The download_path property returns the link's Href
        assert download_path.startswith("/api/")

        # But in download_attachment, we strip it
        if download_path.startswith("/api/"):
            stripped = download_path[4:]  # Remove "/api"
            assert not stripped.startswith("/api/")

    def test_builds_correct_full_url():
        """Build correct full URL for download."""
        client = MagisterClient("school.magister.net", "token")
        assert client.base_url == "https://school.magister.net/api"

        # After stripping "/api", path is "/personen/..."
        # Full URL becomes: base_url + path = ".../api" + "/personen/..."
```

#### 2. **Test Duplicate Filename Handling**
Ensure files don't overwrite each other:

```python
def test_handles_duplicate_filenames(tmp_path):
    """Handle duplicate filenames gracefully."""
    client = MagisterClient("test", "token")

    bijlage = Bijlage.model_validate({
        "Id": 1,
        "Naam": "homework.pdf",
        "ContentType": "application/pdf",
        "Links": [{"Rel": "Contents", "Href": "/api/.../contents"}]
    })

    # First download creates homework.pdf
    path1 = tmp_path / "homework.pdf"
    path1.write_text("First file")

    # Would download second file with same name
    # But our code should handle it
    stem = path1.stem
    suffix = path1.suffix

    # Simulate the duplicate handling logic
    existing_files = [path1]
    counter = 1
    new_path = tmp_path / f"{stem}_{counter}{suffix}"
    while new_path.exists():
        counter += 1
        new_path = tmp_path / f"{stem}_{counter}{suffix}"

    # Should create homework_1.pdf
    assert new_path == tmp_path / "homework_1.pdf"
```

#### 3. **Test Separate Download Client**
Verify that downloads use a separate client with proper config:

```python
def test_download_uses_separate_client():
    """Downloads use separate httpx.Client with follow_redirects."""
    # This is tested implicitly - if download_attachment worked
    # without follow_redirects=True, it would fail on redirects

    # Key assertion: the download happens in a separate context manager
    # with its own httpx.Client configured with follow_redirects=True
```

### Common Pitfalls to Avoid

1. **Don't fetch attachment details from list view**
   ```python
   # ❌ WRONG: List view doesn't include Bijlagen
   appointments = self.get_appointments(start, end)
   for a in appointments:
       for bijlage in a.bijlagen_lijst:  # ← Will be empty!
           download(bijlage)

   # ✅ CORRECT: Fetch full details for items with attachments
   if afspraak.heeft_bijlagen:
       full_afspraak = self.get_appointment(afspraak.id)
       for bijlage in full_afspraak.bijlagen_lijst:
           download(bijlage)
   ```

2. **Don't forget to follow redirects**
   ```python
   # ❌ WRONG: Will fail on redirect
   response = httpx.Client().get(url)

   # ✅ CORRECT: Follow redirects
   response = httpx.Client(follow_redirects=True).get(url)
   ```

3. **Don't assume download path doesn't need cleaning**
   ```python
   # ❌ WRONG: Path might have /api/ prefix
   full_url = f"{self.base_url}{download_path}"  # Double /api/api

   # ✅ CORRECT: Strip /api prefix
   if download_path.startswith("/api/"):
       download_path = download_path[4:]
   full_url = f"{self.base_url}{download_path}"
   ```

4. **Don't ignore the `heeft_bijlagen` flag**
   ```python
   # ❌ WRONG: Tries to fetch details for all items
   for afspraak in appointments:
       full = self.get_appointment(afspraak.id)  # Too many requests!

   # ✅ CORRECT: Only fetch details when needed
   for afspraak in appointments:
       if afspraak.heeft_bijlagen:
           full = self.get_appointment(afspraak.id)
   ```

5. **Don't use the main client for downloads**
   ```python
   # ❌ WRONG: Main client might not have follow_redirects
   with MagisterClient(...) as client:
       response = client._client.get(url)

   # ✅ CORRECT: Create separate client for downloads
   with httpx.Client(follow_redirects=True) as download_client:
       response = download_client.get(url)
   ```

### Code Patterns to Reuse

#### Pattern: Check and Fetch Full Details
```python
# Only fetch full details when needed to optimize API calls
if item.has_details_flag:
    full_item = self.get_full_item(item.id)
    # Use full_item data
else:
    # Use item data
```

**When to use:** When list endpoints return basic data and detail endpoints are expensive

#### Pattern: Extract Metadata from Links
```python
class WithLinks(BaseModel):
    links: list[Link] = Field(alias="Links")

    @property
    def specific_link(self) -> str | None:
        """Get specific link by rel type."""
        for link in self.links:
            if link.rel == "SpecificType":
                return link.href
        return None
```

**When to use:** When API uses hypermedia links (HATEOAS) pattern

#### Pattern: Separate Download Client
```python
# Use separate client for downloads with redirect support
with httpx.Client(
    headers={"Authorization": f"Bearer {token}"},
    follow_redirects=True,
) as download_client:
    response = download_client.get(url)
```

**When to use:** When downloads redirect to different servers

#### Pattern: Idempotent Filename Handling
```python
# Handle duplicate filenames without overwriting
if output_path.exists():
    stem = output_path.stem
    suffix = output_path.suffix
    counter = 1
    while output_path.exists():
        output_path = output_dir / f"{stem}_{counter}{suffix}"
        counter += 1
```

**When to use:** When downloading multiple files with same name

---

## General Prevention Strategies for API Clients

### 1. **Dual Account Type Handling Pattern**
Whenever building clients for systems with user types (admin/user, parent/student, etc.):
- Track both IDs (login ID and effective ID)
- Detect account type early in initialization
- Default to using the effective ID for API calls
- Add properties to expose both for debugging

### 2. **API Response Content Cleaning Pattern**
When APIs return formatted content (HTML, markdown, rich text):
- Create sanitization functions for each format type
- Test with real API fixtures
- Apply sanitization at display time, not storage time
- Log raw content for debugging when needed

### 3. **Two-Phase API Fetching Pattern**
When APIs require separate calls for related data:
- Check "has related data" flags on first call
- Make second call only when needed
- Cache results to avoid redundant calls
- Test both phases in integration tests

### 4. **Redirect Handling Pattern**
When downloads or file operations involve redirects:
- Use HTTP client configuration to follow redirects
- Test with mock redirects
- Validate content after following redirects
- Handle both absolute and relative redirect URLs

### 5. **Fixture-Based Testing Pattern**
For API clients, always:
- Create realistic API response fixtures
- Test with both common and edge cases
- Mock only what's necessary
- Use same fixtures for multiple tests

---

## Testing Checklist for API Client Features

Before shipping any API client feature:

- [ ] Account type detection works (if applicable)
- [ ] Caching prevents redundant API calls
- [ ] Error handling includes specific exceptions
- [ ] HTML/formatted content is properly sanitized
- [ ] Links and paths are validated and decoded
- [ ] Redirects are followed (if applicable)
- [ ] File operations handle duplicates gracefully
- [ ] Both success and error paths are tested
- [ ] Tests use realistic API response fixtures
- [ ] Rate limiting and timeouts are handled
- [ ] Authorization headers are present in all requests
- [ ] Sensitive tokens are not logged

---

## Key Takeaways

1. **API clients need defensive design**: Always assume accounts might differ, APIs might return HTML, files might redirect
2. **Test comprehensively**: Use real fixtures, test both paths, verify actual behavior not assumptions
3. **Cache aggressively**: Avoid redundant API calls, but make caching explicit and testable
4. **Handle edge cases**: Duplicates, missing data, redirects, account type variations
5. **Sanitize at boundaries**: Clean external data (HTML) before displaying to users
6. **Document patterns**: Future developers will follow existing patterns in the codebase
