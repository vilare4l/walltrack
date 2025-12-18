"""Cluster and funding relationship models."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class RelationshipType(str, Enum):
    """Types of wallet relationships."""

    FUNDED_BY = "FUNDED_BY"
    BUYS_WITH = "BUYS_WITH"
    CO_OCCURS = "CO_OCCURS"
    MEMBER_OF = "MEMBER_OF"


class FundingEdge(BaseModel):
    """FUNDED_BY relationship between wallets."""

    source_wallet: str = Field(..., description="Wallet that sent funds")
    target_wallet: str = Field(..., description="Wallet that received funds")
    amount_sol: float = Field(..., ge=0, description="Amount transferred in SOL")
    timestamp: datetime = Field(..., description="When the transfer occurred")
    tx_signature: str = Field(..., description="Transaction signature")
    strength: float = Field(default=0.0, ge=0, le=1, description="Relationship strength")

    model_config = {"frozen": True}


class SyncBuyEdge(BaseModel):
    """BUYS_WITH relationship - synchronized buying pattern."""

    wallet_a: str = Field(..., description="First wallet")
    wallet_b: str = Field(..., description="Second wallet")
    token_mint: str = Field(..., description="Token they both bought")
    time_delta_seconds: int = Field(..., description="Time between purchases")
    correlation_score: float = Field(default=0.0, ge=0, le=1)
    occurrences: int = Field(default=1, ge=1)

    model_config = {"frozen": True}


class CoOccurrenceEdge(BaseModel):
    """CO_OCCURS relationship - wallets appearing on same token launches."""

    wallet_a: str = Field(..., description="First wallet")
    wallet_b: str = Field(..., description="Second wallet")
    shared_tokens: list[str] = Field(default_factory=list)
    occurrence_count: int = Field(default=1, ge=1)
    jaccard_similarity: float = Field(default=0.0, ge=0, le=1)

    model_config = {"frozen": True}


class FundingNode(BaseModel):
    """A wallet node in the funding tree."""

    address: str
    level: int = Field(..., ge=0, description="Depth in funding tree (0 = target)")
    total_funded: float = Field(default=0.0, description="Total SOL funded to target")
    funding_count: int = Field(default=1, description="Number of funding transactions")
    first_funding: datetime | None = None
    last_funding: datetime | None = None


class FundingTree(BaseModel):
    """Complete funding tree for a wallet."""

    root_wallet: str
    nodes: list[FundingNode] = Field(default_factory=list)
    edges: list[FundingEdge] = Field(default_factory=list)
    max_depth: int = Field(default=0, description="Maximum depth of tree")


class CommonAncestor(BaseModel):
    """Common funding ancestor between wallets."""

    ancestor_address: str
    wallets_funded: list[str] = Field(default_factory=list)
    total_descendants: int = Field(default=0)
    funding_strength: float = Field(default=0.0)


class ClusterMember(BaseModel):
    """A wallet that belongs to a cluster."""

    address: str = Field(default="", description="Wallet address")
    wallet_address: str = Field(default="", description="Alias for address")
    role: str = Field(default="member", description="leader, coordinator, or member")
    join_reason: str = Field(default="unknown", description="Why wallet joined cluster")
    influence_score: float = Field(default=0.0, ge=0, le=1)
    connection_count: int = Field(default=0, description="Number of connections")
    funding_received: float = Field(default=0.0, description="SOL received from cluster")
    sync_buy_count: int = Field(default=0, description="Synchronized buys with cluster")
    co_occurrence_count: int = Field(default=0, description="Token co-occurrences")

    def __init__(self, **data: object) -> None:
        """Initialize with address aliasing."""
        # Allow wallet_address as alias for address
        if "wallet_address" in data and "address" not in data:
            data["address"] = data["wallet_address"]
        elif "address" in data and "wallet_address" not in data:
            data["wallet_address"] = data["address"]
        super().__init__(**data)


class Cluster(BaseModel):
    """A group of related wallets."""

    id: str = Field(..., description="Unique cluster identifier")
    name: str | None = Field(default=None, description="Human-readable name")
    members: list[ClusterMember] = Field(default_factory=list)
    leader_address: str | None = Field(default=None)

    # Cluster metrics
    size: int = Field(default=0, ge=0)
    total_volume_sol: float = Field(default=0.0, ge=0)
    avg_member_score: float = Field(default=0.0, ge=0, le=1)
    cohesion_score: float = Field(default=0.0, ge=0, le=1, description="How tightly connected")

    # Activity
    active_members: int = Field(default=0)
    last_activity: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Signal amplification
    signal_multiplier: float = Field(default=1.0, ge=1.0, le=3.0)

    def get_leader(self) -> ClusterMember | None:
        """Get the cluster leader."""
        for member in self.members:
            if member.role == "leader":
                return member
        return None

    def get_member_addresses(self) -> list[str]:
        """Get all member wallet addresses."""
        return [m.address for m in self.members]


class ClusterSignal(BaseModel):
    """Signal from cluster activity."""

    wallet_address: str = Field(default="", description="Source wallet")
    token_mint: str = Field(default="", description="Token being traded")
    cluster_id: str | None = Field(default=None, description="Associated cluster")
    base_strength: float = Field(default=0.0, ge=0, le=1)
    amplified_strength: float = Field(default=0.0, ge=0, le=1)
    participating_wallets: list[str] = Field(default_factory=list)
    amplification_reason: str = Field(default="", description="Reason for amplification")
    # Legacy fields for backward compatibility
    participating_members: list[str] = Field(default_factory=list)
    participation_ratio: float = Field(default=0.0, ge=0, le=1)
    base_score: float = Field(default=0.0, ge=0, le=1)
    amplified_score: float = Field(default=0.0, ge=0, le=1)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
