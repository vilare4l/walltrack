"""Behavioral profiling orchestrator.

This module provides the main orchestration logic for analyzing wallet behavior
by combining position sizing, hold duration, and transaction patterns.

Story 3.3 RPC Migration: Uses Solana RPC instead of Helius for transaction history.
"""

from dataclasses import dataclass
from decimal import Decimal

import structlog

from walltrack.core.behavioral.hold_duration import (
    calculate_hold_duration_avg,
    classify_hold_duration,
)
from walltrack.core.behavioral.position_sizing import (
    calculate_position_size_avg,
    classify_position_size,
)
from walltrack.data.models.transaction import TransactionType
from walltrack.data.supabase.repositories.config_repo import ConfigRepository
from walltrack.services.solana.rpc_client import SolanaRPCClient
from walltrack.services.solana.transaction_parser import TransactionParser

log = structlog.get_logger(__name__)


@dataclass
class BehavioralProfile:
    """Wallet behavioral profile result.

    Contains all behavioral metrics and classifications for a wallet.

    Attributes:
        wallet_address: Solana wallet address analyzed.
        confidence: Confidence level (high, medium, low, unknown).
        total_trades: Total number of BUY/SELL pairs analyzed.
        position_size_style: Position size classification (small, medium, large).
        position_size_avg: Average position size in SOL.
        hold_duration_style: Hold duration classification (scalper, day_trader, swing_trader, position_trader).
        hold_duration_avg: Average hold duration in seconds.

    Example:
        >>> profile = BehavioralProfile(
        ...     wallet_address="9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",
        ...     confidence="high",
        ...     total_trades=75,
        ...     position_size_style="medium",
        ...     position_size_avg=Decimal("2.5"),
        ...     hold_duration_style="day_trader",
        ...     hold_duration_avg=7200,
        ... )
    """

    wallet_address: str
    confidence: str
    total_trades: int
    position_size_style: str | None
    position_size_avg: Decimal
    hold_duration_style: str | None
    hold_duration_avg: int


class BehavioralProfiler:
    """Orchestrates behavioral profiling analysis for wallets.

    Combines transaction history analysis, position sizing, and hold duration
    patterns to produce a comprehensive behavioral profile.

    Story 3.3 RPC Migration: Uses RPC client instead of Helius for cost optimization.

    Attributes:
        rpc_client: SolanaRPCClient for fetching transaction history via RPC.
        config: ConfigRepository for threshold values.

    Example:
        >>> profiler = BehavioralProfiler(rpc_client, config)
        >>> profile = await profiler.analyze("9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin")
        >>> print(f"Wallet style: {profile.position_size_style}, {profile.hold_duration_style}")
    """

    def __init__(
        self,
        rpc_client: SolanaRPCClient,
        config: ConfigRepository,
    ) -> None:
        """Initialize profiler with dependencies.

        Args:
            rpc_client: SolanaRPCClient instance for transaction fetching via RPC.
            config: ConfigRepository instance for threshold values.
        """
        self.rpc_client = rpc_client
        self.config = config
        self.parser = TransactionParser()

    async def analyze(self, wallet_address: str) -> BehavioralProfile | None:
        """Analyze wallet behavior and produce behavioral profile.

        Orchestrates the full behavioral profiling pipeline:
        1. Fetch transaction history from RPC (Story 3.3 RPC migration)
        2. Check minimum trade count (returns None if insufficient)
        3. Calculate position size metrics and classify
        4. Calculate hold duration metrics and classify
        5. Determine confidence level based on trade count
        6. Return comprehensive behavioral profile

        Args:
            wallet_address: Solana wallet address to analyze.

        Returns:
            BehavioralProfile with all calculated metrics if sufficient data (>=10 trades),
            None otherwise (AC4 compliance).

        Raises:
            Exception: If transaction fetching fails or analysis encounters errors.

        Example:
            >>> profiler = BehavioralProfiler(rpc_client, config)
            >>> profile = await profiler.analyze("9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin")
            >>> if profile and profile.confidence == "high":
            ...     print(f"High confidence profile: {profile.position_size_style}")
        """
        log.info(
            "starting_behavioral_analysis",
            wallet_address=wallet_address[:8] + "...",
        )

        # Load RPC rate limiting config (Story 3.5.5)
        signatures_limit_value = await self.config.get_value("profiling_signatures_limit")
        signatures_limit = int(signatures_limit_value) if signatures_limit_value else 20

        transactions_limit_value = await self.config.get_value("profiling_transactions_limit")
        transactions_limit = int(transactions_limit_value) if transactions_limit_value else 20

        # Step 1: Fetch transaction history via RPC (Story 3.3 RPC Migration)
        try:
            # Fetch transaction signatures (AC1)
            signatures = await self.rpc_client.getSignaturesForAddress(
                address=wallet_address,
                limit=signatures_limit,
            )

            log.debug(
                "signatures_fetched",
                wallet_address=wallet_address[:8] + "...",
                signature_count=len(signatures),
                transactions_to_fetch=min(len(signatures), transactions_limit),
            )

            # Fetch and parse each transaction (AC1 - reuse parser from Story 3.1)
            # Limit to transactions_limit to reduce RPC calls (Story 3.5.5)
            transactions = []
            for sig_info in signatures[:transactions_limit]:
                signature = sig_info.get("signature")
                if not signature:
                    continue

                # Fetch full transaction
                tx_data = await self.rpc_client.getTransaction(signature)
                if not tx_data:
                    continue

                # Parse transaction
                parsed = self.parser.parse(tx_data)
                if parsed:
                    transactions.append(parsed)

            log.info(
                "transactions_parsed",
                wallet_address=wallet_address[:8] + "...",
                transaction_count=len(transactions),
            )
        except Exception as e:
            log.error(
                "transaction_fetch_failed",
                wallet_address=wallet_address[:8] + "...",
                error=str(e),
            )
            raise

        # Step 2: Check minimum trade count (AC4 compliance)
        buy_count = sum(1 for tx in transactions if tx.tx_type == TransactionType.BUY)
        min_trades = await self.config.get_behavioral_min_trades()
        
        if buy_count < min_trades:
            log.info(
                "insufficient_data_for_profiling",
                wallet_address=wallet_address[:8] + "...",
                buy_count=buy_count,
                min_required=min_trades,
            )
            return None

        # Step 3: Calculate position sizing metrics
        position_size_avg = calculate_position_size_avg(transactions)
        position_size_style = await classify_position_size(
            position_size_avg, self.config
        )

        log.debug(
            "position_sizing_calculated",
            wallet_address=wallet_address[:8] + "...",
            avg=float(position_size_avg),
            style=position_size_style,
        )

        # Step 4: Calculate hold duration metrics
        hold_duration_avg = calculate_hold_duration_avg(transactions)
        hold_duration_style = await classify_hold_duration(
            hold_duration_avg, self.config
        )

        log.debug(
            "hold_duration_calculated",
            wallet_address=wallet_address[:8] + "...",
            avg=hold_duration_avg,
            style=hold_duration_style,
        )

        # Step 5: Determine confidence level based on trade count
        confidence = await self._calculate_confidence(buy_count)

        log.info(
            "behavioral_analysis_complete",
            wallet_address=wallet_address[:8] + "...",
            confidence=confidence,
            total_trades=buy_count,
            position_style=position_size_style,
            hold_style=hold_duration_style,
        )

        # Step 6: Build and return profile
        return BehavioralProfile(
            wallet_address=wallet_address,
            confidence=confidence,
            total_trades=buy_count,
            position_size_style=position_size_style if buy_count > 0 else None,
            position_size_avg=position_size_avg,
            hold_duration_style=hold_duration_style if hold_duration_avg > 0 else None,
            hold_duration_avg=hold_duration_avg,
        )

    async def _calculate_confidence(self, trade_count: int) -> str:
        """Calculate confidence level based on trade count.

        Uses configurable thresholds from config repository:
        - unknown: < min_trades (default: 10)
        - low: >= min_trades and < confidence_medium (default: 10)
        - medium: >= confidence_medium and < confidence_high (default: 50)
        - high: >= confidence_high

        Args:
            trade_count: Number of trades executed by wallet.

        Returns:
            Confidence level: "unknown", "low", "medium", or "high".
        """
        min_trades = await self.config.get_behavioral_min_trades()
        confidence_medium = await self.config.get_behavioral_confidence_medium()
        confidence_high = await self.config.get_behavioral_confidence_high()

        if trade_count < min_trades:
            return "unknown"
        elif trade_count < confidence_medium:
            return "low"
        elif trade_count < confidence_high:
            return "medium"
        else:
            return "high"
