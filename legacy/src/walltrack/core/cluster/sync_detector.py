"""Synchronized buying pattern detector."""

from collections import defaultdict
from datetime import datetime
from typing import Any

import structlog

from walltrack.data.models.cluster import SyncBuyEdge
from walltrack.data.neo4j.client import Neo4jClient
from walltrack.data.neo4j.queries.cluster import ClusterQueries
from walltrack.services.helius.client import HeliusClient

log = structlog.get_logger()

# Time window for considering buys as "synchronized"
SYNC_WINDOW_SECONDS = 300  # 5 minutes


class SyncBuyDetector:
    """Detects synchronized buying patterns between wallets."""

    def __init__(
        self,
        neo4j_client: Neo4jClient,
        helius_client: HeliusClient,
        sync_window_seconds: int = SYNC_WINDOW_SECONDS,
    ) -> None:
        self._neo4j = neo4j_client
        self._helius = helius_client
        self._queries = ClusterQueries(neo4j_client)
        self._sync_window = sync_window_seconds

    async def detect_sync_buys_for_token(
        self, token_mint: str, wallet_addresses: list[str]
    ) -> list[SyncBuyEdge]:
        """
        Detect synchronized buys for a token among a set of wallets.

        Args:
            token_mint: Token to analyze
            wallet_addresses: Wallets to check for synchronized buying

        Returns:
            List of BUYS_WITH edges detected
        """
        log.info(
            "detecting_sync_buys",
            token=token_mint[:16],
            wallet_count=len(wallet_addresses),
        )

        # Get buy transactions for each wallet
        wallet_buys: dict[str, list[dict[str, Any]]] = {}

        for address in wallet_addresses:
            try:
                txs = await self._helius.get_token_transactions(
                    mint=token_mint,
                    wallet=address,
                    tx_type="SWAP",
                    limit=50,
                )
                # Filter to buys only (receiving the token)
                buys = [
                    tx for tx in txs
                    if self._is_buy_transaction(tx, address, token_mint)
                ]
                if buys:
                    wallet_buys[address] = buys
            except Exception as e:
                log.debug("fetch_buys_error", wallet=address[:16], error=str(e))

        # Find synchronized pairs
        edges: list[SyncBuyEdge] = []
        wallets = list(wallet_buys.keys())

        for i, wallet_a in enumerate(wallets):
            for wallet_b in wallets[i + 1:]:
                sync_edge = self._find_sync_pattern(
                    wallet_a,
                    wallet_buys[wallet_a],
                    wallet_b,
                    wallet_buys[wallet_b],
                    token_mint,
                )
                if sync_edge:
                    await self._queries.create_sync_buy_edge(sync_edge)
                    edges.append(sync_edge)

        log.info(
            "sync_detection_complete",
            token=token_mint[:16],
            edges_found=len(edges),
        )
        return edges

    def _is_buy_transaction(
        self, tx: dict[str, Any], wallet: str, token_mint: str
    ) -> bool:
        """Check if transaction is a buy (wallet receives the token)."""
        for transfer in tx.get("tokenTransfers", []):
            if (
                transfer.get("mint") == token_mint
                and transfer.get("toUserAccount") == wallet
            ):
                return True
        return False

    def _find_sync_pattern(
        self,
        wallet_a: str,
        buys_a: list[dict[str, Any]],
        wallet_b: str,
        buys_b: list[dict[str, Any]],
        token_mint: str,
    ) -> SyncBuyEdge | None:
        """Find synchronized buying pattern between two wallets."""
        min_delta = float("inf")
        sync_count = 0

        for buy_a in buys_a:
            ts_a = self._get_timestamp(buy_a)
            if not ts_a:
                continue

            for buy_b in buys_b:
                ts_b = self._get_timestamp(buy_b)
                if not ts_b:
                    continue

                delta = abs((ts_a - ts_b).total_seconds())
                if delta <= self._sync_window:
                    sync_count += 1
                    min_delta = min(min_delta, delta)

        if sync_count > 0:
            # Calculate correlation score based on timing
            # Closer timing = higher score
            correlation = max(0.0, 1.0 - (min_delta / self._sync_window))

            return SyncBuyEdge(
                wallet_a=wallet_a,
                wallet_b=wallet_b,
                token_mint=token_mint,
                time_delta_seconds=int(min_delta) if min_delta != float("inf") else 0,
                correlation_score=correlation,
                occurrences=sync_count,
            )

        return None

    def _get_timestamp(self, tx: dict[str, Any]) -> datetime | None:
        """Extract timestamp from transaction."""
        ts = tx.get("timestamp")
        if isinstance(ts, int):
            return datetime.fromtimestamp(ts)
        elif isinstance(ts, str):
            try:
                return datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except ValueError:
                return None
        elif isinstance(ts, datetime):
            return ts
        return None

    async def detect_all_sync_patterns(
        self, wallet_addresses: list[str], lookback_days: int = 30  # noqa: ARG002
    ) -> list[SyncBuyEdge]:
        """
        Detect all synchronized buying patterns among wallets.

        This analyzes recent transactions to find wallets buying
        the same tokens within the sync window.
        """
        log.info("detecting_all_sync_patterns", wallet_count=len(wallet_addresses))

        # Collect all tokens each wallet has traded
        wallet_tokens: dict[str, set[str]] = defaultdict(set)

        for address in wallet_addresses:
            try:
                txs = await self._helius.get_wallet_transactions(
                    wallet=address,
                    tx_types=["SWAP"],
                    limit=100,
                )
                for tx in txs:
                    for transfer in tx.get("tokenTransfers", []):
                        mint = transfer.get("mint")
                        if mint:
                            wallet_tokens[address].add(mint)
            except Exception as e:
                log.debug("fetch_tokens_error", wallet=address[:16], error=str(e))

        # Find tokens traded by multiple wallets
        token_wallets: dict[str, list[str]] = defaultdict(list)
        for wallet, tokens in wallet_tokens.items():
            for token in tokens:
                token_wallets[token].append(wallet)

        # Analyze tokens with multiple traders
        all_edges: list[SyncBuyEdge] = []
        for token, traders in token_wallets.items():
            if len(traders) >= 2:
                edges = await self.detect_sync_buys_for_token(token, traders)
                all_edges.extend(edges)

        return all_edges

    async def get_sync_partners(
        self, wallet_address: str, min_occurrences: int = 2
    ) -> list[SyncBuyEdge]:
        """Get wallets that frequently buy in sync with the given wallet."""
        return await self._queries.get_sync_buyers(wallet_address, min_occurrences)
