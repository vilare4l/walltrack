"""Wallet decay detection for identifying underperforming wallets."""

import asyncio
from datetime import datetime
from typing import Any

import structlog

from walltrack.config.settings import get_settings
from walltrack.data.models.trade import Trade
from walltrack.data.models.wallet import Wallet, WalletStatus
from walltrack.data.supabase.repositories.trade_repo import TradeRepository
from walltrack.data.supabase.repositories.wallet_repo import WalletRepository

log = structlog.get_logger()

# Configuration constants
ROLLING_WINDOW_SIZE = 20
MIN_TRADES_FOR_DECAY_CHECK = 20
DECAY_THRESHOLD = 0.40  # 40% win rate
RECOVERY_THRESHOLD = 0.50  # 50% win rate
CONSECUTIVE_LOSS_THRESHOLD = 3
SCORE_DOWNGRADE_FACTOR = 0.8  # Reduce score by 20%


class DecayEvent:
    """Represents a decay detection event."""

    def __init__(
        self,
        wallet_address: str,
        event_type: str,
        rolling_win_rate: float,
        lifetime_win_rate: float,
        consecutive_losses: int,
        score_before: float,
        score_after: float,
        timestamp: datetime,
    ) -> None:
        self.wallet_address = wallet_address
        self.event_type = event_type  # "decay_detected", "recovery", "consecutive_losses"
        self.rolling_win_rate = rolling_win_rate
        self.lifetime_win_rate = lifetime_win_rate
        self.consecutive_losses = consecutive_losses
        self.score_before = score_before
        self.score_after = score_after
        self.timestamp = timestamp

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for logging/storage."""
        return {
            "wallet_address": self.wallet_address,
            "event_type": self.event_type,
            "rolling_win_rate": self.rolling_win_rate,
            "lifetime_win_rate": self.lifetime_win_rate,
            "consecutive_losses": self.consecutive_losses,
            "score_before": self.score_before,
            "score_after": self.score_after,
            "timestamp": self.timestamp.isoformat(),
        }


class DecayDetector:
    """Detects wallet performance decay and manages flagging."""

    def __init__(
        self,
        wallet_repo: WalletRepository,
        trade_repo: TradeRepository,
        notification_callback: Any | None = None,
    ) -> None:
        self.wallet_repo = wallet_repo
        self.trade_repo = trade_repo
        self.notify = notification_callback
        self.settings = get_settings()

    async def check_wallet_decay(self, wallet: Wallet) -> DecayEvent | None:
        """
        Check a single wallet for decay.

        Args:
            wallet: Wallet to check

        Returns:
            DecayEvent if state changed, None otherwise
        """
        # Get recent trades for rolling window
        recent_trades = await self.trade_repo.get_wallet_trades(
            wallet_address=wallet.address,
            limit=ROLLING_WINDOW_SIZE,
            order_by="exit_at",
            order_desc=True,
        )

        if len(recent_trades) < MIN_TRADES_FOR_DECAY_CHECK:
            log.debug(
                "insufficient_trades_for_decay",
                address=wallet.address,
                trades=len(recent_trades),
            )
            return None

        # Calculate rolling win rate
        wins = sum(1 for t in recent_trades if (t.pnl_sol or 0) > 0)
        rolling_win_rate = wins / len(recent_trades)

        # Update wallet's rolling win rate
        wallet.rolling_win_rate = rolling_win_rate

        # Check consecutive losses
        consecutive_losses = self._count_consecutive_losses(recent_trades)

        score_before = wallet.score
        event: DecayEvent | None = None

        # Check for decay
        if rolling_win_rate < DECAY_THRESHOLD:
            if wallet.status != WalletStatus.DECAY_DETECTED:
                # New decay detected
                event = await self._handle_decay_detected(
                    wallet, rolling_win_rate, consecutive_losses, score_before
                )

        # Check for recovery
        elif (
            rolling_win_rate >= RECOVERY_THRESHOLD
            and wallet.status == WalletStatus.DECAY_DETECTED
        ):
            # Recovery detected
            event = await self._handle_recovery(
                wallet, rolling_win_rate, consecutive_losses, score_before
            )

        # Check consecutive losses (independent of decay status)
        if (
            consecutive_losses >= CONSECUTIVE_LOSS_THRESHOLD
            and wallet.consecutive_losses < CONSECUTIVE_LOSS_THRESHOLD
        ):
            # New consecutive loss threshold breach
            event = await self._handle_consecutive_losses(
                wallet, rolling_win_rate, consecutive_losses, score_before
            )

        wallet.consecutive_losses = consecutive_losses

        # Save wallet changes
        await self.wallet_repo.update(wallet)

        return event

    async def check_all_wallets(
        self,
        batch_size: int = 100,
        max_concurrent: int = 20,
    ) -> list[DecayEvent]:
        """
        Check all active wallets for decay.

        Args:
            batch_size: Number of wallets to process per batch
            max_concurrent: Maximum concurrent checks

        Returns:
            List of decay events
        """
        log.info("decay_check_started")
        events: list[DecayEvent] = []

        # Get all wallets that can be checked (active or decay_detected)
        active_wallets = await self.wallet_repo.get_by_status(
            WalletStatus.ACTIVE, limit=batch_size
        )
        decay_wallets = await self.wallet_repo.get_by_status(
            WalletStatus.DECAY_DETECTED, limit=batch_size
        )

        all_wallets = active_wallets + decay_wallets

        if not all_wallets:
            log.info("no_wallets_to_check")
            return events

        log.info("checking_wallets", count=len(all_wallets))

        semaphore = asyncio.Semaphore(max_concurrent)

        async def bounded_check(wallet: Wallet) -> DecayEvent | None:
            async with semaphore:
                try:
                    return await self.check_wallet_decay(wallet)
                except Exception as e:
                    log.error("decay_check_error", address=wallet.address, error=str(e))
                    return None

        results = await asyncio.gather(
            *[bounded_check(w) for w in all_wallets],
            return_exceptions=True,
        )

        events = [r for r in results if isinstance(r, DecayEvent)]

        log.info(
            "decay_check_completed",
            checked=len(all_wallets),
            events=len(events),
        )

        return events

    async def record_trade_outcome(
        self,
        wallet_address: str,
        is_win: bool,
        pnl: float,  # noqa: ARG002 - kept for API consistency
    ) -> DecayEvent | None:
        """
        Record a trade outcome and check for decay implications.

        Called after each trade completes.

        Args:
            wallet_address: Wallet that made the trade
            is_win: Whether trade was profitable
            pnl: Profit/loss amount

        Returns:
            DecayEvent if triggered, None otherwise
        """
        wallet = await self.wallet_repo.get_by_address(wallet_address)
        if not wallet:
            log.warning("wallet_not_found_for_outcome", address=wallet_address)
            return None

        # Update consecutive losses
        if not is_win:
            wallet.consecutive_losses += 1
        else:
            wallet.consecutive_losses = 0

        # Check if consecutive loss threshold reached
        if wallet.consecutive_losses >= CONSECUTIVE_LOSS_THRESHOLD:
            score_before = wallet.score
            event = await self._handle_consecutive_losses(
                wallet,
                wallet.rolling_win_rate or 0.5,
                wallet.consecutive_losses,
                score_before,
            )
            await self.wallet_repo.update(wallet)
            return event

        await self.wallet_repo.update(wallet)
        return None

    async def _handle_decay_detected(
        self,
        wallet: Wallet,
        rolling_win_rate: float,
        consecutive_losses: int,
        score_before: float,
    ) -> DecayEvent:
        """Handle decay detection."""
        wallet.status = WalletStatus.DECAY_DETECTED
        wallet.decay_detected_at = datetime.utcnow()
        wallet.score = max(wallet.score * SCORE_DOWNGRADE_FACTOR, 0.1)

        event = DecayEvent(
            wallet_address=wallet.address,
            event_type="decay_detected",
            rolling_win_rate=rolling_win_rate,
            lifetime_win_rate=wallet.profile.win_rate if wallet.profile else 0.0,
            consecutive_losses=consecutive_losses,
            score_before=score_before,
            score_after=wallet.score,
            timestamp=datetime.utcnow(),
        )

        log.warning(
            "decay_detected",
            address=wallet.address,
            rolling_win_rate=f"{rolling_win_rate:.2%}",
            score_change=f"{score_before:.3f} -> {wallet.score:.3f}",
        )

        # Send notification
        if self.notify:
            await self.notify(event)

        return event

    async def _handle_recovery(
        self,
        wallet: Wallet,
        rolling_win_rate: float,
        consecutive_losses: int,
        score_before: float,
    ) -> DecayEvent:
        """Handle recovery from decay."""
        wallet.status = WalletStatus.ACTIVE
        wallet.decay_detected_at = None

        # Restore some score (not full - needs to prove itself)
        wallet.score = min(wallet.score / SCORE_DOWNGRADE_FACTOR * 0.9, 1.0)

        event = DecayEvent(
            wallet_address=wallet.address,
            event_type="recovery",
            rolling_win_rate=rolling_win_rate,
            lifetime_win_rate=wallet.profile.win_rate if wallet.profile else 0.0,
            consecutive_losses=consecutive_losses,
            score_before=score_before,
            score_after=wallet.score,
            timestamp=datetime.utcnow(),
        )

        log.info(
            "decay_recovery",
            address=wallet.address,
            rolling_win_rate=f"{rolling_win_rate:.2%}",
            score_change=f"{score_before:.3f} -> {wallet.score:.3f}",
        )

        if self.notify:
            await self.notify(event)

        return event

    async def _handle_consecutive_losses(
        self,
        wallet: Wallet,
        rolling_win_rate: float,
        consecutive_losses: int,
        score_before: float,
    ) -> DecayEvent:
        """Handle consecutive loss threshold breach."""
        # Apply smaller downgrade for consecutive losses
        downgrade = 0.95 ** (consecutive_losses - CONSECUTIVE_LOSS_THRESHOLD + 1)
        wallet.score = max(wallet.score * downgrade, 0.1)

        event = DecayEvent(
            wallet_address=wallet.address,
            event_type="consecutive_losses",
            rolling_win_rate=rolling_win_rate,
            lifetime_win_rate=wallet.profile.win_rate if wallet.profile else 0.0,
            consecutive_losses=consecutive_losses,
            score_before=score_before,
            score_after=wallet.score,
            timestamp=datetime.utcnow(),
        )

        log.warning(
            "consecutive_losses_detected",
            address=wallet.address,
            losses=consecutive_losses,
            score_change=f"{score_before:.3f} -> {wallet.score:.3f}",
        )

        if self.notify:
            await self.notify(event)

        return event

    def _count_consecutive_losses(self, trades: list[Trade]) -> int:
        """Count consecutive losses from most recent trades."""
        consecutive = 0
        for trade in trades:  # trades already sorted by date desc
            if (trade.pnl_sol or 0) <= 0:
                consecutive += 1
            else:
                break
        return consecutive
