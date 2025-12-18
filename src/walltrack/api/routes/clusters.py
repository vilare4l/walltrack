"""Cluster API routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from walltrack.api.dependencies import (
    get_cluster_grouper,
    get_cluster_signal_amplifier,
    get_cooccurrence_analyzer,
    get_funding_analyzer,
    get_leader_detector,
    get_sync_detector,
)
from walltrack.core.cluster.cooccurrence import CoOccurrenceAnalyzer
from walltrack.core.cluster.funding_analyzer import FundingAnalyzer
from walltrack.core.cluster.grouping import ClusterGrouper
from walltrack.core.cluster.leader_detection import LeaderDetector
from walltrack.core.cluster.signal_amplifier import SignalAmplifier
from walltrack.core.cluster.sync_detector import SyncBuyDetector
from walltrack.data.models.cluster import (
    Cluster,
    ClusterSignal,
    CommonAncestor,
    CoOccurrenceEdge,
    FundingEdge,
    FundingTree,
    SyncBuyEdge,
)

router = APIRouter(prefix="/clusters", tags=["clusters"])


# Request/Response Models
class AnalyzeFundingRequest(BaseModel):
    """Request to analyze wallet funding."""

    wallet_addresses: list[str] = Field(..., min_length=1, max_length=50)
    lookback_days: int = Field(default=90, ge=7, le=365)


class AnalyzeSyncBuysRequest(BaseModel):
    """Request to analyze synchronized buying."""

    token_mint: str
    wallet_addresses: list[str] = Field(..., min_length=2, max_length=100)


class AnalyzeCoOccurrenceRequest(BaseModel):
    """Request to analyze co-occurrence patterns."""

    token_mint: str | None = None


class FindCommonAncestorsRequest(BaseModel):
    """Request to find common funding sources."""

    wallet_addresses: list[str] = Field(..., min_length=2, max_length=20)
    max_depth: int = Field(default=3, ge=1, le=5)


class AmplifySignalRequest(BaseModel):
    """Request to amplify a trading signal."""

    wallet_address: str
    token_mint: str
    base_signal: float = Field(..., ge=0.0, le=1.0)


class ClusterListResponse(BaseModel):
    """Response for cluster list."""

    clusters: list[Cluster]
    total: int


class FundingAnalysisResponse(BaseModel):
    """Response for funding analysis."""

    edges: list[FundingEdge]
    total_wallets: int
    total_edges: int


class SyncAnalysisResponse(BaseModel):
    """Response for sync buy analysis."""

    edges: list[SyncBuyEdge]
    token_mint: str
    wallet_count: int


class CoOccurrenceResponse(BaseModel):
    """Response for co-occurrence analysis."""

    edges: list[CoOccurrenceEdge]
    total_wallets: int


# Routes
@router.get("", response_model=ClusterListResponse)
async def list_clusters(
    grouper: Annotated[ClusterGrouper, Depends(get_cluster_grouper)],
    min_size: Annotated[int, Query(ge=2)] = 3,
    min_cohesion: Annotated[float, Query(ge=0.0, le=1.0)] = 0.0,
) -> ClusterListResponse:
    """List all detected clusters."""
    clusters = await grouper._queries.get_all_clusters()

    # Filter by criteria
    filtered = [
        c for c in clusters
        if c.size >= min_size and c.cohesion_score >= min_cohesion
    ]

    return ClusterListResponse(
        clusters=filtered,
        total=len(filtered),
    )


@router.get("/{cluster_id}", response_model=Cluster)
async def get_cluster(
    cluster_id: str,
    grouper: Annotated[ClusterGrouper, Depends(get_cluster_grouper)],
) -> Cluster:
    """Get cluster by ID."""
    cluster = await grouper._queries.get_cluster(cluster_id)
    if not cluster:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cluster {cluster_id} not found",
        )
    return cluster


@router.post("/find", response_model=ClusterListResponse)
async def find_clusters(
    grouper: Annotated[ClusterGrouper, Depends(get_cluster_grouper)],
) -> ClusterListResponse:
    """Find and create clusters from existing graph relationships."""
    clusters = await grouper.find_clusters()
    return ClusterListResponse(
        clusters=clusters,
        total=len(clusters),
    )


@router.post("/{cluster_id}/expand")
async def expand_cluster(
    cluster_id: str,
    grouper: Annotated[ClusterGrouper, Depends(get_cluster_grouper)],
    max_new_members: Annotated[int, Query(ge=1, le=50)] = 10,
) -> dict[str, list[str]]:
    """Expand a cluster by finding connected wallets."""
    added = await grouper.expand_cluster(cluster_id, max_new_members)
    return {"added_wallets": added}


@router.post("/{cluster_id}/detect-leader")
async def detect_cluster_leader(
    cluster_id: str,
    detector: Annotated[LeaderDetector, Depends(get_leader_detector)],
) -> dict[str, str | None]:
    """Detect the leader of a cluster."""
    leader = await detector.detect_cluster_leader(cluster_id)
    return {"leader_address": leader}


@router.get("/{cluster_id}/rankings")
async def get_member_rankings(
    cluster_id: str,
    detector: Annotated[LeaderDetector, Depends(get_leader_detector)],
) -> list[dict[str, float | str]]:
    """Get leadership rankings for all cluster members."""
    rankings = await detector.rank_cluster_members(cluster_id)
    return [{"address": addr, "score": score} for addr, score in rankings]


@router.delete("/{cluster_id}")
async def delete_cluster(
    cluster_id: str,
    grouper: Annotated[ClusterGrouper, Depends(get_cluster_grouper)],
) -> dict[str, str]:
    """Delete a cluster."""
    await grouper._delete_cluster(cluster_id)
    return {"message": f"Cluster {cluster_id} deleted"}


# Funding Analysis Routes
@router.post("/analysis/funding", response_model=FundingAnalysisResponse)
async def analyze_funding(
    request: AnalyzeFundingRequest,
    analyzer: Annotated[FundingAnalyzer, Depends(get_funding_analyzer)],
) -> FundingAnalysisResponse:
    """Analyze funding relationships for wallets."""
    all_edges: list[FundingEdge] = []
    for address in request.wallet_addresses:
        edges = await analyzer.analyze_wallet_funding(
            address, request.lookback_days
        )
        all_edges.extend(edges)

    return FundingAnalysisResponse(
        edges=all_edges,
        total_wallets=len(request.wallet_addresses),
        total_edges=len(all_edges),
    )


@router.get("/analysis/funding/{address}/tree", response_model=FundingTree)
async def get_funding_tree(
    address: str,
    analyzer: Annotated[FundingAnalyzer, Depends(get_funding_analyzer)],
    max_depth: Annotated[int, Query(ge=1, le=5)] = 3,
) -> FundingTree:
    """Get funding tree for a wallet."""
    return await analyzer.get_funding_tree(address, max_depth)


@router.post("/analysis/funding/common-ancestors", response_model=list[CommonAncestor])
async def find_common_ancestors(
    request: FindCommonAncestorsRequest,
    analyzer: Annotated[FundingAnalyzer, Depends(get_funding_analyzer)],
) -> list[CommonAncestor]:
    """Find common funding sources between wallets."""
    return await analyzer.find_common_funding_sources(
        request.wallet_addresses, request.max_depth
    )


# Sync Buy Analysis Routes
@router.post("/analysis/sync-buys", response_model=SyncAnalysisResponse)
async def analyze_sync_buys(
    request: AnalyzeSyncBuysRequest,
    detector: Annotated[SyncBuyDetector, Depends(get_sync_detector)],
) -> SyncAnalysisResponse:
    """Analyze synchronized buying patterns."""
    edges = await detector.detect_sync_buys_for_token(
        request.token_mint, request.wallet_addresses
    )
    return SyncAnalysisResponse(
        edges=edges,
        token_mint=request.token_mint,
        wallet_count=len(request.wallet_addresses),
    )


@router.get("/analysis/sync-buys/{address}")
async def get_sync_partners(
    address: str,
    detector: Annotated[SyncBuyDetector, Depends(get_sync_detector)],
    min_occurrences: Annotated[int, Query(ge=1)] = 2,
) -> list[SyncBuyEdge]:
    """Get wallets that buy in sync with the given wallet."""
    return await detector.get_sync_partners(address, min_occurrences)


# Co-occurrence Analysis Routes
@router.post("/analysis/cooccurrence", response_model=CoOccurrenceResponse)
async def analyze_cooccurrence(
    request: AnalyzeCoOccurrenceRequest,
    analyzer: Annotated[CoOccurrenceAnalyzer, Depends(get_cooccurrence_analyzer)],
) -> CoOccurrenceResponse:
    """Analyze co-occurrence patterns among wallets."""
    if request.token_mint:
        edges = await analyzer.analyze_for_token(request.token_mint)
    else:
        edges = await analyzer.analyze_cooccurrences()

    return CoOccurrenceResponse(
        edges=edges,
        total_wallets=len({e.wallet_a for e in edges} | {e.wallet_b for e in edges}),
    )


@router.get("/analysis/cooccurrence/{address}")
async def get_cooccurring_wallets(
    address: str,
    analyzer: Annotated[CoOccurrenceAnalyzer, Depends(get_cooccurrence_analyzer)],
    min_similarity: Annotated[float, Query(ge=0.0, le=1.0)] = 0.2,
) -> list[CoOccurrenceEdge]:
    """Get wallets that co-occur with the given wallet."""
    return await analyzer.get_cooccurring_wallets(address, min_similarity)


@router.get("/analysis/cooccurrence/highly-correlated")
async def get_highly_correlated_pairs(
    analyzer: Annotated[CoOccurrenceAnalyzer, Depends(get_cooccurrence_analyzer)],
    min_jaccard: Annotated[float, Query(ge=0.0, le=1.0)] = 0.5,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[CoOccurrenceEdge]:
    """Get highly correlated wallet pairs."""
    return await analyzer.find_highly_correlated_pairs(min_jaccard, limit)


# Signal Amplification Routes
@router.post("/signals/amplify", response_model=ClusterSignal)
async def amplify_signal(
    request: AmplifySignalRequest,
    amplifier: Annotated[SignalAmplifier, Depends(get_cluster_signal_amplifier)],
) -> ClusterSignal:
    """Get amplified signal for a wallet's activity."""
    return await amplifier.get_amplified_signal(
        request.wallet_address,
        request.token_mint,
        request.base_signal,
    )


@router.get("/signals/convergence/{token_mint}")
async def detect_convergence(
    token_mint: str,
    amplifier: Annotated[SignalAmplifier, Depends(get_cluster_signal_amplifier)],
    min_cluster_wallets: Annotated[int, Query(ge=2)] = 3,
) -> list[ClusterSignal]:
    """Detect cluster convergence on a token."""
    return await amplifier.detect_cluster_convergence(token_mint, min_cluster_wallets)


@router.post("/signals/update-multipliers")
async def update_multipliers(
    amplifier: Annotated[SignalAmplifier, Depends(get_cluster_signal_amplifier)],
) -> dict[str, float]:
    """Update signal multipliers for all clusters."""
    return await amplifier.update_cluster_multipliers()


# Wallet cluster lookup
@router.get("/wallet/{address}")
async def get_wallet_clusters(
    address: str,
    grouper: Annotated[ClusterGrouper, Depends(get_cluster_grouper)],
) -> list[Cluster]:
    """Get all clusters a wallet belongs to."""
    return await grouper.get_wallet_clusters(address)
