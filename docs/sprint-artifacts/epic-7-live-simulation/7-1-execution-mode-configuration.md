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

- [ ] Add ExecutionMode enum to settings.py
- [ ] Add execution_mode field to Settings
- [ ] Create src/walltrack/core/simulation/ directory
- [ ] Implement context.py for mode management
- [ ] Implement executor_factory.py
- [ ] Update main.py to initialize execution mode
- [ ] Add mode indicator to dashboard
- [ ] Write unit tests for mode switching

## Definition of Done

- [ ] EXECUTION_MODE config controls system behavior
- [ ] Mode is clearly displayed in dashboard
- [ ] Mode can be verified via health endpoint
- [ ] Tests cover mode switching scenarios
- [ ] Documentation updated
