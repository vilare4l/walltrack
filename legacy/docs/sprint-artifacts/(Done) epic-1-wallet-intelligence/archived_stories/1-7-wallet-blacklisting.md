# Story 1.7: Wallet Blacklisting

## Story Info
- **Epic**: Epic 1 - Wallet Intelligence & Discovery
- **Status**: completed
- **Priority**: Medium
- **FR**: FR6
- **Completed**: 2024-12-17

## User Story

**As an** operator,
**I want** to manually blacklist wallets,
**So that** they are excluded from all signals and analysis.

## Acceptance Criteria

### AC 1: Add to Blacklist
**Given** a wallet address
**When** operator adds to blacklist via dashboard or API
**Then** wallet status is set to "blacklisted"
**And** blacklist timestamp and reason are recorded
**And** wallet is excluded from signal processing

### AC 2: Signal Blocking
**Given** a blacklisted wallet
**When** a signal is received from this wallet
**Then** signal is logged but not scored
**And** signal is marked as "blocked_blacklisted"

### AC 3: Remove from Blacklist
**Given** a blacklisted wallet
**When** operator removes from blacklist
**Then** wallet status returns to previous state
**And** wallet resumes normal signal processing

## Technical Specifications

### Blacklist Service

**src/walltrack/core/blacklist_service.py:**
```python
"""Wallet blacklist management service."""

from datetime import datetime
from typing import Any

import structlog

from walltrack.data.models.wallet import Wallet, WalletStatus
from walltrack.data.supabase.repositories.wallet_repo import WalletRepository

log = structlog.get_logger()


class BlacklistService:
    """Service for managing wallet blacklisting."""

    def __init__(self, wallet_repo: WalletRepository) -> None:
        self.wallet_repo = wallet_repo

    async def add_to_blacklist(
        self,
        address: str,
        reason: str,
        operator_id: str | None = None,
    ) -> Wallet:
        """
        Add a wallet to the blacklist.

        Args:
            address: Wallet address to blacklist
            reason: Reason for blacklisting
            operator_id: Optional ID of operator who blacklisted

        Returns:
            Updated Wallet

        Raises:
            ValueError: If wallet not found
        """
        wallet = await self.wallet_repo.get_by_address(address)
        if not wallet:
            raise ValueError(f"Wallet {address} not found")

        if wallet.status == WalletStatus.BLACKLISTED:
            log.info("wallet_already_blacklisted", address=address)
            return wallet

        # Store previous status for potential restoration
        previous_status = wallet.status.value

        wallet.status = WalletStatus.BLACKLISTED
        wallet.blacklisted_at = datetime.utcnow()
        wallet.blacklist_reason = reason

        await self.wallet_repo.update(wallet)

        log.warning(
            "wallet_blacklisted",
            address=address,
            reason=reason,
            previous_status=previous_status,
            operator=operator_id,
        )

        return wallet

    async def remove_from_blacklist(
        self,
        address: str,
        operator_id: str | None = None,
    ) -> Wallet:
        """
        Remove a wallet from the blacklist.

        Args:
            address: Wallet address to unblacklist
            operator_id: Optional ID of operator who removed blacklist

        Returns:
            Updated Wallet

        Raises:
            ValueError: If wallet not found or not blacklisted
        """
        wallet = await self.wallet_repo.get_by_address(address)
        if not wallet:
            raise ValueError(f"Wallet {address} not found")

        if wallet.status != WalletStatus.BLACKLISTED:
            raise ValueError(f"Wallet {address} is not blacklisted")

        blacklist_reason = wallet.blacklist_reason
        blacklisted_at = wallet.blacklisted_at

        # Restore to active status (will need re-evaluation)
        wallet.status = WalletStatus.ACTIVE
        wallet.blacklisted_at = None
        wallet.blacklist_reason = None

        await self.wallet_repo.update(wallet)

        log.info(
            "wallet_unblacklisted",
            address=address,
            previous_reason=blacklist_reason,
            blacklisted_duration=(datetime.utcnow() - blacklisted_at).total_seconds() if blacklisted_at else None,
            operator=operator_id,
        )

        return wallet

    async def is_blacklisted(self, address: str) -> bool:
        """
        Check if a wallet is blacklisted.

        Args:
            address: Wallet address to check

        Returns:
            True if blacklisted, False otherwise
        """
        wallet = await self.wallet_repo.get_by_address(address)
        return wallet is not None and wallet.status == WalletStatus.BLACKLISTED

    async def get_blacklisted_wallets(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Wallet]:
        """Get all blacklisted wallets."""
        return await self.wallet_repo.get_by_status(
            WalletStatus.BLACKLISTED,
            limit=limit,
        )

    async def check_and_block_signal(
        self,
        wallet_address: str,
    ) -> tuple[bool, str | None]:
        """
        Check if signal should be blocked due to blacklist.

        Args:
            wallet_address: Source wallet of the signal

        Returns:
            Tuple of (is_blocked, block_reason)
        """
        if await self.is_blacklisted(wallet_address):
            return True, "blocked_blacklisted"
        return False, None
```

### Blacklist History Table

**src/walltrack/data/supabase/migrations/004_blacklist_history.sql:**
```sql
-- Blacklist history table for audit trail
CREATE TABLE IF NOT EXISTS blacklist_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    wallet_address VARCHAR(44) NOT NULL REFERENCES wallets(address),
    action VARCHAR(20) NOT NULL,  -- 'blacklisted' or 'unblacklisted'
    reason TEXT,
    operator_id VARCHAR(100),
    previous_status VARCHAR(20),
    created_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT valid_action CHECK (action IN ('blacklisted', 'unblacklisted'))
);

-- Index for querying by wallet
CREATE INDEX IF NOT EXISTS idx_blacklist_history_wallet ON blacklist_history(wallet_address);
CREATE INDEX IF NOT EXISTS idx_blacklist_history_created ON blacklist_history(created_at DESC);

-- RLS policies
ALTER TABLE blacklist_history ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow read access" ON blacklist_history FOR SELECT USING (true);
CREATE POLICY "Allow insert" ON blacklist_history FOR INSERT WITH CHECK (true);
```

### Blacklist History Repository

**src/walltrack/data/supabase/repositories/blacklist_history_repo.py:**
```python
"""Repository for blacklist history."""

from datetime import datetime
from typing import Any

import structlog
from supabase import AsyncClient

log = structlog.get_logger()


class BlacklistHistoryRepository:
    """Repository for blacklist history records."""

    def __init__(self, client: AsyncClient) -> None:
        self.client = client
        self.table = "blacklist_history"

    async def record_blacklist(
        self,
        wallet_address: str,
        reason: str,
        previous_status: str,
        operator_id: str | None = None,
    ) -> str:
        """Record a blacklist action."""
        data = {
            "wallet_address": wallet_address,
            "action": "blacklisted",
            "reason": reason,
            "previous_status": previous_status,
            "operator_id": operator_id,
        }

        response = await self.client.table(self.table).insert(data).execute()
        return response.data[0]["id"]

    async def record_unblacklist(
        self,
        wallet_address: str,
        operator_id: str | None = None,
    ) -> str:
        """Record an unblacklist action."""
        data = {
            "wallet_address": wallet_address,
            "action": "unblacklisted",
            "operator_id": operator_id,
        }

        response = await self.client.table(self.table).insert(data).execute()
        return response.data[0]["id"]

    async def get_wallet_history(
        self,
        wallet_address: str,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Get blacklist history for a wallet."""
        response = await (
            self.client.table(self.table)
            .select("*")
            .eq("wallet_address", wallet_address)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return response.data

    async def get_recent_actions(
        self,
        action: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get recent blacklist actions."""
        query = self.client.table(self.table).select("*")

        if action:
            query = query.eq("action", action)

        response = await (
            query
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return response.data
```

### Blacklist API Endpoints

**src/walltrack/api/routes/blacklist.py:**
```python
"""Blacklist management API routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from walltrack.api.dependencies import (
    get_blacklist_service,
    get_blacklist_history_repo,
)
from walltrack.core.blacklist_service import BlacklistService
from walltrack.data.models.wallet import Wallet
from walltrack.data.supabase.repositories.blacklist_history_repo import (
    BlacklistHistoryRepository,
)

router = APIRouter(prefix="/blacklist", tags=["blacklist"])


class BlacklistRequest(BaseModel):
    """Request to blacklist a wallet."""

    address: str = Field(..., min_length=32, max_length=44)
    reason: str = Field(..., min_length=1, max_length=500)


class UnblacklistRequest(BaseModel):
    """Request to remove wallet from blacklist."""

    address: str = Field(..., min_length=32, max_length=44)


class BlacklistResponse(BaseModel):
    """Response from blacklist operation."""

    success: bool
    wallet: Wallet
    message: str


class BlacklistHistoryEntry(BaseModel):
    """Blacklist history entry."""

    id: str
    wallet_address: str
    action: str
    reason: str | None
    operator_id: str | None
    previous_status: str | None
    created_at: str


@router.post("/add", response_model=BlacklistResponse)
async def add_to_blacklist(
    request: BlacklistRequest,
    service: Annotated[BlacklistService, Depends(get_blacklist_service)],
    history_repo: Annotated[BlacklistHistoryRepository, Depends(get_blacklist_history_repo)],
) -> BlacklistResponse:
    """
    Add a wallet to the blacklist.

    Blacklisted wallets are excluded from all signal processing.
    """
    try:
        wallet = await service.add_to_blacklist(
            address=request.address,
            reason=request.reason,
        )

        # Record in history
        await history_repo.record_blacklist(
            wallet_address=request.address,
            reason=request.reason,
            previous_status="active",  # Simplified
        )

        return BlacklistResponse(
            success=True,
            wallet=wallet,
            message=f"Wallet {request.address} has been blacklisted",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.post("/remove", response_model=BlacklistResponse)
async def remove_from_blacklist(
    request: UnblacklistRequest,
    service: Annotated[BlacklistService, Depends(get_blacklist_service)],
    history_repo: Annotated[BlacklistHistoryRepository, Depends(get_blacklist_history_repo)],
) -> BlacklistResponse:
    """
    Remove a wallet from the blacklist.

    Wallet will resume normal signal processing.
    """
    try:
        wallet = await service.remove_from_blacklist(address=request.address)

        # Record in history
        await history_repo.record_unblacklist(wallet_address=request.address)

        return BlacklistResponse(
            success=True,
            wallet=wallet,
            message=f"Wallet {request.address} has been removed from blacklist",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/check/{address}")
async def check_blacklist_status(
    address: str,
    service: Annotated[BlacklistService, Depends(get_blacklist_service)],
) -> dict:
    """Check if a wallet is blacklisted."""
    is_blacklisted = await service.is_blacklisted(address)
    return {
        "address": address,
        "is_blacklisted": is_blacklisted,
    }


@router.get("/list", response_model=list[Wallet])
async def list_blacklisted_wallets(
    service: Annotated[BlacklistService, Depends(get_blacklist_service)],
    limit: int = Query(default=50, ge=1, le=200),
) -> list[Wallet]:
    """Get all blacklisted wallets."""
    return await service.get_blacklisted_wallets(limit=limit)


@router.get("/history", response_model=list[BlacklistHistoryEntry])
async def get_blacklist_history(
    history_repo: Annotated[BlacklistHistoryRepository, Depends(get_blacklist_history_repo)],
    action: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[BlacklistHistoryEntry]:
    """Get recent blacklist actions."""
    history = await history_repo.get_recent_actions(action=action, limit=limit)
    return [BlacklistHistoryEntry(**h) for h in history]


@router.get("/history/{address}", response_model=list[BlacklistHistoryEntry])
async def get_wallet_blacklist_history(
    address: str,
    history_repo: Annotated[BlacklistHistoryRepository, Depends(get_blacklist_history_repo)],
    limit: int = Query(default=20, ge=1, le=100),
) -> list[BlacklistHistoryEntry]:
    """Get blacklist history for a specific wallet."""
    history = await history_repo.get_wallet_history(wallet_address=address, limit=limit)
    return [BlacklistHistoryEntry(**h) for h in history]
```

### Add to Wallet API

**Update src/walltrack/api/routes/wallets.py:**
```python
# Add these endpoints to existing wallets router

from walltrack.core.blacklist_service import BlacklistService
from walltrack.api.dependencies import get_blacklist_service


@router.post("/{address}/blacklist", response_model=Wallet)
async def blacklist_wallet(
    address: str,
    reason: str = Query(..., min_length=1),
    service: Annotated[BlacklistService, Depends(get_blacklist_service)],
) -> Wallet:
    """Blacklist a specific wallet."""
    try:
        return await service.add_to_blacklist(address=address, reason=reason)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.delete("/{address}/blacklist", response_model=Wallet)
async def unblacklist_wallet(
    address: str,
    service: Annotated[BlacklistService, Depends(get_blacklist_service)],
) -> Wallet:
    """Remove wallet from blacklist."""
    try:
        return await service.remove_from_blacklist(address=address)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
```

### Signal Processing Integration

**src/walltrack/core/signal_filter.py:**
```python
"""Signal filtering including blacklist checks."""

from typing import Any

import structlog

from walltrack.core.blacklist_service import BlacklistService
from walltrack.data.models.signal import Signal, SignalStatus

log = structlog.get_logger()


class SignalFilter:
    """Filters signals based on various criteria including blacklist."""

    def __init__(self, blacklist_service: BlacklistService) -> None:
        self.blacklist = blacklist_service

    async def filter_signal(
        self,
        signal: Signal,
    ) -> tuple[Signal, bool]:
        """
        Filter a signal and determine if it should be processed.

        Args:
            signal: Signal to filter

        Returns:
            Tuple of (possibly modified signal, should_process)
        """
        # Check blacklist
        is_blocked, block_reason = await self.blacklist.check_and_block_signal(
            signal.wallet_address
        )

        if is_blocked:
            signal.status = SignalStatus.BLOCKED
            signal.block_reason = block_reason

            log.info(
                "signal_blocked_blacklist",
                wallet=signal.wallet_address,
                token=signal.token_mint,
            )

            return signal, False

        return signal, True

    async def filter_batch(
        self,
        signals: list[Signal],
    ) -> tuple[list[Signal], list[Signal]]:
        """
        Filter a batch of signals.

        Args:
            signals: List of signals to filter

        Returns:
            Tuple of (signals_to_process, blocked_signals)
        """
        to_process: list[Signal] = []
        blocked: list[Signal] = []

        for signal in signals:
            filtered_signal, should_process = await self.filter_signal(signal)

            if should_process:
                to_process.append(filtered_signal)
            else:
                blocked.append(filtered_signal)

        log.info(
            "signal_batch_filtered",
            total=len(signals),
            to_process=len(to_process),
            blocked=len(blocked),
        )

        return to_process, blocked
```

### Unit Tests

**tests/unit/core/test_blacklist_service.py:**
```python
"""Tests for blacklist service."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from walltrack.core.blacklist_service import BlacklistService
from walltrack.data.models.wallet import Wallet, WalletStatus


@pytest.fixture
def mock_wallet_repo() -> AsyncMock:
    """Mock wallet repository."""
    return AsyncMock()


@pytest.fixture
def service(mock_wallet_repo: AsyncMock) -> BlacklistService:
    """Create blacklist service with mocked repo."""
    return BlacklistService(wallet_repo=mock_wallet_repo)


class TestBlacklistService:
    """Tests for BlacklistService."""

    async def test_add_to_blacklist(
        self,
        service: BlacklistService,
        mock_wallet_repo: AsyncMock,
    ) -> None:
        """Test adding wallet to blacklist."""
        wallet = Wallet(address="test_wallet", status=WalletStatus.ACTIVE)
        mock_wallet_repo.get_by_address.return_value = wallet

        result = await service.add_to_blacklist(
            address="test_wallet",
            reason="Suspicious activity",
        )

        assert result.status == WalletStatus.BLACKLISTED
        assert result.blacklist_reason == "Suspicious activity"
        assert result.blacklisted_at is not None
        mock_wallet_repo.update.assert_called_once()

    async def test_add_to_blacklist_already_blacklisted(
        self,
        service: BlacklistService,
        mock_wallet_repo: AsyncMock,
    ) -> None:
        """Test adding already blacklisted wallet."""
        wallet = Wallet(
            address="test_wallet",
            status=WalletStatus.BLACKLISTED,
            blacklisted_at=datetime.utcnow(),
        )
        mock_wallet_repo.get_by_address.return_value = wallet

        result = await service.add_to_blacklist(
            address="test_wallet",
            reason="New reason",
        )

        # Should return existing blacklisted wallet without update
        assert result.status == WalletStatus.BLACKLISTED
        mock_wallet_repo.update.assert_not_called()

    async def test_add_to_blacklist_wallet_not_found(
        self,
        service: BlacklistService,
        mock_wallet_repo: AsyncMock,
    ) -> None:
        """Test blacklisting non-existent wallet."""
        mock_wallet_repo.get_by_address.return_value = None

        with pytest.raises(ValueError, match="not found"):
            await service.add_to_blacklist(
                address="nonexistent",
                reason="Test",
            )

    async def test_remove_from_blacklist(
        self,
        service: BlacklistService,
        mock_wallet_repo: AsyncMock,
    ) -> None:
        """Test removing wallet from blacklist."""
        wallet = Wallet(
            address="test_wallet",
            status=WalletStatus.BLACKLISTED,
            blacklisted_at=datetime.utcnow(),
            blacklist_reason="Test reason",
        )
        mock_wallet_repo.get_by_address.return_value = wallet

        result = await service.remove_from_blacklist(address="test_wallet")

        assert result.status == WalletStatus.ACTIVE
        assert result.blacklisted_at is None
        assert result.blacklist_reason is None
        mock_wallet_repo.update.assert_called_once()

    async def test_remove_from_blacklist_not_blacklisted(
        self,
        service: BlacklistService,
        mock_wallet_repo: AsyncMock,
    ) -> None:
        """Test removing non-blacklisted wallet."""
        wallet = Wallet(address="test_wallet", status=WalletStatus.ACTIVE)
        mock_wallet_repo.get_by_address.return_value = wallet

        with pytest.raises(ValueError, match="not blacklisted"):
            await service.remove_from_blacklist(address="test_wallet")

    async def test_is_blacklisted_true(
        self,
        service: BlacklistService,
        mock_wallet_repo: AsyncMock,
    ) -> None:
        """Test checking blacklisted wallet."""
        wallet = Wallet(address="test_wallet", status=WalletStatus.BLACKLISTED)
        mock_wallet_repo.get_by_address.return_value = wallet

        result = await service.is_blacklisted("test_wallet")

        assert result is True

    async def test_is_blacklisted_false(
        self,
        service: BlacklistService,
        mock_wallet_repo: AsyncMock,
    ) -> None:
        """Test checking non-blacklisted wallet."""
        wallet = Wallet(address="test_wallet", status=WalletStatus.ACTIVE)
        mock_wallet_repo.get_by_address.return_value = wallet

        result = await service.is_blacklisted("test_wallet")

        assert result is False

    async def test_is_blacklisted_not_found(
        self,
        service: BlacklistService,
        mock_wallet_repo: AsyncMock,
    ) -> None:
        """Test checking non-existent wallet."""
        mock_wallet_repo.get_by_address.return_value = None

        result = await service.is_blacklisted("nonexistent")

        assert result is False

    async def test_check_and_block_signal_blacklisted(
        self,
        service: BlacklistService,
        mock_wallet_repo: AsyncMock,
    ) -> None:
        """Test signal blocking for blacklisted wallet."""
        wallet = Wallet(address="test_wallet", status=WalletStatus.BLACKLISTED)
        mock_wallet_repo.get_by_address.return_value = wallet

        is_blocked, reason = await service.check_and_block_signal("test_wallet")

        assert is_blocked is True
        assert reason == "blocked_blacklisted"

    async def test_check_and_block_signal_not_blacklisted(
        self,
        service: BlacklistService,
        mock_wallet_repo: AsyncMock,
    ) -> None:
        """Test signal not blocked for active wallet."""
        wallet = Wallet(address="test_wallet", status=WalletStatus.ACTIVE)
        mock_wallet_repo.get_by_address.return_value = wallet

        is_blocked, reason = await service.check_and_block_signal("test_wallet")

        assert is_blocked is False
        assert reason is None
```

## Implementation Tasks

- [x] Create `src/walltrack/core/blacklist_service.py`
- [x] Create `src/walltrack/data/supabase/migrations/004_blacklist_history.sql`
- [x] Create `src/walltrack/data/supabase/repositories/blacklist_history_repo.py`
- [x] Create `src/walltrack/api/routes/blacklist.py`
- [x] Create `src/walltrack/core/signal_filter.py`
- [x] Update wallet routes with blacklist endpoints
- [x] Implement blacklist check in signal processing pipeline
- [x] Write unit tests
- [x] Write integration tests

## Definition of Done

- [x] Wallets can be blacklisted via API/dashboard
- [x] Blacklisted wallets excluded from signal processing
- [x] Signals from blacklisted wallets logged but not scored
- [x] Blacklist can be removed
- [x] Blacklist history is maintained
- [x] All unit tests pass
- [x] mypy and ruff pass

## Implementation Notes

### Files Created
- `src/walltrack/core/blacklist_service.py` - BlacklistService with add/remove/check operations
- `src/walltrack/data/supabase/repositories/blacklist_history_repo.py` - BlacklistHistoryRepository
- `src/walltrack/api/routes/blacklist.py` - Dedicated blacklist API routes
- `src/walltrack/api/routes/wallets.py` - Extended with `POST /wallets/{address}/blacklist` and `DELETE /wallets/{address}/blacklist`

### Tests
- `tests/unit/core/test_blacklist_service.py` - 16 tests for blacklist service
- Tests cover: add/remove blacklist, signal blocking, history tracking, validation

### Key Implementation Details
- BlacklistService methods: add_to_blacklist(), remove_from_blacklist(), is_blacklisted(), check_and_block_signal()
- History tracking with action types: "blacklisted", "unblacklisted"
- Previous status preserved in history for audit trail
- Operator ID tracking for accountability
- Signal blocking returns tuple (is_blocked, reason) for logging
