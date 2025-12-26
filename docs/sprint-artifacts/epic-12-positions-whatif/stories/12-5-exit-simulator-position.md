# Story 12.5: Exit Simulator - Position-Level Engine

## Story Info
- **Epic**: Epic 12 - Positions Management & Exit Strategy Simulator
- **Status**: ready
- **Priority**: P0 - Critical
- **Story Points**: 8
- **Depends on**: Story 12-4 (Price History), Story 11-8 (Base Simulation Engine)

## User Story

**As a** the system,
**I want** un moteur de simulation qui rejoue une stratégie sur l'historique de prix d'une position,
**So that** je peux calculer le résultat alternatif d'une stratégie différente.

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

### Position Simulator

**src/walltrack/services/simulation/position_simulator.py:**
```python
"""Position-level exit strategy simulator."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional

import structlog

from walltrack.services.exit.exit_strategy_service import ExitStrategy, ExitStrategyRule

logger = structlog.get_logger(__name__)


@dataclass
class ExitEvent:
    """A single exit event during simulation."""
    timestamp: datetime
    event_type: str  # take_profit, stop_loss, trailing_stop, time_based, stagnation
    trigger_pct: Optional[Decimal]
    price: Decimal
    exit_pct: Decimal  # Percentage of remaining position
    cumulative_exited_pct: Decimal  # Total exited so far
    pnl_at_exit: Decimal  # P&L for this exit


@dataclass
class PositionSimulationResult:
    """Result of simulating a strategy on a position."""
    position_id: str
    strategy_id: str
    strategy_name: str

    # Position info
    entry_price: Decimal
    entry_time: datetime
    position_size_sol: Decimal

    # Simulation results
    exit_events: list[ExitEvent]
    final_pnl_pct: Decimal
    final_pnl_sol: Decimal
    remaining_position_pct: Decimal

    # Timing
    first_exit_time: Optional[datetime]
    last_exit_time: Optional[datetime]
    total_duration_hours: Decimal

    # Stats
    max_unrealized_gain_pct: Decimal
    max_unrealized_loss_pct: Decimal
    peak_price: Decimal
    trough_price: Decimal


class PositionSimulator:
    """
    Simulates exit strategies on position price history.

    Handles:
    - Multiple partial exits (TPs)
    - Stop losses
    - Trailing stops with activation
    - Time-based exits
    - Stagnation exits
    """

    def simulate(
        self,
        strategy: ExitStrategy,
        entry_price: Decimal,
        entry_time: datetime,
        position_size_sol: Decimal,
        price_history: list[dict],  # [{timestamp, price}, ...]
        position_id: str = "sim",
        already_exited_pct: Decimal = Decimal("0"),
    ) -> PositionSimulationResult:
        """
        Simulate a strategy on price history.

        Args:
            strategy: Exit strategy to simulate
            entry_price: Position entry price
            entry_time: Position entry time
            position_size_sol: Initial position size in SOL
            price_history: List of {timestamp, price} dicts
            position_id: Position identifier
            already_exited_pct: Percentage already exited (for partial sim)

        Returns:
            PositionSimulationResult
        """
        if not price_history:
            return self._empty_result(strategy, entry_price, entry_time, position_size_sol, position_id)

        # Initialize state
        remaining_pct = Decimal("100") - already_exited_pct
        exit_events: list[ExitEvent] = []
        cumulative_exited = already_exited_pct

        # Tracking
        max_gain = Decimal("0")
        max_loss = Decimal("0")
        peak_price = entry_price
        trough_price = entry_price

        # Trailing stop state
        trailing_activated = False
        trailing_stop_price: Optional[Decimal] = None

        # Sort rules by priority
        rules = [r for r in strategy.rules if r.enabled]
        rules.sort(key=lambda r: r.priority)

        for point in price_history:
            if remaining_pct <= 0:
                break

            ts = point["timestamp"]
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))

            price = Decimal(str(point["price"]))

            # Update tracking
            if price > peak_price:
                peak_price = price
            if price < trough_price:
                trough_price = price

            # Calculate current P&L
            pnl_pct = ((price - entry_price) / entry_price) * 100

            if pnl_pct > max_gain:
                max_gain = pnl_pct
            if pnl_pct < max_loss:
                max_loss = pnl_pct

            # Calculate hold time
            hold_hours = (ts.replace(tzinfo=None) - entry_time.replace(tzinfo=None) if entry_time.tzinfo else ts - entry_time).total_seconds() / 3600

            # Check stagnation
            if hold_hours >= strategy.stagnation_hours:
                if abs(pnl_pct) <= strategy.stagnation_threshold_pct:
                    exit_event = ExitEvent(
                        timestamp=ts,
                        event_type="stagnation",
                        trigger_pct=strategy.stagnation_threshold_pct,
                        price=price,
                        exit_pct=remaining_pct,
                        cumulative_exited_pct=Decimal("100"),
                        pnl_at_exit=pnl_pct,
                    )
                    exit_events.append(exit_event)
                    remaining_pct = Decimal("0")
                    break

            # Check max hold time
            if hold_hours >= strategy.max_hold_hours:
                exit_event = ExitEvent(
                    timestamp=ts,
                    event_type="time_based",
                    trigger_pct=None,
                    price=price,
                    exit_pct=remaining_pct,
                    cumulative_exited_pct=Decimal("100"),
                    pnl_at_exit=pnl_pct,
                )
                exit_events.append(exit_event)
                remaining_pct = Decimal("0")
                break

            # Check each rule
            for rule in rules:
                if remaining_pct <= 0:
                    break

                triggered, event = self._check_rule(
                    rule=rule,
                    price=price,
                    entry_price=entry_price,
                    pnl_pct=pnl_pct,
                    timestamp=ts,
                    remaining_pct=remaining_pct,
                    cumulative_exited=cumulative_exited,
                    peak_price=peak_price,
                    trailing_activated=trailing_activated,
                    trailing_stop_price=trailing_stop_price,
                )

                if triggered and event:
                    exit_events.append(event)
                    remaining_pct -= event.exit_pct
                    cumulative_exited = event.cumulative_exited_pct

                    # Update trailing state if needed
                    if rule.rule_type == "trailing_stop":
                        trailing_activated = True

            # Update trailing stop price
            if trailing_activated:
                trailing_rule = next((r for r in rules if r.rule_type == "trailing_stop"), None)
                if trailing_rule and trailing_rule.trigger_pct:
                    new_stop = peak_price * (1 + trailing_rule.trigger_pct / 100)
                    if trailing_stop_price is None or new_stop > trailing_stop_price:
                        trailing_stop_price = new_stop

        # Calculate final results
        final_pnl_pct = self._calculate_weighted_pnl(exit_events, entry_price, price_history[-1]["price"] if price_history else entry_price, remaining_pct)
        final_pnl_sol = position_size_sol * (final_pnl_pct / 100)

        last_price = price_history[-1] if price_history else {"timestamp": entry_time, "price": entry_price}
        last_ts = last_price["timestamp"]
        if isinstance(last_ts, str):
            last_ts = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))

        total_duration = Decimal(str((last_ts.replace(tzinfo=None) - entry_time.replace(tzinfo=None) if entry_time.tzinfo else last_ts - entry_time).total_seconds() / 3600))

        return PositionSimulationResult(
            position_id=position_id,
            strategy_id=strategy.id,
            strategy_name=strategy.name,
            entry_price=entry_price,
            entry_time=entry_time,
            position_size_sol=position_size_sol,
            exit_events=exit_events,
            final_pnl_pct=final_pnl_pct,
            final_pnl_sol=final_pnl_sol,
            remaining_position_pct=remaining_pct,
            first_exit_time=exit_events[0].timestamp if exit_events else None,
            last_exit_time=exit_events[-1].timestamp if exit_events else None,
            total_duration_hours=total_duration,
            max_unrealized_gain_pct=max_gain,
            max_unrealized_loss_pct=max_loss,
            peak_price=peak_price,
            trough_price=trough_price,
        )

    def _check_rule(
        self,
        rule: ExitStrategyRule,
        price: Decimal,
        entry_price: Decimal,
        pnl_pct: Decimal,
        timestamp: datetime,
        remaining_pct: Decimal,
        cumulative_exited: Decimal,
        peak_price: Decimal,
        trailing_activated: bool,
        trailing_stop_price: Optional[Decimal],
    ) -> tuple[bool, Optional[ExitEvent]]:
        """Check if a rule is triggered and create exit event."""
        triggered = False
        event_type = rule.rule_type

        if rule.rule_type == "take_profit" and rule.trigger_pct:
            triggered = pnl_pct >= rule.trigger_pct

        elif rule.rule_type == "stop_loss" and rule.trigger_pct:
            triggered = pnl_pct <= rule.trigger_pct

        elif rule.rule_type == "trailing_stop":
            activation_pct = rule.params.get("activation_pct", 0)

            if not trailing_activated:
                # Check activation
                if pnl_pct >= activation_pct:
                    trailing_activated = True
                    # Calculate initial stop
                    if rule.trigger_pct:
                        trailing_stop_price = peak_price * (1 + rule.trigger_pct / 100)
            else:
                # Check if stop hit
                if trailing_stop_price and price <= trailing_stop_price:
                    triggered = True

        elif rule.rule_type == "time_based":
            # Handled separately in main loop
            pass

        if triggered:
            exit_amount = min(rule.exit_pct, remaining_pct)
            new_cumulative = cumulative_exited + exit_amount

            return True, ExitEvent(
                timestamp=timestamp,
                event_type=event_type,
                trigger_pct=rule.trigger_pct,
                price=price,
                exit_pct=exit_amount,
                cumulative_exited_pct=new_cumulative,
                pnl_at_exit=pnl_pct,
            )

        return False, None

    def _calculate_weighted_pnl(
        self,
        exit_events: list[ExitEvent],
        entry_price: Decimal,
        final_price: Decimal,
        remaining_pct: Decimal,
    ) -> Decimal:
        """Calculate weighted average P&L across all exits."""
        if not exit_events and remaining_pct == Decimal("100"):
            return ((final_price - entry_price) / entry_price) * 100

        total_pnl = Decimal("0")
        total_weight = Decimal("0")

        for event in exit_events:
            weight = event.exit_pct / 100
            total_pnl += event.pnl_at_exit * weight
            total_weight += weight

        # Add remaining position at final price
        if remaining_pct > 0:
            remaining_weight = remaining_pct / 100
            remaining_pnl = ((final_price - entry_price) / entry_price) * 100
            total_pnl += remaining_pnl * remaining_weight
            total_weight += remaining_weight

        return total_pnl

    def _empty_result(
        self,
        strategy: ExitStrategy,
        entry_price: Decimal,
        entry_time: datetime,
        position_size_sol: Decimal,
        position_id: str,
    ) -> PositionSimulationResult:
        """Create empty result when no price history."""
        return PositionSimulationResult(
            position_id=position_id,
            strategy_id=strategy.id,
            strategy_name=strategy.name,
            entry_price=entry_price,
            entry_time=entry_time,
            position_size_sol=position_size_sol,
            exit_events=[],
            final_pnl_pct=Decimal("0"),
            final_pnl_sol=Decimal("0"),
            remaining_position_pct=Decimal("100"),
            first_exit_time=None,
            last_exit_time=None,
            total_duration_hours=Decimal("0"),
            max_unrealized_gain_pct=Decimal("0"),
            max_unrealized_loss_pct=Decimal("0"),
            peak_price=entry_price,
            trough_price=entry_price,
        )


# Singleton
_position_simulator: Optional[PositionSimulator] = None


def get_position_simulator() -> PositionSimulator:
    """Get position simulator instance."""
    global _position_simulator
    if _position_simulator is None:
        _position_simulator = PositionSimulator()
    return _position_simulator
```

## Implementation Tasks

- [ ] Create ExitEvent dataclass
- [ ] Create PositionSimulationResult dataclass
- [ ] Implement PositionSimulator class
- [ ] Implement simulate() main method
- [ ] Implement _check_rule() for each rule type
- [ ] Handle partial exits correctly
- [ ] Handle trailing stop activation and tracking
- [ ] Implement weighted P&L calculation
- [ ] Optimize for performance (<100ms for 5 strategies)
- [ ] Write comprehensive tests

## Definition of Done

- [ ] Simulation produces correct results
- [ ] All rule types handled
- [ ] Partial exits calculated correctly
- [ ] Trailing stop works with activation
- [ ] Performance under 100ms for 5 strategies
- [ ] Unit tests pass

## File List

### New Files
- `src/walltrack/services/simulation/position_simulator.py` - Simulator

### Modified Files
- `src/walltrack/services/simulation/__init__.py` - Export
