# Story 13-11: Remove Exit Simulation & What-If Features

## Priority: MEDIUM

## Problem Statement

The Exit Simulation and What-If analysis features add significant complexity to the codebase without providing proportional value. These features require maintenance overhead and create cognitive load during development. To simplify the system and focus on core functionality, these features should be removed end-to-end.

## Current State

### UI Layer (~650 lines)
- `src/walltrack/ui/pages/exit_simulator.py` - Full page (251+ lines)
- `src/walltrack/ui/components/whatif_modal.py` - Modal component (396 lines)
- Dashboard tab "Exit Simulator" in `dashboard.py`
- What-If buttons in `position_details_sidebar.py` and `positions_list.py`

### Service Layer (~1,200+ lines)
- `src/walltrack/services/exit/simulation_engine.py` - Core simulation engine
- `src/walltrack/services/exit/what_if_calculator.py` - What-If calculator
- `src/walltrack/services/simulation/position_simulator.py` - Position simulator
- `src/walltrack/services/simulation/strategy_comparator.py` - Multi-strategy comparison
- `src/walltrack/services/simulation/global_analyzer.py` - Cross-position analysis

### API Layer (~240 lines)
- `POST /positions/simulate` endpoint
- `GET /analysis/positions/{id}/compare-all` endpoint
- SimulationRequest/SimulationRow models in `routes/positions.py`

### Tests (~75KB)
- 5 unit test files for simulation services
- 1 unit test file for whatif_modal component
- Related tests in position_details_sidebar and positions API tests

## Required Implementation

### Phase 1: Remove UI Components

1. **DELETE** `src/walltrack/ui/pages/exit_simulator.py`
2. **DELETE** `src/walltrack/ui/components/whatif_modal.py`
3. **MODIFY** `src/walltrack/ui/dashboard.py`:
   - Remove Exit Simulator tab/route (~lines 250-270)
   - Remove import of `create_exit_simulator_page`
4. **MODIFY** `src/walltrack/ui/pages/__init__.py`:
   - Remove `create_exit_simulator_page` export
5. **MODIFY** `src/walltrack/ui/components/__init__.py`:
   - Remove whatif_modal exports: `open_whatif_modal`, `fetch_position_for_whatif`, `fetch_strategies_for_whatif`
6. **MODIFY** `src/walltrack/ui/components/position_details_sidebar.py`:
   - Remove What-If button and related handlers
7. **MODIFY** `src/walltrack/ui/components/positions_list.py`:
   - Remove What-If button for closed positions

### Phase 2: Remove Services

1. **DELETE** `src/walltrack/services/exit/simulation_engine.py`
2. **DELETE** `src/walltrack/services/exit/what_if_calculator.py`
3. **DELETE** `src/walltrack/services/simulation/position_simulator.py`
4. **DELETE** `src/walltrack/services/simulation/strategy_comparator.py`
5. **DELETE** `src/walltrack/services/simulation/global_analyzer.py`
6. **MODIFY** `src/walltrack/services/exit/__init__.py`:
   - Remove simulation_engine and what_if_calculator exports
7. **DELETE or MODIFY** `src/walltrack/services/simulation/__init__.py`:
   - Delete entire folder if empty, or remove relevant exports

### Phase 3: Remove API Endpoints

1. **MODIFY** `src/walltrack/api/routes/positions.py`:
   - Remove `POST /positions/simulate` endpoint
   - Remove `GET /analysis/positions/{position_id}/compare-all` endpoint
   - Remove `SimulationRequest`, `SimulationRow` models
   - Remove simulation service imports

### Phase 4: Remove Tests

1. **DELETE** `tests/unit/services/exit/test_simulation_engine.py`
2. **DELETE** `tests/unit/services/exit/test_what_if.py`
3. **DELETE** `tests/unit/services/simulation/test_position_simulator.py`
4. **DELETE** `tests/unit/services/simulation/test_strategy_comparator.py`
5. **DELETE** `tests/unit/services/simulation/test_global_analyzer.py`
6. **DELETE** `tests/unit/ui/components/test_whatif_modal.py`
7. **MODIFY** `tests/unit/ui/components/test_position_details_sidebar.py`:
   - Remove what_if related tests
8. **MODIFY** `tests/unit/api/routes/test_positions.py`:
   - Remove simulation endpoint tests

### Phase 5: Remove Documentation & Artifacts

1. **DELETE** `docs/sprint-artifacts/(To review) epic-12-positions-whatif/` (entire folder)
2. **MODIFY** `docs/sprint-artifacts/(To review) epic-11-config-centralization/`:
   - Delete `stories/11-8-exit-simulation-engine.md`
   - Delete `stories/11-10-exit-simulator-ui.md`
3. **DELETE** `.playwright-mcp/e2e_exit_simulator_page.png`
4. **MODIFY** `tests/e2e/E2E_TEST_STORIES.md`:
   - Remove exit simulator test references

### Phase 6: Update Epic 13 Overview

1. **MODIFY** `epic-13-overview.md`:
   - Remove M3 "Exit simulator page not verified"
   - Remove "What-If simulator functional" from success criteria

## Acceptance Criteria

- [ ] Exit Simulator page removed from UI navigation
- [ ] What-If modal and buttons removed from position components
- [ ] All simulation service files deleted
- [ ] API endpoints removed from positions router
- [ ] All related tests deleted or updated
- [ ] Documentation artifacts cleaned up
- [ ] `uv run pytest` passes with no errors
- [ ] `uv run mypy src/` passes with no errors
- [ ] `uv run ruff check src/` passes with no errors
- [ ] Application starts without import errors
- [ ] No dead imports or references remain

## Files Summary

### To DELETE (15 files)
```
src/walltrack/ui/pages/exit_simulator.py
src/walltrack/ui/components/whatif_modal.py
src/walltrack/services/exit/simulation_engine.py
src/walltrack/services/exit/what_if_calculator.py
src/walltrack/services/simulation/position_simulator.py
src/walltrack/services/simulation/strategy_comparator.py
src/walltrack/services/simulation/global_analyzer.py
src/walltrack/services/simulation/__init__.py
tests/unit/services/exit/test_simulation_engine.py
tests/unit/services/exit/test_what_if.py
tests/unit/services/simulation/test_position_simulator.py
tests/unit/services/simulation/test_strategy_comparator.py
tests/unit/services/simulation/test_global_analyzer.py
tests/unit/ui/components/test_whatif_modal.py
.playwright-mcp/e2e_exit_simulator_page.png
```

### To MODIFY (10 files)
```
src/walltrack/ui/dashboard.py
src/walltrack/ui/pages/__init__.py
src/walltrack/ui/components/__init__.py
src/walltrack/ui/components/position_details_sidebar.py
src/walltrack/ui/components/positions_list.py
src/walltrack/services/exit/__init__.py
src/walltrack/api/routes/positions.py
tests/unit/ui/components/test_position_details_sidebar.py
tests/unit/api/routes/test_positions.py
tests/e2e/E2E_TEST_STORIES.md
```

### Documentation to DELETE
```
docs/sprint-artifacts/(To review) epic-12-positions-whatif/ (entire folder)
docs/sprint-artifacts/(To review) epic-11-config-centralization/stories/11-8-exit-simulation-engine.md
docs/sprint-artifacts/(To review) epic-11-config-centralization/stories/11-10-exit-simulator-ui.md
```

## Dependencies

- None - this is a removal task

## Estimated Effort

3-4 hours

## Impact

- **Reduces codebase by ~2,500 lines**
- **Simplifies maintenance** - fewer features to maintain
- **Reduces test surface** - faster test runs
- **No user-facing impact** - features were not yet in production use

## Rollback Plan

If needed, features can be restored from git history:
```bash
git checkout HEAD~1 -- src/walltrack/services/simulation/
git checkout HEAD~1 -- src/walltrack/services/exit/simulation_engine.py
git checkout HEAD~1 -- src/walltrack/ui/pages/exit_simulator.py
git checkout HEAD~1 -- src/walltrack/ui/components/whatif_modal.py
```
