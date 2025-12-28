"""Exit strategy assignment based on conviction tier."""

from decimal import Decimal

import structlog

from walltrack.services.config.config_service import ConfigService, get_config_service
from walltrack.services.exit.exit_strategy_service import (
    ExitStrategy,
    ExitStrategyService,
    get_exit_strategy_service,
)

logger = structlog.get_logger(__name__)


class ConvictionTier:
    """Conviction tier definitions."""

    STANDARD = "standard"
    HIGH = "high"
    LOW = "low"


class ExitStrategyAssigner:
    """
    Assigns exit strategies based on conviction tier.

    Uses ConfigService for default strategy IDs.
    Supports manual override.
    """

    def __init__(
        self,
        config_service: ConfigService,
        strategy_service: ExitStrategyService,
    ) -> None:
        self.config = config_service
        self.strategy_service = strategy_service

    async def determine_conviction_tier(
        self,
        signal_score: Decimal,
    ) -> str:
        """
        Determine conviction tier from signal score.

        Args:
            signal_score: The signal score (0-1)

        Returns:
            ConvictionTier value
        """
        high_threshold = await self.config.get(
            "trading.high_conviction_threshold",
            Decimal("0.85"),
        )

        if signal_score >= high_threshold:
            return ConvictionTier.HIGH

        return ConvictionTier.STANDARD

    async def get_default_strategy_id(
        self,
        conviction_tier: str,
    ) -> str | None:
        """
        Get default strategy ID for a conviction tier.

        Args:
            conviction_tier: The conviction tier

        Returns:
            Strategy ID or None if not configured
        """
        if conviction_tier == ConvictionTier.HIGH:
            return await self.config.get(
                "exit.default_strategy_high_conviction_id",
                None,
            )
        return await self.config.get(
            "exit.default_strategy_standard_id",
            None,
        )

    async def get_strategy_for_position(
        self,
        signal_score: Decimal,
        override_strategy_id: str | None = None,
    ) -> ExitStrategy | None:
        """
        Get the appropriate exit strategy for a position.

        Args:
            signal_score: The signal score
            override_strategy_id: Optional manual override

        Returns:
            ExitStrategy or None
        """
        # Check for manual override
        if override_strategy_id:
            strategy = await self.strategy_service.get(override_strategy_id)
            if strategy:
                logger.info(
                    "strategy_override_used",
                    strategy_id=override_strategy_id,
                    strategy_name=strategy.name,
                )
                return strategy
            logger.warning(
                "override_strategy_not_found",
                strategy_id=override_strategy_id,
            )

        # Determine tier and get default
        tier = await self.determine_conviction_tier(signal_score)
        default_id = await self.get_default_strategy_id(tier)

        if default_id:
            strategy = await self.strategy_service.get(default_id)
            if strategy:
                logger.debug(
                    "default_strategy_assigned",
                    tier=tier,
                    strategy_id=default_id,
                    strategy_name=strategy.name,
                )
                return strategy
            logger.warning(
                "default_strategy_not_found",
                tier=tier,
                strategy_id=default_id,
            )

        # Fallback to active strategy by name
        fallback_name = "High Conviction" if tier == ConvictionTier.HIGH else "Standard"
        strategy = await self.strategy_service.get_active_by_name(fallback_name)

        if strategy:
            logger.info(
                "fallback_strategy_used",
                tier=tier,
                strategy_name=strategy.name,
            )
            return strategy

        logger.error(
            "no_strategy_available",
            tier=tier,
        )
        return None

    async def assign_strategy_to_position(
        self,
        position_id: str,
        signal_score: Decimal,
        override_strategy_id: str | None = None,
    ) -> str | None:
        """
        Assign strategy to a position and update database.

        Args:
            position_id: The position ID
            signal_score: The signal score
            override_strategy_id: Optional manual override

        Returns:
            Assigned strategy ID or None
        """
        strategy = await self.get_strategy_for_position(
            signal_score=signal_score,
            override_strategy_id=override_strategy_id,
        )

        if not strategy:
            return None

        # Update position in database
        from walltrack.data.supabase.client import get_supabase_client  # noqa: PLC0415

        client = await get_supabase_client()

        await (
            client.table("positions")
            .update({"exit_strategy_id": strategy.id})
            .eq("id", position_id)
            .execute()
        )

        logger.info(
            "strategy_assigned_to_position",
            position_id=position_id,
            strategy_id=strategy.id,
            strategy_name=strategy.name,
        )

        return strategy.id

    async def change_position_strategy(
        self,
        position_id: str,
        new_strategy_id: str,
    ) -> bool:
        """
        Change the exit strategy for an existing position.

        Args:
            position_id: The position ID
            new_strategy_id: The new strategy ID

        Returns:
            True if successful
        """
        strategy = await self.strategy_service.get(new_strategy_id)
        if not strategy:
            logger.error("strategy_not_found", strategy_id=new_strategy_id)
            return False

        from walltrack.data.supabase.client import get_supabase_client  # noqa: PLC0415

        client = await get_supabase_client()

        result = await (
            client.table("positions")
            .update(
                {
                    "exit_strategy_id": new_strategy_id,
                    "exit_strategy_changed_at": "now()",
                }
            )
            .eq("id", position_id)
            .execute()
        )

        if result.data:
            logger.info(
                "position_strategy_changed",
                position_id=position_id,
                new_strategy_id=new_strategy_id,
                strategy_name=strategy.name,
            )
            return True

        return False


# Singleton
_assigner: ExitStrategyAssigner | None = None


async def get_exit_strategy_assigner() -> ExitStrategyAssigner:
    """Get or create exit strategy assigner singleton."""
    global _assigner

    if _assigner is None:
        config = await get_config_service()
        strategy_service = await get_exit_strategy_service()
        _assigner = ExitStrategyAssigner(config, strategy_service)

    return _assigner


def reset_exit_strategy_assigner() -> None:
    """Reset the singleton (for testing)."""
    global _assigner
    _assigner = None
