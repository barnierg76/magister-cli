# Prevention Quick Reference - Magister CLI Issues

Quick lookup guide for preventing the three major issues that were solved.

## Issue 1: Parent vs Student Account IDs

### Detection: Red Flags
- [ ] Empty results when there should be data
- [ ] Different data appears for parent than expected
- [ ] API returns 403/401 for some endpoints but not others
- [ ] Account ID in logs doesn't match student/child ID

### Prevention Checklist
```python
# 1. Always track dual IDs
self._account_id    # Login account
self._student_id    # Effective student (may be different)

# 2. Detect account type early
account = self.get_account()
self._is_parent = account.is_parent

# 3. Use student_id for ALL data API calls
student_id = self._ensure_student_id()
data = self._request("GET", f"/personen/{student_id}/...")

# 4. Test both account types
@pytest.mark.parametrize("account_type", ["student", "parent"])
def test_data_endpoints(account_type):
    # Test with both fixture types
```

### Quick Test
```bash
# Test with parent account
magister login --school myschool  # Parent account
magister homework list  # Should show child's homework

# Verify IDs in debug logs
MAGISTER_DEBUG=1 magister homework list
```

---

## Issue 2: HTML in API Responses

### Detection: Red Flags
- [ ] Output shows `<p>`, `<br/>`, `&nbsp;` in text
- [ ] Line breaks look wrong or missing
- [ ] Bullet points or lists don't render properly
- [ ] Text has entity codes like `&amp;`

### Prevention Checklist
```python
# 1. Always sanitize at display boundary
clean_text = strip_html(api_response_text)

# 2. Test with realistic HTML samples
html_samples = [
    "<p>Paragraph</p><br/>",
    "List:<li>Item A</li><li>Item B</li>",
    "Entities: &nbsp; &amp; &quot;",
]

for sample in html_samples:
    result = strip_html(sample)
    assert "<" not in result
    assert "&" not in result

# 3. Use comprehensive regex patterns
# Convert blocks to newlines
# Decode entities
# Normalize whitespace
```

### Quick Test
```bash
# Run homework command and check output
magister homework list

# Should see:
# ✓ No visible HTML tags
# ✓ Readable bullet points (•)
# ✓ Proper line breaks
# ✗ No &nbsp; or &amp;
```

---

## Issue 3: Attachments and Redirects

### Detection: Red Flags
- [ ] Downloads fail silently (no error, empty file)
- [ ] Download starts but gets incomplete file
- [ ] `Bijlagen` field is None when `HeeftBijlagen=True`
- [ ] Download link returns redirect but file doesn't arrive

### Prevention Checklist
```python
# 1. Check has_attachment flag before fetching
if item.heeft_bijlagen:
    full_item = self.get_attachment_details(item.id)

# 2. Extract download link correctly
download_path = bijlage.download_path
if not download_path:
    raise Error("No download path available")

# 3. Handle URL prefix stripping
if download_path.startswith("/api/"):
    download_path = download_path[4:]

# 4. Use separate client with follow_redirects
with httpx.Client(follow_redirects=True) as client:
    response = client.get(url)

# 5. Handle duplicate filenames
if output_path.exists():
    output_path = output_dir / f"{stem}_{counter}{suffix}"
```

### Quick Test
```bash
# Download attachments and verify
magister homework download --days 7

# Check:
# ✓ Files actually created
# ✓ File sizes are reasonable
# ✓ Files are readable (not HTML/redirect page)
# ✓ No filename collisions
```

---

## Testing Templates

### Template 1: Account Type Test
```python
@respx.mock
def test_parent_vs_student(account_type):
    """Test both account types."""
    if account_type == "parent":
        account_data = {..., "Groep": [{"Naam": "Ouder"}]}
        children_data = {"Items": [{"Id": 999, ...}]}
        respx.get("/.../kinderen").mock(...)
        expected_id = 999  # Child ID
    else:
        account_data = {..., "Groep": [{"Naam": "Leerling"}]}
        expected_id = 123  # Own ID

    respx.get("/.../account").mock(return_value=account_data)

    with MagisterClient("test", "token") as client:
        client.get_account()
        assert client.person_id == expected_id
```

### Template 2: HTML Sanitization Test
```python
def test_html_variants():
    """Test all HTML variations."""
    test_cases = [
        ("<p>Text</p>", "Text"),
        ("<br/>", "\n"),
        ("<li>Item</li>", "• Item"),
        ("&nbsp;&amp;", " &"),
    ]

    for html, expected in test_cases:
        result = strip_html(html)
        assert expected in result
```

### Template 3: Download Test
```python
@respx.mock
def test_download_flow():
    """Test attachment download."""
    # List has flag
    respx.get("/.../afspraken").mock(json={"Items": [{
        "HeeftBijlagen": True, "Bijlagen": None
    }]})

    # Detail has attachment
    respx.get("/.../afspraken/1").mock(json={
        "Bijlagen": [{"Href": "/api/.../contents"}]
    })

    # Download follows redirect
    respx.get("/.../contents").mock(
        return_value=httpx.Response(302, headers={"Location": "https://cdn/.../file.pdf"})
    )
    respx.get("https://cdn/.../file.pdf").mock(content=b"file data")

    # ... test download succeeds
```

---

## Debugging Commands

### Debug Parent Account Issue
```bash
# Enable debug logging
export MAGISTER_LOG_LEVEL=DEBUG

# Check what IDs are being used
magister -v homework list 2>&1 | grep -E "person_id|student_id|account_id"

# Compare account vs student ID
magister debug account-info
```

### Debug HTML Issue
```bash
# Capture raw API response
magister -v homework list --days 1 2>&1 | grep -A20 "Inhoud"

# Check if HTML is still present
magister homework list | grep -E "<|&[a-z]+;"
```

### Debug Download Issue
```bash
# Test single attachment
magister homework download --days 1 --output ./test_download

# Check file properties
file test_download/*
hexdump -C test_download/* | head -20

# Check if file looks like HTML/redirect page
cat test_download/*
```

---

## Code Review Checklist

When reviewing API client changes:

### For Account Type Changes
- [ ] Both `_account_id` and `_student_id` are tracked
- [ ] Account type detection happens in `get_account()`
- [ ] All data API calls use `_student_id` not `_account_id`
- [ ] Tests cover both parent and student accounts
- [ ] Parent account tests include children fetch

### For Content Display Changes
- [ ] `strip_html()` is called before displaying user content
- [ ] HTML test cases cover real API response samples
- [ ] Entity decoding is tested (check for `&nbsp;`, etc.)
- [ ] Whitespace normalization doesn't break formatting
- [ ] Output is tested with `rich` console for rendering

### For Download/File Changes
- [ ] `heeft_bijlagen` flag is checked before fetching details
- [ ] Details are fetched separately with `get_appointment()`
- [ ] Download link is extracted from `Links` array
- [ ] `follow_redirects=True` is set on download client
- [ ] Duplicate filename handling is tested
- [ ] File size/content is validated after download

---

## Common Mistakes to Avoid

| Mistake | Why Bad | Fix |
|---------|---------|-----|
| Use `account_id` in data endpoints | Gets wrong data or 403 error | Always use `student_id` |
| Skip HTML sanitization | Raw HTML tags show in output | Always call `strip_html()` |
| Don't follow redirects | Download fails silently | Set `follow_redirects=True` |
| Assume list has attachment data | Bijlagen is None | Fetch details separately |
| Don't test parent accounts | Works for students, breaks for parents | Test both types |
| Forget to decode entities | `&nbsp;` shows in output | Use `html.unescape()` |
| Use single client for downloads | Can't follow redirects | Create separate client |
| Don't handle duplicate files | Later downloads overwrite | Add counter logic |

---

## When Adding Similar Features

If you're adding similar API client features:

1. **Determine if dual IDs needed**
   - Do users have different roles that affect API calls?
   - Document which ID is used where

2. **Check for HTML content**
   - Does API return formatted text?
   - Create sanitization function
   - Test with API response samples

3. **Check for multi-step processes**
   - Does fetching file data require separate call?
   - Does download involve redirects?
   - Create separate methods for each step

4. **Add comprehensive tests**
   - Create realistic API response fixtures
   - Test both common and edge cases
   - Test with actual HTTP client mocking

5. **Document the pattern**
   - Add comments explaining why dual IDs/calls/etc. exist
   - Reference similar code elsewhere in codebase
   - Add to LEARNINGS.md when complete
