"""Simplified threshold checker for trade eligibility.

Epic 14 Simplification:
- Single threshold (0.65) instead of dual HIGH/STANDARD thresholds
- Token safety is a binary gate in SignalScorer (not here)
- position_multiplier equals cluster_boost
"""

import structlog

from walltrack.models.scoring import ScoredSignal, ScoringConfig

logger = structlog.get_logger(__name__)


class ThresholdResult:
    """Result of threshold check (simplified)."""

    def __init__(
        self,
        passed: bool,
        score: float,
        threshold: float,
        position_multiplier: float,
    ) -> None:
        """Initialize threshold result.

        Args:
            passed: Whether signal passed threshold
            score: Final signal score
            threshold: Threshold used for comparison
            position_multiplier: Position size multiplier (equals cluster_boost)
        """
        self.passed = passed
        self.score = score
        self.threshold = threshold
        self.position_multiplier = position_multiplier


class ThresholdChecker:
    """Simplified single-threshold checker.

    Replaces the dual HIGH/STANDARD threshold system with a single
    threshold at 0.65. Position sizing is determined by cluster_boost,
    not conviction tiers.
    """

    def __init__(self, config: ScoringConfig | None = None) -> None:
        """Initialize threshold checker.

        Args:
            config: Scoring configuration with threshold
        """
        self.config = config or ScoringConfig()

    def check(self, signal: ScoredSignal) -> ThresholdResult:
        """Check if signal passes trade threshold.

        Args:
            signal: Scored signal to check

        Returns:
            ThresholdResult with pass/fail and multiplier
        """
        # Token safety is handled in SignalScorer - if token_safe is False,
        # the signal has already been rejected
        if not signal.token_safe:
            logger.info(
                "signal_below_threshold",
                wallet=signal.wallet_address[:8] + "...",
                token=signal.token_address[:8] + "...",
                reason=signal.token_reject_reason,
            )
            return ThresholdResult(
                passed=False,
                score=0.0,
                threshold=self.config.trade_threshold,
                position_multiplier=1.0,
            )

        passed = signal.final_score >= self.config.trade_threshold

        if passed:
            logger.info(
                "signal_trade_eligible",
                wallet=signal.wallet_address[:8] + "...",
                token=signal.token_address[:8] + "...",
                score=round(signal.final_score, 4),
                multiplier=round(signal.cluster_boost, 2),
            )
        else:
            logger.info(
                "signal_below_threshold",
                wallet=signal.wallet_address[:8] + "...",
                token=signal.token_address[:8] + "...",
                score=round(signal.final_score, 4),
                threshold=self.config.trade_threshold,
            )

        return ThresholdResult(
            passed=passed,
            score=signal.final_score,
            threshold=self.config.trade_threshold,
            position_multiplier=signal.cluster_boost if passed else 1.0,
        )

    def update_config(self, config: ScoringConfig) -> None:
        """Update threshold configuration.

        Args:
            config: New scoring configuration
        """
        self.config = config
        logger.info(
            "threshold_config_updated",
            trade_threshold=config.trade_threshold,
        )


# Module-level singleton
_checker: ThresholdChecker | None = None


def get_checker(config: ScoringConfig | None = None) -> ThresholdChecker:
    """Get or create threshold checker singleton.

    Args:
        config: Optional scoring configuration

    Returns:
        ThresholdChecker singleton instance
    """
    global _checker
    if _checker is None:
        _checker = ThresholdChecker(config=config)
    return _checker


def reset_checker() -> None:
    """Reset checker singleton (for testing)."""
    global _checker
    _checker = None
