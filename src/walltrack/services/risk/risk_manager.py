"""Risk manager for entry and position sizing.

Story 13-4: Integrated with PositionSizer for full risk management.
Delegates to PositionSizer for position sizing with:
- Drawdown-based size reduction (Story 10.5-9)
- Daily loss limit enforcement (Story 10.5-10)
- Concentration limits (Story 10.5-11)
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from walltrack.models.signal_log import SignalLogEntry
    from walltrack.services.trade.position_sizer import PositionSizer

logger = structlog.get_logger(__name__)


@dataclass
class RiskCheck:
    """Result of a risk check."""

    allowed: bool
    reason: str | None = None
    daily_loss_pct: float | None = None
    current_concentration: float | None = None
    drawdown_pct: float | None = None


@dataclass
class PositionSizeResult:
    """Result of position sizing calculation."""

    amount_sol: Decimal
    mode: str  # "full", "reduced", "blocked"
    reason: str | None = None
    conviction_multiplier: float = 1.0


class RiskManager:
    """
    Risk manager for entry validation and position sizing.

    Delegates to PositionSizer for full risk management including:
    - Risk-based position sizing (Story 10.5-8)
    - Drawdown-based size reduction (Story 10.5-9)
    - Daily loss limit enforcement (Story 10.5-10)
    - Concentration limits (Story 10.5-11)
    """

    def __init__(
        self,
        base_position_sol: Decimal = Decimal("0.5"),
        max_position_sol: Decimal = Decimal("2.0"),
        min_position_sol: Decimal = Decimal("0.1"),
        max_daily_loss_pct: float = 10.0,
        max_concentration_pct: float = 20.0,
        max_drawdown_pct: float = 15.0,
    ) -> None:
        """
        Initialize RiskManager.

        Args:
            base_position_sol: Base position size in SOL (fallback)
            max_position_sol: Maximum position size in SOL (fallback)
            min_position_sol: Minimum position size in SOL (fallback)
            max_daily_loss_pct: Maximum daily loss percentage (fallback)
            max_concentration_pct: Maximum concentration per token (fallback)
            max_drawdown_pct: Maximum drawdown before size reduction (fallback)
        """
        self.base_position_sol = base_position_sol
        self.max_position_sol = max_position_sol
        self.min_position_sol = min_position_sol
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_concentration_pct = max_concentration_pct
        self.max_drawdown_pct = max_drawdown_pct
        self._position_sizer: PositionSizer | None = None

    async def _get_position_sizer(self) -> Any:
        """Get or create position sizer singleton."""
        if self._position_sizer is None:
            # Lazy import to avoid circular dependency
            from walltrack.services.trade.position_sizer import get_position_sizer
            self._position_sizer = await get_position_sizer()
        return self._position_sizer

    async def _get_available_balance(self) -> float:
        """Get available balance for trading.

        Returns:
            Available SOL balance
        """
        # TODO: Get real balance from wallet or position tracker
        # For now, return a default value
        return 10.0

    async def _get_position_count(self) -> int:
        """Get current open position count.

        Returns:
            Number of open positions
        """
        # TODO: Get real count from position repository
        return 0

    async def _get_allocated_sol(self) -> float:
        """Get currently allocated SOL in positions.

        Returns:
            SOL currently allocated to positions
        """
        # TODO: Get real allocation from position repository
        return 0.0

    async def check_entry_allowed(
        self,
        token_address: str,
        cluster_id: str | None = None,
    ) -> RiskCheck:
        """
        Check if a new entry is allowed based on risk limits.

        Uses PositionSizer's built-in checks for:
        - Daily loss limit (Story 10.5-10)
        - Concentration limits (Story 10.5-11)
        - Drawdown limits (Story 10.5-9)

        Args:
            token_address: Token to trade
            cluster_id: Optional cluster ID for concentration check

        Returns:
            RiskCheck indicating if entry is allowed
        """
        log = logger.bind(token=token_address[:8])

        try:
            sizer = await self._get_position_sizer()

            # Build request for check (use dummy score for validation)
            request = PositionSizeRequest(
                signal_score=0.75,
                available_balance_sol=await self._get_available_balance(),
                current_position_count=await self._get_position_count(),
                current_allocated_sol=await self._get_allocated_sol(),
                token_address=token_address,
                cluster_id=cluster_id,
            )

            result = await sizer.calculate_size(request, audit=False)

            # Check decision for blocking conditions
            if result.decision == SizingDecision.BLOCKED_DRAWDOWN:
                log.info("entry_blocked_drawdown")
                return RiskCheck(
                    allowed=False,
                    reason="Blocked by drawdown limit",
                    drawdown_pct=result.drawdown_metrics.drawdown_pct
                    if result.drawdown_metrics
                    else None,
                )

            if result.decision == SizingDecision.BLOCKED_DAILY_LOSS:
                log.info("entry_blocked_daily_loss")
                return RiskCheck(
                    allowed=False,
                    reason="Blocked by daily loss limit",
                    daily_loss_pct=result.daily_loss_metrics.pnl_pct
                    if result.daily_loss_metrics
                    else None,
                )

            if result.decision == SizingDecision.BLOCKED_CONCENTRATION:
                log.info("entry_blocked_concentration")
                return RiskCheck(
                    allowed=False,
                    reason="Blocked by concentration limit",
                    current_concentration=result.concentration_metrics.token_current_pct
                    if result.concentration_metrics
                    else None,
                )

            if result.decision == SizingDecision.BLOCKED_DUPLICATE:
                log.info("entry_blocked_duplicate")
                return RiskCheck(
                    allowed=False,
                    reason="Position already exists for this token",
                )

            if result.decision == SizingDecision.SKIPPED_MAX_POSITIONS:
                log.info("entry_blocked_max_positions")
                return RiskCheck(
                    allowed=False,
                    reason="Maximum positions reached",
                )

            log.debug("risk_check_passed")
            return RiskCheck(allowed=True, reason=None)

        except Exception as e:
            log.warning("risk_check_error", error=str(e))
            # Allow entry on error - fail open
            return RiskCheck(allowed=True, reason=f"Check failed: {str(e)}")

    async def calculate_position_size(
        self,
        signal: SignalLogEntry,
        current_price: Decimal,  # noqa: ARG002
    ) -> PositionSizeResult:
        """
        Calculate position size based on risk factors.

        Uses PositionSizer for full risk-based sizing including:
        - Score-based conviction tiers
        - Drawdown-based reduction
        - Daily loss limit enforcement
        - Concentration limits

        Args:
            signal: Signal to size
            current_price: Current token price (not used, kept for compatibility)

        Returns:
            PositionSizeResult with recommended size
        """
        log = logger.bind(
            signal_id=signal.id,
            score=signal.final_score,
        )

        try:
            sizer = await self._get_position_sizer()

            # Build request from signal
            request = PositionSizeRequest(
                signal_score=signal.final_score or 0.5,
                available_balance_sol=await self._get_available_balance(),
                current_position_count=await self._get_position_count(),
                current_allocated_sol=await self._get_allocated_sol(),
                token_address=signal.token_address,
                signal_id=signal.id,
                cluster_id=None,  # TODO: Add cluster_id to signal
            )

            result = await sizer.calculate_size(request)

            # Map decision to mode
            if result.decision in (
                SizingDecision.BLOCKED_DRAWDOWN,
                SizingDecision.BLOCKED_DAILY_LOSS,
                SizingDecision.BLOCKED_CONCENTRATION,
                SizingDecision.BLOCKED_DUPLICATE,
            ):
                mode = "blocked"
            elif result.decision == SizingDecision.REDUCED:
                mode = "reduced"
            elif result.decision == SizingDecision.APPROVED:
                mode = "full"
            else:
                mode = "skipped"

            log.info(
                "position_size_calculated",
                decision=result.decision.value,
                mode=mode,
                size=result.final_size_sol,
                multiplier=result.multiplier,
            )

            return PositionSizeResult(
                amount_sol=Decimal(str(result.final_size_sol)),
                mode=mode,
                reason=result.reason,
                conviction_multiplier=result.multiplier,
            )

        except Exception as e:
            log.warning("position_sizing_error", error=str(e))
            # Fallback to simple calculation on error
            return self._fallback_calculate(signal)

    def _fallback_calculate(self, signal: SignalLogEntry) -> PositionSizeResult:
        """Fallback position sizing if PositionSizer fails.

        Args:
            signal: Signal to size

        Returns:
            PositionSizeResult with basic calculation
        """
        score = signal.final_score or 0.5
        if score >= 0.85:
            multiplier = 1.5
        elif score >= 0.70:
            multiplier = 1.0
        else:
            multiplier = 0.5

        base_size = self.base_position_sol
        calculated_size = base_size * Decimal(str(multiplier))
        final_size = min(calculated_size, self.max_position_sol)
        final_size = max(final_size, self.min_position_sol)

        return PositionSizeResult(
            amount_sol=final_size,
            mode="full" if final_size == calculated_size else "reduced",
            reason="Fallback calculation",
            conviction_multiplier=multiplier,
        )


# Singleton
_risk_manager: RiskManager | None = None


async def get_risk_manager() -> RiskManager:
    """Get or create risk manager singleton."""
    global _risk_manager
    if _risk_manager is None:
        _risk_manager = RiskManager()
    return _risk_manager
