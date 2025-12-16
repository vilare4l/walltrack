# Story 1.5: Wallet Performance Profiling

## Story Info
- **Epic**: Epic 1 - Wallet Intelligence & Discovery
- **Status**: ready
- **Priority**: High
- **FR**: FR2, FR3

## User Story

**As an** operator,
**I want** to see performance metrics and behavioral patterns for each wallet,
**So that** I can assess wallet quality before adding to watchlist.

## Acceptance Criteria

### AC 1: Profiling Execution
**Given** a wallet address
**When** profiling is requested
**Then** historical performance is calculated (win rate, total PnL, average PnL per trade)
**And** timing percentile is calculated (how early they typically enter)
**And** behavioral patterns are extracted (activity hours, avg position size, preferred token types)
**And** profile is stored in Supabase wallets table

### AC 2: Insufficient Data
**Given** insufficient historical data (< 5 trades)
**When** profiling is requested
**Then** profile is marked as "insufficient_data"
**And** available metrics are still calculated

### AC 3: Dashboard Display
**Given** profiling completes successfully
**When** the wallet is viewed in dashboard
**Then** all metrics are displayed with last updated timestamp

## Technical Specifications

### Profiler Implementation

**src/walltrack/discovery/profiler.py:**
```python
"""Wallet performance profiling engine."""

import asyncio
from collections import Counter
from datetime import datetime, timedelta
from statistics import mean, median
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
            log.info("profile_recent", address=address, last_profiled=wallet.last_profiled_at)
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
        trades = []
        positions: dict[str, dict] = {}  # token -> position data

        for tx in transactions:
            if tx.get("type") == "SWAP":
                trade = self._parse_swap_transaction(tx, positions)
                if trade:
                    trades.append(trade)

        return trades

    def _parse_swap_transaction(
        self,
        tx: dict[str, Any],
        positions: dict[str, dict],
    ) -> dict[str, Any] | None:
        """Parse a swap transaction into trade data."""
        token_in = tx.get("tokenIn", {})
        token_out = tx.get("tokenOut", {})
        timestamp = tx.get("timestamp")

        if not all([token_in, token_out, timestamp]):
            return None

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

    async def _calculate_profile(self, trades: list[dict[str, Any]]) -> WalletProfile:
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

            # Find corresponding buy
            matching_buys = [
                b for b in buys
                if b.get("token") == token and b.get("timestamp") < sell_time
            ]
            if matching_buys:
                buy_time = max(b["timestamp"] for b in matching_buys)
                hold_hours = (sell_time - buy_time).total_seconds() / 3600
                hold_times.append(hold_hours)

        avg_hold_time = mean(hold_times) if hold_times else 0.0

        # Extract behavioral patterns
        trade_hours = [t["timestamp"].hour for t in trades if t.get("timestamp")]
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
            win_rate_score * 0.35 +
            pnl_score * 0.25 +
            timing_score * 0.25 +
            trade_score * 0.15
        )

        return round(score, 4)
```

### Profiling API Endpoint

**Add to src/walltrack/api/routes/wallets.py:**
```python
from walltrack.discovery.profiler import WalletProfiler
from walltrack.api.dependencies import get_wallet_profiler


class ProfileRequest(BaseModel):
    """Request to profile wallets."""

    addresses: list[str] = Field(..., min_length=1, max_length=50)
    lookback_days: int = Field(default=90, ge=7, le=365)
    force_update: bool = Field(default=False)


class ProfileResponse(BaseModel):
    """Response from profiling operation."""

    profiled: int
    failed: int
    wallets: list[Wallet]


@router.post("/profile", response_model=ProfileResponse)
async def profile_wallets(
    request: ProfileRequest,
    profiler: Annotated[WalletProfiler, Depends(get_wallet_profiler)],
) -> ProfileResponse:
    """
    Profile one or more wallets.

    Calculates performance metrics and behavioral patterns from historical data.
    """
    wallets = await profiler.profile_batch(
        addresses=request.addresses,
        lookback_days=request.lookback_days,
    )

    return ProfileResponse(
        profiled=len(wallets),
        failed=len(request.addresses) - len(wallets),
        wallets=wallets,
    )


@router.post("/{address}/profile", response_model=Wallet)
async def profile_single_wallet(
    address: str,
    profiler: Annotated[WalletProfiler, Depends(get_wallet_profiler)],
    lookback_days: int = Query(default=90, ge=7, le=365),
    force_update: bool = Query(default=False),
) -> Wallet:
    """Profile a single wallet and return updated data."""
    return await profiler.profile_wallet(
        address=address,
        lookback_days=lookback_days,
        force_update=force_update,
    )
```

### Scheduled Profiling Task

**src/walltrack/scheduler/tasks/profiling_task.py:**
```python
"""Scheduled task for periodic wallet profiling."""

import asyncio
from datetime import datetime, timedelta

import structlog

from walltrack.config.settings import get_settings
from walltrack.data.models.wallet import WalletStatus
from walltrack.data.supabase.repositories.wallet_repo import WalletRepository
from walltrack.discovery.profiler import WalletProfiler

log = structlog.get_logger()


async def run_periodic_profiling(
    wallet_repo: WalletRepository,
    profiler: WalletProfiler,
    stale_threshold_hours: int = 24,
    batch_size: int = 50,
) -> None:
    """
    Re-profile wallets that haven't been profiled recently.

    Args:
        wallet_repo: Wallet repository
        profiler: Wallet profiler
        stale_threshold_hours: Hours since last profile to consider stale
        batch_size: Number of wallets to profile per batch
    """
    log.info("periodic_profiling_started", stale_threshold_hours=stale_threshold_hours)

    try:
        # Get active wallets with stale profiles
        stale_threshold = datetime.utcnow() - timedelta(hours=stale_threshold_hours)

        # Query wallets needing re-profile
        active_wallets = await wallet_repo.get_active_wallets(limit=batch_size * 2)

        stale_wallets = [
            w for w in active_wallets
            if w.last_profiled_at is None or w.last_profiled_at < stale_threshold
        ][:batch_size]

        if not stale_wallets:
            log.info("no_stale_profiles")
            return

        log.info("profiling_stale_wallets", count=len(stale_wallets))

        # Profile in batches
        addresses = [w.address for w in stale_wallets]
        results = await profiler.profile_batch(addresses, max_concurrent=10)

        log.info(
            "periodic_profiling_completed",
            requested=len(addresses),
            profiled=len(results),
        )

    except Exception as e:
        log.error("periodic_profiling_error", error=str(e))
        raise
```

### Unit Tests

**tests/unit/discovery/test_profiler.py:**
```python
"""Tests for wallet profiler."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from walltrack.data.models.wallet import Wallet, WalletProfile, WalletStatus
from walltrack.discovery.profiler import WalletProfiler, MIN_TRADES_FOR_PROFILE


@pytest.fixture
def mock_wallet_repo() -> AsyncMock:
    """Mock wallet repository."""
    repo = AsyncMock()
    repo.get_by_address.return_value = None
    repo.exists.return_value = False
    return repo


@pytest.fixture
def mock_helius_client() -> AsyncMock:
    """Mock Helius client."""
    return AsyncMock()


@pytest.fixture
def profiler(mock_wallet_repo: AsyncMock, mock_helius_client: AsyncMock) -> WalletProfiler:
    """Create profiler with mocked dependencies."""
    return WalletProfiler(
        wallet_repo=mock_wallet_repo,
        helius_client=mock_helius_client,
    )


class TestWalletProfiler:
    """Tests for WalletProfiler."""

    async def test_profile_new_wallet(
        self,
        profiler: WalletProfiler,
        mock_helius_client: AsyncMock,
        mock_wallet_repo: AsyncMock,
    ) -> None:
        """Test profiling a new wallet."""
        sol_mint = "So11111111111111111111111111111111111111112"

        # Mock transaction history
        mock_helius_client.get_wallet_transactions.return_value = [
            {
                "type": "SWAP",
                "tokenIn": {"mint": sol_mint, "amount": 1.0},
                "tokenOut": {"mint": "token1", "amount": 1000},
                "timestamp": datetime.utcnow() - timedelta(days=10),
            },
            {
                "type": "SWAP",
                "tokenIn": {"mint": "token1", "amount": 1000},
                "tokenOut": {"mint": sol_mint, "amount": 1.5},
                "timestamp": datetime.utcnow() - timedelta(days=5),
            },
        ] * 5  # Repeat to get enough trades

        wallet = await profiler.profile_wallet("test_wallet")

        assert wallet.address == "test_wallet"
        assert wallet.last_profiled_at is not None
        mock_wallet_repo.create.assert_called_once()

    async def test_profile_insufficient_data(
        self,
        profiler: WalletProfiler,
        mock_helius_client: AsyncMock,
    ) -> None:
        """Test profiling with insufficient trade data."""
        mock_helius_client.get_wallet_transactions.return_value = [
            {"type": "SWAP", "tokenIn": {}, "tokenOut": {}, "timestamp": datetime.utcnow()}
        ]

        wallet = await profiler.profile_wallet("sparse_wallet")

        assert wallet.status == WalletStatus.INSUFFICIENT_DATA
        assert wallet.profile.total_trades < MIN_TRADES_FOR_PROFILE

    async def test_profile_skip_recent(
        self,
        profiler: WalletProfiler,
        mock_wallet_repo: AsyncMock,
        mock_helius_client: AsyncMock,
    ) -> None:
        """Test skipping recently profiled wallet."""
        existing_wallet = Wallet(
            address="recent_wallet",
            last_profiled_at=datetime.utcnow() - timedelta(hours=1),
        )
        mock_wallet_repo.get_by_address.return_value = existing_wallet

        wallet = await profiler.profile_wallet("recent_wallet", force_update=False)

        assert wallet == existing_wallet
        mock_helius_client.get_wallet_transactions.assert_not_called()

    async def test_profile_force_update(
        self,
        profiler: WalletProfiler,
        mock_wallet_repo: AsyncMock,
        mock_helius_client: AsyncMock,
    ) -> None:
        """Test force update of recent profile."""
        existing_wallet = Wallet(
            address="recent_wallet",
            last_profiled_at=datetime.utcnow() - timedelta(hours=1),
        )
        mock_wallet_repo.get_by_address.return_value = existing_wallet
        mock_wallet_repo.exists.return_value = True
        mock_helius_client.get_wallet_transactions.return_value = []

        await profiler.profile_wallet("recent_wallet", force_update=True)

        mock_helius_client.get_wallet_transactions.assert_called_once()

    async def test_calculate_win_rate(self, profiler: WalletProfiler) -> None:
        """Test win rate calculation."""
        trades = [
            {"type": "sell", "pnl": 10, "is_win": True},
            {"type": "sell", "pnl": -5, "is_win": False},
            {"type": "sell", "pnl": 15, "is_win": True},
            {"type": "sell", "pnl": 8, "is_win": True},
            {"type": "sell", "pnl": -3, "is_win": False},
        ]

        profile = await profiler._calculate_profile(trades)

        assert profile.win_rate == 0.6  # 3/5 wins
        assert profile.total_pnl == 25  # Sum of PnLs
        assert profile.total_trades == 5

    async def test_profile_batch(
        self,
        profiler: WalletProfiler,
        mock_helius_client: AsyncMock,
    ) -> None:
        """Test batch profiling."""
        mock_helius_client.get_wallet_transactions.return_value = []

        addresses = ["wallet1", "wallet2", "wallet3"]
        results = await profiler.profile_batch(addresses)

        assert len(results) == 3
        assert mock_helius_client.get_wallet_transactions.call_count == 3
```

## Implementation Tasks

- [ ] Create `src/walltrack/discovery/profiler.py`
- [ ] Implement win rate calculation
- [ ] Implement PnL calculation
- [ ] Implement timing percentile calculation
- [ ] Extract behavioral patterns (hours, size, preferences)
- [ ] Store profile in Supabase
- [ ] Handle insufficient data gracefully
- [ ] Add profile API endpoints
- [ ] Create scheduled profiling task
- [ ] Write unit tests

## Definition of Done

- [ ] Profiler calculates all metrics accurately
- [ ] Insufficient data handled gracefully
- [ ] Profile stored in database
- [ ] Metrics retrievable for dashboard display
- [ ] All unit tests pass
- [ ] mypy and ruff pass
