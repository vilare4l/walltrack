# Story 13-10: UI Polish & Cleanup

## Priority: MEDIUM

## Problem Statement

Several UI issues identified during review:

1. **French text in components** - Should be English
2. **Duplicate positions components** - positions.py vs positions_list.py
3. **Exit simulator page** - Needs verification
4. **Legacy config_panel.py** - Uses old API endpoints

## Issues Detail

### Issue 1: French Text

**File: `src/walltrack/ui/components/position_details_sidebar.py`**

```python
# Line 169:
"Stratégie Active"  # Should be "Active Strategy"

# Line 188:
"Prochain TP dans"  # Should be "Next TP in"

# Line 242:
"Résultat Final"  # Should be "Final Result"

# Line 254:
"Source"  # Could stay as-is (same in English)
```

### Issue 2: Duplicate Positions Components

**Files:**
- `src/walltrack/ui/components/positions.py` - Legacy, uses sample data
- `src/walltrack/ui/components/positions_list.py` - New, uses real API

The legacy `positions.py` should be removed or clearly marked as deprecated.

### Issue 3: Exit Simulator Page

**File:** `src/walltrack/ui/pages/exit_simulator.py`

Needs verification that:
- It loads correctly
- Calls correct API endpoints
- Displays simulation results properly

### Issue 4: Legacy Config Panel

**File:** `src/walltrack/ui/components/config_panel.py`

Uses old endpoints:
```python
GET /api/v1/scoring/config
GET /api/v1/threshold/config
PUT /api/v1/scoring/config/weights
PUT /api/v1/threshold/config
```

Should migrate to ConfigService or mark as deprecated.

## Solution

### Part 1: Fix French Text

**File: `src/walltrack/ui/components/position_details_sidebar.py`**

```python
# Line 169:
# Before: "Stratégie Active"
# After: "Active Strategy"

# Line 188:
# Before: "Prochain TP dans"
# After: "Next TP in"

# Line 242:
# Before: "Résultat Final"
# After: "Final Result"
```

### Part 2: Handle Duplicate Components

**Option A: Remove positions.py** (Recommended)
- Delete `components/positions.py`
- Update any imports that reference it

**Option B: Mark as deprecated**
- Add deprecation warning to module docstring
- Add comment pointing to positions_list.py

### Part 3: Verify Exit Simulator

Perform manual testing:
1. Navigate to Exit Simulator page
2. Select a position
3. Select strategies to simulate
4. Run simulation
5. Verify results display correctly

If issues found, create sub-tasks.

### Part 4: Handle Legacy Config Panel

**Option A: Migrate to ConfigService** (More work)
- Update API calls to use new endpoints
- Use config lifecycle instead of direct updates

**Option B: Mark as deprecated and hide** (Quick fix)
- Add deprecation warning
- Remove from navigation if possible

## Acceptance Criteria

- [ ] All French text replaced with English
- [ ] positions.py removed or marked deprecated
- [ ] Exit simulator page verified working
- [ ] config_panel.py decision made (migrate or deprecate)
- [ ] No console errors in Gradio UI
- [ ] All pages load without errors

## Files to Modify

- `src/walltrack/ui/components/position_details_sidebar.py`
- `src/walltrack/ui/components/positions.py` (remove or deprecate)
- `src/walltrack/ui/components/config_panel.py` (migrate or deprecate)
- `src/walltrack/ui/pages/exit_simulator.py` (verify)

## Testing

1. **Manual UI Testing:**
   - Navigate all pages
   - Check for French text
   - Check for console errors
   - Verify all modals open/close

2. **Playwright Tests (Phase 3):**
   - Page load tests
   - Modal interaction tests
   - Form submission tests

## Estimated Effort

2-3 hours

## Notes

This is a cleanup story - all changes are cosmetic/organizational. No functional changes to core logic.
