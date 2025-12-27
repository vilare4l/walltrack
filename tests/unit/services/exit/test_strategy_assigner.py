"""Tests for exit strategy assigner."""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from walltrack.services.exit.exit_strategy_service import ExitStrategy
from walltrack.services.exit.strategy_assigner import (
    ConvictionTier,
    ExitStrategyAssigner,
    reset_exit_strategy_assigner,
)


@pytest.fixture
def mock_config_service() -> MagicMock:
    """Create mock config service."""
    service = MagicMock()
    service.get = AsyncMock()
    return service


@pytest.fixture
def mock_strategy_service() -> MagicMock:
    """Create mock strategy service."""
    service = MagicMock()
    service.get = AsyncMock()
    service.get_active_by_name = AsyncMock()
    return service


@pytest.fixture
def assigner(
    mock_config_service: MagicMock,
    mock_strategy_service: MagicMock,
) -> ExitStrategyAssigner:
    """Create assigner with mocked services."""
    reset_exit_strategy_assigner()
    return ExitStrategyAssigner(mock_config_service, mock_strategy_service)


@pytest.fixture
def sample_strategy() -> ExitStrategy:
    """Create sample strategy."""
    now = datetime.now(UTC)
    return ExitStrategy(
        id="strategy-123",
        name="Test Strategy",
        description="Test",
        version=1,
        status="active",
        rules=[],
        max_hold_hours=168,
        stagnation_hours=6,
        stagnation_threshold_pct=Decimal("5.0"),
        created_at=now,
        updated_at=now,
    )


class TestConvictionTier:
    """Tests for ConvictionTier constants."""

    def test_standard_value(self) -> None:
        """Standard tier has correct value."""
        assert ConvictionTier.STANDARD == "standard"

    def test_high_value(self) -> None:
        """High tier has correct value."""
        assert ConvictionTier.HIGH == "high"

    def test_low_value(self) -> None:
        """Low tier has correct value."""
        assert ConvictionTier.LOW == "low"


class TestDetermineConvictionTier:
    """Tests for determine_conviction_tier method."""

    @pytest.mark.asyncio
    async def test_high_score_returns_high_tier(
        self,
        assigner: ExitStrategyAssigner,
        mock_config_service: MagicMock,
    ) -> None:
        """High score returns HIGH tier."""
        mock_config_service.get.return_value = Decimal("0.85")

        tier = await assigner.determine_conviction_tier(Decimal("0.90"))

        assert tier == ConvictionTier.HIGH

    @pytest.mark.asyncio
    async def test_threshold_score_returns_high_tier(
        self,
        assigner: ExitStrategyAssigner,
        mock_config_service: MagicMock,
    ) -> None:
        """Score at threshold returns HIGH tier."""
        mock_config_service.get.return_value = Decimal("0.85")

        tier = await assigner.determine_conviction_tier(Decimal("0.85"))

        assert tier == ConvictionTier.HIGH

    @pytest.mark.asyncio
    async def test_below_threshold_returns_standard_tier(
        self,
        assigner: ExitStrategyAssigner,
        mock_config_service: MagicMock,
    ) -> None:
        """Score below threshold returns STANDARD tier."""
        mock_config_service.get.return_value = Decimal("0.85")

        tier = await assigner.determine_conviction_tier(Decimal("0.75"))

        assert tier == ConvictionTier.STANDARD


class TestGetDefaultStrategyId:
    """Tests for get_default_strategy_id method."""

    @pytest.mark.asyncio
    async def test_high_tier_gets_high_conviction_id(
        self,
        assigner: ExitStrategyAssigner,
        mock_config_service: MagicMock,
    ) -> None:
        """High tier gets high conviction strategy ID."""
        mock_config_service.get.return_value = "high-strategy-id"

        strategy_id = await assigner.get_default_strategy_id(ConvictionTier.HIGH)

        assert strategy_id == "high-strategy-id"
        mock_config_service.get.assert_called_with(
            "exit.default_strategy_high_conviction_id",
            None,
        )

    @pytest.mark.asyncio
    async def test_standard_tier_gets_standard_id(
        self,
        assigner: ExitStrategyAssigner,
        mock_config_service: MagicMock,
    ) -> None:
        """Standard tier gets standard strategy ID."""
        mock_config_service.get.return_value = "standard-strategy-id"

        strategy_id = await assigner.get_default_strategy_id(ConvictionTier.STANDARD)

        assert strategy_id == "standard-strategy-id"
        mock_config_service.get.assert_called_with(
            "exit.default_strategy_standard_id",
            None,
        )

    @pytest.mark.asyncio
    async def test_returns_none_when_not_configured(
        self,
        assigner: ExitStrategyAssigner,
        mock_config_service: MagicMock,
    ) -> None:
        """Returns None when strategy not configured."""
        mock_config_service.get.return_value = None

        strategy_id = await assigner.get_default_strategy_id(ConvictionTier.STANDARD)

        assert strategy_id is None


class TestGetStrategyForPosition:
    """Tests for get_strategy_for_position method."""

    @pytest.mark.asyncio
    async def test_override_takes_precedence(
        self,
        assigner: ExitStrategyAssigner,
        mock_strategy_service: MagicMock,
        sample_strategy: ExitStrategy,
    ) -> None:
        """Override strategy takes precedence over default."""
        mock_strategy_service.get.return_value = sample_strategy

        strategy = await assigner.get_strategy_for_position(
            signal_score=Decimal("0.5"),
            override_strategy_id="override-id",
        )

        assert strategy == sample_strategy
        mock_strategy_service.get.assert_called_once_with("override-id")

    @pytest.mark.asyncio
    async def test_uses_default_when_no_override(
        self,
        assigner: ExitStrategyAssigner,
        mock_config_service: MagicMock,
        mock_strategy_service: MagicMock,
        sample_strategy: ExitStrategy,
    ) -> None:
        """Uses default strategy when no override provided."""
        mock_config_service.get.side_effect = [
            Decimal("0.85"),  # high_conviction_threshold
            "standard-id",  # default_strategy_standard_id
        ]
        mock_strategy_service.get.return_value = sample_strategy

        strategy = await assigner.get_strategy_for_position(
            signal_score=Decimal("0.5"),
        )

        assert strategy == sample_strategy

    @pytest.mark.asyncio
    async def test_fallback_to_active_by_name(
        self,
        assigner: ExitStrategyAssigner,
        mock_config_service: MagicMock,
        mock_strategy_service: MagicMock,
        sample_strategy: ExitStrategy,
    ) -> None:
        """Falls back to active strategy by name when default not found."""
        mock_config_service.get.side_effect = [
            Decimal("0.85"),  # high_conviction_threshold
            None,  # default_strategy_standard_id not configured
        ]
        mock_strategy_service.get_active_by_name.return_value = sample_strategy

        strategy = await assigner.get_strategy_for_position(
            signal_score=Decimal("0.5"),
        )

        assert strategy == sample_strategy
        mock_strategy_service.get_active_by_name.assert_called_once_with("Standard")

    @pytest.mark.asyncio
    async def test_high_conviction_fallback_name(
        self,
        assigner: ExitStrategyAssigner,
        mock_config_service: MagicMock,
        mock_strategy_service: MagicMock,
        sample_strategy: ExitStrategy,
    ) -> None:
        """High conviction uses 'High Conviction' fallback name."""
        mock_config_service.get.side_effect = [
            Decimal("0.85"),  # high_conviction_threshold
            None,  # default_strategy_high_conviction_id not configured
        ]
        mock_strategy_service.get_active_by_name.return_value = sample_strategy

        strategy = await assigner.get_strategy_for_position(
            signal_score=Decimal("0.90"),
        )

        assert strategy == sample_strategy
        mock_strategy_service.get_active_by_name.assert_called_once_with(
            "High Conviction"
        )

    @pytest.mark.asyncio
    async def test_returns_none_when_no_strategy_available(
        self,
        assigner: ExitStrategyAssigner,
        mock_config_service: MagicMock,
        mock_strategy_service: MagicMock,
    ) -> None:
        """Returns None when no strategy available."""
        mock_config_service.get.side_effect = [
            Decimal("0.85"),  # high_conviction_threshold
            None,  # no default configured
        ]
        mock_strategy_service.get_active_by_name.return_value = None

        strategy = await assigner.get_strategy_for_position(
            signal_score=Decimal("0.5"),
        )

        assert strategy is None

    @pytest.mark.asyncio
    async def test_override_not_found_falls_back(
        self,
        assigner: ExitStrategyAssigner,
        mock_config_service: MagicMock,
        mock_strategy_service: MagicMock,
        sample_strategy: ExitStrategy,
    ) -> None:
        """When override not found, falls back to default."""
        # First call (override) returns None, second call (default) returns strategy
        mock_strategy_service.get.side_effect = [None, sample_strategy]
        mock_config_service.get.side_effect = [
            Decimal("0.85"),  # high_conviction_threshold
            "default-id",  # default_strategy_standard_id
        ]

        strategy = await assigner.get_strategy_for_position(
            signal_score=Decimal("0.5"),
            override_strategy_id="invalid-id",
        )

        assert strategy == sample_strategy
