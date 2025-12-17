"""Wallet performance profiling engine."""

import asyncio
from collections import Counter
from datetime import datetime, timedelta
from statistics import mean
from typing import Any

import structlog

from walltrack.config.settings import get_settings
from walltrack.data.models.wallet import Wallet, WalletProfile, WalletStatus
from walltrack.data.supabase.repositories.wallet_repo import WalletRepository
from walltrack.services.helius.client import HeliusClient

log = structlog.get_logger()

# Minimum trades required for full profiling
MIN_TRADES_FOR_PROFILE = 5


class WalletProfiler:
    """Profiles wallet performance and behavioral patterns."""

    def __init__(
        self,
        wallet_repo: WalletRepository,
        helius_client: HeliusClient,
    ) -> None:
        self.wallet_repo = wallet_repo
        self.helius = helius_client
        self.settings = get_settings()

    async def profile_wallet(
        self,
        address: str,
        lookback_days: int = 90,
        force_update: bool = False,
    ) -> Wallet:
        """
        Profile a wallet's performance and behavior.

        Args:
            address: Wallet address to profile
            lookback_days: Days of history to analyze
            force_update: Force update even if recently profiled

        Returns:
            Updated Wallet with profile data
        """
        log.info("profiling_wallet", address=address, lookback_days=lookback_days)

        # Get existing wallet or create new
        wallet = await self.wallet_repo.get_by_address(address)
        if not wallet:
            wallet = Wallet(address=address)

        # Check if recent profile exists
        if (
            not force_update
            and wallet.last_profiled_at
            and (datetime.utcnow() - wallet.last_profiled_at) < timedelta(hours=24)
        ):
            log.info(
                "profile_recent",
                address=address,
                last_profiled=wallet.last_profiled_at,
            )
            return wallet

        # Fetch historical trades
        start_time = datetime.utcnow() - timedelta(days=lookback_days)
        trades = await self._fetch_wallet_trades(address, start_time)

        # Calculate profile metrics
        profile = await self._calculate_profile(trades)
        wallet.profile = profile

        # Update status based on data sufficiency
        if profile.total_trades < MIN_TRADES_FOR_PROFILE:
            wallet.status = WalletStatus.INSUFFICIENT_DATA
            log.info(
                "insufficient_data",
                address=address,
                trades=profile.total_trades,
                required=MIN_TRADES_FOR_PROFILE,
            )
        elif wallet.status == WalletStatus.INSUFFICIENT_DATA:
            wallet.status = WalletStatus.ACTIVE

        # Calculate initial score based on profile
        wallet.score = self._calculate_initial_score(profile)
        wallet.last_profiled_at = datetime.utcnow()

        # Save to database
        if await self.wallet_repo.exists(address):
            await self.wallet_repo.update(wallet)
        else:
            await self.wallet_repo.create(wallet)

        log.info(
            "profile_completed",
            address=address,
            win_rate=profile.win_rate,
            total_pnl=profile.total_pnl,
            trades=profile.total_trades,
            score=wallet.score,
        )

        return wallet

    async def profile_batch(
        self,
        addresses: list[str],
        lookback_days: int = 90,
        max_concurrent: int = 10,
    ) -> list[Wallet]:
        """Profile multiple wallets concurrently."""
        semaphore = asyncio.Semaphore(max_concurrent)

        async def bounded_profile(address: str) -> Wallet | None:
            async with semaphore:
                try:
                    return await self.profile_wallet(address, lookback_days)
                except Exception as e:
                    log.error("profile_error", address=address, error=str(e))
                    return None

        results = await asyncio.gather(
            *[bounded_profile(addr) for addr in addresses],
            return_exceptions=True,
        )

        return [r for r in results if isinstance(r, Wallet)]

    async def _fetch_wallet_trades(
        self,
        address: str,
        start_time: datetime,
    ) -> list[dict[str, Any]]:
        """Fetch wallet's historical trades from Helius."""
        transactions = await self.helius.get_wallet_transactions(
            wallet=address,
            start_time=start_time,
            tx_types=["SWAP", "TRANSFER"],
        )

        # Parse into trades
        trades: list[dict[str, Any]] = []
        positions: dict[str, dict[str, Any]] = {}  # token -> position data

        for tx in transactions:
            if tx.get("type") == "SWAP":
                trade = self._parse_swap_transaction(tx, positions)
                if trade:
                    trades.append(trade)

        return trades

    def _parse_swap_transaction(
        self,
        tx: dict[str, Any],
        positions: dict[str, dict[str, Any]],
    ) -> dict[str, Any] | None:
        """Parse a swap transaction into trade data."""
        token_in = tx.get("tokenIn", {})
        token_out = tx.get("tokenOut", {})
        timestamp = tx.get("timestamp")

        if not all([token_in, token_out, timestamp]):
            return None

        # Convert timestamp to datetime if needed
        if isinstance(timestamp, (int, float)):
            timestamp = datetime.fromtimestamp(timestamp)
        elif isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)

        # Determine if buy or sell (SOL -> token = buy, token -> SOL = sell)
        sol_mint = "So11111111111111111111111111111111111111112"

        if token_in.get("mint") == sol_mint:
            # Buy
            token_mint = token_out.get("mint")
            amount_sol = float(token_in.get("amount", 0))
            amount_token = float(token_out.get("amount", 0))

            # Track position
            if token_mint not in positions:
                positions[token_mint] = {
                    "entry_sol": amount_sol,
                    "entry_time": timestamp,
                    "tokens": amount_token,
                }
            else:
                # Add to existing position
                positions[token_mint]["entry_sol"] += amount_sol
                positions[token_mint]["tokens"] += amount_token

            return {
                "type": "buy",
                "token": token_mint,
                "amount_sol": amount_sol,
                "amount_token": amount_token,
                "timestamp": timestamp,
                "pnl": None,  # Not calculated for buys
            }

        elif token_out.get("mint") == sol_mint:
            # Sell
            token_mint = token_in.get("mint")
            amount_sol = float(token_out.get("amount", 0))
            amount_token = float(token_in.get("amount", 0))

            # Calculate PnL if we have entry data
            pnl = None
            is_win = None

            if token_mint in positions and positions[token_mint]["entry_sol"] > 0:
                entry_sol = positions[token_mint]["entry_sol"]
                pnl = amount_sol - entry_sol
                is_win = pnl > 0

                # Clear or reduce position
                positions[token_mint]["entry_sol"] = max(0, entry_sol - amount_sol)
                positions[token_mint]["tokens"] -= amount_token

            return {
                "type": "sell",
                "token": token_mint,
                "amount_sol": amount_sol,
                "amount_token": amount_token,
                "timestamp": timestamp,
                "pnl": pnl,
                "is_win": is_win,
            }

        return None

    async def _calculate_profile(
        self, trades: list[dict[str, Any]]
    ) -> WalletProfile:
        """Calculate profile metrics from trade history."""
        if not trades:
            return WalletProfile()

        # Separate buys and sells
        buys = [t for t in trades if t["type"] == "buy"]
        sells = [t for t in trades if t["type"] == "sell"]

        # Calculate win rate (from completed trades with PnL)
        completed_trades = [t for t in sells if t.get("pnl") is not None]
        wins = [t for t in completed_trades if t.get("is_win")]
        win_rate = len(wins) / len(completed_trades) if completed_trades else 0.0

        # Calculate PnL metrics
        pnls = [t["pnl"] for t in completed_trades if t.get("pnl") is not None]
        total_pnl = sum(pnls) if pnls else 0.0
        avg_pnl = mean(pnls) if pnls else 0.0

        # Calculate timing percentile (0 = earliest, 1 = latest)
        # This requires comparing to other wallets - simplified here
        timing_percentile = 0.5  # Default, would be calculated with more context

        # Calculate hold times
        hold_times: list[float] = []
        for sell in sells:
            token = sell.get("token")
            sell_time = sell.get("timestamp")

            if not isinstance(sell_time, datetime):
                continue

            # Find corresponding buy
            matching_buys = [
                b
                for b in buys
                if b.get("token") == token
                and isinstance((ts := b.get("timestamp")), datetime)
                and ts < sell_time
            ]
            if matching_buys:
                buy_time = max(b["timestamp"] for b in matching_buys)
                hold_hours = (sell_time - buy_time).total_seconds() / 3600
                hold_times.append(hold_hours)

        avg_hold_time = mean(hold_times) if hold_times else 0.0

        # Extract behavioral patterns
        trade_hours = [
            t["timestamp"].hour
            for t in trades
            if isinstance(t.get("timestamp"), datetime)
        ]
        hour_counts = Counter(trade_hours)
        preferred_hours = [h for h, _ in hour_counts.most_common(5)]

        # Average position size
        buy_amounts = [t.get("amount_sol", 0) for t in buys]
        avg_position = mean(buy_amounts) if buy_amounts else 0.0

        return WalletProfile(
            win_rate=win_rate,
            total_pnl=total_pnl,
            avg_pnl_per_trade=avg_pnl,
            total_trades=len(completed_trades),
            timing_percentile=timing_percentile,
            avg_hold_time_hours=avg_hold_time,
            preferred_hours=preferred_hours,
            avg_position_size_sol=avg_position,
        )

    def _calculate_initial_score(self, profile: WalletProfile) -> float:
        """Calculate initial wallet score from profile metrics."""
        if profile.total_trades < MIN_TRADES_FOR_PROFILE:
            return 0.3  # Low default for insufficient data

        # Score components (0-1 each)
        win_rate_score = min(profile.win_rate, 1.0)

        # PnL score - normalize to reasonable range
        pnl_score = min(max(profile.total_pnl / 100, 0), 1.0)  # 100 SOL = max

        # Timing score (lower is better)
        timing_score = 1.0 - profile.timing_percentile

        # Trade count score (more trades = more reliable)
        trade_score = min(profile.total_trades / 50, 1.0)  # 50 trades = max

        # Weighted average
        score = (
            win_rate_score * 0.35
            + pnl_score * 0.25
            + timing_score * 0.25
            + trade_score * 0.15
        )

        return round(score, 4)

    def _needs_profiling(self, wallet: Wallet, stale_hours: int = 24) -> bool:
        """Check if a wallet needs to be profiled.

        Args:
            wallet: Wallet to check
            stale_hours: Consider profile stale after this many hours

        Returns:
            True if wallet needs profiling
        """
        # Never profiled
        if wallet.last_profiled_at is None:
            return True

        # Profile is stale
        stale_threshold = datetime.utcnow() - timedelta(hours=stale_hours)
        return wallet.last_profiled_at < stale_threshold
