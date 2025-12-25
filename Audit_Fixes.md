# Flowrex Audit Fixes Plan

**Audit Date:** December 25, 2025  
**Auditor:** Flowrex Planning Agent  
**Scope:** Complete codebase and meta-knowledge file review

---

## Executive Summary

| Category | Status |
|----------|--------|
| **Prompts Completed** | 01-13 ✅ |
| **Prompts Pending** | 14-18 |
| **Backend Tests** | ✅ 210/210 passing |
| **Frontend Tests** | ✅ 41/41 passing |
| **Frontend Build** | ✅ Passing |
| **Critical Issues** | ~~1~~ → 0 ✅ RESOLVED |
| **High Priority Issues** | ~~5~~ → 2 remaining |
| **Medium Priority Issues** | ~~6~~ → 3 remaining |
| **Low Priority Issues** | 3 |

---

## 🟢 RESOLVED ISSUES

### ~~C1: Rate Limiter Breaks All Backend Tests~~ ✅ FIXED

**Fixed:** Added `request: Request` parameter to `login()` and `refresh()` functions.
Also added `HTTPAuthorizationCredentials` import for logout endpoint.

### ~~H1: Tasks.md Out of Sync~~ ✅ FIXED

**Fixed:** Updated Tasks.md with correct prompt names and marked Prompt 13 complete.

### ~~H2: Completed_Tasks.md Missing Prompt 13 Entry~~ ✅ FIXED

**Fixed:** Added comprehensive Prompt 13 completion entry with all deliverables.

### ~~H3: Memories.md Has Stale Information~~ ✅ FIXED

**Fixed:** Updated test counts and added new gotchas about rate limiting and test isolation.

### ~~M5: Skills.md Incomplete for Prompt 13~~ ✅ FIXED

**Fixed:** Added Frontend Charting (Recharts) section and Multi-Tenancy Testing skills.

### ~~M6: References.md Outdated~~ ✅ FIXED

**Fixed:** Added all current stack references including Recharts, React Query, TailwindCSS, Jest, SlowAPI.

---

## 🔴 CRITICAL ISSUES (P0) - Must Fix Immediately

### C1: Rate Limiter Breaks All Backend Tests

**Location:** [backend/app/api/v1/auth_routes.py](backend/app/api/v1/auth_routes.py#L42-L43)

**Problem:** The `@limiter.limit()` decorator from `slowapi` requires a `request: Request` parameter in the function signature. Current implementation is missing it:

```python
@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login(credentials: UserLogin, response: Response, db: AsyncSession = Depends(get_db)):
    # ❌ MISSING: request: Request parameter
```

**Impact:**
- 210 backend tests cannot import/run
- Application cannot start
- All development blocked

**Fix:**
```python
from fastapi import Request

@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login(
    request: Request,  # ADD THIS
    credentials: UserLogin, 
    response: Response, 
    db: AsyncSession = Depends(get_db)
):
```

Same fix needed for `refresh()` function at line 66.

**Priority:** P0 - IMMEDIATE  
**Estimated Effort:** 10 minutes  
**Assigned To:** Builder Agent

---

## 🟡 HIGH PRIORITY ISSUES (P1)

### H1: Tasks.md Out of Sync with Completed_Tasks.md

**Location:** [Tasks.md](Tasks.md)

**Problem:** Tasks.md shows different prompt descriptions and doesn't reflect Prompt 13 completion:

| Prompt | Tasks.md Says | Actual Status |
|--------|---------------|---------------|
| 13 | "Strategy Dashboard" | ✅ Completed as "UI Dashboards" |
| 14 | "Backtest Dashboard" | Not Started - Actually "Settings and Modes" |
| 15 | "Risk & Journal Dashboard" | Not Started - Actually "Testing and Validation" |
| 16 | "Integration Testing" | Not Started - Actually "Simulation and Demo Mode" |
| 17 | "Documentation" | Not Started - Actually "Deployment Prep" |
| 18 | "Deployment & DevOps" | Not Started - Actually "Production Deployment" |

**Fix:** Update Tasks.md to match actual prompt file names and mark Prompt 13 complete.

**Priority:** P1 - HIGH  
**Estimated Effort:** 5 minutes

---

### H2: Completed_Tasks.md Missing Prompt 13 Entry

**Location:** [Completed_Tasks.md](Completed_Tasks.md)

**Problem:** Prompt 13: UI Dashboards was completed but not documented.

**Missing Documentation:**
- 10 dashboard pages created
- Recharts integration
- Build passing
- TypeScript type fixes

**Fix:** Add Prompt 13 completion entry with all deliverables.

**Priority:** P1 - HIGH  
**Estimated Effort:** 10 minutes

---

### H3: Memories.md Has Stale/Incorrect Information

**Location:** [Memories.md](Memories.md#L88-L99)

**Problem:** Test counts section says "210 backend tests" but backend tests currently don't run due to C1.

**Also:** Notes section still references some outdated fixture names.

**Fix:** Update after C1 is fixed and tests verified.

**Priority:** P1 - HIGH (after C1 fix)  
**Estimated Effort:** 15 minutes

---

### H4: No Dashboard Page Tests

**Location:** [frontend/__tests__/](frontend/__tests__/)

**Problem:** 10 new dashboard pages from Prompt 13 have zero test coverage:

| Page | Test File | Status |
|------|-----------|--------|
| `app/page.tsx` | None | ❌ Missing |
| `app/strategies/page.tsx` | None | ❌ Missing |
| `app/backtest/page.tsx` | None | ❌ Missing |
| `app/optimization/page.tsx` | None | ❌ Missing |
| `app/signals/page.tsx` | None | ❌ Missing |
| `app/execution/page.tsx` | None | ❌ Missing |
| `app/performance/page.tsx` | None | ❌ Missing |
| `app/journal/page.tsx` | None | ❌ Missing |
| `app/ai-chat/page.tsx` | None | ❌ Missing |
| `app/settings/page.tsx` | None | ❌ Missing |

**Fix:** Create test files for each dashboard page with basic render tests.

**Priority:** P1 - HIGH (before Prompt 15)  
**Estimated Effort:** 2-3 hours

---

### H5: Frontend React Warning in Tests

**Location:** [frontend/__tests__/hooks/useAuth.test.tsx](frontend/__tests__/hooks/useAuth.test.tsx)

**Problem:** Console warning during test execution:
```
Warning: An update to TestComponent inside a test was not wrapped in act(...)
```

**Impact:** While tests pass, this indicates potential async state update issues.

**Fix:** Wrap state-changing operations in `act()` or use `waitFor()`.

**Priority:** P1 - HIGH  
**Estimated Effort:** 30 minutes

---

## 🟠 MEDIUM PRIORITY ISSUES (P2)

### M1: Prompt 14 Prerequisites Not Met

**Location:** [prompts/14_SETTINGS_AND_MODES.md](prompts/14_SETTINGS_AND_MODES.md#L8-L11)

**Problem:** Prompt 14 requires:
- ✅ Prompt 09 (Risk Engine) - Complete
- ✅ Prompt 12 (Frontend Core) - Complete
- ✅ Prompt 13 (UI Dashboards) - Complete
- ✅ Database models exist

But Prompt 14 expects to CREATE new models (`SystemSettings`, `UserPreferences`, `SettingsAudit`) that don't exist yet.

**Note:** Current `SystemConfig` in ai_agent.py is different from `SystemSettings` in Prompt 14.

**Fix:** This is expected - Prompt 14 implementation will create these.

**Priority:** P2 - MEDIUM (informational)

---

### M2: Risk Constants Location Mismatch

**Location:** Risk constants file path

**Problem:** 
- Prompt 14 references: `backend/app/risk_engine/constants.py`
- Actual location: `backend/app/risk/constants.py`

**Fix:** Update Prompt 14 references or move file to match expected location.

**Priority:** P2 - MEDIUM  
**Estimated Effort:** 5 minutes (path update) or 15 minutes (move file)

---

### M3: No Integration Tests Running

**Location:** [backend/tests/integration/](backend/tests/integration/)

**Problem:** Integration test directory exists but status unknown. Need to verify tests exist and can run.

**Fix:** Audit integration tests after C1 is resolved.

**Priority:** P2 - MEDIUM  
**Estimated Effort:** 30 minutes

---

### M4: E2E Tests Skip by Default

**Location:** [backend/tests/e2e/](backend/tests/e2e/)

**Problem:** E2E tests require `--e2e` flag and running services. No CI/CD pipeline configured to run them.

**Current State:** Tests exist but are never automatically executed.

**Fix:** Consider adding E2E tests to CI/CD workflow with service containers.

**Priority:** P2 - MEDIUM (before Prompt 15)  
**Estimated Effort:** 2-3 hours

---

### M5: Skills.md Incomplete for Prompt 13

**Location:** [Skills.md](Skills.md)

**Problem:** Missing skills acquired from Prompt 13:
- Recharts integration (LineChart, BarChart, PieChart, AreaChart)
- Responsive chart containers
- Chart data transformation patterns
- TypeScript strict mode chart typing

**Fix:** Add frontend charting skills section.

**Priority:** P2 - MEDIUM  
**Estimated Effort:** 10 minutes

---

### M6: References.md Outdated

**Location:** [References.md](References.md)

**Problem:** 
- Still says "04+: TBD (read prompts as needed)"
- Missing Recharts documentation link
- Missing React Query documentation link
- Missing TailwindCSS documentation link

**Fix:** Update with all current stack references.

**Priority:** P2 - MEDIUM  
**Estimated Effort:** 10 minutes

---

## 🔵 LOW PRIORITY ISSUES (P3)

### L1: Inconsistent Test Count Tracking

**Location:** Multiple files

**Problem:** Test counts mentioned in different places may drift:
- Memories.md says 210+41=251
- Completed_Tasks.md says 210+41
- Prompt 12 completion says 41 frontend tests

**Fix:** Establish single source of truth for test counts (possibly auto-generated).

**Priority:** P3 - LOW  
**Estimated Effort:** 30 minutes

---

### L2: Debug Code Remnants

**Location:** Various files (need grep search)

**Problem:** May have `console.log` or `print` statements left from debugging.

**Fix:** Audit for debug statements before production.

**Priority:** P3 - LOW (before Prompt 17)  
**Estimated Effort:** 1 hour

---

### L3: Sidebar Navigation May Not Match All Routes

**Location:** [frontend/components/layout/Sidebar.tsx](frontend/components/layout/Sidebar.tsx)

**Problem:** Need to verify all 10 dashboard routes are in sidebar navigation.

**Fix:** Cross-reference sidebar links with app/ directory.

**Priority:** P3 - LOW  
**Estimated Effort:** 15 minutes

---

## Implementation Order

### Phase 1: Unblock Development (1 hour)
1. **[C1]** Fix rate limiter decorator in auth_routes.py
2. Verify 210 backend tests pass
3. **[H2]** Add Prompt 13 to Completed_Tasks.md

### Phase 2: Meta-Knowledge Sync (30 minutes)
4. **[H1]** Update Tasks.md with correct prompt names
5. **[H3]** Update Memories.md test counts
6. **[M5]** Add charting skills to Skills.md
7. **[M6]** Update References.md

### Phase 3: Test Coverage (3 hours)
8. **[H4]** Create dashboard page tests (10 files)
9. **[H5]** Fix React act() warning in useAuth tests
10. **[M3]** Audit integration tests

### Phase 4: Before Prompt 14 (Recommended)
11. **[M2]** Resolve risk constants path (optional)
12. **[L3]** Verify sidebar navigation

### Phase 5: Before Prompt 15
13. **[M4]** Configure E2E tests in CI/CD
14. **[L2]** Audit for debug code

---

## Verification Checklist

After Builder Agent implements fixes:

- [ ] `pytest tests/unit/ -q` passes (210 tests)
- [ ] `pytest tests/integration/ -q` passes
- [ ] `npm run build` passes
- [ ] `npm test` passes (41+ tests, no warnings)
- [ ] Tasks.md matches prompt file names
- [ ] Completed_Tasks.md has Prompt 13 entry
- [ ] Memories.md has accurate test counts
- [ ] Skills.md includes Prompt 13 skills
- [ ] References.md is up to date

---

## Handoff to Builder Agent

The Builder Agent should:

1. **Start with C1** - This unblocks everything
2. **Run full test suite** to establish baseline
3. **Update meta-knowledge files** in order
4. **Create dashboard tests** (can be batched)
5. **Verify checklist items** before marking complete

**Note:** Do NOT proceed to Prompt 14 until Phase 1 and Phase 2 are complete.

---

*This audit plan was generated by the Flowrex Planning Agent. Builder Agent should implement fixes in priority order.*
