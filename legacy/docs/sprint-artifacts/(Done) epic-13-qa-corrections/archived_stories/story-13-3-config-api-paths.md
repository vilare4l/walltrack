# Story 13-3: Fix Config API Path Mismatch

## Priority: CRITICAL

## Problem Statement

The UI calls `/api/config/{table}` but the API implements `/api/config/lifecycle/{table}`. This breaks the entire config page.

## Evidence

**UI Code (`config_handlers.py`):**
```python
response = await client.get(f"/api/config/{table}")  # Line 23
```

**API Implementation (`config.py`):**
```python
@router.get("/lifecycle/{table}")  # Actual path
async def get_active_config(table: str):
```

## Impact

- Config page cannot load any configurations
- Draft/activate workflow is broken
- Epic 11 UI stories are non-functional

## Solution Options

### Option A: Update UI to use /lifecycle/ paths (Recommended)
Modify `config_handlers.py` to use the correct paths.

### Option B: Add alias routes in API
Add convenience routes that redirect to /lifecycle/ endpoints.

## Recommended: Option A

Less code change, maintains clean API structure.

### Changes Required

**File: `src/walltrack/ui/pages/config_handlers.py`**

```python
# Line 23: GET config
# Before:
response = await client.get(f"/api/config/{table}")
# After:
response = await client.get(f"/api/config/lifecycle/{table}")

# Line 45: GET all versions
# Before:
response = await client.get(f"/api/config/{table}/all")
# After:
response = await client.get(f"/api/config/lifecycle/{table}/all")

# Line 67: POST draft
# Before:
response = await client.post(f"/api/config/{table}/draft")
# After:
response = await client.post(f"/api/config/lifecycle/{table}/draft")

# Line 89: PATCH draft
# Before:
response = await client.patch(f"/api/config/{table}/draft", json=data)
# After:
response = await client.patch(f"/api/config/lifecycle/{table}/draft", json=data)

# Line 111: POST activate
# Before:
response = await client.post(f"/api/config/{table}/activate")
# After:
response = await client.post(f"/api/config/lifecycle/{table}/activate")

# Line 133: POST restore
# Before:
response = await client.post(f"/api/config/{table}/{id}/restore")
# After:
response = await client.post(f"/api/config/lifecycle/{table}/{id}/restore")

# Line 155: DELETE draft
# Before:
response = await client.delete(f"/api/config/{table}/draft")
# After:
response = await client.delete(f"/api/config/lifecycle/{table}/draft")
```

## Acceptance Criteria

- [ ] All config_handlers.py endpoints use `/api/config/lifecycle/` prefix
- [ ] Config page loads configurations successfully
- [ ] Draft creation works
- [ ] Draft update works
- [ ] Activate works
- [ ] Delete draft works
- [ ] Restore archived works
- [ ] Audit log endpoint works

## Files to Modify

- `src/walltrack/ui/pages/config_handlers.py`

## Testing

1. Navigate to Config page
2. Verify Trading config loads
3. Create a draft
4. Modify draft
5. Activate draft
6. Verify audit log shows changes

## Estimated Effort

30 minutes
