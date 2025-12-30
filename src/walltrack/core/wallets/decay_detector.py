"""Decay detector service for wallet performance degradation detection.

This module provides decay detection functionality to identify when wallets
lose their edge through rolling window analysis, consecutive loss detection,
and dormancy tracking.

Story 3.4 - Wallet Decay Detection
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import structlog

from walltrack.data.models.decay_event import DecayEvent, DecayEventCreate, DecayEventType
from walltrack.data.models.transaction import SwapTransaction, TransactionType
from walltrack.data.models.wallet import Wallet
from walltrack.data.supabase.repositories.config_repo import ConfigRepository
from walltrack.data.supabase.repositories.wallet_repo import WalletRepository
from walltrack.services.helius.client import HeliusClient

log = structlog.get_logger(__name__)

# Score bounds (AC: Score adjustment)
MIN_SCORE = 0.1  # Never reduce below (wallet still viable)
MAX_SCORE = 1.0  # Perfect score ceiling


@dataclass
class Trade:
    """Completed trade (matched BUY+SELL pair).

    Attributes:
        token_mint: Token address.
        entry_time: BUY timestamp.
        exit_time: SELL timestamp.
        pnl: Profit/loss in SOL (SELL - BUY).
        profitable: True if pnl > 0.
    """

    token_mint: str
    entry_time: datetime
    exit_time: datetime
    pnl: float
    profitable: bool


@dataclass
class DecayConfig:
    """Configuration for decay detection (loaded from database).

    Attributes:
        rolling_window_size: Number of recent completed trades to analyze (default: 20).
        min_trades: Minimum completed trades required for decay check (default: 20).
        decay_threshold: Rolling win rate below this triggers "flagged" (default: 0.40).
        recovery_threshold: Rolling win rate above this triggers recovery from "flagged" (default: 0.50).
        consecutive_loss_threshold: Consecutive losses to trigger "downgraded" (default: 3).
        dormancy_days: Days without activity to trigger "dormant" (default: 30).
        score_downgrade_decay: Multiplier for decay event (default: 0.80 = 20% reduction).
        score_downgrade_loss: Multiplier per loss beyond threshold (default: 0.95 = 5% per loss).
        score_recovery_boost: Multiplier for recovery event (default: 1.10 = 10% increase).
    """

    rolling_window_size: int
    min_trades: int
    decay_threshold: float
    recovery_threshold: float
    consecutive_loss_threshold: int
    dormancy_days: int
    score_downgrade_decay: float
    score_downgrade_loss: float
    score_recovery_boost: float

    @classmethod
    async def from_db(cls, config_repo: ConfigRepository) -> "DecayConfig":
        """Load decay configuration from database.

        Args:
            config_repo: ConfigRepository instance.

        Returns:
            DecayConfig with values from database (or defaults).

        Example:
            config_repo = ConfigRepository(client)
            config = await DecayConfig.from_db(config_repo)
        """
        return cls(
            rolling_window_size=await config_repo.get_decay_rolling_window_size(),
            min_trades=await config_repo.get_decay_min_trades(),
            decay_threshold=await config_repo.get_decay_threshold(),
            recovery_threshold=await config_repo.get_decay_recovery_threshold(),
            consecutive_loss_threshold=await config_repo.get_decay_consecutive_loss_threshold(),
            dormancy_days=await config_repo.get_decay_dormancy_days(),
            score_downgrade_decay=await config_repo.get_decay_score_downgrade_decay(),
            score_downgrade_loss=await config_repo.get_decay_score_downgrade_loss(),
            score_recovery_boost=await config_repo.get_decay_score_recovery_boost(),
        )


class DecayDetector:
    """Detector for wallet performance decay.

    Analyzes wallet trading history to detect decay patterns:
    - AC1: Rolling window decay (win rate < 40% over 20 trades)
    - AC2: Consecutive losses (3+ losses → downgraded)
    - AC3: Dormancy (30+ days inactive → dormant)

    Attributes:
        config: DecayConfig loaded from database.
        wallet_repo: WalletRepository for wallet data operations.
        helius_client: HeliusClient for fetching transaction history.

    Example:
        detector = DecayDetector(config, wallet_repo, helius_client)
        event = await detector.check_wallet_decay("9xQeWvG...")
        if event:
            print(f"Decay detected: {event.event_type}")
    """

    def __init__(
        self,
        config: DecayConfig,
        wallet_repo: WalletRepository,
        helius_client: HeliusClient,
    ) -> None:
        """Initialize decay detector.

        Args:
            config: DecayConfig with detection parameters.
            wallet_repo: WalletRepository instance.
            helius_client: HeliusClient instance.
        """
        self.config = config
        self.wallet_repo = wallet_repo
        self.helius_client = helius_client

    async def check_wallet_decay(self, wallet_address: str) -> DecayEvent | None:
        """Check wallet for decay conditions and update status if changed.

        Fetches wallet data, analyzes recent trades, checks decay conditions,
        and updates wallet status/score if a transition occurred.

        Args:
            wallet_address: Solana wallet address to check.

        Returns:
            DecayEvent if status changed, None otherwise.

        Example:
            event = await detector.check_wallet_decay("9xQeWvG...")
            if event and event.event_type == DecayEventType.DECAY_DETECTED:
                print(f"Wallet flagged: rolling_win_rate={event.rolling_win_rate}")
        """
        # Fetch wallet from repository
        wallet = await self.wallet_repo.get_by_address(wallet_address)
        if not wallet:
            log.warning("wallet_not_found", wallet_address=wallet_address[:8] + "...")
            return None

        # Fetch recent transactions and match trades
        transactions = await self.helius_client.get_swap_transactions(
            wallet_address, limit=100
        )
        trades = self._match_trades(transactions)

        # Check if wallet has enough trades for analysis
        if len(trades) < self.config.min_trades:
            log.debug(
                "insufficient_trades_for_decay_check",
                wallet_address=wallet_address[:8] + "...",
                trades_count=len(trades),
                min_required=self.config.min_trades,
            )
            return None

        # Calculate rolling window win rate (AC1)
        rolling_trades = trades[-self.config.rolling_window_size :]
        rolling_win_rate = sum(1 for t in rolling_trades if t.profitable) / len(
            rolling_trades
        )

        # Count consecutive losses (AC2)
        consecutive_losses = self._count_consecutive_losses(trades)

        # Calculate days since last activity (AC3)
        days_since_activity = self._calculate_days_since_activity(wallet)

        # Determine new decay status with priority order
        old_status = wallet.decay_status or "ok"
        new_status = self._determine_decay_status(
            wallet, rolling_win_rate, consecutive_losses, days_since_activity
        )

        # If status unchanged, no event needed
        if new_status == old_status:
            # Update tracking fields even if status unchanged
            await self.wallet_repo.update_decay_status(
                wallet_address=wallet_address,
                decay_status=new_status,
                score=wallet.score,
                rolling_win_rate=rolling_win_rate,
                consecutive_losses=consecutive_losses,
                last_activity_date=(
                    trades[-1].exit_time if trades else wallet.last_activity_date
                ),
            )
            return None

        # Calculate score adjustment
        old_score = wallet.score
        new_score = self._calculate_score_adjustment(
            old_score, old_status, new_status, consecutive_losses
        )

        # Determine event type
        event_type = self._determine_event_type(old_status, new_status)

        # Update wallet in repository
        await self.wallet_repo.update_decay_status(
            wallet_address=wallet_address,
            decay_status=new_status,
            score=new_score,
            rolling_win_rate=rolling_win_rate,
            consecutive_losses=consecutive_losses,
            last_activity_date=trades[-1].exit_time if trades else wallet.last_activity_date,
        )

        # Create and return decay event
        event = DecayEventCreate(
            wallet_address=wallet_address,
            event_type=event_type,
            rolling_win_rate=Decimal(str(rolling_win_rate)),
            lifetime_win_rate=Decimal(str(wallet.win_rate)) if wallet.win_rate else None,
            consecutive_losses=consecutive_losses,
            score_before=Decimal(str(old_score)),
            score_after=Decimal(str(new_score)),
        )

        log.info(
            "wallet_decay_status_changed",
            wallet_address=wallet_address[:8] + "...",
            old_status=old_status,
            new_status=new_status,
            event_type=event_type.value,
            score_change=f"{old_score:.4f} → {new_score:.4f}",
        )

        return event

    def _match_trades(self, transactions: list[SwapTransaction]) -> list[Trade]:
        """Match BUY/SELL pairs to create completed trades (FIFO).

        Uses FIFO matching: oldest BUY matches oldest SELL for each token.
        Reuses logic from Story 3.2 (PerformanceCalculator).

        Args:
            transactions: List of swap transactions.

        Returns:
            List of Trade objects representing completed BUY/SELL pairs.

        Example:
            transactions = [buy1, sell1, buy2, sell2]
            trades = detector._match_trades(transactions)
            # Returns: [Trade(pnl=0.5, profitable=True), Trade(pnl=-0.2, profitable=False)]
        """
        # Group transactions by token_mint
        by_token: dict[str, list[SwapTransaction]] = defaultdict(list)
        for tx in transactions:
            by_token[tx.token_mint].append(tx)

        trades: list[Trade] = []

        # Match BUY/SELL pairs for each token
        for token_mint, txs in by_token.items():
            # Separate BUYs and SELLs, sort by timestamp (FIFO)
            buys = sorted(
                [t for t in txs if t.tx_type == TransactionType.BUY],
                key=lambda t: t.timestamp,
            )
            sells = sorted(
                [t for t in txs if t.tx_type == TransactionType.SELL],
                key=lambda t: t.timestamp,
            )

            # Match oldest BUY with oldest SELL (FIFO)
            for buy, sell in zip(buys, sells):
                pnl = sell.sol_amount - buy.sol_amount
                profitable = pnl > 0

                trade = Trade(
                    token_mint=token_mint,
                    entry_time=buy.timestamp,
                    exit_time=sell.timestamp,
                    pnl=pnl,
                    profitable=profitable,
                )
                trades.append(trade)

        return sorted(trades, key=lambda t: t.exit_time)  # Sort by exit time

    def _count_consecutive_losses(self, trades: list[Trade]) -> int:
        """Count consecutive losses from most recent trade backwards.

        Iterates from newest to oldest trade, counting losses until first win.
        Resets to 0 if latest trade is a win.

        Args:
            trades: List of completed trades (sorted by exit_time).

        Returns:
            Number of consecutive losing trades.

        Example:
            # Latest trades: [win, loss, loss, loss, win]
            count = detector._count_consecutive_losses(trades)
            # Returns: 3 (3 losses before the latest win)
        """
        if not trades:
            return 0

        consecutive = 0
        for trade in reversed(trades):
            if not trade.profitable:
                consecutive += 1
            else:
                break

        return consecutive

    def _calculate_days_since_activity(self, wallet: Wallet) -> int:
        """Calculate days since last trading activity.

        Uses wallet.last_activity_date if available, otherwise calculates
        from current time.

        Args:
            wallet: Wallet instance.

        Returns:
            Number of days since last activity.

        Example:
            days = detector._calculate_days_since_activity(wallet)
            # Returns: 45 (wallet hasn't traded in 45 days)
        """
        if not wallet.last_activity_date:
            # No activity date recorded - assume very old
            return 9999

        now = datetime.now(UTC)
        delta = now - wallet.last_activity_date
        return delta.days

    def _determine_decay_status(
        self,
        wallet: Wallet,
        rolling_win_rate: float,
        consecutive_losses: int,
        days_since_activity: int,
    ) -> str:
        """Determine decay status with explicit priority order.

        Priority (highest to lowest):
        1. DORMANT (days_inactive >= 30) - Overrides all
        2. DOWNGRADED (consecutive_losses >= 3) - Most severe
        3. FLAGGED (rolling_win_rate < 0.40) - Moderate warning
        4. OK (recovery: rolling_win_rate >= 0.50 AND currently flagged)
        5. OK (default)

        Args:
            wallet: Wallet instance with current status.
            rolling_win_rate: Win rate over recent trades (0.0-1.0).
            consecutive_losses: Number of consecutive losses.
            days_since_activity: Days since last trade.

        Returns:
            New decay status string.

        Example:
            status = detector._determine_decay_status(wallet, 0.35, 0, 5)
            # Returns: "flagged" (win rate < 40%)
        """
        # Priority 1: Dormancy (highest)
        if days_since_activity >= self.config.dormancy_days:
            return "dormant"

        # Priority 2: Consecutive losses (severe)
        if consecutive_losses >= self.config.consecutive_loss_threshold:
            return "downgraded"

        # Priority 3: Rolling window decay (moderate)
        if rolling_win_rate < self.config.decay_threshold:
            return "flagged"

        # Priority 4: Recovery (only if currently flagged)
        if (
            wallet.decay_status == "flagged"
            and rolling_win_rate >= self.config.recovery_threshold
        ):
            return "ok"

        # Priority 5: Default
        return wallet.decay_status or "ok"

    def _calculate_score_adjustment(
        self,
        old_score: float,
        old_status: str,
        new_status: str,
        consecutive_losses: int,
    ) -> float:
        """Calculate adjusted score based on status transition.

        Adjustments:
        - Decay detected: score *= 0.80 (20% reduction)
        - Consecutive losses: score *= 0.95 per loss beyond threshold (5% per loss)
        - Recovery: score *= 1.10 (10% increase)

        Enforces bounds: MIN_SCORE (0.1) to MAX_SCORE (1.0).

        Args:
            old_score: Current wallet score.
            old_status: Previous decay status.
            new_status: New decay status.
            consecutive_losses: Number of consecutive losses.

        Returns:
            Adjusted score (bounded).

        Example:
            new_score = detector._calculate_score_adjustment(0.85, "ok", "flagged", 0)
            # Returns: 0.68 (0.85 * 0.80 = 20% reduction)
        """
        # Special case: reset from zero/negative score
        if old_score <= 0:
            return MIN_SCORE

        new_score = old_score

        # Decay detected (ok → flagged)
        if old_status == "ok" and new_status == "flagged":
            new_score *= self.config.score_downgrade_decay

        # Consecutive losses (ok/flagged → downgraded)
        elif new_status == "downgraded":
            # Apply loss penalty for losses beyond threshold
            losses_beyond_threshold = max(
                0, consecutive_losses - self.config.consecutive_loss_threshold
            )
            for _ in range(losses_beyond_threshold):
                new_score *= self.config.score_downgrade_loss

        # Recovery (flagged → ok)
        elif old_status == "flagged" and new_status == "ok":
            new_score *= self.config.score_recovery_boost

        # Enforce bounds
        new_score = max(MIN_SCORE, min(MAX_SCORE, new_score))

        return new_score

    def _determine_event_type(self, old_status: str, new_status: str) -> DecayEventType:
        """Determine decay event type from status transition.

        Args:
            old_status: Previous decay status.
            new_status: New decay status.

        Returns:
            DecayEventType enum value.

        Example:
            event_type = detector._determine_event_type("ok", "flagged")
            # Returns: DecayEventType.DECAY_DETECTED
        """
        if new_status == "dormant":
            return DecayEventType.DORMANCY
        elif new_status == "downgraded":
            return DecayEventType.CONSECUTIVE_LOSSES
        elif new_status == "flagged":
            return DecayEventType.DECAY_DETECTED
        elif old_status == "flagged" and new_status == "ok":
            return DecayEventType.RECOVERY
        else:
            # Fallback (should not happen with proper logic)
            return DecayEventType.DECAY_DETECTED
