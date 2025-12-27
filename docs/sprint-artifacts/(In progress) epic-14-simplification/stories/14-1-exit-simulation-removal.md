# Story 14.1: Exit Simulation Removal

## Story Info
- **Epic**: Epic 14 - System Simplification & Automation
- **Status**: ready-for-dev
- **Priority**: P1 - High
- **Story Points**: 3
- **Depends on**: None (can run in parallel with 14-2)

## User Story

**As a** system operator,
**I want** the unused Exit Simulation and What-If features removed from the codebase,
**So that** I have a cleaner, more maintainable system with ~2,500 fewer lines of code.

## Acceptance Criteria

### AC 1: UI Pages Removal
**Given** the WallTrack dashboard is running
**When** I navigate through all tabs
**Then** the "Exit Simulator" tab no longer appears in the navigation
**And** the dashboard loads without any import errors
**And** no console errors appear in the Gradio UI

### AC 2: UI Components Removal
**Given** the position management UI
**When** I view a position in the details sidebar
**Then** the "What-If Analysis" button no longer appears
**And** when I view the positions list
**Then** the "Simulate" action button no longer appears
**And** whatif_modal is completely removed

### AC 3: Backend Services Removal
**Given** the codebase after changes
**When** I search for simulation-related files
**Then** `services/exit/simulation_engine.py` no longer exists (533 lines removed)
**And** `services/exit/what_if_calculator.py` no longer exists (242 lines removed)
**And** `services/simulation/` folder no longer exists (1,053 lines removed)
**And** no dead imports remain in `services/exit/__init__.py`

### AC 4: API Endpoints Removal
**Given** the API routes after changes
**When** I check `routes/positions.py`
**Then** the simulation endpoint is removed
**And** `SimulationRequest` and `SimulationRow` models are removed
**And** simulation-related imports are cleaned up

### AC 5: Test Cleanup
**Given** the test suite after changes
**When** I run `uv run pytest`
**Then** all tests pass
**And** simulation test files are deleted
**And** no test failures due to missing imports

### AC 6: Quality Gates
**Given** the codebase after all changes
**When** I run quality checks
**Then** `uv run mypy src/` passes with no errors
**And** `uv run ruff check src/` passes with no errors
**And** the application starts without import errors

### AC 7: Documentation Cleanup
**Given** the docs folder after changes
**When** I check for obsolete documentation
**Then** `docs/sprint-artifacts/(To review) epic-12-positions-whatif/` folder is deleted
**And** obsolete screenshot files are removed

## Technical Specifications

### Phase 1: UI Layer Removal

**Files to DELETE:**
```
src/walltrack/ui/pages/exit_simulator.py              # 251 lines
src/walltrack/ui/components/whatif_modal.py           # 396 lines
```

**Files to MODIFY:**

**ui/dashboard.py** - Remove Exit Simulator tab:
```python
# BEFORE:
tabs = [
    ("Home", create_home_tab),
    ("Explorer", create_explorer_tab),
    ("Positions", create_positions_tab),
    ("Exit Strategies", create_exit_strategies_tab),
    ("Exit Simulator", create_exit_simulator_tab),  # <- REMOVE
    ("Clusters", create_clusters_tab),
    ...
]

# AFTER:
tabs = [
    ("Home", create_home_tab),
    ("Explorer", create_explorer_tab),
    ("Positions", create_positions_tab),
    ("Exit Strategies", create_exit_strategies_tab),
    ("Clusters", create_clusters_tab),
    ...
]
```

**ui/components/position_details_sidebar.py** - Remove What-If button:
```python
# REMOVE these imports:
# from walltrack.ui.components.whatif_modal import create_whatif_modal

# REMOVE these UI elements:
# whatif_btn = gr.Button("What-If Analysis", variant="secondary")
# whatif_modal = create_whatif_modal(...)

# REMOVE these event handlers:
# whatif_btn.click(fn=open_whatif_modal, ...)
```

**ui/components/positions_list.py** - Remove Simulate button:
```python
# REMOVE "Simulate" action button and related handlers
```

**ui/pages/__init__.py** - Remove exit_simulator export
**ui/components/__init__.py** - Remove whatif_modal export

### Phase 2: Service Layer Removal

**Files to DELETE:**
```
src/walltrack/services/simulation/__init__.py         #  39 lines
src/walltrack/services/simulation/global_analyzer.py  # 520 lines
src/walltrack/services/simulation/position_simulator.py # 180 lines
src/walltrack/services/simulation/strategy_comparator.py # 314 lines
src/walltrack/services/exit/simulation_engine.py      # 533 lines
src/walltrack/services/exit/what_if_calculator.py     # 242 lines
```

**services/exit/__init__.py** - Remove these exports:
```python
# REMOVE:
# - AggregateStats, ExitSimulationEngine, PricePoint, RuleTrigger
# - SimulationResult, StrategyComparison
# - WhatIfAnalysis, WhatIfCalculator, WhatIfScenario
# - get_simulation_engine, reset_simulation_engine
```

### Phase 3: API Layer Removal

**routes/positions.py** - Remove simulation endpoint:
```python
# REMOVE imports:
# from walltrack.services.simulation.global_analyzer import get_global_analyzer
# from walltrack.services.simulation.strategy_comparator import ...

# REMOVE models:
# class SimulationRequest(BaseModel): ...
# class SimulationRow(BaseModel): ...

# REMOVE endpoint:
# @router.post("/{position_id}/simulate", ...)
```

### Phase 4: Test & Doc Cleanup

**Test files to DELETE:**
```
tests/unit/services/exit/test_simulation_engine.py
tests/unit/services/exit/test_what_if.py
tests/unit/services/simulation/__init__.py
tests/unit/services/simulation/test_position_simulator.py
tests/unit/services/simulation/test_strategy_comparator.py
tests/unit/services/simulation/test_global_analyzer.py
tests/unit/ui/components/test_whatif_modal.py
```

**Documentation to DELETE:**
```
docs/sprint-artifacts/(To review) epic-12-positions-whatif/
.playwright-mcp/e2e_exit_simulator_page.png
```

## Implementation Tasks

- [ ] Delete `ui/pages/exit_simulator.py`
- [ ] Delete `ui/components/whatif_modal.py`
- [ ] Modify `ui/dashboard.py` - remove Exit Simulator tab
- [ ] Modify `ui/components/position_details_sidebar.py` - remove What-If button
- [ ] Modify `ui/components/positions_list.py` - remove Simulate button
- [ ] Update `ui/pages/__init__.py` - remove export
- [ ] Update `ui/components/__init__.py` - remove export
- [ ] Delete `services/simulation/` folder (entire)
- [ ] Delete `services/exit/simulation_engine.py`
- [ ] Delete `services/exit/what_if_calculator.py`
- [ ] Update `services/exit/__init__.py` - remove 11 exports
- [ ] Modify `routes/positions.py` - remove simulation endpoint
- [ ] Delete 7 test files
- [ ] Delete obsolete documentation folder
- [ ] Run `uv run pytest` - verify all tests pass
- [ ] Run `uv run mypy src/` - verify no type errors
- [ ] Run `uv run ruff check src/` - verify no lint errors
- [ ] Start application - verify no import errors
- [ ] Verify Gradio UI loads without console errors

## Definition of Done

- [ ] Exit Simulator tab removed from dashboard
- [ ] What-If buttons removed from position views
- [ ] All simulation services deleted (~1,800 LOC)
- [ ] All simulation tests deleted
- [ ] No dead imports remaining (verify with grep)
- [ ] All quality gates pass (pytest, mypy, ruff)
- [ ] Application starts without errors
- [ ] No console errors in Gradio UI
- [ ] Documentation cleaned up

## Dev Notes

**Search for missed references:**
```bash
git grep -l "simulation\|whatif\|what_if\|exit_simul" -- "*.py"
```

**Order of deletion:**
1. Start with UI files (they import services)
2. Then delete services (they have no dependents after UI removal)
3. Finally clean up API routes and tests

**Verification steps after each phase:**
- Run `uv run python -c "from walltrack.ui.dashboard import create_dashboard"` to verify imports

## File List

### Files to DELETE (Total: ~2,875 LOC)
- `src/walltrack/ui/pages/exit_simulator.py`
- `src/walltrack/ui/components/whatif_modal.py`
- `src/walltrack/services/simulation/__init__.py`
- `src/walltrack/services/simulation/global_analyzer.py`
- `src/walltrack/services/simulation/position_simulator.py`
- `src/walltrack/services/simulation/strategy_comparator.py`
- `src/walltrack/services/exit/simulation_engine.py`
- `src/walltrack/services/exit/what_if_calculator.py`
- `tests/unit/services/exit/test_simulation_engine.py`
- `tests/unit/services/exit/test_what_if.py`
- `tests/unit/services/simulation/` (folder)
- `tests/unit/ui/components/test_whatif_modal.py`
- `docs/sprint-artifacts/(To review) epic-12-positions-whatif/` (folder)

### Files to MODIFY
- `src/walltrack/ui/dashboard.py`
- `src/walltrack/ui/pages/__init__.py`
- `src/walltrack/ui/components/__init__.py`
- `src/walltrack/ui/components/position_details_sidebar.py`
- `src/walltrack/ui/components/positions_list.py`
- `src/walltrack/api/routes/positions.py`
- `src/walltrack/services/exit/__init__.py`
