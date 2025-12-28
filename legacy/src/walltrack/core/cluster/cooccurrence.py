"""Co-occurrence analyzer - finds wallets appearing on same token launches."""

from collections import defaultdict

import structlog

from walltrack.data.models.cluster import CoOccurrenceEdge
from walltrack.data.models.wallet import Wallet
from walltrack.data.neo4j.client import Neo4jClient
from walltrack.data.neo4j.queries.cluster import ClusterQueries
from walltrack.data.supabase.repositories.wallet_repo import WalletRepository

log = structlog.get_logger()


class CoOccurrenceAnalyzer:
    """Analyzes co-occurrence patterns between wallets on token launches."""

    def __init__(
        self,
        neo4j_client: Neo4jClient,
        wallet_repo: WalletRepository,
        min_cooccurrences: int = 2,
        min_jaccard: float = 0.2,
    ) -> None:
        self._neo4j = neo4j_client
        self._wallet_repo = wallet_repo
        self._queries = ClusterQueries(neo4j_client)
        self._min_cooccurrences = min_cooccurrences
        self._min_jaccard = min_jaccard

    async def analyze_cooccurrences(
        self, wallets: list[Wallet] | None = None
    ) -> list[CoOccurrenceEdge]:
        """
        Analyze co-occurrence patterns among wallets.

        Uses the discovery_tokens field to find wallets that
        appear together on the same token launches.

        Args:
            wallets: Wallets to analyze (fetches all active if None)

        Returns:
            List of CO_OCCURS edges detected
        """
        if wallets is None:
            wallets = await self._wallet_repo.get_active_wallets(limit=500)

        log.info("analyzing_cooccurrences", wallet_count=len(wallets))

        # Build token -> wallets mapping
        token_wallets: dict[str, set[str]] = defaultdict(set)
        wallet_tokens: dict[str, set[str]] = {}

        for wallet in wallets:
            tokens = set(wallet.discovery_tokens or [])
            wallet_tokens[wallet.address] = tokens
            for token in tokens:
                token_wallets[token].add(wallet.address)

        # Find co-occurring wallet pairs
        edges: list[CoOccurrenceEdge] = []
        wallet_list = list(wallet_tokens.keys())

        for i, wallet_a in enumerate(wallet_list):
            tokens_a = wallet_tokens[wallet_a]
            if not tokens_a:
                continue

            for wallet_b in wallet_list[i + 1:]:
                tokens_b = wallet_tokens[wallet_b]
                if not tokens_b:
                    continue

                # Calculate Jaccard similarity
                shared = tokens_a & tokens_b
                union = tokens_a | tokens_b

                if len(shared) >= self._min_cooccurrences:
                    jaccard = len(shared) / len(union) if union else 0.0

                    if jaccard >= self._min_jaccard:
                        edge = CoOccurrenceEdge(
                            wallet_a=wallet_a,
                            wallet_b=wallet_b,
                            shared_tokens=list(shared),
                            occurrence_count=len(shared),
                            jaccard_similarity=jaccard,
                        )
                        await self._queries.create_cooccurrence_edge(edge)
                        edges.append(edge)

        log.info("cooccurrence_analysis_complete", edges_found=len(edges))
        return edges

    async def analyze_for_token(self, token_mint: str) -> list[CoOccurrenceEdge]:
        """
        Analyze co-occurrences for wallets discovered from a specific token.

        Args:
            token_mint: The token to analyze

        Returns:
            List of CO_OCCURS edges for wallets from this token
        """
        # Get wallets discovered from this token
        all_wallets = await self._wallet_repo.get_active_wallets(limit=1000)
        token_wallets = [
            w for w in all_wallets
            if token_mint in (w.discovery_tokens or [])
        ]

        if len(token_wallets) < 2:
            return []

        return await self.analyze_cooccurrences(token_wallets)

    async def get_cooccurring_wallets(
        self, wallet_address: str, min_similarity: float | None = None
    ) -> list[CoOccurrenceEdge]:
        """Get wallets that co-occur with the given wallet."""
        min_sim = min_similarity if min_similarity is not None else self._min_jaccard
        return await self._queries.get_cooccurring_wallets(wallet_address, min_sim)

    def calculate_jaccard_similarity(
        self, tokens_a: set[str], tokens_b: set[str]
    ) -> float:
        """Calculate Jaccard similarity between two token sets."""
        if not tokens_a or not tokens_b:
            return 0.0

        intersection = len(tokens_a & tokens_b)
        union = len(tokens_a | tokens_b)

        return intersection / union if union > 0 else 0.0

    async def find_highly_correlated_pairs(
        self, min_jaccard: float = 0.5, limit: int = 100
    ) -> list[CoOccurrenceEdge]:
        """Find wallet pairs with high co-occurrence correlation."""
        # Query Neo4j for high-correlation pairs
        query = """
        MATCH (a:Wallet)-[r:CO_OCCURS]-(b:Wallet)
        WHERE r.jaccard_similarity >= $min_jaccard
        AND a.address < b.address
        RETURN a.address as wallet_a,
               b.address as wallet_b,
               r.shared_tokens as tokens,
               r.occurrence_count as count,
               r.jaccard_similarity as jaccard
        ORDER BY r.jaccard_similarity DESC
        LIMIT $limit
        """
        results = await self._neo4j.execute_query(
            query, {"min_jaccard": min_jaccard, "limit": limit}
        )

        return [
            CoOccurrenceEdge(
                wallet_a=r["wallet_a"],
                wallet_b=r["wallet_b"],
                shared_tokens=r.get("tokens") or [],
                occurrence_count=r.get("count") or 0,
                jaccard_similarity=r.get("jaccard") or 0.0,
            )
            for r in results
        ]
