"""Wallet-related Pydantic models.

This module defines data models for wallet validation and operations.
All models use Pydantic BaseModel (not dataclass) per architecture rules.
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class WalletValidationResult(BaseModel):
    """Result of wallet address validation.

    Attributes:
        is_valid: Whether the wallet address is valid.
        address: The validated wallet address.
        exists_on_chain: Whether the wallet exists on Solana network.
        error_message: Error description if validation failed.

    Example:
        result = WalletValidationResult(
            is_valid=True,
            address="9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM",
            exists_on_chain=True,
        )
    """

    is_valid: bool = Field(description="Whether the wallet address is valid")
    address: str = Field(description="The validated wallet address")
    exists_on_chain: bool = Field(
        default=False, description="Whether the wallet exists on Solana network"
    )
    error_message: str | None = Field(
        default=None, description="Error description if validation failed"
    )


class Wallet(BaseModel):
    """Wallet model for database storage.

    Represents a discovered smart money wallet from token holder analysis.
    Maps directly to the walltrack.wallets table schema.

    Attributes:
        wallet_address: Solana wallet address (PRIMARY KEY, unique).
        discovery_date: When this wallet was first discovered.
        token_source: First token address that led to discovery.
        score: Wallet performance score (0.0-1.0, calculated in Epic 5).
        win_rate: Win rate percentage (0.0-100.0, calculated in Story 3.2).
        decay_status: Activity status (ok, flagged, downgraded, dormant).
        is_blacklisted: TRUE if wallet is blacklisted (Story 3.5).
        pnl_total: Total PnL in SOL (Story 3.2).
        entry_delay_seconds: Average seconds between token launch and first buy (Story 3.2).
        total_trades: Total number of trades analyzed (Story 3.2).
        metrics_last_updated: Last metrics calculation timestamp (Story 3.2).
        metrics_confidence: Metrics confidence level: unknown, low, medium, high (Story 3.2).
        position_size_style: Position size classification: small, medium, large (Story 3.3).
        position_size_avg: Average position size in SOL (Story 3.3).
        hold_duration_avg: Average hold duration in seconds (Story 3.3).
        hold_duration_style: Hold duration style: scalper, day_trader, swing_trader, position_trader (Story 3.3).
        behavioral_last_updated: Last behavioral profiling timestamp (Story 3.3).
        behavioral_confidence: Behavioral confidence: unknown, low, medium, high (Story 3.3).
        consecutive_losses: Number of consecutive losing trades (Story 3.4).
        last_activity_date: Last trade activity date for dormancy detection (Story 3.4).
        rolling_win_rate: Win rate over most recent 20 trades (Story 3.4).
        created_at: Record creation timestamp.
        updated_at: Last modification timestamp.

    Example:
        wallet = Wallet(
            wallet_address="9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",
            discovery_date=datetime.now(),
            token_source="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
            score=0.0,
            win_rate=78.5,
            pnl_total=15.25,
            entry_delay_seconds=3600,
            total_trades=25,
            metrics_confidence="high",
        )
    """

    wallet_address: str = Field(description="Solana wallet address (PRIMARY KEY)")
    discovery_date: datetime = Field(description="When this wallet was first discovered")
    token_source: str = Field(description="First token address that led to discovery")
    score: float = Field(default=0.0, description="Wallet performance score (0.0-1.0)")
    win_rate: float = Field(default=0.0, description="Win rate percentage (0.0-100.0)")
    decay_status: str = Field(
        default="ok", description="Activity status: ok, flagged, downgraded, dormant"
    )
    is_blacklisted: bool = Field(default=False, description="TRUE if wallet is blacklisted")
    pnl_total: float | None = Field(default=None, description="Total PnL in SOL")
    entry_delay_seconds: int | None = Field(
        default=None, description="Average seconds between token launch and first buy"
    )
    total_trades: int = Field(default=0, description="Total number of trades analyzed")
    metrics_last_updated: datetime | None = Field(
        default=None, description="Last metrics calculation timestamp"
    )
    metrics_confidence: str = Field(
        default="unknown", description="Metrics confidence: unknown, low, medium, high"
    )
    # Behavioral profiling fields (Story 3.3)
    position_size_style: str | None = Field(
        default=None, description="Position size classification: small, medium, large"
    )
    position_size_avg: Decimal | None = Field(
        default=None, description="Average position size in SOL"
    )
    hold_duration_avg: int | None = Field(
        default=None, description="Average hold duration in seconds"
    )
    hold_duration_style: str | None = Field(
        default=None,
        description="Hold duration classification: scalper, day_trader, swing_trader, position_trader",
    )
    behavioral_last_updated: datetime | None = Field(
        default=None, description="Last behavioral profiling timestamp"
    )
    behavioral_confidence: str = Field(
        default="unknown",
        description="Behavioral profiling confidence: unknown, low, medium, high",
    )
    # Decay detection fields (Story 3.4)
    consecutive_losses: int = Field(
        default=0, description="Number of consecutive losing trades (AC2)"
    )
    last_activity_date: datetime | None = Field(
        default=None, description="Last trade activity date for dormancy detection (AC3)"
    )
    rolling_win_rate: Decimal | None = Field(
        default=None, description="Win rate over most recent 20 trades (AC1)"
    )
    created_at: datetime | None = Field(default=None, description="Record creation timestamp")
    updated_at: datetime | None = Field(default=None, description="Last modification timestamp")

    @field_validator("wallet_address", "token_source")
    @classmethod
    def validate_solana_address(cls, v: str) -> str:
        """Validate Solana address format (base58, 32-44 characters).

        Args:
            v: Address string to validate.

        Returns:
            Validated address string.

        Raises:
            ValueError: If address format is invalid.
        """
        if not (32 <= len(v) <= 44):
            msg = f"Invalid Solana address length: {len(v)}"
            raise ValueError(msg)

        base58_chars = set("123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz")
        if not set(v).issubset(base58_chars):
            msg = "Invalid Solana address: contains non-base58 characters"
            raise ValueError(msg)

        return v

    @field_validator("decay_status")
    @classmethod
    def validate_decay_status(cls, v: str) -> str:
        """Validate decay_status is one of allowed values.

        Args:
            v: Status string to validate.

        Returns:
            Validated status string.

        Raises:
            ValueError: If status is not in allowed values.
        """
        allowed = {"ok", "flagged", "downgraded", "dormant"}
        if v not in allowed:
            msg = f"Invalid decay_status: {v}. Must be one of {allowed}"
            raise ValueError(msg)
        return v

    @field_validator("score")
    @classmethod
    def validate_score_range(cls, v: float) -> float:
        """Validate score is between 0.0 and 1.0.

        Args:
            v: Float value to validate.

        Returns:
            Validated float value.

        Raises:
            ValueError: If value is outside 0.0-1.0 range.
        """
        if not 0.0 <= v <= 1.0:
            msg = f"Score must be between 0.0 and 1.0, got {v}"
            raise ValueError(msg)
        return v

    @field_validator("win_rate")
    @classmethod
    def validate_win_rate_range(cls, v: float) -> float:
        """Validate win_rate is between 0.0 and 100.0.

        Args:
            v: Float value to validate.

        Returns:
            Validated float value.

        Raises:
            ValueError: If value is outside 0.0-100.0 range.
        """
        if not 0.0 <= v <= 100.0:
            msg = f"Win rate must be between 0.0 and 100.0, got {v}"
            raise ValueError(msg)
        return v

    @field_validator("entry_delay_seconds")
    @classmethod
    def validate_entry_delay(cls, v: int | None) -> int | None:
        """Validate entry_delay_seconds is >= 0.

        Args:
            v: Integer value to validate.

        Returns:
            Validated integer value.

        Raises:
            ValueError: If value is negative.
        """
        if v is not None and v < 0:
            msg = f"Entry delay seconds must be >= 0, got {v}"
            raise ValueError(msg)
        return v

    @field_validator("metrics_confidence")
    @classmethod
    def validate_metrics_confidence(cls, v: str) -> str:
        """Validate metrics_confidence is one of allowed values.

        Args:
            v: String value to validate.

        Returns:
            Validated string value.

        Raises:
            ValueError: If value is not in allowed values.
        """
        allowed = {"unknown", "low", "medium", "high"}
        if v not in allowed:
            msg = f"Invalid metrics_confidence: {v}. Must be one of {allowed}"
            raise ValueError(msg)
        return v

    @field_validator("position_size_avg")
    @classmethod
    def validate_position_size_avg(cls, v: Decimal | None) -> Decimal | None:
        """Validate position_size_avg is >= 0.

        Args:
            v: Decimal value to validate.

        Returns:
            Validated Decimal value.

        Raises:
            ValueError: If value is negative.
        """
        if v is not None and v < 0:
            msg = f"Position size average must be >= 0, got {v}"
            raise ValueError(msg)
        return v

    @field_validator("hold_duration_avg")
    @classmethod
    def validate_hold_duration_avg(cls, v: int | None) -> int | None:
        """Validate hold_duration_avg is >= 0.

        Args:
            v: Integer value to validate.

        Returns:
            Validated integer value.

        Raises:
            ValueError: If value is negative.
        """
        if v is not None and v < 0:
            msg = f"Hold duration average must be >= 0, got {v}"
            raise ValueError(msg)
        return v

    @field_validator("position_size_style")
    @classmethod
    def validate_position_size_style(cls, v: str | None) -> str | None:
        """Validate position_size_style is one of allowed values.

        Args:
            v: String value to validate.

        Returns:
            Validated string value.

        Raises:
            ValueError: If value is not in allowed values.
        """
        if v is not None:
            allowed = {"small", "medium", "large"}
            if v not in allowed:
                msg = f"Invalid position_size_style: {v}. Must be one of {allowed}"
                raise ValueError(msg)
        return v

    @field_validator("hold_duration_style")
    @classmethod
    def validate_hold_duration_style(cls, v: str | None) -> str | None:
        """Validate hold_duration_style is one of allowed values.

        Args:
            v: String value to validate.

        Returns:
            Validated string value.

        Raises:
            ValueError: If value is not in allowed values.
        """
        if v is not None:
            allowed = {"scalper", "day_trader", "swing_trader", "position_trader"}
            if v not in allowed:
                msg = f"Invalid hold_duration_style: {v}. Must be one of {allowed}"
                raise ValueError(msg)
        return v

    @field_validator("behavioral_confidence")
    @classmethod
    def validate_behavioral_confidence(cls, v: str) -> str:
        """Validate behavioral_confidence is one of allowed values.

        Args:
            v: String value to validate.

        Returns:
            Validated string value.

        Raises:
            ValueError: If value is not in allowed values.
        """
        allowed = {"unknown", "low", "medium", "high"}
        if v not in allowed:
            msg = f"Invalid behavioral_confidence: {v}. Must be one of {allowed}"
            raise ValueError(msg)
        return v


class WalletCreate(BaseModel):
    """Model for creating a new wallet record.

    Subset of Wallet model containing only fields required for insertion.
    Auto-generated fields (created_at, updated_at, discovery_date) are excluded.

    Attributes:
        wallet_address: Solana wallet address (PRIMARY KEY, unique).
        token_source: First token address that led to discovery.
        score: Optional wallet performance score (defaults to 0.0).
        win_rate: Optional win rate percentage (defaults to 0.0).
        decay_status: Optional activity status (defaults to 'ok').
        is_blacklisted: Optional blacklist flag (defaults to False).

    Example:
        wallet_create = WalletCreate(
            wallet_address="9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",
            token_source="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
        )
    """

    wallet_address: str = Field(description="Solana wallet address (PRIMARY KEY)")
    token_source: str = Field(description="First token address that led to discovery")
    score: float = Field(default=0.0, description="Wallet performance score (0.0-1.0)")
    win_rate: float = Field(default=0.0, description="Win rate percentage (0.0-1.0)")
    decay_status: str = Field(
        default="ok", description="Activity status: ok, flagged, downgraded, dormant"
    )
    is_blacklisted: bool = Field(default=False, description="TRUE if wallet is blacklisted")

    @field_validator("wallet_address", "token_source")
    @classmethod
    def validate_solana_address(cls, v: str) -> str:
        """Validate Solana address format (base58, 32-44 characters)."""
        if not (32 <= len(v) <= 44):
            msg = f"Invalid Solana address length: {len(v)}"
            raise ValueError(msg)

        base58_chars = set("123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz")
        if not set(v).issubset(base58_chars):
            msg = "Invalid Solana address: contains non-base58 characters"
            raise ValueError(msg)

        return v

    @field_validator("decay_status")
    @classmethod
    def validate_decay_status(cls, v: str) -> str:
        """Validate decay_status is one of allowed values."""
        allowed = {"ok", "flagged", "downgraded", "dormant"}
        if v not in allowed:
            msg = f"Invalid decay_status: {v}. Must be one of {allowed}"
            raise ValueError(msg)
        return v

    @field_validator("score", "win_rate")
    @classmethod
    def validate_percentage_range(cls, v: float) -> float:
        """Validate score/win_rate is between 0.0 and 1.0."""
        if not 0.0 <= v <= 1.0:
            msg = f"Score/win_rate must be between 0.0 and 1.0, got {v}"
            raise ValueError(msg)
        return v


class WalletUpdate(BaseModel):
    """Model for updating an existing wallet record.

    All fields are optional - only provided fields will be updated.
    Primary key (wallet_address) cannot be updated.

    Attributes:
        score: Optional wallet performance score (0.0-1.0).
        win_rate: Optional win rate percentage (0.0-100.0).
        decay_status: Optional activity status.
        is_blacklisted: Optional blacklist flag.
        pnl_total: Optional total PnL in SOL.
        entry_delay_seconds: Optional average entry delay.
        total_trades: Optional total trades count.
        metrics_last_updated: Optional metrics update timestamp.
        metrics_confidence: Optional confidence level.

    Example:
        wallet_update = WalletUpdate(
            score=0.0,
            win_rate=72.5,
            pnl_total=25.8,
            total_trades=30,
            metrics_confidence="high",
        )
    """

    score: float | None = Field(default=None, description="Wallet performance score (0.0-1.0)")
    win_rate: float | None = Field(default=None, description="Win rate percentage (0.0-100.0)")
    decay_status: str | None = Field(
        default=None, description="Activity status: ok, flagged, downgraded, dormant"
    )
    is_blacklisted: bool | None = Field(default=None, description="TRUE if wallet is blacklisted")
    pnl_total: float | None = Field(default=None, description="Total PnL in SOL")
    entry_delay_seconds: int | None = Field(
        default=None, description="Average seconds between token launch and first buy"
    )
    total_trades: int | None = Field(default=None, description="Total number of trades analyzed")
    metrics_last_updated: datetime | None = Field(
        default=None, description="Last metrics calculation timestamp"
    )
    metrics_confidence: str | None = Field(
        default=None, description="Metrics confidence: unknown, low, medium, high"
    )

    @field_validator("decay_status")
    @classmethod
    def validate_decay_status(cls, v: str | None) -> str | None:
        """Validate decay_status is one of allowed values."""
        if v is None:
            return v
        allowed = {"ok", "flagged", "downgraded", "dormant"}
        if v not in allowed:
            msg = f"Invalid decay_status: {v}. Must be one of {allowed}"
            raise ValueError(msg)
        return v

    @field_validator("score")
    @classmethod
    def validate_score_range(cls, v: float | None) -> float | None:
        """Validate score is between 0.0 and 1.0."""
        if v is None:
            return v
        if not 0.0 <= v <= 1.0:
            msg = f"Score must be between 0.0 and 1.0, got {v}"
            raise ValueError(msg)
        return v

    @field_validator("win_rate")
    @classmethod
    def validate_win_rate_range(cls, v: float | None) -> float | None:
        """Validate win_rate is between 0.0 and 100.0."""
        if v is None:
            return v
        if not 0.0 <= v <= 100.0:
            msg = f"Win rate must be between 0.0 and 100.0, got {v}"
            raise ValueError(msg)
        return v

    @field_validator("entry_delay_seconds")
    @classmethod
    def validate_entry_delay(cls, v: int | None) -> int | None:
        """Validate entry_delay_seconds is >= 0."""
        if v is not None and v < 0:
            msg = f"Entry delay seconds must be >= 0, got {v}"
            raise ValueError(msg)
        return v

    @field_validator("metrics_confidence")
    @classmethod
    def validate_metrics_confidence(cls, v: str | None) -> str | None:
        """Validate metrics_confidence is one of allowed values."""
        if v is None:
            return v
        allowed = {"unknown", "low", "medium", "high"}
        if v not in allowed:
            msg = f"Invalid metrics_confidence: {v}. Must be one of {allowed}"
            raise ValueError(msg)
        return v


class PerformanceMetrics(BaseModel):
    """Performance metrics calculated from wallet transaction history.

    Attributes:
        win_rate: Win rate percentage (0.0-100.0).
        pnl_total: Total PnL in SOL.
        entry_delay_seconds: Average seconds between token launch and first buy.
        total_trades: Total number of trades analyzed.
        confidence: Metrics confidence level (high: 20+ trades, medium: 5-19, low: <5).

    Example:
        metrics = PerformanceMetrics(
            win_rate=78.5,
            pnl_total=15.25,
            entry_delay_seconds=3600,
            total_trades=25,
            confidence="high",
        )
    """

    win_rate: float = Field(description="Win rate percentage (0.0-100.0)")
    pnl_total: float = Field(description="Total PnL in SOL")
    entry_delay_seconds: int = Field(
        description="Average seconds between token launch and first buy"
    )
    total_trades: int = Field(description="Total number of trades analyzed")
    confidence: str = Field(description="Metrics confidence: unknown, low, medium, high")

    @field_validator("win_rate")
    @classmethod
    def validate_win_rate_range(cls, v: float) -> float:
        """Validate win_rate is between 0.0 and 100.0."""
        if not 0.0 <= v <= 100.0:
            msg = f"Win rate must be between 0.0 and 100.0, got {v}"
            raise ValueError(msg)
        return v

    @field_validator("entry_delay_seconds")
    @classmethod
    def validate_entry_delay(cls, v: int) -> int:
        """Validate entry_delay_seconds is >= 0."""
        if v < 0:
            msg = f"Entry delay seconds must be >= 0, got {v}"
            raise ValueError(msg)
        return v

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: str) -> str:
        """Validate confidence is one of allowed values."""
        allowed = {"unknown", "low", "medium", "high"}
        if v not in allowed:
            msg = f"Invalid confidence: {v}. Must be one of {allowed}"
            raise ValueError(msg)
        return v

    @classmethod
    def calculate_confidence(cls, total_trades: int) -> str:
        """Calculate confidence level based on total trades.

        Args:
            total_trades: Total number of trades analyzed.

        Returns:
            Confidence level string.
        """
        if total_trades >= 20:
            return "high"
        elif total_trades >= 5:
            return "medium"
        elif total_trades > 0:
            return "low"
        else:
            return "unknown"
