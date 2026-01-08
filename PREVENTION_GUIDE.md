# Magister CLI - Prevention Guide for Solved Issues

Complete guide for preventing and handling three critical issues in API client development.

## Overview

This guide documents three issues that were discovered and solved in the Magister CLI project. The learnings apply to any API client, especially those dealing with:
- Multi-user systems with different account types
- HTML content in API responses
- File downloads and redirects
- Multi-step API workflows

## The Three Issues

### Issue 1: Parent vs Student Account Handling
**Problem:** Parent accounts use their own ID for authentication but child IDs for API calls.
**Impact:** Parent users see no data or wrong student's data.
**Solution:** Track both IDs, detect account type, use student ID for all data calls.

### Issue 2: HTML Content in API Responses
**Problem:** API returns homework descriptions with embedded HTML tags.
**Impact:** CLI output shows raw HTML tags and entity codes.
**Solution:** Sanitize HTML at display time using regex + entity decoding.

### Issue 3: Attachments Requiring Separate Calls & Redirects
**Problem:** List endpoint doesn't include attachment details; downloads redirect to CDN.
**Impact:** Attachments appear to exist but can't be downloaded.
**Solution:** Two-phase fetch (list + details), separate download client with follow_redirects.

---

## Documentation Structure

### LEARNINGS.md (989 lines)
Comprehensive analysis of each issue with:
- Detailed problem explanation
- Working code patterns
- Detection strategies (how to find similar issues)
- Testing strategies (comprehensive test examples)
- Common pitfalls to avoid
- Reusable code patterns

**Use this for:** Understanding the problem deeply, learning patterns, implementing similar features

**Key sections:**
1. Parent vs Student Account ID Handling
   - Code pattern with dual ID tracking
   - Detection methods
   - Testing strategies
   - Pitfalls and patterns

2. HTML Content Sanitization
   - Comprehensive sanitization function
   - Detection via visual inspection
   - Entity decoding tests
   - Screenshot/terminal output testing

3. Attachment Download and Redirects
   - Two-phase fetch pattern
   - URL path handling
   - Redirect following
   - Duplicate filename handling

### PREVENTION_QUICK_REFERENCE.md (308 lines)
Quick lookup guide with:
- Red flags to watch for
- Prevention checklists
- Quick tests you can run
- Testing templates (copy-paste ready)
- Debugging commands
- Code review checklist
- Common mistakes table

**Use this for:** Quick reference during code review, debugging, or implementation

**Key sections:**
1. Issue Detection (red flags for each)
2. Prevention Checklists
3. Quick Tests
4. Testing Templates
5. Debugging Commands
6. Code Review Checklists

### EXAMPLES_AND_PATTERNS.md (971 lines)
Complete, production-ready code examples with:
- Full working implementations
- Comprehensive test suites
- Usage examples in real CLI code
- Copy-paste ready patterns

**Use this for:** Copy-paste implementations, seeing complete working code

**Key sections:**
1. Complete account handling implementation with tests
2. Complete HTML sanitization with test suite
3. Complete attachment download with test suite
4. Usage patterns in real CLI

---

## How to Use These Documents

### Scenario 1: Adding a Similar Feature
1. Read the relevant section in LEARNINGS.md
2. Copy the pattern from EXAMPLES_AND_PATTERNS.md
3. Adjust for your use case
4. Add tests from the comprehensive test suite
5. Reference PREVENTION_QUICK_REFERENCE.md before code review

### Scenario 2: Debugging a Similar Issue
1. Check red flags in PREVENTION_QUICK_REFERENCE.md
2. Run the quick test
3. Use debugging commands from PREVENTION_QUICK_REFERENCE.md
4. Read problem explanation in LEARNINGS.md
5. Review common pitfalls section

### Scenario 3: Code Review
1. Use code review checklist from PREVENTION_QUICK_REFERENCE.md
2. Verify patterns match EXAMPLES_AND_PATTERNS.md
3. Ensure tests cover scenarios in LEARNINGS.md
4. Check for pitfalls from each section

### Scenario 4: Learning API Client Patterns
1. Start with LEARNINGS.md overview
2. Look at working code in EXAMPLES_AND_PATTERNS.md
3. Study test patterns
4. Review PREVENTION_QUICK_REFERENCE.md for edge cases

---

## Quick Reference by Issue

### Issue 1: Parent vs Student Account IDs

| Resource | Content |
|----------|---------|
| LEARNINGS.md | Complete explanation, detection strategies, test patterns |
| PREVENTION_QUICK_REFERENCE.md | Red flags, checklist, debugging commands |
| EXAMPLES_AND_PATTERNS.md | Full working implementation with test suite |

**Key patterns:**
```python
self._account_id      # Login account ID
self._student_id      # Effective student ID (may be child's)
self._ensure_student_id()  # Get cached student ID
# Use student_id in all data API calls
```

### Issue 2: HTML Content Sanitization

| Resource | Content |
|----------|---------|
| LEARNINGS.md | Sanitization function, entity handling, whitespace normalization |
| PREVENTION_QUICK_REFERENCE.md | Visual inspection test, entity decoding test |
| EXAMPLES_AND_PATTERNS.md | Full sanitization function with comprehensive test suite |

**Key function:**
```python
clean_text = strip_html(api_response_text)
```

### Issue 3: Attachments & Redirects

| Resource | Content |
|----------|---------|
| LEARNINGS.md | Two-phase fetch, redirect handling, URL path logic |
| PREVENTION_QUICK_REFERENCE.md | Red flags, quick test, debugging |
| EXAMPLES_AND_PATTERNS.md | Full download implementation with test suite |

**Key pattern:**
```python
# Phase 1: Check flag
if item.heeft_bijlagen:
    # Phase 2: Fetch details
    full_item = self.get_appointment(item.id)

# Download with redirects
with httpx.Client(follow_redirects=True):
    response = download_client.get(url)
```

---

## Testing Checklist Before Committing

- [ ] All account types tested (student, parent, etc.)
- [ ] HTML sanitization tested with real API samples
- [ ] Attachments tested with redirect mocking
- [ ] Caching prevents redundant API calls
- [ ] Error paths tested (404, 401, 500)
- [ ] Rate limiting handled
- [ ] Duplicate filenames handled
- [ ] Tokens not logged anywhere
- [ ] Tests use respx/httpx mocking
- [ ] Fixtures use realistic API data

---

## File Locations

```
/Users/iamstudios/Desktop/Magister/magister-cli/
├── LEARNINGS.md                      # Main reference (989 lines)
├── PREVENTION_QUICK_REFERENCE.md     # Quick lookup (308 lines)
├── EXAMPLES_AND_PATTERNS.md          # Copy-paste ready code (971 lines)
├── PREVENTION_GUIDE.md               # This file
├── src/magister_cli/api/
│   ├── client.py                     # Account handling, download logic
│   └── models.py                     # Bijlage, Afspraak models
├── src/magister_cli/cli/
│   ├── formatters.py                 # strip_html() implementation
│   └── commands/homework.py          # CLI commands using patterns
└── tests/
    ├── test_api_client.py            # Account handling tests
    └── test_homework_service.py      # Service layer tests
```

---

## Key Takeaways

### 1. API Client Design Principles
- **Be defensive**: Assume APIs might return HTML, have redirects, require redirects
- **Track state carefully**: Use dual IDs when account types differ
- **Cache aggressively**: Avoid redundant calls but make caching explicit
- **Sanitize at boundaries**: Clean external data before displaying

### 2. Testing Patterns
- **Use realistic fixtures**: Real API response samples in tests
- **Mock comprehensively**: Mock both success and error paths, redirects
- **Test edge cases**: Duplicates, missing data, wrong account types
- **Verify actual behavior**: Don't assume, test what really happens

### 3. Code Patterns to Reuse
- **Cached lazy initialization**: `_ensure_student_id()` pattern
- **Two-phase fetching**: List + detail for expensive operations
- **Separate clients**: Use different clients for different concerns (main vs download)
- **Defensive property access**: Link extraction with fallbacks

### 4. Common Pitfalls to Avoid
- Using wrong ID in API calls (account vs student)
- Not following HTTP redirects on downloads
- Skipping HTML sanitization
- Not testing both account types
- Assuming list endpoints have all data
- Not handling duplicate filenames

---

## When These Patterns Apply

### Pattern Recognition

#### Account Type Pattern
Apply when:
- System has multiple user types (parent/student, admin/user, etc.)
- Different types use different IDs for API calls
- Type detection happens after authentication

#### HTML Sanitization Pattern
Apply when:
- APIs return formatted content (HTML, markdown, rich text)
- Content displays in terminal/CLI
- Need human-readable output

#### Two-Phase Fetching Pattern
Apply when:
- List endpoints don't include all details
- Fetching details is expensive
- Details are optional/conditional

#### Redirect Following Pattern
Apply when:
- Downloads involve redirects
- Files stored on different servers (CDN, etc.)
- API uses redirect for access control

---

## Reference: Real Code Locations

### Account Type Implementation
**File:** `/Users/iamstudios/Desktop/Magister/magister-cli/src/magister_cli/api/client.py`
**Lines:** 54-170
**Functions:** `get_account()`, `get_children()`, `_ensure_student_id()`

### HTML Sanitization
**File:** `/Users/iamstudios/Desktop/Magister/magister-cli/src/magister_cli/cli/formatters.py`
**Lines:** 13-37
**Function:** `strip_html()`

### Attachment Download
**File:** `/Users/iamstudios/Desktop/Magister/magister-cli/src/magister_cli/api/client.py`
**Lines:** 217-279
**Functions:** `get_homework_with_attachments()`, `download_attachment()`

### Tests
**Files:**
- `/Users/iamstudios/Desktop/Magister/magister-cli/tests/test_api_client.py`
- `/Users/iamstudios/Desktop/Magister/magister-cli/tests/test_homework_service.py`

---

## Future Enhancements

These learnings can be extended for:
1. **Multi-child parent accounts**: Currently uses first child, could allow selection
2. **Streaming downloads**: Currently buffers entire file in memory
3. **Progress tracking**: Downloads could show progress bar
4. **Batch operations**: Download multiple items in parallel
5. **Content type handling**: Extend sanitization for markdown, rich text, etc.
6. **Caching layer**: Cache API responses with TTL
7. **Retry strategy**: Exponential backoff for rate limits
8. **Monitoring**: Log metrics for API calls, cache hits, download speeds

---

## Contributing Back

When you solve a new issue:
1. Document in LEARNINGS.md format
2. Add code examples to EXAMPLES_AND_PATTERNS.md
3. Create testing patterns in PREVENTION_QUICK_REFERENCE.md
4. Reference in this guide
5. Update code comments to link to learnings

This compounds the team's knowledge over time.

---

## Questions?

Refer to:
- **"What went wrong?"** → Red flags in PREVENTION_QUICK_REFERENCE.md
- **"How do I fix it?"** → Patterns in EXAMPLES_AND_PATTERNS.md
- **"Why does it work this way?"** → Explanation in LEARNINGS.md
- **"What should I test?"** → Test suites in EXAMPLES_AND_PATTERNS.md
- **"What will reviewers look for?"** → Checklists in PREVENTION_QUICK_REFERENCE.md
