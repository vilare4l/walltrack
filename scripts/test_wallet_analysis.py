"""Test wallet analysis end-to-end.

Tests that wallet analysis (Performance + Behavioral + Decay) works correctly.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import structlog

from walltrack.core.analysis.performance_orchestrator import PerformanceOrchestrator
from walltrack.core.behavioral.profiler import BehavioralProfiler
from walltrack.core.wallets.decay_detector import DecayConfig, DecayDetector
from walltrack.data.supabase.client import get_supabase_client
from walltrack.data.supabase.repositories.config_repo import ConfigRepository
from walltrack.data.supabase.repositories.wallet_repo import WalletRepository
from walltrack.services.solana.rpc_client import SolanaRPCClient

log = structlog.get_logger(__name__)


async def _load_decay_config(config_repo: ConfigRepository) -> DecayConfig:
    """Load decay configuration from database.

    Args:
        config_repo: ConfigRepository instance.

    Returns:
        DecayConfig with values from database or defaults.
    """
    return DecayConfig(
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


async def test_analysis():
    """Test complete wallet analysis pipeline."""
    # Get Supabase client (uses settings from env)
    client = await get_supabase_client()

    try:
        # Initialize repositories and RPC client
        print("\n[Setup] Initializing dependencies...")
        wallet_repo = WalletRepository(client=client)
        config_repo = ConfigRepository(client=client)
        rpc_client = SolanaRPCClient()
        print("[OK] Dependencies initialized")

        # Step 1: Check wallets exist
        print("\n[Step 1] Checking wallets in database...")
        wallets = await wallet_repo.get_all(limit=2)  # Limit to 2 wallets to avoid RPC rate limiting

        if not wallets:
            print("[ERROR] No wallets found in database")
            print("[INFO] Run wallet discovery first")
            return

        print(f"[OK] Found {len(wallets)} wallets")
        for wallet in wallets[:3]:
            print(f"   - {wallet.wallet_address[:12]}... (Status: {wallet.wallet_status})")

        # Step 2: Test Performance Analysis
        print("\n[Step 2] Running Performance Analysis...")
        perf_orchestrator = PerformanceOrchestrator(
            rpc_client=rpc_client,
            config_repo=config_repo,
            wallet_repo=wallet_repo,
        )

        try:
            result = await perf_orchestrator.analyze_all_wallets(max_concurrent=1)  # Sequential to respect RPC rate limit
            print(f"[OK] Performance analysis completed: {result}")
        except Exception as e:
            print(f"[ERROR] Performance analysis failed: {e}")
            import traceback
            traceback.print_exc()
            return

        # Step 3: Test Behavioral Profiling
        print("\n[Step 3] Running Behavioral Profiling...")
        profiler = BehavioralProfiler(
            rpc_client=rpc_client,
            config=config_repo,
        )

        profiled = 0
        skipped = 0
        for wallet in wallets:
            try:
                profile = await profiler.analyze(wallet.wallet_address)
                if profile is None:
                    skipped += 1
                    continue

                # Update wallet with behavioral data
                success = await wallet_repo.update_behavioral_profile(
                    wallet_address=wallet.wallet_address,
                    position_size_style=profile.position_size_style or "unknown",
                    position_size_avg=float(profile.position_size_avg),
                    hold_duration_avg=profile.hold_duration_avg,
                    hold_duration_style=profile.hold_duration_style or "unknown",
                    behavioral_confidence=profile.confidence,
                )
                if success:
                    profiled += 1
            except Exception as e:
                print(f"   [ERROR] Failed to profile {wallet.wallet_address[:12]}: {e}")

        print(f"[OK] Behavioral profiling completed: {profiled} profiled, {skipped} skipped")

        # Step 4: Test Decay Detection
        print("\n[Step 4] Running Decay Detection...")
        decay_config = await _load_decay_config(config_repo)
        detector = DecayDetector(
            config=decay_config,
            wallet_repo=wallet_repo,
            rpc_client=rpc_client,
        )

        flagged = 0
        downgraded = 0
        dormant = 0
        for wallet in wallets:
            try:
                event = await detector.check_wallet_decay(wallet.wallet_address)
                if event:
                    if event.event_type.value == "flagged":
                        flagged += 1
                    elif event.event_type.value == "downgraded":
                        downgraded += 1
                    elif event.event_type.value == "dormant":
                        dormant += 1
            except Exception as e:
                print(f"   [ERROR] Failed to check decay for {wallet.wallet_address[:12]}: {e}")

        print(f"[OK] Decay detection completed: {flagged} flagged, {downgraded} downgraded, {dormant} dormant")

        # Step 5: Verify results saved
        print("\n[Step 5] Verifying results saved to database...")
        wallets_after = await wallet_repo.get_all(limit=10)

        for wallet in wallets_after[:3]:
            print(f"\n   Wallet: {wallet.wallet_address[:12]}...")
            print(f"   - Win Rate: {wallet.win_rate}")
            print(f"   - PnL Total: {wallet.pnl_total}")
            print(f"   - Total Trades: {wallet.total_trades}")
            print(f"   - Entry Delay: {wallet.entry_delay_seconds}s")
            print(f"   - Behavioral Confidence: {wallet.behavioral_confidence}")
            print(f"   - Decay Status: {wallet.decay_status}")
            print(f"   - Score: {wallet.score}")
            print(f"   - Watchlist Score: {wallet.watchlist_score}")

        # Check if metrics were calculated
        analyzed_wallets = [w for w in wallets_after if w.metrics_last_updated is not None]
        print(f"\n[OK] {len(analyzed_wallets)}/{len(wallets_after)} wallets have metrics")

        if len(analyzed_wallets) == 0:
            print("[WARNING] No wallets have calculated metrics!")
            print("   Analysis may have failed silently")
        else:
            print("[SUCCESS] Wallet analysis pipeline working!")

    finally:
        # AsyncClient doesn't have aclose() - just pass
        pass


if __name__ == "__main__":
    asyncio.run(test_analysis())
