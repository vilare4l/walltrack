"""Watchlist evaluation service for wallets.

This module implements automatic watchlist evaluation based on configurable
criteria (win rate, PnL, trades, decay score). Wallets that pass all criteria
are marked as 'watchlisted' for downstream operations (clustering, signal scoring).

Pattern: Status-based filtering (Story 3.5)
  - Only 'watchlisted' wallets are processed by expensive operations (20-100x perf gain)
  - Evaluation triggered automatically after behavioral profiling (Story 3.3)
  - Manual override supported via UI controls (Task 8)
"""

from datetime import datetime
from decimal import Decimal

import structlog

from walltrack.data.models.wallet import Wallet, WatchlistDecision, WalletStatus
from walltrack.data.supabase.repositories.config_repo import ConfigRepository

log = structlog.get_logger(__name__)


class WatchlistEvaluator:
    """Evaluates wallets against configurable criteria for watchlist inclusion.

    Uses weighted scoring formula combining win rate, PnL, trade count, and decay score.
    ALL criteria must be met for wallet to be watchlisted (strict AND logic).

    Scoring weights:
      - Win rate: 40%
      - PnL: 30%
      - Trade count: 20%
      - Decay score: 10%

    Attributes:
        _config_repo: ConfigRepository instance for fetching criteria.

    Example:
        evaluator = WatchlistEvaluator(config_repo)
        decision = await evaluator.evaluate_wallet(wallet)
        # decision.status = WalletStatus.WATCHLISTED or WalletStatus.IGNORED
        # decision.score = 0.8523 (composite score)
        # decision.reason = "Meets all criteria" or "Failed: win_rate < 0.70"
    """

    def __init__(self, config_repo: ConfigRepository) -> None:
        """Initialize evaluator with config repository.

        Args:
            config_repo: ConfigRepository instance for fetching watchlist criteria and scoring weights.
        """
        self._config_repo = config_repo

        # Load scoring weights from config (Story 3.5 Issue #5 fix)
        # These weights are now configurable instead of hardcoded
        self.weight_win_rate = 0.40  # Default
        self.weight_pnl = 0.30  # Default
        self.weight_trades = 0.20  # Default
        self.weight_decay = 0.10  # Default

    async def evaluate_wallet(self, wallet: Wallet) -> WatchlistDecision:
        """Evaluate wallet against watchlist criteria.

        Fetches criteria and scoring weights from config, calculates composite score,
        checks all criteria. Returns WatchlistDecision with status (watchlisted/ignored),
        score, and reason.

        Args:
            wallet: Wallet instance with performance and behavioral metrics.

        Returns:
            WatchlistDecision with evaluation results.

        Example:
            decision = await evaluator.evaluate_wallet(wallet)
            if decision.status == WalletStatus.WATCHLISTED:
                print(f"Wallet qualifies! Score: {decision.score}")
            else:
                print(f"Wallet ignored: {decision.reason}")
        """
        # Fetch criteria from config (cached for 5 minutes)
        criteria = await self._config_repo.get_watchlist_criteria()

        # Fetch scoring weights from config (Story 3.5 Issue #5 fix - configurable weights)
        weights = await self._config_repo.get_scoring_weights()
        self.weight_win_rate = weights["weight_win_rate"]
        self.weight_pnl = weights["weight_pnl"]
        self.weight_trades = weights["weight_trades"]
        self.weight_decay = weights["weight_decay"]

        # Calculate composite score
        score = self._calculate_composite_score(wallet, criteria)

        # Check all criteria
        failed_criteria = self._check_criteria(wallet, criteria)

        # Determine status and reason
        if not failed_criteria:
            # ALL criteria met → watchlisted
            status = WalletStatus.WATCHLISTED
            reason = "Meets all criteria"
            log.info(
                "wallet_watchlisted",
                wallet_address=wallet.wallet_address,
                score=float(score),
                win_rate=wallet.win_rate,
                pnl_total=wallet.pnl_total,
                total_trades=wallet.total_trades,
            )
        else:
            # ANY criteria failed → ignored
            status = WalletStatus.IGNORED
            reason = f"Failed: {', '.join(failed_criteria)}"
            log.info(
                "wallet_ignored",
                wallet_address=wallet.wallet_address,
                score=float(score),
                failed_criteria=failed_criteria,
            )

        return WatchlistDecision(
            status=status,
            score=score,
            reason=reason,
            timestamp=datetime.utcnow(),
        )

    def _calculate_composite_score(self, wallet: Wallet, criteria: dict[str, float]) -> Decimal:
        """Calculate weighted composite score (0.0000-1.0000).

        Each component is normalized to 0.0-1.0 range by dividing by minimum threshold.
        Values exceeding threshold are capped at 1.0 (no extra credit).
        Components are then weighted and summed.

        Args:
            wallet: Wallet with performance metrics.
            criteria: Watchlist criteria thresholds.

        Returns:
            Composite score as Decimal with 4 decimal places.

        Example:
            # Wallet: win_rate=0.75, pnl=10.0, trades=20, decay=0.2
            # Criteria: min_winrate=0.70, min_pnl=5.0, min_trades=10, max_decay=0.3
            # Components: [1.0, 1.0, 1.0, 0.333]
            # Score: (1.0*0.4) + (1.0*0.3) + (1.0*0.2) + (0.333*0.1) = 0.9333
        """
        # Normalize win_rate component (0-100 → 0.0-1.0, then divide by threshold)
        win_rate_normalized = wallet.win_rate / 100.0  # Convert percentage to decimal
        win_rate_component = min(win_rate_normalized / criteria["min_winrate"], 1.0)

        # Normalize PnL component (divide by threshold, cap at 1.0)
        pnl_total = wallet.pnl_total if wallet.pnl_total is not None else 0.0
        pnl_component = min(pnl_total / criteria["min_pnl"], 1.0) if pnl_total > 0 else 0.0

        # Normalize trades component (divide by threshold, cap at 1.0)
        trades_component = min(wallet.total_trades / criteria["min_trades"], 1.0)

        # Normalize decay component (inverted: lower decay = higher score)
        # Handle missing decay_score gracefully (None = no decay detected = perfect score)
        if wallet.rolling_win_rate is None:
            # No decay calculated yet → assume perfect (1.0)
            decay_component = 1.0
        else:
            # Decay score is based on rolling_win_rate degradation
            # For Story 3.5, we use a simple heuristic: if rolling_win_rate exists,
            # calculate pseudo-decay-score = 1 - (rolling_win_rate / 100)
            # This is a placeholder until decay_score column is properly populated
            rolling_wr_decimal = float(wallet.rolling_win_rate) / 100.0
            pseudo_decay = 1.0 - rolling_wr_decimal
            decay_component = (
                1.0 - (pseudo_decay / criteria["max_decay_score"])
                if pseudo_decay <= criteria["max_decay_score"]
                else 0.0
            )
            decay_component = max(0.0, min(1.0, decay_component))  # Clamp [0, 1]

        # Apply weights (must sum to 1.0)
        # Story 3.5 Issue #5 fix - Use configurable weights instead of hardcoded constants
        composite = (
            win_rate_component * self.weight_win_rate
            + pnl_component * self.weight_pnl
            + trades_component * self.weight_trades
            + decay_component * self.weight_decay
        )

        # Round to 4 decimal places and return as Decimal
        return Decimal(str(round(composite, 4)))

    def _check_criteria(self, wallet: Wallet, criteria: dict[str, float]) -> list[str]:
        """Check wallet against all criteria and return list of failures.

        ALL criteria must pass for wallet to be watchlisted.
        Returns empty list if all pass, or list of failure reasons if any fail.

        Args:
            wallet: Wallet to evaluate.
            criteria: Watchlist criteria thresholds.

        Returns:
            List of failed criteria reasons (empty if all pass).

        Example:
            failures = _check_criteria(wallet, criteria)
            if not failures:
                # All criteria passed
            else:
                # failures = ["win_rate < 0.70", "pnl_total < 5.0"]
        """
        failed = []

        # Check win_rate (stored as 0-100 percentage)
        win_rate_decimal = wallet.win_rate / 100.0
        if win_rate_decimal < criteria["min_winrate"]:
            failed.append(f"win_rate < {criteria['min_winrate']}")

        # Check pnl_total
        pnl_total = wallet.pnl_total if wallet.pnl_total is not None else 0.0
        if pnl_total < criteria["min_pnl"]:
            failed.append(f"pnl_total < {criteria['min_pnl']}")

        # Check total_trades
        if wallet.total_trades < criteria["min_trades"]:
            failed.append(f"total_trades < {int(criteria['min_trades'])}")

        # Check decay_score (skip if not calculated yet)
        if wallet.rolling_win_rate is not None:
            rolling_wr_decimal = float(wallet.rolling_win_rate) / 100.0
            pseudo_decay = 1.0 - rolling_wr_decimal
            if pseudo_decay > criteria["max_decay_score"]:
                failed.append(f"decay_score > {criteria['max_decay_score']}")

        return failed
