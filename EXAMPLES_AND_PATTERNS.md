# Code Examples and Patterns - Magister CLI Solutions

Complete, copy-paste ready examples for each solved issue.

---

## Example 1: Implementing Parent/Student Account Handling

### Complete Working Implementation

```python
from typing import Optional
from magister_cli.api.models import Account, Kind

class MagisterClient:
    """API client with parent/student account handling."""

    def __init__(self, school: str, token: str, timeout: Optional[int] = None):
        self.school = school
        self.token = token
        # Dual ID tracking
        self._account_id: Optional[int] = None  # Login account
        self._student_id: Optional[int] = None  # Effective student ID
        self._person_name: Optional[str] = None
        self._is_parent: bool = False
        self._children: Optional[list[Kind]] = None

    def get_account(self) -> Account:
        """
        Get account info and determine account type.

        Sets both _account_id (login account) and _student_id (effective student).
        For parent accounts, fetches children and uses first child's ID.
        """
        data = self._request("GET", "/account")
        account = Account.model_validate(data)

        # Store login account ID
        self._account_id = account.persoon_id
        self._person_name = account.naam

        # Determine account type
        self._is_parent = account.is_parent

        if self._is_parent:
            # Parent account: use child's ID
            children = self.get_children()
            if children:
                self._student_id = children[0].id
                self._person_name = children[0].volledige_naam
            else:
                # Fallback: no children found
                self._student_id = self._account_id
        else:
            # Student account: use own ID
            self._student_id = self._account_id

        return account

    def get_children(self) -> list[Kind]:
        """Fetch children for a parent account."""
        if self._account_id is None:
            self.get_account()

        try:
            data = self._request("GET", f"/personen/{self._account_id}/kinderen")
            response = KindResponse.from_response(data)
            self._children = response.items
            return self._children
        except MagisterAPIError:
            # Not a parent account or no children
            return []

    def _ensure_student_id(self) -> int:
        """
        Ensure student_id is loaded (cached).

        Returns student ID, fetching account if needed.
        Always use this method instead of accessing _student_id directly.
        """
        if self._student_id is None:
            self.get_account()
        assert self._student_id is not None
        return self._student_id

    # All data API calls use _student_id
    def get_appointments(self, start: date, end: date) -> list[Afspraak]:
        """Get appointments for date range."""
        student_id = self._ensure_student_id()

        data = self._request(
            "GET",
            f"/personen/{student_id}/afspraken",  # ← Use student_id
            params={"van": start.isoformat(), "tot": end.isoformat()},
        )

        response = AfspraakResponse.from_response(data)
        return response.items

    def get_recent_grades(self, limit: int = 10) -> list[Cijfer]:
        """Get recent grades."""
        student_id = self._ensure_student_id()

        data = self._request(
            "GET",
            f"/personen/{student_id}/cijfers/laatste",  # ← Use student_id
            params={"top": limit},
        )

        response = CijferResponse.from_response(data)
        return response.items

    # Properties for external access
    @property
    def person_id(self) -> Optional[int]:
        """Get the student's ID (for API calls)."""
        return self._student_id

    @property
    def person_name(self) -> Optional[str]:
        """Get the person's name."""
        return self._person_name

    @property
    def is_parent_account(self) -> bool:
        """Check if this is a parent account."""
        return self._is_parent
```

### Comprehensive Test Suite

```python
import pytest
import httpx
import respx
from datetime import date
from magister_cli.api.client import MagisterClient

@pytest.fixture
def student_account_fixture():
    """Student account fixture."""
    return {
        "Persoon": {
            "Id": 123,
            "Voornaam": "Jan",
            "Achternaam": "Jansen",
        },
        "Groep": [{"Naam": "Leerling"}]
    }

@pytest.fixture
def parent_account_fixture():
    """Parent account fixture."""
    return {
        "Persoon": {
            "Id": 555,
            "Voornaam": "Parent",
            "Achternaam": "Jansen",
        },
        "Groep": [{"Naam": "Ouder"}]
    }

@pytest.fixture
def children_fixture():
    """Children list fixture."""
    return {
        "Items": [
            {
                "Id": 999,
                "Voornaam": "Child",
                "Achternaam": "Jansen",
            }
        ]
    }

@pytest.fixture
def homework_fixture():
    """Homework list fixture."""
    return {
        "Items": [
            {
                "Id": 1,
                "Start": "2026-01-09T09:00:00",
                "Einde": "2026-01-09T09:50:00",
                "Omschrijving": "Wiskunde",
                "Inhoud": "Maak opgaven",
                "InfoType": 1,
            }
        ]
    }

class TestAccountTypeHandling:
    """Test parent vs student account handling."""

    @respx.mock
    def test_student_account_uses_own_id(self, student_account_fixture, homework_fixture):
        """Student account uses own ID for API calls."""
        respx.get("https://test.magister.net/api/account").mock(
            return_value=httpx.Response(200, json=student_account_fixture)
        )
        respx.get("https://test.magister.net/api/personen/123/afspraken").mock(
            return_value=httpx.Response(200, json=homework_fixture)
        )

        with MagisterClient("test", "token") as client:
            account = client.get_account()
            homework = client.get_homework(date(2026, 1, 9), date(2026, 1, 15))

        # Student ID should be own ID
        assert client.person_id == 123
        assert not client.is_parent_account
        assert len(homework) == 1

    @respx.mock
    def test_parent_account_uses_child_id(
        self, parent_account_fixture, children_fixture, homework_fixture
    ):
        """Parent account uses child's ID for API calls."""
        respx.get("https://test.magister.net/api/account").mock(
            return_value=httpx.Response(200, json=parent_account_fixture)
        )
        respx.get("https://test.magister.net/api/personen/555/kinderen").mock(
            return_value=httpx.Response(200, json=children_fixture)
        )
        respx.get("https://test.magister.net/api/personen/999/afspraken").mock(
            return_value=httpx.Response(200, json=homework_fixture)
        )

        with MagisterClient("test", "token") as client:
            account = client.get_account()
            homework = client.get_homework(date(2026, 1, 9), date(2026, 1, 15))

        # Should use child's ID, not parent's ID
        assert client.person_id == 999  # Child ID
        assert client.is_parent_account
        assert len(homework) == 1

    @respx.mock
    def test_person_id_is_cached(self, student_account_fixture, homework_fixture):
        """Person ID is fetched once and cached."""
        account_route = respx.get("https://test.magister.net/api/account").mock(
            return_value=httpx.Response(200, json=student_account_fixture)
        )
        respx.get("https://test.magister.net/api/personen/123/afspraken").mock(
            return_value=httpx.Response(200, json=homework_fixture)
        )

        with MagisterClient("test", "token") as client:
            # Multiple calls
            client.get_account()
            client.get_homework(date(2026, 1, 9), date(2026, 1, 15))
            client.get_homework(date(2026, 1, 9), date(2026, 1, 15))
            client.get_recent_grades()

        # Account endpoint should only be called once
        assert len(account_route.calls) == 1

    @respx.mock
    def test_parent_with_no_children_fallback(self, parent_account_fixture):
        """Parent with no children falls back to own ID."""
        respx.get("https://test.magister.net/api/account").mock(
            return_value=httpx.Response(200, json=parent_account_fixture)
        )
        respx.get("https://test.magister.net/api/personen/555/kinderen").mock(
            return_value=httpx.Response(200, json={"Items": []})
        )

        with MagisterClient("test", "token") as client:
            account = client.get_account()

        # Should fallback to parent's ID
        assert client.person_id == 555
        assert client.is_parent_account
```

---

## Example 2: Implementing HTML Sanitization

### Complete HTML Sanitization Function

```python
import html
import re
from typing import Optional

def strip_html(text: str) -> str:
    """
    Strip HTML tags and decode entities from text.

    Handles:
    - Block elements (<p>, </p>, <br>, </br>)
    - List items (<li>, </li>)
    - HTML entities (&nbsp;, &amp;, &quot;, etc.)
    - Whitespace normalization

    Args:
        text: HTML text to sanitize

    Returns:
        Clean plain text with semantic newlines preserved
    """
    if not text:
        return ""

    # Step 1: Convert semantic block elements to newlines
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</li>", "\n", text, flags=re.IGNORECASE)

    # Step 2: Convert list items to bullet points
    text = re.sub(r"<li[^>]*>", "• ", text, flags=re.IGNORECASE)

    # Step 3: Remove all remaining HTML tags
    text = re.sub(r"<[^>]+>", "", text)

    # Step 4: Decode HTML entities
    # This handles: &nbsp; &amp; &quot; &apos; &lt; &gt; and others
    text = html.unescape(text)

    # Step 5: Normalize whitespace
    # Collapse multiple spaces/tabs to single space
    text = re.sub(r"[ \t]+", " ", text)
    # Convert multiple newlines to double newline (paragraph break)
    text = re.sub(r"\n\s*\n", "\n\n", text)
    # Cap at 2 consecutive newlines
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()
```

### Comprehensive Test Suite

```python
import pytest
from magister_cli.cli.formatters import strip_html

class TestStripHTML:
    """Test HTML sanitization."""

    # Basic tag removal
    def test_removes_paragraph_tags(self):
        """Remove <p> tags."""
        html = "<p>Hello world</p>"
        result = strip_html(html)
        assert result == "Hello world"
        assert "<p>" not in result

    def test_converts_multiple_paragraphs_to_newlines(self):
        """Multiple paragraphs separated by newlines."""
        html = "<p>Paragraph 1</p><p>Paragraph 2</p>"
        result = strip_html(html)
        assert "Paragraph 1" in result
        assert "Paragraph 2" in result
        assert "\n" in result

    # Line breaks
    def test_converts_br_to_newline(self):
        """Convert <br> to newline."""
        assert "\n" in strip_html("Line 1<br>Line 2")
        assert "\n" in strip_html("Line 1<br/>Line 2")
        assert "\n" in strip_html("Line 1<BR>Line 2")

    # List items
    def test_converts_list_items_to_bullets(self):
        """Convert <li> to bullet points."""
        html = "<ul><li>Item A</li><li>Item B</li></ul>"
        result = strip_html(html)
        assert "• Item A" in result
        assert "• Item B" in result
        assert "<li>" not in result

    # Inline formatting
    def test_removes_bold_tags(self):
        """Remove <b> and <strong> tags."""
        assert strip_html("<b>Bold</b>") == "Bold"
        assert strip_html("<strong>Strong</strong>") == "Strong"

    def test_removes_italic_tags(self):
        """Remove <i> and <em> tags."""
        assert strip_html("<i>Italic</i>") == "Italic"
        assert strip_html("<em>Emphasis</em>") == "Emphasis"

    def test_removes_span_and_div_tags(self):
        """Remove generic container tags."""
        assert strip_html("<span>Text</span>") == "Text"
        assert strip_html("<div>Content</div>") == "Content"

    # HTML entities
    def test_decodes_non_breaking_space(self):
        """Decode &nbsp; to space."""
        result = strip_html("Word1&nbsp;Word2")
        assert "&nbsp;" not in result
        assert " " in result

    def test_decodes_ampersand(self):
        """Decode &amp; to &."""
        assert strip_html("A&amp;B") == "A&B"

    def test_decodes_quote_entities(self):
        """Decode quote entities."""
        assert strip_html("&quot;Quote&quot;") == '"Quote"'
        assert strip_html("&apos;Quote&apos;") == "'Quote'"

    def test_decodes_comparison_operators(self):
        """Decode < and > entities."""
        assert strip_html("1&lt;2") == "1<2"
        assert strip_html("2&gt;1") == "2>1"

    def test_decodes_common_entities(self):
        """Decode various HTML entities."""
        assert strip_html("&ndash;") == "–"  # En dash
        assert strip_html("&hellip;") == "…"  # Ellipsis
        assert strip_html("&copy;") == "©"    # Copyright

    # Whitespace handling
    def test_collapses_multiple_spaces(self):
        """Collapse multiple spaces to single."""
        result = strip_html("Word1    Word2")
        assert "    " not in result
        assert result == "Word1 Word2"

    def test_collapses_multiple_newlines(self):
        """Collapse multiple newlines to double."""
        result = strip_html("Line1\n\n\n\nLine2")
        assert "\n\n\n" not in result  # No triple newlines

    def test_preserves_single_newlines(self):
        """Single newlines are preserved."""
        result = strip_html("Line1<br>Line2")
        assert result.count("\n") >= 1

    # Real API response scenarios
    def test_realistic_homework_html(self):
        """Test with realistic Magister homework HTML."""
        html = (
            "<p>Maak opgaven <b>4.1-4.15</b></p>"
            "<br/>"
            "Vragen:<li>Vraag 1</li><li>Vraag 2</li>"
        )
        result = strip_html(html)

        # Should have no HTML
        assert "<p>" not in result
        assert "<br" not in result
        assert "<li>" not in result

        # Should be readable
        assert "Maak opgaven" in result
        assert "4.1-4.15" in result
        assert "•" in result  # Bullets

    def test_realistic_with_entities(self):
        """Test with HTML entities."""
        html = (
            "School&apos;s&nbsp;homework:&nbsp;<br/>"
            "Solve&nbsp;a&amp;b&nbsp;&lt;c&nbsp;problems"
        )
        result = strip_html(html)

        assert "&nbsp;" not in result
        assert "&amp;" not in result
        assert "School's homework:" in result
        assert "a&b<c" in result

    # Edge cases
    def test_empty_string(self):
        """Handle empty string."""
        assert strip_html("") == ""

    def test_none_input(self):
        """Handle None input."""
        assert strip_html(None) == ""

    def test_only_html_tags(self):
        """String with only HTML tags."""
        assert strip_html("<p></p><br/>") == ""

    def test_nested_tags(self):
        """Handle nested HTML tags."""
        html = "<p>Text with <b>bold <i>and italic</i></b> here</p>"
        result = strip_html(html)
        assert result == "Text with bold and italic here"

    def test_malformed_html(self):
        """Handle malformed HTML gracefully."""
        html = "<p>Unclosed tag <b>Bold text"
        result = strip_html(html)
        assert "Unclosed tag" in result
        assert "Bold text" in result
        assert "<" not in result or ">" not in result  # No complete tags
```

### Usage in CLI

```python
from rich.console import Console
from magister_cli.cli.formatters import strip_html
from magister_cli.services.homework import HomeworkItem

def format_homework_item(item: HomeworkItem, console: Console) -> None:
    """Format and print a single homework item."""
    icon = "[red]TOETS[/red]" if item.is_test else "[cyan]Huiswerk[/cyan]"

    # Build subject text with optional lesson number
    subject_text = f"[bold]{item.subject}[/bold]"
    if item.lesson_number:
        subject_text += f" [dim](les {item.lesson_number})[/dim]"

    console.print(f"  {icon} {subject_text}")

    # Sanitize HTML and format description
    clean_description = strip_html(item.description)
    for line in clean_description.split("\n"):
        line = line.strip()
        if line:
            console.print(f"     {line}")

    # Additional metadata
    if item.teacher or item.location:
        details = []
        if item.teacher:
            details.append(f"Docent: {item.teacher}")
        if item.location:
            details.append(f"Lokaal: {item.location}")
        console.print(f"     [dim]{' | '.join(details)}[/dim]")

    # Show attachments if present
    if item.attachments:
        console.print(f"     [yellow]📎 {len(item.attachments)} bijlage(n):[/yellow]")
        for att in item.attachments:
            console.print(f"        • {att.name} [dim]({att.size})[/dim]")

    console.print()
```

---

## Example 3: Implementing Attachment Downloads with Redirects

### Complete Download Implementation

```python
from pathlib import Path
from typing import Optional
import httpx
from magister_cli.api.models import Bijlage
from magister_cli.api.client import MagisterAPIError

class MagisterClient:
    """API client with attachment download support."""

    def get_homework_with_attachments(self, start: date, end: date) -> list[Afspraak]:
        """
        Get homework with attachments populated.

        Two-phase fetch:
        1. Get homework list (lightweight, has_attachment flag)
        2. For items with attachments, fetch full details (separate call)
        """
        # Phase 1: Get list of homework
        appointments = self.get_homework(start, end)

        # Phase 2: Fetch full details only for items with attachments
        result = []
        for afspraak in appointments:
            if afspraak.heeft_bijlagen:
                # Fetch full appointment to get bijlagen array
                full_afspraak = self.get_appointment(afspraak.id)
                result.append(full_afspraak)
            else:
                # No attachments, use list data
                result.append(afspraak)

        return result

    def download_attachment(
        self, bijlage: Bijlage, output_dir: Optional[Path] = None
    ) -> Path:
        """
        Download an attachment to the specified directory.

        Handles:
        - Extracting download path from attachment metadata
        - Stripping /api prefix from paths
        - Following HTTP redirects
        - Creating output directory
        - Handling duplicate filenames

        Args:
            bijlage: Attachment object with download link
            output_dir: Directory to save file (defaults to current directory)

        Returns:
            Path to downloaded file

        Raises:
            MagisterAPIError: If attachment has no download path or download fails
        """
        self._check_client()
        assert self._client is not None

        # Get download path from attachment metadata
        download_path = bijlage.download_path
        if not download_path:
            raise MagisterAPIError(
                f"No download path for attachment: {bijlage.naam}"
            )

        # Handle /api prefix in path
        # Some responses include /api/personen/.../bijlagen/contents
        # Base URL already includes /api, so we need to strip the prefix
        if download_path.startswith("/api/"):
            download_path = download_path[4:]  # Remove "/api"

        # Build full URL
        full_url = f"{self.base_url}{download_path}"

        # Create separate client with follow_redirects for downloads
        # The main client might not have this enabled
        with httpx.Client(
            headers={"Authorization": f"Bearer {self.token}"},
            timeout=self._timeout,
            follow_redirects=True,  # ← CRITICAL: Follow server redirects
        ) as download_client:
            response = download_client.get(full_url)

        # Check for download errors
        if response.status_code >= 400:
            raise MagisterAPIError(
                f"Failed to download attachment: {response.status_code}",
                response.status_code,
            )

        # Determine output directory
        if output_dir is None:
            output_dir = Path.cwd()

        # Create directory if it doesn't exist
        output_dir.mkdir(parents=True, exist_ok=True)

        # Determine output path
        output_path = output_dir / bijlage.naam

        # Handle duplicate filenames
        # If file already exists, add counter (file_1.pdf, file_2.pdf, etc.)
        if output_path.exists():
            stem = output_path.stem  # filename without extension
            suffix = output_path.suffix  # extension (.pdf, etc.)
            counter = 1
            while output_path.exists():
                output_path = output_dir / f"{stem}_{counter}{suffix}"
                counter += 1

        # Write file to disk
        output_path.write_bytes(response.content)

        return output_path
```

### Comprehensive Test Suite

```python
import pytest
import httpx
import respx
from pathlib import Path
from magister_cli.api.models import Bijlage, BijlageLink
from magister_cli.api.client import MagisterClient, MagisterAPIError
from datetime import date

@pytest.fixture
def sample_bijlage():
    """Sample attachment with download link."""
    return {
        "Id": 1,
        "Naam": "homework.pdf",
        "ContentType": "application/pdf",
        "Grootte": 12345,
        "Links": [
            {"Rel": "Contents", "Href": "/api/personen/123/bijlagen/456/contents"}
        ]
    }

@pytest.fixture
def afspraken_with_attachments():
    """Homework list with attachment flags."""
    return {
        "Items": [
            {
                "Id": 1,
                "HeeftBijlagen": True,  # Has attachments
                "Bijlagen": None,  # But details not included in list
            },
            {
                "Id": 2,
                "HeeftBijlagen": False,
            }
        ]
    }

@pytest.fixture
def appointment_with_details(sample_bijlage):
    """Full appointment with attachment details."""
    return {
        "Id": 1,
        "HeeftBijlagen": True,
        "Bijlagen": [sample_bijlage],
    }

class TestAttachmentHandling:
    """Test attachment download flow."""

    def test_bijlage_model_has_download_path(self, sample_bijlage):
        """Bijlage model provides download path."""
        bijlage = Bijlage.model_validate(sample_bijlage)

        assert bijlage.download_path is not None
        assert bijlage.download_path.startswith("/api/")
        assert "contents" in bijlage.download_path

    def test_bijlage_without_contents_link(self):
        """Handle attachment without Contents link."""
        bijlage = Bijlage.model_validate({
            "Id": 1,
            "Naam": "file.pdf",
            "ContentType": "application/pdf",
            "Links": [
                {"Rel": "Other", "Href": "/api/.../other"}
            ]
        })

        assert bijlage.download_path is None

    @respx.mock
    def test_two_phase_attachment_fetch(self, afspraken_with_attachments, appointment_with_details):
        """Attachments require separate API call for details."""
        # Phase 1: List view returns has_attachment flag but no details
        list_route = respx.get("https://test.magister.net/api/personen/123/afspraken").mock(
            return_value=httpx.Response(200, json=afspraken_with_attachments)
        )

        # Phase 2: Detail view returns full attachment data
        detail_route = respx.get("https://test.magister.net/api/personen/123/afspraken/1").mock(
            return_value=httpx.Response(200, json=appointment_with_details)
        )

        with MagisterClient("test", "token") as client:
            client._student_id = 123

            # This should fetch both list and detail
            result = client.get_homework_with_attachments(date(2026, 1, 1), date(2026, 1, 31))

        # Both endpoints should be called
        assert len(list_route.calls) > 0
        assert len(detail_route.calls) > 0

        # Result should have attachment data
        assert result[0].bijlagen is not None
        assert len(result[0].bijlagen) > 0

    @respx.mock
    def test_download_follows_redirects(self, sample_bijlage):
        """Download follows HTTP redirects."""
        # API returns redirect
        respx.get("https://test.magister.net/api/bijlagen/456/contents").mock(
            return_value=httpx.Response(
                302,
                headers={"Location": "https://cdn.example.com/file_uuid.pdf"}
            )
        )

        # Actual file is on CDN
        respx.get("https://cdn.example.com/file_uuid.pdf").mock(
            return_value=httpx.Response(200, content=b"PDF file content here")
        )

        with MagisterClient("test", "token") as client:
            bijlage = Bijlage.model_validate(sample_bijlage)
            output_path = client.download_attachment(bijlage, Path("/tmp/test"))

        # File should exist and contain correct content
        assert output_path.exists()
        assert output_path.read_bytes() == b"PDF file content here"

    @respx.mock
    def test_download_strips_api_prefix(self, sample_bijlage, tmp_path):
        """Strip /api prefix from download path."""
        # Mock the download with correct path handling
        respx.get("https://test.magister.net/personen/123/bijlagen/456/contents").mock(
            return_value=httpx.Response(200, content=b"content")
        )

        with MagisterClient("test", "token") as client:
            bijlage = Bijlage.model_validate(sample_bijlage)

            # get_download_attachment should strip /api prefix
            output_path = client.download_attachment(bijlage, tmp_path)

        # Download should succeed
        assert output_path.exists()

    @respx.mock
    def test_download_creates_output_directory(self, sample_bijlage):
        """Create output directory if it doesn't exist."""
        respx.get("https://test.magister.net/personen/123/bijlagen/456/contents").mock(
            return_value=httpx.Response(200, content=b"content")
        )

        with MagisterClient("test", "token") as client:
            # Non-existent directory
            output_dir = Path("/tmp/test_magister_downloads_unique_dir_12345")
            if output_dir.exists():
                import shutil
                shutil.rmtree(output_dir)

            bijlage = Bijlage.model_validate(sample_bijlage)
            output_path = client.download_attachment(bijlage, output_dir)

        # Directory should be created
        assert output_dir.exists()
        assert output_path.exists()

    @respx.mock
    def test_handles_duplicate_filenames(self, tmp_path):
        """Handle files with same name."""
        respx.get("https://test.magister.net/personen/123/bijlagen/456/contents").mock(
            return_value=httpx.Response(200, content=b"content1")
        )
        respx.get("https://test.magister.net/personen/123/bijlagen/789/contents").mock(
            return_value=httpx.Response(200, content=b"content2")
        )

        with MagisterClient("test", "token") as client:
            bijlage1 = Bijlage.model_validate({
                "Id": 1,
                "Naam": "homework.pdf",
                "ContentType": "application/pdf",
                "Links": [{"Rel": "Contents", "Href": "/api/personen/123/bijlagen/456/contents"}]
            })
            bijlage2 = Bijlage.model_validate({
                "Id": 2,
                "Naam": "homework.pdf",  # Same name!
                "ContentType": "application/pdf",
                "Links": [{"Rel": "Contents", "Href": "/api/personen/123/bijlagen/789/contents"}]
            })

            # Download both
            path1 = client.download_attachment(bijlage1, tmp_path)
            path2 = client.download_attachment(bijlage2, tmp_path)

        # Both should exist with different names
        assert path1.exists()
        assert path2.exists()
        assert path1 != path2
        assert path1.name == "homework.pdf"
        assert path2.name == "homework_1.pdf"

    @respx.mock
    def test_download_error_handling(self, sample_bijlage):
        """Handle download errors gracefully."""
        # Mock download failure
        respx.get("https://test.magister.net/personen/123/bijlagen/456/contents").mock(
            return_value=httpx.Response(404, text="Not found")
        )

        with pytest.raises(MagisterAPIError) as exc_info:
            with MagisterClient("test", "token") as client:
                bijlage = Bijlage.model_validate(sample_bijlage)
                client.download_attachment(bijlage)

        assert exc_info.value.status_code == 404

    def test_attachment_no_download_path(self):
        """Error when attachment has no download path."""
        bijlage = Bijlage.model_validate({
            "Id": 1,
            "Naam": "file.pdf",
            "ContentType": "application/pdf",
            "Links": []  # No links!
        })

        with pytest.raises(MagisterAPIError, match="No download path"):
            with MagisterClient("test", "token") as client:
                client.download_attachment(bijlage)
```

### Usage in CLI

```python
from pathlib import Path
from magister_cli.api import MagisterClient
from magister_cli.auth import get_current_token
from magister_cli.cli.formatters import format_no_auth_error
from magister_cli.services.homework import HomeworkService
from rich.console import Console

console = Console()

def download_attachments(
    days: int = 7,
    subject: str | None = None,
    output_dir: Path | None = None,
    school: str | None = None,
):
    """Download all homework attachments."""
    # Get authentication
    token_data = get_current_token(school)
    if token_data is None:
        format_no_auth_error(console, school)
        raise Exit(1)

    # Default output directory
    if output_dir is None:
        output_dir = Path.cwd() / "magister_bijlagen"

    # Get homework with attachments
    service = HomeworkService(school=school)
    homework_days = service.get_homework(
        days=days,
        subject=subject,
        include_attachments=True,  # ← Triggers two-phase fetch
    )

    # Collect all attachments
    attachments_to_download = []
    for day in homework_days:
        for item in day.items:
            for att in item.attachments:
                attachments_to_download.append((item, att))

    if not attachments_to_download:
        console.print("[yellow]Geen bijlagen gevonden.[/yellow]")
        return

    console.print(f"[bold]📎 {len(attachments_to_download)} bijlage(n) gevonden[/bold]")
    console.print()

    # Download each attachment
    with MagisterClient(token_data.school, token_data.access_token) as client:
        for item, att in attachments_to_download:
            # Create subject subfolder
            subject_dir = output_dir / item.subject.replace("/", "-")

            console.print(f"  Downloaden: [cyan]{att.name}[/cyan] ({att.size})")

            try:
                # Two-step process handled by client:
                # 1. Client verifies attachment has download path
                # 2. Creates separate client with follow_redirects=True
                # 3. Downloads and handles redirects
                output_path = client.download_attachment(att.raw, subject_dir)
                console.print(f"    ✓ Opgeslagen: [dim]{output_path}[/dim]")
            except MagisterAPIError as e:
                console.print(f"    [red]✗ Fout: {e}[/red]")

    console.print()
    console.print(f"[green]✓ Downloads opgeslagen in: {output_dir}[/green]")
```

---

## Summary: When to Use Each Pattern

| Pattern | Problem It Solves | Where Used |
|---------|------------------|-----------|
| **Dual ID Tracking** | Different user types use different IDs | Parent/student accounts, admin/user roles |
| **HTML Sanitization** | API returns formatted content | CLI display, text fields, descriptions |
| **Two-Phase Fetching** | List and detail endpoints have different data | Attachments, detailed views, nested resources |
| **Redirect Following** | File downloads redirect to CDN | File downloads, external links |
| **Duplicate Handling** | Multiple files with same name | File downloads, batch operations |
