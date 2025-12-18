"""Funding relationship analyzer - detects FUNDED_BY relationships."""

from datetime import datetime
from typing import Any

import structlog

from walltrack.data.models.cluster import CommonAncestor, FundingEdge, FundingTree
from walltrack.data.neo4j.client import Neo4jClient
from walltrack.data.neo4j.queries.cluster import ClusterQueries
from walltrack.services.helius.client import HeliusClient

log = structlog.get_logger()

# SOL transfer program ID
SOL_TRANSFER_TYPE = "TRANSFER"
LAMPORTS_PER_SOL = 1_000_000_000


class FundingAnalyzer:
    """Analyzes wallet funding relationships."""

    def __init__(
        self,
        neo4j_client: Neo4jClient,
        helius_client: HeliusClient,
        min_funding_sol: float = 0.1,
    ) -> None:
        self._neo4j = neo4j_client
        self._helius = helius_client
        self._queries = ClusterQueries(neo4j_client)
        self._min_funding = min_funding_sol

    async def analyze_wallet_funding(
        self, wallet_address: str, lookback_days: int = 90  # noqa: ARG002
    ) -> list[FundingEdge]:
        """
        Analyze incoming SOL transfers to detect funding sources.

        Args:
            wallet_address: The wallet to analyze
            lookback_days: How far back to look for funding

        Returns:
            List of funding edges detected
        """
        log.info("analyzing_wallet_funding", wallet=wallet_address[:16])

        # Get wallet transactions from Helius
        transactions = await self._helius.get_wallet_transactions(
            wallet=wallet_address,
            tx_types=[SOL_TRANSFER_TYPE],
            limit=100,
        )

        edges: list[FundingEdge] = []

        for tx in transactions:
            # Parse SOL transfers to this wallet
            funding_edge = self._parse_funding_transfer(tx, wallet_address)
            if funding_edge and funding_edge.amount_sol >= self._min_funding:
                # Store in Neo4j
                await self._queries.create_funding_edge(funding_edge)
                edges.append(funding_edge)

        log.info(
            "funding_analysis_complete",
            wallet=wallet_address[:16],
            edges_found=len(edges),
        )
        return edges

    def _parse_funding_transfer(
        self, tx: dict[str, Any], target_wallet: str
    ) -> FundingEdge | None:
        """Parse a transaction to extract funding information."""
        try:
            # Check native transfers (SOL)
            native_transfers = tx.get("nativeTransfers", [])
            for transfer in native_transfers:
                to_account = transfer.get("toUserAccount")
                from_account = transfer.get("fromUserAccount")
                amount_lamports = transfer.get("amount", 0)

                if to_account == target_wallet and from_account:
                    amount_sol = amount_lamports / LAMPORTS_PER_SOL

                    # Calculate strength based on amount
                    strength = min(1.0, amount_sol / 10.0)  # Cap at 10 SOL = 1.0

                    timestamp = tx.get("timestamp")
                    if isinstance(timestamp, int):
                        timestamp = datetime.fromtimestamp(timestamp)
                    elif isinstance(timestamp, str):
                        timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                    else:
                        timestamp = datetime.utcnow()

                    return FundingEdge(
                        source_wallet=from_account,
                        target_wallet=target_wallet,
                        amount_sol=amount_sol,
                        timestamp=timestamp,
                        tx_signature=tx.get("signature", ""),
                        strength=strength,
                    )
        except Exception as e:
            log.warning("parse_funding_error", error=str(e))

        return None

    async def get_funding_tree(
        self, wallet_address: str, max_depth: int = 3
    ) -> FundingTree:
        """
        Get the complete funding tree for a wallet.

        Args:
            wallet_address: Root wallet to analyze
            max_depth: Maximum depth to traverse

        Returns:
            FundingTree with all upstream funding sources
        """
        return await self._queries.get_funding_tree(wallet_address, max_depth)

    async def find_common_funding_sources(
        self, wallet_addresses: list[str], max_depth: int = 3
    ) -> list[CommonAncestor]:
        """
        Find common funding ancestors between wallets.

        Args:
            wallet_addresses: Wallets to compare
            max_depth: Maximum depth to search

        Returns:
            List of common ancestors with funding details
        """
        return await self._queries.find_common_ancestors(wallet_addresses, max_depth)

    async def analyze_batch(
        self, wallet_addresses: list[str], lookback_days: int = 90
    ) -> dict[str, list[FundingEdge]]:
        """
        Analyze funding for multiple wallets.

        Args:
            wallet_addresses: Wallets to analyze
            lookback_days: How far back to look

        Returns:
            Dict mapping wallet address to funding edges
        """
        results: dict[str, list[FundingEdge]] = {}

        for address in wallet_addresses:
            try:
                edges = await self.analyze_wallet_funding(address, lookback_days)
                results[address] = edges
            except Exception as e:
                log.warning("batch_analyze_error", wallet=address[:16], error=str(e))
                results[address] = []

        return results

    async def calculate_funding_strength(
        self, source_wallet: str, target_wallet: str
    ) -> float:
        """
        Calculate the funding relationship strength between two wallets.

        Returns a value between 0 and 1.
        """
        edges = await self._queries.get_funding_sources(target_wallet, min_amount=0.0)

        for edge in edges:
            if edge.source_wallet == source_wallet:
                return edge.strength

        return 0.0
