---
status: complete
priority: p2
issue_id: "012"
tags: [code-review, testing]
dependencies: []
---

# Missing Tests for Async Service and Core Logic

## Problem Statement

The primary service implementation (`MagisterAsyncService`) and core business logic (`MagisterCore`) have zero test coverage. This is the code that runs for MCP tools.

**Why it matters:** Main code path for AI agents is untested. Bugs won't be caught before production.

## Findings

**Evidence:**
- `test_homework_service.py` - Tests legacy sync service
- NO tests for `services/async_magister.py` (primary implementation!)
- NO tests for `services/core.py` (business logic)
- NO tests for MCP server tools

**Test-to-Code Ratio:**
- 5 test files for 49 source files (10.2%)
- Below recommended 1:1 ratio

## Proposed Solutions

### Option A: Add Core Test Coverage (Recommended)
1. Test `MagisterCore` static methods (pure functions, easy to test)
2. Test `MagisterAsyncService` with mocked httpx.AsyncClient
3. Test MCP tools with mocked service

**Pros:** Covers critical code paths
**Cons:** Time investment
**Effort:** Medium (4-6 hours)
**Risk:** Low - adds safety

## Recommended Action
<!-- To be filled during triage -->

## Technical Details

**Tests to create:**
- `tests/test_core.py` - Business logic tests
- `tests/test_async_magister.py` - Async service tests
- `tests/test_mcp_server.py` - MCP tool tests

## Acceptance Criteria

- [ ] MagisterCore methods have unit tests
- [ ] MagisterAsyncService has integration tests with mocks
- [ ] MCP tools have basic test coverage
- [ ] Test coverage > 50%

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-01-08 | Created from code review | Testing gap |

## Resources

- Pattern analysis report
