"""Threshold checker for trade eligibility."""

import structlog

from walltrack.constants.threshold import NO_TRADE_MULTIPLIER
from walltrack.models.scoring import ScoredSignal
from walltrack.models.threshold import (
    ConvictionTier,
    EligibilityStatus,
    ThresholdConfig,
    ThresholdResult,
    TradeEligibleSignal,
)
from walltrack.models.token import TokenCharacteristics

logger = structlog.get_logger(__name__)


class ThresholdChecker:
    """Applies scoring threshold to determine trade eligibility.

    Implements position sizing tiers based on score ranges.
    """

    def __init__(self, config: ThresholdConfig | None = None) -> None:
        """Initialize threshold checker.

        Args:
            config: Threshold configuration
        """
        self.config = config or ThresholdConfig()

    def check(
        self,
        scored_signal: ScoredSignal,
        token: TokenCharacteristics | None = None,
    ) -> ThresholdResult:
        """Check if signal meets threshold for trade eligibility.

        Args:
            scored_signal: Signal with calculated score
            token: Optional token characteristics for additional filters

        Returns:
            ThresholdResult with eligibility status and position sizing
        """
        score = scored_signal.final_score
        filter_failures: list[str] = []

        # Additional safety checks
        passed_liquidity = True
        passed_honeypot = True

        if token and self.config.require_min_liquidity:
            liquidity = token.liquidity.usd if token.liquidity else 0
            if liquidity < self.config.min_liquidity_usd:
                passed_liquidity = False
                filter_failures.append(
                    f"liquidity_below_min: {liquidity} < {self.config.min_liquidity_usd}"
                )

        if token and self.config.require_non_honeypot and token.is_honeypot:
            passed_honeypot = False
            filter_failures.append("honeypot_detected")

        # Determine eligibility status (AC1, AC2, AC3)
        if score >= self.config.high_conviction_threshold:
            status = EligibilityStatus.HIGH_CONVICTION
            tier = ConvictionTier.HIGH
            multiplier = self.config.high_conviction_multiplier
        elif score >= self.config.trade_threshold:
            status = EligibilityStatus.TRADE_ELIGIBLE
            tier = ConvictionTier.STANDARD
            multiplier = self.config.standard_multiplier
        else:
            status = EligibilityStatus.BELOW_THRESHOLD
            tier = ConvictionTier.NONE
            multiplier = NO_TRADE_MULTIPLIER

        # Apply filter failures - downgrade to below threshold
        if filter_failures:
            status = EligibilityStatus.BELOW_THRESHOLD
            tier = ConvictionTier.NONE
            multiplier = NO_TRADE_MULTIPLIER

        # Calculate margin above threshold (for analysis)
        margin = None
        if status != EligibilityStatus.BELOW_THRESHOLD:
            margin = score - self.config.trade_threshold

        result = ThresholdResult(
            tx_signature=scored_signal.tx_signature,
            wallet_address=scored_signal.wallet_address,
            token_address=scored_signal.token_address,
            final_score=score,
            eligibility_status=status,
            conviction_tier=tier,
            position_multiplier=multiplier,
            threshold_used=self.config.trade_threshold,
            margin_above_threshold=margin,
            passed_liquidity_check=passed_liquidity,
            passed_honeypot_check=passed_honeypot,
            filter_failures=filter_failures,
        )

        # Log result
        if status == EligibilityStatus.BELOW_THRESHOLD:
            logger.info(
                "signal_below_threshold",
                wallet=scored_signal.wallet_address[:8] + "...",
                token=scored_signal.token_address[:8] + "...",
                score=round(score, 4),
                threshold=self.config.trade_threshold,
                filter_failures=filter_failures,
            )
        else:
            logger.info(
                "signal_trade_eligible",
                wallet=scored_signal.wallet_address[:8] + "...",
                token=scored_signal.token_address[:8] + "...",
                score=round(score, 4),
                tier=tier.value,
                multiplier=multiplier,
            )

        return result

    def create_trade_eligible_signal(
        self,
        scored_signal: ScoredSignal,
        threshold_result: ThresholdResult,
        amount_sol: float,
    ) -> TradeEligibleSignal | None:
        """Create trade-eligible signal ready for execution.

        Returns None if signal didn't pass threshold.
        """
        if threshold_result.eligibility_status == EligibilityStatus.BELOW_THRESHOLD:
            return None

        return TradeEligibleSignal(
            tx_signature=scored_signal.tx_signature,
            wallet_address=scored_signal.wallet_address,
            token_address=scored_signal.token_address,
            direction=scored_signal.direction,
            amount_sol=amount_sol,
            final_score=scored_signal.final_score,
            conviction_tier=threshold_result.conviction_tier,
            position_multiplier=threshold_result.position_multiplier,
            wallet_score=scored_signal.wallet_score.score,
            cluster_score=scored_signal.cluster_score.score,
            token_score=scored_signal.token_score.score,
            context_score=scored_signal.context_score.score,
        )

    def update_config(self, config: ThresholdConfig) -> None:
        """Update threshold configuration (hot-reload)."""
        self.config = config
        logger.info(
            "threshold_config_updated",
            trade_threshold=config.trade_threshold,
            high_conviction_threshold=config.high_conviction_threshold,
        )


# Module-level singleton
_checker: ThresholdChecker | None = None


def get_checker(config: ThresholdConfig | None = None) -> ThresholdChecker:
    """Get or create threshold checker singleton."""
    global _checker
    if _checker is None:
        _checker = ThresholdChecker(config=config)
    return _checker


def reset_checker() -> None:
    """Reset checker singleton (for testing)."""
    global _checker
    _checker = None
