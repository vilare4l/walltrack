# Story 7.1: Execution Mode Configuration

## Story Info
- **Epic**: Epic 7 - Live Simulation (Paper Trading)
- **Status**: ready
- **Priority**: Critical (Foundation)
- **FR**: FR55

## User Story

**As an** operator,
**I want** to configure the system to run in live or simulation mode,
**So that** I can test the system without risking real capital.

## Acceptance Criteria

### AC 1: Mode Configuration
**Given** the system configuration
**When** EXECUTION_MODE is set to "simulation"
**Then** all trades are simulated (no real swaps)
**And** all signals are processed normally
**And** UI indicates simulation mode clearly

### AC 2: Signal Processing
**Given** simulation mode is active
**When** a trade signal is generated
**Then** the signal is processed through the full pipeline
**And** instead of Jupiter execution, simulated execution occurs
**And** position is tracked as simulated

### AC 3: Mode Switching
**Given** operator wants to switch modes
**When** mode is changed via config or dashboard
**Then** system restarts in new mode
**And** existing positions are preserved
**And** clear warning is shown when switching to live

### AC 4: UI Indication
**Given** system is in simulation mode
**When** dashboard loads
**Then** prominent "SIMULATION MODE" banner is displayed
**And** all P&L figures are marked as simulated
**And** no real wallet balance changes occur

## Technical Specifications

### Settings Extension

**src/walltrack/config/settings.py:**
```python
from enum import Enum
from pydantic import Field

class ExecutionMode(str, Enum):
    """Trading execution mode."""
    LIVE = "live"
    SIMULATION = "simulation"


class Settings(BaseSettings):
    # ... existing fields ...

    # Execution Mode
    execution_mode: ExecutionMode = Field(
        default=ExecutionMode.SIMULATION,
        description="Trading execution mode (live/simulation)",
    )

    # Simulation Settings
    simulation_slippage_bps: int = Field(
        default=100,
        ge=0,
        le=500,
        description="Simulated slippage in basis points (100 = 1%)",
    )
```

### Mode Context

**src/walltrack/core/simulation/context.py:**
```python
"""Execution mode context management."""

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Generator

from walltrack.config.settings import ExecutionMode, get_settings

_execution_mode: ContextVar[ExecutionMode] = ContextVar(
    "execution_mode",
    default=ExecutionMode.SIMULATION,
)


def get_execution_mode() -> ExecutionMode:
    """Get current execution mode."""
    return _execution_mode.get()


def is_simulation_mode() -> bool:
    """Check if running in simulation mode."""
    return get_execution_mode() == ExecutionMode.SIMULATION


def is_live_mode() -> bool:
    """Check if running in live mode."""
    return get_execution_mode() == ExecutionMode.LIVE


@contextmanager
def execution_mode_context(mode: ExecutionMode) -> Generator[None, None, None]:
    """Context manager for temporary mode override."""
    token = _execution_mode.set(mode)
    try:
        yield
    finally:
        _execution_mode.reset(token)


def initialize_execution_mode() -> None:
    """Initialize execution mode from settings."""
    settings = get_settings()
    _execution_mode.set(settings.execution_mode)
```

### Trade Executor Factory

**src/walltrack/core/trading/executor_factory.py:**
```python
"""Factory for creating trade executors based on mode."""

import structlog
from typing import Protocol

from walltrack.core.simulation.context import is_simulation_mode

log = structlog.get_logger()


class TradeExecutor(Protocol):
    """Protocol for trade executors."""

    async def execute_buy(
        self,
        token_address: str,
        amount_sol: float,
        slippage_bps: int,
    ) -> dict:
        """Execute a buy trade."""
        ...

    async def execute_sell(
        self,
        token_address: str,
        amount_tokens: float,
        slippage_bps: int,
    ) -> dict:
        """Execute a sell trade."""
        ...


def get_trade_executor() -> TradeExecutor:
    """Get appropriate trade executor based on execution mode."""
    if is_simulation_mode():
        from walltrack.core.simulation.simulated_executor import SimulatedTradeExecutor
        log.info("using_simulated_executor")
        return SimulatedTradeExecutor()
    else:
        from walltrack.core.trading.jupiter_executor import JupiterExecutor
        log.info("using_live_executor")
        return JupiterExecutor()
```

## Environment Variables

```bash
# Execution mode: live or simulation
EXECUTION_MODE=simulation

# Simulation settings
SIMULATION_SLIPPAGE_BPS=100
```

## Implementation Tasks

- [x] Add ExecutionMode enum to settings.py
- [x] Add execution_mode field to Settings
- [x] Create src/walltrack/core/simulation/ directory
- [x] Implement context.py for mode management
- [x] Implement executor_factory.py
- [x] Update main.py to initialize execution mode
- [x] Add mode indicator to dashboard
- [x] Write unit tests for mode switching

## Definition of Done

- [x] EXECUTION_MODE config controls system behavior
- [x] Mode is clearly displayed in dashboard
- [x] Mode can be verified via health endpoint
- [x] Tests cover mode switching scenarios
- [ ] Documentation updated

## Dev Agent Record

### Implementation Notes
- Added `ExecutionMode` enum to `settings.py` with LIVE and SIMULATION values
- Added `execution_mode` and `simulation_slippage_bps` fields to Settings class
- Created `src/walltrack/core/simulation/` module with context management
- Implemented `context.py` with ContextVar for thread-safe mode tracking
- Created `executor_factory.py` with TradeExecutor protocol and factory function
- Created `simulated_executor.py` for paper trading execution
- Created `jupiter_executor.py` wrapper for live trading
- Added execution mode initialization in `api/app.py` lifespan
- Added execution mode to `/health` and `/health/detailed` endpoints
- Added prominent mode banner to Gradio dashboard

### Tests Created
- `tests/unit/core/simulation/test_context.py` - 10 tests for ExecutionMode and context
- `tests/unit/core/simulation/test_executor_factory.py` - 4 tests for factory function

## File List

### New Files
- `src/walltrack/core/simulation/__init__.py`
- `src/walltrack/core/simulation/context.py`
- `src/walltrack/core/simulation/simulated_executor.py`
- `src/walltrack/core/trading/__init__.py`
- `src/walltrack/core/trading/executor_factory.py`
- `src/walltrack/core/trading/jupiter_executor.py`
- `tests/unit/core/simulation/__init__.py`
- `tests/unit/core/simulation/test_context.py`
- `tests/unit/core/simulation/test_executor_factory.py`

### Modified Files
- `src/walltrack/config/settings.py` - Added ExecutionMode enum and settings fields
- `src/walltrack/api/app.py` - Added execution mode initialization in lifespan
- `src/walltrack/api/routes/health.py` - Added execution_mode to health endpoints
- `src/walltrack/ui/dashboard.py` - Added simulation mode banner

## Change Log

- 2025-12-21: Story 7-1 implementation complete - ExecutionMode configuration system
