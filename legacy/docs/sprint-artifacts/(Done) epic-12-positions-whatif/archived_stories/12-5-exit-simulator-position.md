# Story 12.5: Exit Simulator - Position-Level Wrapper

## Story Info
- **Epic**: Epic 12 - Positions Management & Exit Strategy Simulator
- **Status**: ready
- **Priority**: P1 - High
- **Story Points**: 3 (réduit - wrapper uniquement)
- **Depends on**: Story 11-8 (Exit Simulation Engine - CORE)

## ⚠️ Important: Wrapper autour de 11-8

**Cette story NE réimplémente PAS le simulateur** - elle crée un wrapper position-aware autour de `ExitSimulationEngine` (Story 11-8).

| Responsabilité | Composant |
|----------------|-----------|
| Core simulation logic | `ExitSimulationEngine` (11-8) |
| Position data loading | `PositionSimulator` (12-5) |
| Price history fetching | Via 10.5-7 infrastructure |

Le `PositionSimulator` devient un **convenience wrapper** qui:
1. Charge les données de position depuis la DB
2. Récupère l'historique de prix
3. Appelle `ExitSimulationEngine.simulate_position()`
4. Retourne le résultat formaté

## User Story

**As a** the system,
**I want** un wrapper qui charge une position et lance la simulation,
**So that** je peux facilement simuler des stratégies sur des positions existantes.

## Acceptance Criteria

### AC 1: Simulate Strategy on Position
**Given** un historique de prix et une stratégie
**When** je lance la simulation
**Then** le moteur:
1. Initialise la position au prix d'entrée
2. Parcourt chaque point de prix chronologiquement
3. Vérifie les conditions de sortie à chaque point
4. Retourne le résultat final

### AC 2: Handle Partial Exits
**Given** une stratégie avec TP1=2x(33%), TP2=3x(50%)
**When** le prix atteint 2.5x puis redescend à 1.5x
**Then** la simulation montre:
- TP1 hit à 2x → vendu 33%
- TP2 non atteint
- Reste: 67% à 1.5x
- P&L total calculé

### AC 3: Handle Trailing Stop
**Given** une stratégie avec trailing stop
**When** le prix monte à 3x puis redescend
**Then** le trailing s'active au bon niveau
**And** le stop suit le pic
**And** la sortie se fait au bon niveau

### AC 4: Position-Specific Context
**Given** une position with executed exits
**When** je simule
**Then** les exits déjà exécutés sont pris en compte
**And** seule la portion restante est simulée

### AC 5: Performance
**Given** 360 points de prix (6h de données)
**When** je simule 5 stratégies
**Then** la simulation prend moins de 100ms

## Technical Specifications

### Position Simulator (Wrapper)

**src/walltrack/services/simulation/position_simulator.py:**
```python
"""Position-level wrapper around ExitSimulationEngine."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

import structlog

from walltrack.services.exit.simulation_engine import (
    ExitSimulationEngine,
    SimulationResult,
    get_simulation_engine,
)
from walltrack.services.exit.exit_strategy_service import ExitStrategy

logger = structlog.get_logger(__name__)


class PositionSimulator:
    """
    Position-level wrapper around ExitSimulationEngine.

    This is a convenience wrapper that:
    1. Loads position data from database
    2. Fetches price history
    3. Delegates to ExitSimulationEngine for actual simulation
    """

    def __init__(self):
        self._engine: Optional[ExitSimulationEngine] = None
        self._client = None

    async def _get_engine(self) -> ExitSimulationEngine:
        """Get simulation engine."""
        if self._engine is None:
            self._engine = await get_simulation_engine()
        return self._engine

    async def _get_client(self):
        """Get Supabase client."""
        if self._client is None:
            from walltrack.data.supabase.client import get_supabase_client
            self._client = await get_supabase_client()
        return self._client

    async def simulate_by_id(
        self,
        position_id: str,
        strategy: ExitStrategy,
    ) -> SimulationResult:
        """
        Simulate a strategy on a position by ID.

        Loads position from database and runs simulation.
        """
        client = await self._get_client()

        # Load position
        result = await client.table("positions") \
            .select("*") \
            .eq("id", position_id) \
            .single() \
            .execute()

        if not result.data:
            raise ValueError(f"Position not found: {position_id}")

        pos = result.data

        # Delegate to engine
        engine = await self._get_engine()
        return await engine.simulate_position(
            strategy=strategy,
            position_id=position_id,
            entry_price=Decimal(str(pos["entry_price"])),
            entry_time=datetime.fromisoformat(pos["entry_time"].replace("Z", "+00:00")),
            position_size_sol=Decimal(str(pos["size_sol"])),
            token_address=pos["token_address"],
            actual_exit=(
                Decimal(str(pos["exit_price"])),
                datetime.fromisoformat(pos["exit_time"].replace("Z", "+00:00"))
            ) if pos.get("exit_price") else None,
        )

    async def batch_simulate_positions(
        self,
        position_ids: list[str],
        strategy: ExitStrategy,
    ) -> list[SimulationResult]:
        """Simulate strategy on multiple positions."""
        results = []
        for pos_id in position_ids:
            try:
                result = await self.simulate_by_id(pos_id, strategy)
                results.append(result)
            except Exception as e:
                logger.warning("position_simulation_error", position=pos_id, error=str(e))
        return results


# Singleton
_position_simulator: Optional[PositionSimulator] = None


async def get_position_simulator() -> PositionSimulator:
    """Get position simulator instance."""
    global _position_simulator
    if _position_simulator is None:
        _position_simulator = PositionSimulator()
    return _position_simulator
```

## Implementation Tasks

- [x] Create PositionSimulator wrapper class
- [x] Implement simulate_by_id() to load position and delegate
- [x] Implement batch_simulate_positions()
- [x] Write tests that verify delegation to ExitSimulationEngine

## Definition of Done

- [x] Wrapper loads positions correctly
- [x] Delegates to ExitSimulationEngine (11-8)
- [x] Batch simulation works
- [x] Tests pass

## File List

### New Files
- `src/walltrack/services/simulation/position_simulator.py` - Wrapper

### Dependencies
- `src/walltrack/services/exit/simulation_engine.py` - Core engine (Story 11-8)
