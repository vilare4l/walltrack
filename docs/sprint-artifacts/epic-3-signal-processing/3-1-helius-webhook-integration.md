# Story 3.1: Helius Webhook Integration

## Story Info
- **Epic**: Epic 3 - Real-Time Signal Processing & Scoring
- **Status**: ready
- **Priority**: High
- **FR**: FR13

## User Story

**As an** operator,
**I want** the system to receive real-time swap notifications from Helius,
**So that** insider movements are detected instantly.

## Acceptance Criteria

### AC 1: Webhook Reception
**Given** Helius webhook is configured with system endpoint
**When** a monitored wallet executes a swap on Solana
**Then** Helius sends webhook notification to FastAPI endpoint
**And** webhook is received within seconds of on-chain confirmation

### AC 2: Signature Validation
**Given** an incoming webhook request
**When** the request is processed
**Then** HMAC signature is validated against Helius secret
**And** invalid signatures are rejected with 401
**And** rejection is logged with request metadata (no sensitive data)

### AC 3: Payload Processing
**Given** a valid webhook payload
**When** payload is parsed
**Then** transaction details are extracted (wallet, token, amount, direction, timestamp)
**And** payload is passed to signal processing pipeline
**And** processing time is < 500ms (NFR2)

### AC 4: Health Check
**Given** webhook endpoint
**When** health check is performed
**Then** endpoint responds with 200 OK
**And** Helius connectivity status is included

## Technical Notes

- Implement in `src/walltrack/api/routes/webhooks.py`
- FR13: Receive real-time swap notifications via Helius webhooks
- NFR8: Webhook validation via signature verification
- Use middleware for HMAC validation (`src/walltrack/api/middleware/hmac_validation.py`)

---

## Technical Specification

### 1. Domain Models

```python
# src/walltrack/core/models/webhook.py
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, field_validator


class TransactionType(str, Enum):
    """Type of transaction detected."""
    SWAP = "swap"
    TRANSFER = "transfer"
    UNKNOWN = "unknown"


class SwapDirection(str, Enum):
    """Direction of swap transaction."""
    BUY = "buy"
    SELL = "sell"


class HeliusWebhookPayload(BaseModel):
    """Raw Helius webhook payload structure."""

    webhook_id: str = Field(..., alias="webhookID")
    transaction_type: str = Field(..., alias="type")
    timestamp: int
    signature: str
    fee: int
    fee_payer: str = Field(..., alias="feePayer")
    slot: int
    native_transfers: list[dict] = Field(default_factory=list, alias="nativeTransfers")
    token_transfers: list[dict] = Field(default_factory=list, alias="tokenTransfers")
    account_data: list[dict] = Field(default_factory=list, alias="accountData")

    model_config = {"populate_by_name": True}


class TokenTransfer(BaseModel):
    """Parsed token transfer from Helius payload."""

    from_account: str = Field(..., alias="fromUserAccount")
    to_account: str = Field(..., alias="toUserAccount")
    mint: str
    amount: float = Field(..., alias="tokenAmount")

    model_config = {"populate_by_name": True}


class ParsedSwapEvent(BaseModel):
    """Parsed and validated swap event."""

    tx_signature: str
    wallet_address: str
    token_address: str
    direction: SwapDirection
    amount_token: float = Field(..., ge=0)
    amount_sol: float = Field(..., ge=0)
    timestamp: datetime
    slot: int
    fee_lamports: int = Field(..., ge=0)
    raw_payload: dict = Field(default_factory=dict)
    processing_started_at: datetime = Field(default_factory=datetime.utcnow)

    @field_validator("wallet_address", "token_address")
    @classmethod
    def validate_solana_address(cls, v: str) -> str:
        """Validate Solana base58 address format."""
        if not v or len(v) < 32 or len(v) > 44:
            raise ValueError(f"Invalid Solana address: {v}")
        return v


class WebhookValidationResult(BaseModel):
    """Result of webhook signature validation."""

    is_valid: bool
    error_message: str | None = None
    request_id: str | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class WebhookHealthStatus(BaseModel):
    """Health status for webhook endpoint."""

    status: str = "healthy"
    helius_connected: bool = True
    last_webhook_received: datetime | None = None
    webhooks_processed_24h: int = 0
    average_processing_ms: float = 0.0
```

### 2. Configuration Constants

```python
# src/walltrack/core/constants/webhook.py
from typing import Final

# HMAC validation
HELIUS_SIGNATURE_HEADER: Final[str] = "X-Helius-Signature"
HMAC_ALGORITHM: Final[str] = "sha256"

# Processing limits
MAX_PROCESSING_TIME_MS: Final[int] = 500  # NFR2
WEBHOOK_TIMEOUT_SECONDS: Final[int] = 30

# Known DEX program IDs for swap detection
KNOWN_DEX_PROGRAMS: Final[set[str]] = {
    "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4",   # Jupiter v6
    "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8",  # Raydium AMM
    "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc",   # Orca Whirlpool
    "9W959DqEETiGZocYWCQPaJ6sBmUzgfxXfqGeTEdp3aQP",  # Orca v1
    "CAMMCzo5YL8w4VFF8KVHrK22GGUsp5VTaW7grrKgrWqK",  # Raydium CLMM
}

# Token programs
SPL_TOKEN_PROGRAM: Final[str] = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
SPL_TOKEN_2022_PROGRAM: Final[str] = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"

# SOL mint address (wrapped SOL)
WRAPPED_SOL_MINT: Final[str] = "So11111111111111111111111111111111111111112"
```

### 3. HMAC Validation Middleware

```python
# src/walltrack/api/middleware/hmac_validation.py
import hashlib
import hmac
from datetime import datetime

import structlog
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from walltrack.core.config import settings
from walltrack.core.constants.webhook import (
    HELIUS_SIGNATURE_HEADER,
    HMAC_ALGORITHM,
)
from walltrack.core.models.webhook import WebhookValidationResult

logger = structlog.get_logger(__name__)


class HMACValidationMiddleware(BaseHTTPMiddleware):
    """Middleware to validate Helius webhook HMAC signatures."""

    async def dispatch(self, request: Request, call_next):
        # Only validate webhook endpoints
        if not request.url.path.startswith("/api/v1/webhooks"):
            return await call_next(request)

        # Skip validation for health check
        if request.url.path.endswith("/health"):
            return await call_next(request)

        validation_result = await self._validate_signature(request)

        if not validation_result.is_valid:
            logger.warning(
                "webhook_signature_invalid",
                path=request.url.path,
                client_ip=request.client.host if request.client else "unknown",
                error=validation_result.error_message,
            )
            raise HTTPException(
                status_code=401,
                detail="Invalid webhook signature",
            )

        # Store validation result for downstream use
        request.state.webhook_validation = validation_result
        return await call_next(request)

    async def _validate_signature(self, request: Request) -> WebhookValidationResult:
        """Validate HMAC signature from Helius."""
        signature = request.headers.get(HELIUS_SIGNATURE_HEADER)

        if not signature:
            return WebhookValidationResult(
                is_valid=False,
                error_message="Missing signature header",
            )

        try:
            body = await request.body()
            expected_signature = hmac.new(
                key=settings.helius_webhook_secret.encode(),
                msg=body,
                digestmod=hashlib.sha256,
            ).hexdigest()

            is_valid = hmac.compare_digest(signature, expected_signature)

            return WebhookValidationResult(
                is_valid=is_valid,
                error_message=None if is_valid else "Signature mismatch",
                request_id=request.headers.get("X-Request-ID"),
            )
        except Exception as e:
            return WebhookValidationResult(
                is_valid=False,
                error_message=f"Validation error: {str(e)}",
            )


def validate_hmac_signature(body: bytes, signature: str, secret: str) -> bool:
    """Standalone HMAC validation function."""
    expected = hmac.new(
        key=secret.encode(),
        msg=body,
        digestmod=hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(signature, expected)
```

### 4. Webhook Parser Service

```python
# src/walltrack/services/webhook/parser.py
from datetime import datetime, timezone

import structlog

from walltrack.core.constants.webhook import (
    KNOWN_DEX_PROGRAMS,
    WRAPPED_SOL_MINT,
)
from walltrack.core.models.webhook import (
    HeliusWebhookPayload,
    ParsedSwapEvent,
    SwapDirection,
    TokenTransfer,
)

logger = structlog.get_logger(__name__)


class WebhookParser:
    """Parses Helius webhook payloads into structured swap events."""

    def parse_payload(self, raw_payload: dict) -> ParsedSwapEvent | None:
        """
        Parse raw Helius webhook payload into ParsedSwapEvent.

        Returns None if payload is not a valid swap event.
        """
        try:
            payload = HeliusWebhookPayload.model_validate(raw_payload)

            # Check if this is a swap transaction
            if not self._is_swap_transaction(payload):
                logger.debug(
                    "webhook_not_swap",
                    signature=payload.signature,
                    type=payload.transaction_type,
                )
                return None

            # Extract swap details
            return self._extract_swap_event(payload, raw_payload)

        except Exception as e:
            logger.error(
                "webhook_parse_error",
                error=str(e),
                payload_keys=list(raw_payload.keys()) if raw_payload else [],
            )
            return None

    def _is_swap_transaction(self, payload: HeliusWebhookPayload) -> bool:
        """Check if transaction involves a known DEX."""
        # Check if fee payer interacted with DEX programs
        for account in payload.account_data:
            if account.get("account") in KNOWN_DEX_PROGRAMS:
                return True

        # Check transaction type from Helius
        return payload.transaction_type.upper() == "SWAP"

    def _extract_swap_event(
        self,
        payload: HeliusWebhookPayload,
        raw_payload: dict,
    ) -> ParsedSwapEvent | None:
        """Extract swap details from payload."""
        token_transfers = [
            TokenTransfer.model_validate(t) for t in payload.token_transfers
        ]

        if not token_transfers:
            return None

        # Identify wallet (fee payer is typically the swapper)
        wallet_address = payload.fee_payer

        # Find the non-SOL token in the swap
        token_address = None
        direction = SwapDirection.BUY
        amount_token = 0.0
        amount_sol = 0.0

        for transfer in token_transfers:
            if transfer.mint == WRAPPED_SOL_MINT:
                amount_sol = transfer.amount / 1e9  # Convert lamports to SOL
                # If wallet sent SOL, it's a buy; if received SOL, it's a sell
                if transfer.from_account == wallet_address:
                    direction = SwapDirection.BUY
                else:
                    direction = SwapDirection.SELL
            else:
                token_address = transfer.mint
                amount_token = transfer.amount

        if not token_address:
            return None

        return ParsedSwapEvent(
            tx_signature=payload.signature,
            wallet_address=wallet_address,
            token_address=token_address,
            direction=direction,
            amount_token=amount_token,
            amount_sol=amount_sol,
            timestamp=datetime.fromtimestamp(payload.timestamp, tz=timezone.utc),
            slot=payload.slot,
            fee_lamports=payload.fee,
            raw_payload=raw_payload,
        )
```

### 5. Webhook API Routes

```python
# src/walltrack/api/routes/webhooks.py
import time
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request

from walltrack.core.constants.webhook import MAX_PROCESSING_TIME_MS
from walltrack.core.models.webhook import (
    ParsedSwapEvent,
    WebhookHealthStatus,
)
from walltrack.services.webhook.parser import WebhookParser
from walltrack.services.signal.pipeline import SignalPipeline
from walltrack.data.supabase.repositories.webhook_repo import WebhookRepository

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def get_webhook_parser() -> WebhookParser:
    """Dependency for webhook parser."""
    return WebhookParser()


def get_signal_pipeline() -> SignalPipeline:
    """Dependency for signal processing pipeline."""
    from walltrack.services.signal.pipeline import get_pipeline
    return get_pipeline()


def get_webhook_repo() -> WebhookRepository:
    """Dependency for webhook repository."""
    from walltrack.data.supabase.client import get_supabase_client
    return WebhookRepository(get_supabase_client())


@router.post("/helius")
async def receive_helius_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    parser: WebhookParser = Depends(get_webhook_parser),
    pipeline: SignalPipeline = Depends(get_signal_pipeline),
    webhook_repo: WebhookRepository = Depends(get_webhook_repo),
) -> dict:
    """
    Receive and process Helius webhook notifications.

    HMAC validation is handled by middleware before this endpoint.
    Processing must complete in < 500ms (NFR2).
    """
    start_time = time.perf_counter()

    try:
        payload = await request.json()

        # Handle array of transactions (Helius sends batches)
        transactions = payload if isinstance(payload, list) else [payload]
        processed_count = 0

        for tx_payload in transactions:
            swap_event = parser.parse_payload(tx_payload)

            if swap_event:
                # Process in background to meet timing requirements
                background_tasks.add_task(
                    _process_swap_event,
                    swap_event,
                    pipeline,
                    webhook_repo,
                )
                processed_count += 1

        processing_time_ms = (time.perf_counter() - start_time) * 1000

        logger.info(
            "webhook_received",
            transaction_count=len(transactions),
            processed_count=processed_count,
            processing_time_ms=round(processing_time_ms, 2),
        )

        # Warn if approaching limit
        if processing_time_ms > MAX_PROCESSING_TIME_MS * 0.8:
            logger.warning(
                "webhook_processing_slow",
                processing_time_ms=processing_time_ms,
                limit_ms=MAX_PROCESSING_TIME_MS,
            )

        return {
            "status": "accepted",
            "transactions_received": len(transactions),
            "swaps_detected": processed_count,
            "processing_time_ms": round(processing_time_ms, 2),
        }

    except Exception as e:
        logger.error("webhook_processing_error", error=str(e))
        raise HTTPException(status_code=500, detail="Webhook processing failed")


async def _process_swap_event(
    event: ParsedSwapEvent,
    pipeline: SignalPipeline,
    webhook_repo: WebhookRepository,
) -> None:
    """Background task to process swap event through signal pipeline."""
    try:
        # Log webhook receipt
        await webhook_repo.log_webhook_received(event)

        # Send to signal processing pipeline
        await pipeline.process_swap_event(event)

        logger.debug(
            "swap_event_processed",
            signature=event.tx_signature,
            wallet=event.wallet_address[:8] + "...",
            token=event.token_address[:8] + "...",
            direction=event.direction.value,
        )
    except Exception as e:
        logger.error(
            "swap_event_processing_failed",
            signature=event.tx_signature,
            error=str(e),
        )


@router.get("/health", response_model=WebhookHealthStatus)
async def webhook_health_check(
    webhook_repo: WebhookRepository = Depends(get_webhook_repo),
) -> WebhookHealthStatus:
    """
    Health check for webhook endpoint.

    Returns Helius connectivity status and processing metrics.
    """
    try:
        stats = await webhook_repo.get_webhook_stats(hours=24)

        return WebhookHealthStatus(
            status="healthy",
            helius_connected=True,  # Would check actual connectivity
            last_webhook_received=stats.get("last_received"),
            webhooks_processed_24h=stats.get("count", 0),
            average_processing_ms=stats.get("avg_processing_ms", 0.0),
        )
    except Exception as e:
        logger.error("health_check_failed", error=str(e))
        return WebhookHealthStatus(
            status="degraded",
            helius_connected=False,
        )
```

### 6. Webhook Repository

```python
# src/walltrack/data/supabase/repositories/webhook_repo.py
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from supabase import AsyncClient

from walltrack.core.models.webhook import ParsedSwapEvent

logger = structlog.get_logger(__name__)


class WebhookRepository:
    """Repository for webhook logging and metrics."""

    def __init__(self, client: AsyncClient):
        self.client = client

    async def log_webhook_received(self, event: ParsedSwapEvent) -> None:
        """Log received webhook for tracking and debugging."""
        await self.client.table("webhook_logs").insert({
            "tx_signature": event.tx_signature,
            "wallet_address": event.wallet_address,
            "token_address": event.token_address,
            "direction": event.direction.value,
            "amount_token": event.amount_token,
            "amount_sol": event.amount_sol,
            "slot": event.slot,
            "received_at": datetime.now(timezone.utc).isoformat(),
            "processing_started_at": event.processing_started_at.isoformat(),
        }).execute()

    async def get_webhook_stats(self, hours: int = 24) -> dict[str, Any]:
        """Get webhook processing statistics."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

        result = await self.client.table("webhook_logs").select(
            "received_at",
            count="exact",
        ).gte("received_at", cutoff.isoformat()).execute()

        # Get latest webhook
        latest = await self.client.table("webhook_logs").select(
            "received_at"
        ).order("received_at", desc=True).limit(1).execute()

        return {
            "count": result.count or 0,
            "last_received": (
                datetime.fromisoformat(latest.data[0]["received_at"])
                if latest.data else None
            ),
            "avg_processing_ms": 0.0,  # Would calculate from actual metrics
        }
```

### 7. Database Schema

```sql
-- Supabase migration: webhook_logs table
CREATE TABLE IF NOT EXISTS webhook_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tx_signature VARCHAR(100) NOT NULL UNIQUE,
    wallet_address VARCHAR(50) NOT NULL,
    token_address VARCHAR(50) NOT NULL,
    direction VARCHAR(10) NOT NULL CHECK (direction IN ('buy', 'sell')),
    amount_token DECIMAL(30, 10) NOT NULL,
    amount_sol DECIMAL(20, 10) NOT NULL,
    slot BIGINT NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processing_started_at TIMESTAMPTZ NOT NULL,
    processing_completed_at TIMESTAMPTZ,
    processing_time_ms DECIMAL(10, 2),
    status VARCHAR(20) DEFAULT 'received',
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX idx_webhook_logs_received_at ON webhook_logs(received_at DESC);
CREATE INDEX idx_webhook_logs_wallet ON webhook_logs(wallet_address);
CREATE INDEX idx_webhook_logs_token ON webhook_logs(token_address);
CREATE INDEX idx_webhook_logs_status ON webhook_logs(status);

-- Partition by month for large volumes (optional)
-- CREATE TABLE webhook_logs_2024_01 PARTITION OF webhook_logs
--     FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
```

### 8. Unit Tests

```python
# tests/unit/api/test_webhooks.py
import hashlib
import hmac
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from walltrack.core.models.webhook import (
    HeliusWebhookPayload,
    ParsedSwapEvent,
    SwapDirection,
)
from walltrack.services.webhook.parser import WebhookParser


@pytest.fixture
def sample_helius_payload() -> dict:
    """Sample Helius webhook payload for a swap."""
    return {
        "webhookID": "test-webhook-123",
        "type": "SWAP",
        "timestamp": 1704067200,
        "signature": "5KtPn1LGuxhFqp7tN3DwYmN7",
        "fee": 5000,
        "feePayer": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
        "slot": 123456789,
        "nativeTransfers": [],
        "tokenTransfers": [
            {
                "fromUserAccount": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                "toUserAccount": "DEXAccount123",
                "mint": "So11111111111111111111111111111111111111112",
                "tokenAmount": 1000000000,  # 1 SOL
            },
            {
                "fromUserAccount": "DEXAccount123",
                "toUserAccount": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                "mint": "TokenMint123456789012345678901234567890123",
                "tokenAmount": 1000000,
            },
        ],
        "accountData": [
            {"account": "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4"},
        ],
    }


class TestWebhookParser:
    """Tests for WebhookParser."""

    def test_parse_valid_swap(self, sample_helius_payload: dict):
        """Test parsing a valid swap payload."""
        parser = WebhookParser()
        result = parser.parse_payload(sample_helius_payload)

        assert result is not None
        assert isinstance(result, ParsedSwapEvent)
        assert result.wallet_address == "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
        assert result.direction == SwapDirection.BUY
        assert result.amount_sol == 1.0

    def test_parse_non_swap_transaction(self):
        """Test that non-swap transactions return None."""
        parser = WebhookParser()
        payload = {
            "webhookID": "test",
            "type": "TRANSFER",
            "timestamp": 1704067200,
            "signature": "sig123",
            "fee": 5000,
            "feePayer": "Wallet123",
            "slot": 123,
            "tokenTransfers": [],
            "accountData": [],
        }

        result = parser.parse_payload(payload)
        assert result is None

    def test_parse_invalid_payload(self):
        """Test that invalid payloads return None."""
        parser = WebhookParser()
        result = parser.parse_payload({})
        assert result is None


class TestHMACValidation:
    """Tests for HMAC signature validation."""

    def test_valid_signature(self):
        """Test that valid signatures pass validation."""
        from walltrack.api.middleware.hmac_validation import validate_hmac_signature

        secret = "test-secret"
        body = b'{"test": "data"}'
        signature = hmac.new(
            key=secret.encode(),
            msg=body,
            digestmod=hashlib.sha256,
        ).hexdigest()

        assert validate_hmac_signature(body, signature, secret) is True

    def test_invalid_signature(self):
        """Test that invalid signatures fail validation."""
        from walltrack.api.middleware.hmac_validation import validate_hmac_signature

        secret = "test-secret"
        body = b'{"test": "data"}'
        wrong_signature = "invalid_signature"

        assert validate_hmac_signature(body, wrong_signature, secret) is False


class TestWebhookEndpoint:
    """Tests for webhook API endpoint."""

    @pytest.fixture
    def mock_dependencies(self):
        """Mock all webhook endpoint dependencies."""
        with patch("walltrack.api.routes.webhooks.get_webhook_parser") as mock_parser, \
             patch("walltrack.api.routes.webhooks.get_signal_pipeline") as mock_pipeline, \
             patch("walltrack.api.routes.webhooks.get_webhook_repo") as mock_repo:

            parser = WebhookParser()
            mock_parser.return_value = parser

            pipeline = AsyncMock()
            mock_pipeline.return_value = pipeline

            repo = AsyncMock()
            repo.log_webhook_received = AsyncMock()
            repo.get_webhook_stats = AsyncMock(return_value={
                "count": 100,
                "last_received": datetime.now(timezone.utc),
                "avg_processing_ms": 45.5,
            })
            mock_repo.return_value = repo

            yield {
                "parser": parser,
                "pipeline": pipeline,
                "repo": repo,
            }

    @pytest.mark.asyncio
    async def test_webhook_processing_time(
        self,
        sample_helius_payload: dict,
        mock_dependencies,
    ):
        """Test that webhook processing completes within time limit."""
        import time
        from walltrack.services.webhook.parser import WebhookParser

        parser = WebhookParser()

        start = time.perf_counter()
        result = parser.parse_payload(sample_helius_payload)
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert elapsed_ms < 500  # NFR2: < 500ms
        assert result is not None
```

### 9. Application Integration

```python
# src/walltrack/api/app.py (update)
from fastapi import FastAPI
from walltrack.api.middleware.hmac_validation import HMACValidationMiddleware
from walltrack.api.routes import webhooks

def create_app() -> FastAPI:
    app = FastAPI(title="WallTrack API", version="1.0.0")

    # Add HMAC validation middleware for webhooks
    app.add_middleware(HMACValidationMiddleware)

    # Include webhook routes
    app.include_router(webhooks.router, prefix="/api/v1")

    return app
```

---

## Implementation Tasks

- [ ] Create `src/walltrack/api/routes/webhooks.py`
- [ ] Implement HMAC signature validation middleware
- [ ] Parse Helius webhook payload
- [ ] Extract transaction details
- [ ] Pass to signal processing pipeline
- [ ] Add health check endpoint
- [ ] Ensure < 500ms processing time

## Definition of Done

- [ ] Webhook endpoint receives Helius notifications
- [ ] HMAC validation rejects invalid requests
- [ ] Payload parsed correctly
- [ ] Processing time < 500ms
