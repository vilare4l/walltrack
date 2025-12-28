"""FastAPI dependencies for dependency injection."""

from typing import Annotated

from fastapi import Depends

from walltrack.config.settings import Settings, get_settings
from walltrack.core.blacklist_service import BlacklistService
from walltrack.core.cluster.cooccurrence import CoOccurrenceAnalyzer
from walltrack.core.cluster.funding_analyzer import FundingAnalyzer
from walltrack.core.cluster.grouping import ClusterGrouper
from walltrack.core.cluster.leader_detection import LeaderDetector
from walltrack.core.cluster.signal_amplifier import SignalAmplifier
from walltrack.core.cluster.sync_detector import SyncBuyDetector
from walltrack.data.neo4j.client import Neo4jClient, get_neo4j_client
from walltrack.data.supabase.client import SupabaseClient, get_supabase_client
from walltrack.data.supabase.repositories.blacklist_history_repo import (
    BlacklistHistoryRepository,
)
from walltrack.data.supabase.repositories.decay_event_repo import DecayEventRepository
from walltrack.data.supabase.repositories.trade_repo import TradeRepository
from walltrack.data.supabase.repositories.wallet_repo import WalletRepository
from walltrack.discovery.decay_detector import DecayDetector
from walltrack.discovery.profiler import WalletProfiler
from walltrack.discovery.scanner import WalletDiscoveryScanner
from walltrack.services.helius.client import HeliusClient, get_helius_client

SettingsDep = Annotated[Settings, Depends(get_settings)]


async def get_wallet_repo() -> WalletRepository:
    """Get wallet repository dependency."""
    client = await get_supabase_client()
    return WalletRepository(client)


async def get_discovery_scanner() -> WalletDiscoveryScanner:
    """Get discovery scanner dependency."""
    supabase = await get_supabase_client()
    wallet_repo = WalletRepository(supabase)
    neo4j = await get_neo4j_client()
    helius = await get_helius_client()
    return WalletDiscoveryScanner(wallet_repo, neo4j, helius)


async def get_wallet_profiler() -> WalletProfiler:
    """Get wallet profiler dependency."""
    supabase = await get_supabase_client()
    wallet_repo = WalletRepository(supabase)
    helius = await get_helius_client()
    return WalletProfiler(wallet_repo, helius)


async def get_trade_repo() -> TradeRepository:
    """Get trade repository dependency."""
    client = await get_supabase_client()
    return TradeRepository(client)


async def get_decay_event_repo() -> DecayEventRepository:
    """Get decay event repository dependency."""
    client = await get_supabase_client()
    return DecayEventRepository(client)


async def get_decay_detector() -> DecayDetector:
    """Get decay detector dependency."""
    supabase = await get_supabase_client()
    wallet_repo = WalletRepository(supabase)
    trade_repo = TradeRepository(supabase)
    return DecayDetector(wallet_repo, trade_repo)


async def get_blacklist_service() -> BlacklistService:
    """Get blacklist service dependency."""
    supabase = await get_supabase_client()
    wallet_repo = WalletRepository(supabase)
    return BlacklistService(wallet_repo)


async def get_blacklist_history_repo() -> BlacklistHistoryRepository:
    """Get blacklist history repository dependency."""
    client = await get_supabase_client()
    return BlacklistHistoryRepository(client)


WalletRepoDep = Annotated[WalletRepository, Depends(get_wallet_repo)]
TradeRepoDep = Annotated[TradeRepository, Depends(get_trade_repo)]
DecayEventRepoDep = Annotated[DecayEventRepository, Depends(get_decay_event_repo)]
DiscoveryScannerDep = Annotated[WalletDiscoveryScanner, Depends(get_discovery_scanner)]
WalletProfilerDep = Annotated[WalletProfiler, Depends(get_wallet_profiler)]
DecayDetectorDep = Annotated[DecayDetector, Depends(get_decay_detector)]
BlacklistServiceDep = Annotated[BlacklistService, Depends(get_blacklist_service)]
BlacklistHistoryRepoDep = Annotated[
    BlacklistHistoryRepository, Depends(get_blacklist_history_repo)
]
Neo4jDep = Annotated[Neo4jClient, Depends(get_neo4j_client)]
SupabaseDep = Annotated[SupabaseClient, Depends(get_supabase_client)]
HeliusDep = Annotated[HeliusClient, Depends(get_helius_client)]


# Cluster analysis dependencies
async def get_funding_analyzer() -> FundingAnalyzer:
    """Get funding analyzer dependency."""
    neo4j = await get_neo4j_client()
    helius = await get_helius_client()
    return FundingAnalyzer(neo4j, helius)


async def get_sync_detector() -> SyncBuyDetector:
    """Get sync buy detector dependency."""
    neo4j = await get_neo4j_client()
    helius = await get_helius_client()
    return SyncBuyDetector(neo4j, helius)


async def get_cooccurrence_analyzer() -> CoOccurrenceAnalyzer:
    """Get co-occurrence analyzer dependency."""
    neo4j = await get_neo4j_client()
    supabase = await get_supabase_client()
    wallet_repo = WalletRepository(supabase)
    return CoOccurrenceAnalyzer(neo4j, wallet_repo)


async def get_cluster_grouper() -> ClusterGrouper:
    """Get cluster grouper dependency."""
    neo4j = await get_neo4j_client()
    return ClusterGrouper(neo4j)


async def get_leader_detector() -> LeaderDetector:
    """Get leader detector dependency."""
    neo4j = await get_neo4j_client()
    supabase = await get_supabase_client()
    wallet_repo = WalletRepository(supabase)
    return LeaderDetector(neo4j, wallet_repo)


async def get_cluster_signal_amplifier() -> SignalAmplifier:
    """Get signal amplifier dependency."""
    neo4j = await get_neo4j_client()
    supabase = await get_supabase_client()
    wallet_repo = WalletRepository(supabase)
    return SignalAmplifier(neo4j, wallet_repo)


FundingAnalyzerDep = Annotated[FundingAnalyzer, Depends(get_funding_analyzer)]
SyncDetectorDep = Annotated[SyncBuyDetector, Depends(get_sync_detector)]
CoOccurrenceAnalyzerDep = Annotated[CoOccurrenceAnalyzer, Depends(get_cooccurrence_analyzer)]
ClusterGrouperDep = Annotated[ClusterGrouper, Depends(get_cluster_grouper)]
LeaderDetectorDep = Annotated[LeaderDetector, Depends(get_leader_detector)]
SignalAmplifierDep = Annotated[SignalAmplifier, Depends(get_cluster_signal_amplifier)]
