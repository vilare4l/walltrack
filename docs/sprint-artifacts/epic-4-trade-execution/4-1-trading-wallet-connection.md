# Story 4.1: Trading Wallet Connection and Balance

## Story Info
- **Epic**: Epic 4 - Automated Trade Execution & Position Management
- **Status**: ready
- **Priority**: High
- **FR**: FR52, FR53, FR54

## User Story

**As an** operator,
**I want** to connect my trading wallet to the system,
**So that** the system can execute trades on my behalf.

## Acceptance Criteria

### AC 1: Wallet Configuration
**Given** operator has a Solana wallet with private key
**When** wallet is configured in environment variables
**Then** system loads wallet securely via pydantic-settings
**And** private key is NEVER logged or exposed (NFR6)

### AC 2: Connectivity Validation
**Given** wallet is configured
**When** connectivity is validated
**Then** system confirms wallet can sign transactions
**And** current SOL balance is retrieved
**And** validation result is displayed in dashboard

### AC 3: Balance View
**Given** connected wallet
**When** balance view is requested
**Then** SOL balance is displayed
**And** token balances (open positions) are listed
**And** balance refreshes on demand or automatically

### AC 4: Connection Failure
**Given** wallet connection fails
**When** trade is attempted
**Then** trade is blocked with clear error
**And** alert is raised to operator
**And** system enters safe mode (no trades until resolved)

## Technical Notes

- FR52: Operator can connect trading wallet
- FR53: View trading wallet balance
- FR54: Validate wallet connectivity before trading
- Implement in `src/walltrack/services/solana/wallet_client.py`
- Use solders or solana-py for wallet operations

---

## Technical Specification

### 1. Data Models

```python
# src/walltrack/models/wallet.py
from __future__ import annotations
from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, SecretStr
from typing import Optional
import base58


class WalletConnectionStatus(str, Enum):
    """Status of wallet connection."""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    VALIDATING = "validating"


class SafeModeReason(str, Enum):
    """Reasons for entering safe mode."""
    CONNECTION_FAILED = "connection_failed"
    SIGNING_FAILED = "signing_failed"
    RPC_UNAVAILABLE = "rpc_unavailable"
    INSUFFICIENT_BALANCE = "insufficient_balance"
    MANUAL = "manual"


class TokenBalance(BaseModel):
    """Balance of a specific SPL token."""

    mint_address: str = Field(..., description="Token mint address")
    symbol: str | None = Field(None, description="Token symbol if known")
    amount: float = Field(..., ge=0, description="Token amount")
    decimals: int = Field(..., ge=0, le=18)
    ui_amount: float = Field(..., ge=0, description="Human-readable amount")
    estimated_value_sol: float | None = Field(None, ge=0)

    @field_validator("mint_address")
    @classmethod
    def validate_mint(cls, v: str) -> str:
        try:
            decoded = base58.b58decode(v)
            if len(decoded) != 32:
                raise ValueError("Invalid mint address length")
        except Exception:
            raise ValueError("Invalid base58 mint address")
        return v


class WalletBalance(BaseModel):
    """Complete wallet balance information."""

    sol_balance: float = Field(..., ge=0, description="SOL balance in lamports")
    sol_balance_ui: float = Field(..., ge=0, description="SOL balance for display")
    token_balances: list[TokenBalance] = Field(default_factory=list)
    total_value_sol: float = Field(..., ge=0, description="Total portfolio value in SOL")
    last_updated: datetime = Field(default_factory=datetime.utcnow)

    @property
    def has_sufficient_sol(self) -> bool:
        """Check if wallet has minimum SOL for transactions."""
        MIN_SOL_REQUIRED = 0.01  # ~10k lamports for fees
        return self.sol_balance_ui >= MIN_SOL_REQUIRED


class WalletState(BaseModel):
    """Current state of the trading wallet."""

    public_key: str = Field(..., description="Wallet public key (base58)")
    status: WalletConnectionStatus = Field(default=WalletConnectionStatus.DISCONNECTED)
    balance: WalletBalance | None = Field(None)
    safe_mode: bool = Field(default=False)
    safe_mode_reason: SafeModeReason | None = Field(None)
    safe_mode_since: datetime | None = Field(None)
    last_validated: datetime | None = Field(None)
    error_message: str | None = Field(None)

    @field_validator("public_key")
    @classmethod
    def validate_public_key(cls, v: str) -> str:
        try:
            decoded = base58.b58decode(v)
            if len(decoded) != 32:
                raise ValueError("Invalid public key length")
        except Exception:
            raise ValueError("Invalid base58 public key")
        return v


class WalletConfig(BaseModel):
    """Wallet configuration from environment (SENSITIVE)."""

    # Private key is stored as SecretStr to prevent accidental logging
    private_key: SecretStr = Field(..., description="Base58 encoded private key")
    rpc_endpoint: str = Field(..., description="Solana RPC endpoint URL")
    rpc_ws_endpoint: str | None = Field(None, description="WebSocket endpoint")
    commitment: str = Field(default="confirmed")

    class Config:
        # Extra security: prevent serialization of sensitive fields
        json_encoders = {
            SecretStr: lambda v: "***REDACTED***"
        }


class SigningResult(BaseModel):
    """Result of a transaction signing test."""

    success: bool
    message_hash: str | None = Field(None)
    signature: str | None = Field(None)
    error: str | None = Field(None)
    latency_ms: float = Field(..., ge=0)
```

### 2. Configuration

```python
# src/walltrack/config/wallet_settings.py
from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings
import structlog

logger = structlog.get_logger()


class WalletSettings(BaseSettings):
    """Wallet configuration loaded securely from environment.

    SECURITY: Private key is loaded as SecretStr to prevent logging.
    NEVER log or expose the private key value.
    """

    # Trading wallet (REQUIRED for execution)
    trading_wallet_private_key: SecretStr = Field(
        ...,
        description="Base58 private key for trading wallet"
    )

    # RPC configuration
    solana_rpc_url: str = Field(
        default="https://api.mainnet-beta.solana.com",
        description="Solana RPC endpoint"
    )
    solana_rpc_ws_url: str | None = Field(
        default=None,
        description="Solana WebSocket endpoint for subscriptions"
    )

    # Connection settings
    rpc_commitment: str = Field(default="confirmed")
    rpc_timeout_seconds: int = Field(default=30, ge=5, le=120)
    rpc_max_retries: int = Field(default=3, ge=1, le=10)

    # Safety settings
    min_sol_balance: float = Field(
        default=0.05,
        ge=0.01,
        description="Minimum SOL to keep for fees"
    )
    auto_safe_mode_on_error: bool = Field(
        default=True,
        description="Automatically enter safe mode on connection errors"
    )
    balance_refresh_interval_seconds: int = Field(
        default=30,
        ge=10,
        le=300
    )

    model_config = {
        "env_prefix": "",
        "env_file": ".env",
        "extra": "ignore"
    }

    @field_validator("trading_wallet_private_key", mode="before")
    @classmethod
    def validate_private_key_format(cls, v):
        """Validate private key format without exposing value."""
        if isinstance(v, SecretStr):
            raw = v.get_secret_value()
        else:
            raw = str(v)

        # Basic format validation (don't log the actual key!)
        if len(raw) < 64:
            raise ValueError("Private key appears too short")

        # Log that key was loaded (not the key itself!)
        logger.info("wallet_private_key_loaded", key_length=len(raw))

        return v


def get_wallet_settings() -> WalletSettings:
    """Get wallet settings singleton."""
    return WalletSettings()
```

### 3. Wallet Client Service

```python
# src/walltrack/services/solana/wallet_client.py
from __future__ import annotations
import asyncio
import base58
import time
from datetime import datetime
from typing import Optional

import structlog
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.signature import Signature
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Commitment
from spl.token.async_client import AsyncToken
from spl.token.constants import TOKEN_PROGRAM_ID

from walltrack.config.wallet_settings import WalletSettings, get_wallet_settings
from walltrack.models.wallet import (
    WalletState,
    WalletBalance,
    TokenBalance,
    WalletConnectionStatus,
    SafeModeReason,
    SigningResult,
)

logger = structlog.get_logger()


class WalletConnectionError(Exception):
    """Raised when wallet connection fails."""
    pass


class WalletClient:
    """Secure Solana wallet client for trade execution.

    SECURITY NOTES:
    - Private key is NEVER logged
    - Safe mode prevents trades on connection failure
    - All operations validate connectivity first
    """

    def __init__(self, settings: WalletSettings | None = None):
        self._settings = settings or get_wallet_settings()
        self._keypair: Keypair | None = None
        self._client: AsyncClient | None = None
        self._state = WalletState(
            public_key="11111111111111111111111111111111",  # Placeholder
            status=WalletConnectionStatus.DISCONNECTED,
        )
        self._initialized = False
        self._balance_lock = asyncio.Lock()

    async def initialize(self) -> WalletState:
        """Initialize wallet from configuration.

        Loads keypair from environment and validates connectivity.
        """
        try:
            logger.info("wallet_initializing")

            # Load keypair from secret (NEVER log the key!)
            private_key_bytes = base58.b58decode(
                self._settings.trading_wallet_private_key.get_secret_value()
            )
            self._keypair = Keypair.from_bytes(private_key_bytes)

            # Update state with actual public key
            self._state = WalletState(
                public_key=str(self._keypair.pubkey()),
                status=WalletConnectionStatus.VALIDATING,
            )

            logger.info(
                "wallet_keypair_loaded",
                public_key=self._state.public_key
            )

            # Initialize RPC client
            self._client = AsyncClient(
                self._settings.solana_rpc_url,
                commitment=Commitment(self._settings.rpc_commitment),
            )

            # Validate connectivity
            await self._validate_connectivity()

            # Fetch initial balance
            await self.refresh_balance()

            self._state.status = WalletConnectionStatus.CONNECTED
            self._state.last_validated = datetime.utcnow()
            self._initialized = True

            logger.info(
                "wallet_initialized",
                public_key=self._state.public_key,
                sol_balance=self._state.balance.sol_balance_ui if self._state.balance else 0,
            )

            return self._state

        except Exception as e:
            logger.error("wallet_initialization_failed", error=str(e))
            await self._enter_safe_mode(SafeModeReason.CONNECTION_FAILED, str(e))
            raise WalletConnectionError(f"Failed to initialize wallet: {e}")

    async def _validate_connectivity(self) -> None:
        """Validate RPC connectivity and wallet access."""
        if not self._client:
            raise WalletConnectionError("RPC client not initialized")

        # Test RPC connection
        try:
            health = await self._client.get_health()
            if health.value != "ok":
                raise WalletConnectionError(f"RPC unhealthy: {health.value}")
        except Exception as e:
            raise WalletConnectionError(f"RPC connection failed: {e}")

        logger.debug("wallet_rpc_healthy")

    async def validate_signing(self) -> SigningResult:
        """Test that wallet can sign transactions.

        Signs a test message to verify keypair works correctly.
        """
        if not self._keypair:
            return SigningResult(
                success=False,
                error="Wallet not initialized",
                latency_ms=0,
            )

        start = time.perf_counter()

        try:
            # Create a test message
            test_message = b"WallTrack signing validation test"

            # Sign the message
            signature = self._keypair.sign_message(test_message)

            latency_ms = (time.perf_counter() - start) * 1000

            logger.info(
                "wallet_signing_validated",
                latency_ms=round(latency_ms, 2),
            )

            return SigningResult(
                success=True,
                message_hash=test_message.hex(),
                signature=str(signature),
                latency_ms=latency_ms,
            )

        except Exception as e:
            latency_ms = (time.perf_counter() - start) * 1000
            logger.error("wallet_signing_failed", error=str(e))

            await self._enter_safe_mode(SafeModeReason.SIGNING_FAILED, str(e))

            return SigningResult(
                success=False,
                error=str(e),
                latency_ms=latency_ms,
            )

    async def refresh_balance(self) -> WalletBalance:
        """Refresh wallet balance (SOL + tokens)."""
        async with self._balance_lock:
            if not self._client or not self._keypair:
                raise WalletConnectionError("Wallet not initialized")

            pubkey = self._keypair.pubkey()

            # Get SOL balance
            sol_response = await self._client.get_balance(pubkey)
            sol_lamports = sol_response.value
            sol_ui = sol_lamports / 1_000_000_000  # Convert lamports to SOL

            # Get token accounts
            token_balances = await self._fetch_token_balances(pubkey)

            # Calculate total value
            total_value = sol_ui + sum(
                tb.estimated_value_sol or 0 for tb in token_balances
            )

            balance = WalletBalance(
                sol_balance=float(sol_lamports),
                sol_balance_ui=sol_ui,
                token_balances=token_balances,
                total_value_sol=total_value,
                last_updated=datetime.utcnow(),
            )

            self._state.balance = balance

            logger.info(
                "wallet_balance_refreshed",
                sol_balance=round(sol_ui, 4),
                token_count=len(token_balances),
                total_value_sol=round(total_value, 4),
            )

            # Check minimum balance
            if not balance.has_sufficient_sol:
                logger.warning(
                    "wallet_low_sol_balance",
                    balance=sol_ui,
                    minimum=self._settings.min_sol_balance,
                )

            return balance

    async def _fetch_token_balances(self, pubkey: Pubkey) -> list[TokenBalance]:
        """Fetch all SPL token balances for wallet."""
        token_balances = []

        try:
            # Get all token accounts
            response = await self._client.get_token_accounts_by_owner_json_parsed(
                pubkey,
                opts={"programId": TOKEN_PROGRAM_ID},
            )

            for account in response.value:
                try:
                    parsed = account.account.data.parsed
                    info = parsed["info"]
                    token_amount = info["tokenAmount"]

                    # Skip zero balances
                    if float(token_amount["uiAmount"] or 0) == 0:
                        continue

                    token_balances.append(TokenBalance(
                        mint_address=info["mint"],
                        symbol=None,  # Would need metadata lookup
                        amount=float(token_amount["amount"]),
                        decimals=token_amount["decimals"],
                        ui_amount=float(token_amount["uiAmount"] or 0),
                        estimated_value_sol=None,  # Would need price lookup
                    ))
                except (KeyError, TypeError) as e:
                    logger.warning("token_balance_parse_error", error=str(e))
                    continue

        except Exception as e:
            logger.error("fetch_token_balances_failed", error=str(e))

        return token_balances

    async def _enter_safe_mode(
        self,
        reason: SafeModeReason,
        error_message: str,
    ) -> None:
        """Enter safe mode - block all trades."""
        if self._settings.auto_safe_mode_on_error:
            self._state.safe_mode = True
            self._state.safe_mode_reason = reason
            self._state.safe_mode_since = datetime.utcnow()
            self._state.error_message = error_message
            self._state.status = WalletConnectionStatus.ERROR

            logger.critical(
                "wallet_safe_mode_activated",
                reason=reason.value,
                error=error_message,
            )

    async def exit_safe_mode(self) -> bool:
        """Attempt to exit safe mode by re-validating connectivity."""
        if not self._state.safe_mode:
            return True

        logger.info("wallet_attempting_safe_mode_exit")

        try:
            await self._validate_connectivity()
            signing_result = await self.validate_signing()

            if signing_result.success:
                self._state.safe_mode = False
                self._state.safe_mode_reason = None
                self._state.safe_mode_since = None
                self._state.error_message = None
                self._state.status = WalletConnectionStatus.CONNECTED
                self._state.last_validated = datetime.utcnow()

                logger.info("wallet_safe_mode_exited")
                return True
            else:
                logger.warning(
                    "wallet_safe_mode_exit_failed",
                    error=signing_result.error,
                )
                return False

        except Exception as e:
            logger.error("wallet_safe_mode_exit_error", error=str(e))
            return False

    def set_manual_safe_mode(self, enabled: bool) -> None:
        """Manually enable/disable safe mode."""
        if enabled:
            self._state.safe_mode = True
            self._state.safe_mode_reason = SafeModeReason.MANUAL
            self._state.safe_mode_since = datetime.utcnow()
            logger.info("wallet_manual_safe_mode_enabled")
        else:
            self._state.safe_mode = False
            self._state.safe_mode_reason = None
            self._state.safe_mode_since = None
            logger.info("wallet_manual_safe_mode_disabled")

    @property
    def state(self) -> WalletState:
        """Get current wallet state."""
        return self._state

    @property
    def is_ready_for_trading(self) -> bool:
        """Check if wallet is ready to execute trades."""
        return (
            self._initialized
            and not self._state.safe_mode
            and self._state.status == WalletConnectionStatus.CONNECTED
            and self._state.balance is not None
            and self._state.balance.has_sufficient_sol
        )

    @property
    def keypair(self) -> Keypair | None:
        """Get keypair for signing (use with caution!)."""
        if self._state.safe_mode:
            logger.warning("keypair_access_blocked_safe_mode")
            return None
        return self._keypair

    @property
    def public_key(self) -> Pubkey | None:
        """Get wallet public key."""
        return self._keypair.pubkey() if self._keypair else None

    async def close(self) -> None:
        """Close RPC client connection."""
        if self._client:
            await self._client.close()
            self._client = None
            self._state.status = WalletConnectionStatus.DISCONNECTED
            logger.info("wallet_client_closed")


# Singleton instance
_wallet_client: WalletClient | None = None


async def get_wallet_client() -> WalletClient:
    """Get or create wallet client singleton."""
    global _wallet_client
    if _wallet_client is None:
        _wallet_client = WalletClient()
        await _wallet_client.initialize()
    return _wallet_client
```

### 4. API Routes

```python
# src/walltrack/api/routes/wallet.py
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from walltrack.services.solana.wallet_client import (
    WalletClient,
    get_wallet_client,
    WalletConnectionError,
)
from walltrack.models.wallet import (
    WalletState,
    WalletBalance,
    SigningResult,
    WalletConnectionStatus,
)

router = APIRouter(prefix="/wallet", tags=["wallet"])


class WalletStatusResponse(BaseModel):
    """Wallet status for dashboard display."""
    public_key: str
    status: WalletConnectionStatus
    safe_mode: bool
    safe_mode_reason: str | None
    error_message: str | None
    last_validated: datetime | None
    is_ready_for_trading: bool


class BalanceResponse(BaseModel):
    """Wallet balance response."""
    sol_balance: float
    sol_balance_ui: float
    token_count: int
    total_value_sol: float
    tokens: list[dict]
    last_updated: datetime
    has_sufficient_sol: bool


class SafeModeRequest(BaseModel):
    """Request to change safe mode."""
    enabled: bool


@router.get("/status", response_model=WalletStatusResponse)
async def get_wallet_status(
    wallet: WalletClient = Depends(get_wallet_client),
) -> WalletStatusResponse:
    """Get current wallet connection status."""
    state = wallet.state
    return WalletStatusResponse(
        public_key=state.public_key,
        status=state.status,
        safe_mode=state.safe_mode,
        safe_mode_reason=state.safe_mode_reason.value if state.safe_mode_reason else None,
        error_message=state.error_message,
        last_validated=state.last_validated,
        is_ready_for_trading=wallet.is_ready_for_trading,
    )


@router.get("/balance", response_model=BalanceResponse)
async def get_wallet_balance(
    wallet: WalletClient = Depends(get_wallet_client),
    refresh: bool = False,
) -> BalanceResponse:
    """Get wallet balance (SOL + tokens)."""
    if refresh:
        await wallet.refresh_balance()

    balance = wallet.state.balance
    if not balance:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Balance not available - wallet may not be connected",
        )

    return BalanceResponse(
        sol_balance=balance.sol_balance,
        sol_balance_ui=balance.sol_balance_ui,
        token_count=len(balance.token_balances),
        total_value_sol=balance.total_value_sol,
        tokens=[tb.model_dump() for tb in balance.token_balances],
        last_updated=balance.last_updated,
        has_sufficient_sol=balance.has_sufficient_sol,
    )


@router.post("/validate", response_model=SigningResult)
async def validate_signing(
    wallet: WalletClient = Depends(get_wallet_client),
) -> SigningResult:
    """Validate wallet can sign transactions."""
    return await wallet.validate_signing()


@router.post("/safe-mode")
async def set_safe_mode(
    request: SafeModeRequest,
    wallet: WalletClient = Depends(get_wallet_client),
) -> dict:
    """Manually enable/disable safe mode."""
    wallet.set_manual_safe_mode(request.enabled)
    return {
        "safe_mode": wallet.state.safe_mode,
        "reason": wallet.state.safe_mode_reason.value if wallet.state.safe_mode_reason else None,
    }


@router.post("/safe-mode/exit")
async def exit_safe_mode(
    wallet: WalletClient = Depends(get_wallet_client),
) -> dict:
    """Attempt to exit safe mode by re-validating connectivity."""
    success = await wallet.exit_safe_mode()
    return {
        "success": success,
        "safe_mode": wallet.state.safe_mode,
        "error": wallet.state.error_message if not success else None,
    }


@router.get("/ready")
async def check_trading_ready(
    wallet: WalletClient = Depends(get_wallet_client),
) -> dict:
    """Quick check if wallet is ready for trading."""
    return {
        "ready": wallet.is_ready_for_trading,
        "status": wallet.state.status.value,
        "safe_mode": wallet.state.safe_mode,
    }
```

### 5. Dashboard Component

```python
# src/walltrack/dashboard/components/wallet_status.py
import gradio as gr
from datetime import datetime
import httpx
from typing import Callable


def create_wallet_status_component(api_base_url: str = "http://localhost:8000") -> gr.Blocks:
    """Create wallet status and balance dashboard component.

    Displays:
    - Connection status with indicator
    - SOL balance with refresh
    - Token balances (open positions)
    - Safe mode controls
    """

    async def fetch_wallet_status() -> dict:
        """Fetch wallet status from API."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{api_base_url}/api/v1/wallet/status")
            return response.json()

    async def fetch_balance(refresh: bool = False) -> dict:
        """Fetch wallet balance from API."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{api_base_url}/api/v1/wallet/balance",
                params={"refresh": refresh},
            )
            return response.json()

    async def validate_signing() -> dict:
        """Validate wallet signing capability."""
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{api_base_url}/api/v1/wallet/validate")
            return response.json()

    async def toggle_safe_mode(enabled: bool) -> dict:
        """Toggle safe mode."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{api_base_url}/api/v1/wallet/safe-mode",
                json={"enabled": enabled},
            )
            return response.json()

    async def exit_safe_mode() -> dict:
        """Attempt to exit safe mode."""
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{api_base_url}/api/v1/wallet/safe-mode/exit")
            return response.json()

    def format_status_indicator(status: str, safe_mode: bool) -> str:
        """Format status as colored indicator."""
        if safe_mode:
            return "🔴 SAFE MODE (Trading Blocked)"
        elif status == "connected":
            return "🟢 Connected"
        elif status == "validating":
            return "🟡 Validating..."
        elif status == "error":
            return "🔴 Error"
        else:
            return "⚪ Disconnected"

    def format_balance_display(balance: dict) -> str:
        """Format balance for display."""
        sol = balance.get("sol_balance_ui", 0)
        total = balance.get("total_value_sol", 0)
        token_count = balance.get("token_count", 0)
        sufficient = balance.get("has_sufficient_sol", False)

        status_icon = "✅" if sufficient else "⚠️"

        return f"""
### Balance Summary {status_icon}
- **SOL Balance:** {sol:.4f} SOL
- **Total Value:** {total:.4f} SOL
- **Open Positions:** {token_count} tokens
- **Last Updated:** {balance.get('last_updated', 'Unknown')}
        """

    def format_tokens_table(tokens: list) -> list[list]:
        """Format token balances as table data."""
        if not tokens:
            return [["No tokens", "-", "-"]]

        return [
            [
                t.get("mint_address", "")[:8] + "...",
                f"{t.get('ui_amount', 0):.4f}",
                f"{t.get('estimated_value_sol', 0) or 'N/A'} SOL",
            ]
            for t in tokens
        ]

    with gr.Blocks() as component:
        gr.Markdown("## 💳 Trading Wallet")

        with gr.Row():
            with gr.Column(scale=2):
                # Status section
                status_display = gr.Markdown("Loading...")
                public_key_display = gr.Textbox(
                    label="Wallet Address",
                    interactive=False,
                    max_lines=1,
                )

                with gr.Row():
                    refresh_status_btn = gr.Button("🔄 Refresh Status", size="sm")
                    validate_btn = gr.Button("✅ Validate Signing", size="sm")

                # Validation result
                validation_result = gr.JSON(label="Validation Result", visible=False)

            with gr.Column(scale=2):
                # Balance section
                balance_display = gr.Markdown("Loading balance...")

                refresh_balance_btn = gr.Button("🔄 Refresh Balance", size="sm")

        # Token balances table
        gr.Markdown("### Token Balances (Open Positions)")
        tokens_table = gr.Dataframe(
            headers=["Token", "Amount", "Value"],
            datatype=["str", "str", "str"],
            interactive=False,
        )

        # Safe mode controls
        gr.Markdown("### ⚠️ Safe Mode Controls")
        with gr.Row():
            safe_mode_toggle = gr.Checkbox(
                label="Safe Mode (Block All Trades)",
                value=False,
            )
            exit_safe_mode_btn = gr.Button(
                "🔓 Exit Safe Mode",
                variant="primary",
                size="sm",
            )
        safe_mode_status = gr.Markdown("")

        # Error display
        error_display = gr.Markdown("", visible=False)

        # Event handlers
        async def update_status():
            try:
                status = await fetch_wallet_status()
                indicator = format_status_indicator(
                    status.get("status", "disconnected"),
                    status.get("safe_mode", False),
                )
                return (
                    f"### Status: {indicator}",
                    status.get("public_key", "Unknown"),
                    status.get("safe_mode", False),
                )
            except Exception as e:
                return f"### Status: ❌ Error: {e}", "", False

        async def update_balance(refresh: bool = True):
            try:
                balance = await fetch_balance(refresh)
                display = format_balance_display(balance)
                tokens = format_tokens_table(balance.get("tokens", []))
                return display, tokens
            except Exception as e:
                return f"### Balance Error: {e}", []

        async def do_validate():
            try:
                result = await validate_signing()
                return gr.update(value=result, visible=True)
            except Exception as e:
                return gr.update(value={"error": str(e)}, visible=True)

        async def do_toggle_safe_mode(enabled):
            try:
                result = await toggle_safe_mode(enabled)
                return f"Safe mode: {'ENABLED' if result.get('safe_mode') else 'DISABLED'}"
            except Exception as e:
                return f"Error: {e}"

        async def do_exit_safe_mode():
            try:
                result = await exit_safe_mode()
                if result.get("success"):
                    return "✅ Successfully exited safe mode", False
                else:
                    return f"❌ Failed: {result.get('error', 'Unknown')}", True
            except Exception as e:
                return f"❌ Error: {e}", True

        # Wire up events
        refresh_status_btn.click(
            fn=update_status,
            outputs=[status_display, public_key_display, safe_mode_toggle],
        )

        refresh_balance_btn.click(
            fn=update_balance,
            inputs=[],
            outputs=[balance_display, tokens_table],
        )

        validate_btn.click(
            fn=do_validate,
            outputs=[validation_result],
        )

        safe_mode_toggle.change(
            fn=do_toggle_safe_mode,
            inputs=[safe_mode_toggle],
            outputs=[safe_mode_status],
        )

        exit_safe_mode_btn.click(
            fn=do_exit_safe_mode,
            outputs=[safe_mode_status, safe_mode_toggle],
        )

        # Auto-refresh on load
        component.load(
            fn=update_status,
            outputs=[status_display, public_key_display, safe_mode_toggle],
        )
        component.load(
            fn=lambda: update_balance(refresh=False),
            outputs=[balance_display, tokens_table],
        )

    return component
```

### 6. Unit Tests

```python
# tests/unit/services/solana/test_wallet_client.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
import base58

from walltrack.services.solana.wallet_client import (
    WalletClient,
    WalletConnectionError,
)
from walltrack.models.wallet import (
    WalletConnectionStatus,
    SafeModeReason,
    WalletBalance,
    TokenBalance,
)
from walltrack.config.wallet_settings import WalletSettings
from pydantic import SecretStr


# Test keypair (DO NOT USE IN PRODUCTION)
TEST_PRIVATE_KEY = base58.b58encode(bytes([1] * 64)).decode()


@pytest.fixture
def mock_settings():
    """Create mock wallet settings."""
    return WalletSettings(
        trading_wallet_private_key=SecretStr(TEST_PRIVATE_KEY),
        solana_rpc_url="https://api.devnet.solana.com",
        min_sol_balance=0.01,
        auto_safe_mode_on_error=True,
    )


@pytest.fixture
def wallet_client(mock_settings):
    """Create wallet client with mock settings."""
    return WalletClient(settings=mock_settings)


class TestWalletClientInitialization:
    """Tests for wallet initialization."""

    @pytest.mark.asyncio
    async def test_initialize_success(self, wallet_client):
        """Test successful wallet initialization."""
        with patch.object(wallet_client, '_validate_connectivity', new_callable=AsyncMock):
            with patch.object(wallet_client, 'refresh_balance', new_callable=AsyncMock) as mock_balance:
                mock_balance.return_value = WalletBalance(
                    sol_balance=1_000_000_000,
                    sol_balance_ui=1.0,
                    token_balances=[],
                    total_value_sol=1.0,
                )

                state = await wallet_client.initialize()

                assert state.status == WalletConnectionStatus.CONNECTED
                assert state.public_key is not None
                assert len(state.public_key) == 44  # Base58 pubkey length

    @pytest.mark.asyncio
    async def test_initialize_connection_failure_enters_safe_mode(self, wallet_client):
        """Test that connection failure enters safe mode."""
        with patch.object(
            wallet_client,
            '_validate_connectivity',
            new_callable=AsyncMock,
            side_effect=Exception("RPC unavailable"),
        ):
            with pytest.raises(WalletConnectionError):
                await wallet_client.initialize()

            assert wallet_client.state.safe_mode is True
            assert wallet_client.state.safe_mode_reason == SafeModeReason.CONNECTION_FAILED


class TestWalletSigning:
    """Tests for transaction signing validation."""

    @pytest.mark.asyncio
    async def test_validate_signing_success(self, wallet_client):
        """Test successful signing validation."""
        # Initialize first
        with patch.object(wallet_client, '_validate_connectivity', new_callable=AsyncMock):
            with patch.object(wallet_client, 'refresh_balance', new_callable=AsyncMock) as mock_balance:
                mock_balance.return_value = WalletBalance(
                    sol_balance=1_000_000_000,
                    sol_balance_ui=1.0,
                    token_balances=[],
                    total_value_sol=1.0,
                )
                await wallet_client.initialize()

        result = await wallet_client.validate_signing()

        assert result.success is True
        assert result.signature is not None
        assert result.latency_ms >= 0

    @pytest.mark.asyncio
    async def test_validate_signing_without_init_fails(self, wallet_client):
        """Test signing fails without initialization."""
        result = await wallet_client.validate_signing()

        assert result.success is False
        assert "not initialized" in result.error.lower()


class TestSafeMode:
    """Tests for safe mode functionality."""

    @pytest.mark.asyncio
    async def test_manual_safe_mode_enable(self, wallet_client):
        """Test manual safe mode activation."""
        wallet_client.set_manual_safe_mode(True)

        assert wallet_client.state.safe_mode is True
        assert wallet_client.state.safe_mode_reason == SafeModeReason.MANUAL
        assert wallet_client.state.safe_mode_since is not None

    @pytest.mark.asyncio
    async def test_manual_safe_mode_disable(self, wallet_client):
        """Test manual safe mode deactivation."""
        wallet_client.set_manual_safe_mode(True)
        wallet_client.set_manual_safe_mode(False)

        assert wallet_client.state.safe_mode is False
        assert wallet_client.state.safe_mode_reason is None

    @pytest.mark.asyncio
    async def test_is_ready_for_trading_blocked_in_safe_mode(self, wallet_client):
        """Test trading blocked in safe mode."""
        # Initialize
        with patch.object(wallet_client, '_validate_connectivity', new_callable=AsyncMock):
            with patch.object(wallet_client, 'refresh_balance', new_callable=AsyncMock) as mock_balance:
                mock_balance.return_value = WalletBalance(
                    sol_balance=1_000_000_000,
                    sol_balance_ui=1.0,
                    token_balances=[],
                    total_value_sol=1.0,
                )
                await wallet_client.initialize()

        assert wallet_client.is_ready_for_trading is True

        # Enable safe mode
        wallet_client.set_manual_safe_mode(True)

        assert wallet_client.is_ready_for_trading is False

    @pytest.mark.asyncio
    async def test_keypair_access_blocked_in_safe_mode(self, wallet_client):
        """Test keypair access blocked in safe mode."""
        wallet_client.set_manual_safe_mode(True)

        assert wallet_client.keypair is None


class TestBalanceRetrieval:
    """Tests for balance retrieval."""

    @pytest.mark.asyncio
    async def test_insufficient_sol_warning(self, wallet_client):
        """Test warning when SOL balance is low."""
        with patch.object(wallet_client, '_validate_connectivity', new_callable=AsyncMock):
            with patch.object(wallet_client, 'refresh_balance', new_callable=AsyncMock) as mock_balance:
                # Low balance
                balance = WalletBalance(
                    sol_balance=1_000,  # 0.000001 SOL
                    sol_balance_ui=0.000001,
                    token_balances=[],
                    total_value_sol=0.000001,
                )
                mock_balance.return_value = balance
                await wallet_client.initialize()

        assert wallet_client.state.balance.has_sufficient_sol is False


class TestTokenBalanceModel:
    """Tests for TokenBalance model."""

    def test_valid_token_balance(self):
        """Test valid token balance creation."""
        token = TokenBalance(
            mint_address="So11111111111111111111111111111111111111112",
            symbol="SOL",
            amount=1000000000.0,
            decimals=9,
            ui_amount=1.0,
            estimated_value_sol=1.0,
        )

        assert token.mint_address is not None
        assert token.ui_amount == 1.0

    def test_invalid_mint_address_rejected(self):
        """Test invalid mint address is rejected."""
        with pytest.raises(ValueError, match="Invalid"):
            TokenBalance(
                mint_address="invalid",
                amount=100.0,
                decimals=9,
                ui_amount=0.0001,
            )
```

### 7. Database Schema

```sql
-- migrations/004_wallet_state.sql

-- Wallet state tracking (single row, updated on changes)
CREATE TABLE IF NOT EXISTS wallet_state (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    public_key TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'disconnected',
    safe_mode BOOLEAN NOT NULL DEFAULT false,
    safe_mode_reason TEXT,
    safe_mode_since TIMESTAMPTZ,
    error_message TEXT,
    last_validated TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT single_row CHECK (id = '00000000-0000-0000-0000-000000000001'::uuid)
);

-- Balance snapshots for history
CREATE TABLE IF NOT EXISTS wallet_balance_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sol_balance_lamports BIGINT NOT NULL,
    sol_balance_ui DECIMAL(20, 9) NOT NULL,
    total_value_sol DECIMAL(20, 9) NOT NULL,
    token_count INTEGER NOT NULL DEFAULT 0,
    snapshot_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Index for time-series queries
    CONSTRAINT valid_balance CHECK (sol_balance_lamports >= 0)
);

CREATE INDEX IF NOT EXISTS idx_balance_snapshots_time
ON wallet_balance_snapshots(snapshot_at DESC);

-- Token balance snapshots
CREATE TABLE IF NOT EXISTS token_balance_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    wallet_snapshot_id UUID REFERENCES wallet_balance_snapshots(id) ON DELETE CASCADE,
    mint_address TEXT NOT NULL,
    symbol TEXT,
    amount DECIMAL(30, 0) NOT NULL,
    decimals INTEGER NOT NULL,
    ui_amount DECIMAL(20, 9) NOT NULL,
    estimated_value_sol DECIMAL(20, 9),
    snapshot_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_token_snapshots_wallet
ON token_balance_snapshots(wallet_snapshot_id);

CREATE INDEX IF NOT EXISTS idx_token_snapshots_mint
ON token_balance_snapshots(mint_address);

-- Safe mode events audit trail
CREATE TABLE IF NOT EXISTS safe_mode_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type TEXT NOT NULL, -- 'entered', 'exited', 'exit_failed'
    reason TEXT,
    error_message TEXT,
    triggered_by TEXT NOT NULL, -- 'auto', 'manual', 'recovery'
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_safe_mode_events_time
ON safe_mode_events(created_at DESC);

-- Initialize single wallet state row
INSERT INTO wallet_state (id, public_key, status)
VALUES ('00000000-0000-0000-0000-000000000001', '', 'disconnected')
ON CONFLICT (id) DO NOTHING;

-- RLS Policies
ALTER TABLE wallet_state ENABLE ROW LEVEL SECURITY;
ALTER TABLE wallet_balance_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE token_balance_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE safe_mode_events ENABLE ROW LEVEL SECURITY;

-- Service role has full access
CREATE POLICY "Service role full access on wallet_state"
ON wallet_state FOR ALL TO service_role USING (true);

CREATE POLICY "Service role full access on wallet_balance_snapshots"
ON wallet_balance_snapshots FOR ALL TO service_role USING (true);

CREATE POLICY "Service role full access on token_balance_snapshots"
ON token_balance_snapshots FOR ALL TO service_role USING (true);

CREATE POLICY "Service role full access on safe_mode_events"
ON safe_mode_events FOR ALL TO service_role USING (true);
```

## Implementation Tasks

- [ ] Create `src/walltrack/models/wallet.py` with all data models
- [ ] Create `src/walltrack/config/wallet_settings.py` for secure config
- [ ] Create `src/walltrack/services/solana/wallet_client.py`
- [ ] Load wallet securely from environment (SecretStr)
- [ ] Implement transaction signing validation
- [ ] Add SOL balance retrieval
- [ ] Add SPL token balance retrieval
- [ ] Implement safe mode on connection failure
- [ ] Create `src/walltrack/api/routes/wallet.py` API endpoints
- [ ] Create `src/walltrack/dashboard/components/wallet_status.py`
- [ ] Add database migrations for wallet state tracking
- [ ] Write comprehensive unit tests

## Definition of Done

- [ ] Wallet loads securely from environment (private key as SecretStr)
- [ ] Connectivity validated before trading
- [ ] SOL and token balances displayed in dashboard
- [ ] Safe mode activates automatically on connection failure
- [ ] Manual safe mode toggle available in dashboard
- [ ] All API endpoints functional
- [ ] Unit tests pass with >90% coverage
- [ ] Private key NEVER appears in logs
