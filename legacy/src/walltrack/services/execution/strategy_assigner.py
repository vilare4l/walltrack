"""Score-based strategy assignment service.

Assigns exit strategies based on signal conviction scores
or manual operator overrides.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from walltrack.models.strategy_assignment import (
    AssignmentSource,
    ManualOverride,
    OverrideLog,
    StrategyAssignment,
    StrategyMappingConfig,
)

if TYPE_CHECKING:
    from walltrack.data.supabase.repositories.exit_strategy_repo import (
        ExitStrategyRepository,
    )
    from walltrack.models.exit_strategy import ExitStrategy

logger = structlog.get_logger()


class StrategyAssigner:
    """Assigns exit strategies based on signal score or manual override.

    Assignment priority:
    1. Manual override (if exists)
    2. Score-based mapping
    3. Default fallback
    """

    def __init__(
        self,
        strategy_repo: ExitStrategyRepository | None = None,
        mapping_config: StrategyMappingConfig | None = None,
    ) -> None:
        """Initialize strategy assigner.

        Args:
            strategy_repo: Repository for exit strategies
            mapping_config: Score-to-strategy mapping configuration
        """
        self._strategy_repo = strategy_repo
        self._config = mapping_config or StrategyMappingConfig()
        self._override_cache: dict[str, ManualOverride] = {}
        self._override_logs: list[OverrideLog] = []

    async def initialize(self) -> None:
        """Initialize dependencies."""
        if self._strategy_repo is None:
            from walltrack.data.supabase.repositories.exit_strategy_repo import (  # noqa: PLC0415
                get_exit_strategy_repository,
            )

            self._strategy_repo = await get_exit_strategy_repository()

        logger.info("strategy_assigner_initialized")

    def set_mapping_config(self, config: StrategyMappingConfig) -> None:
        """Update the mapping configuration.

        Args:
            config: New mapping configuration
        """
        self._config = config
        logger.info(
            "strategy_mapping_updated",
            mappings_count=len(config.mappings),
            default_strategy=config.default_strategy_id,
            enabled=config.enabled,
        )

    def get_mapping_config(self) -> StrategyMappingConfig:
        """Get the current mapping configuration.

        Returns:
            Current mapping configuration
        """
        return self._config

    def assign_strategy(
        self,
        position_id: str,
        signal_id: str,
        signal_score: float,
    ) -> StrategyAssignment:
        """Assign exit strategy to a new position.

        Args:
            position_id: Position ID
            signal_id: Signal ID
            signal_score: Signal conviction score (0.0 to 1.0)

        Returns:
            StrategyAssignment with details
        """
        # 1. Check for manual override
        override = self._override_cache.get(position_id)
        if override:
            logger.info(
                "strategy_assigned_manual_override",
                position_id=position_id[:8],
                strategy_id=override.new_strategy_id,
                override_by=override.override_by,
            )

            return StrategyAssignment(
                position_id=position_id,
                signal_id=signal_id,
                signal_score=signal_score,
                assigned_strategy_id=override.new_strategy_id,
                assignment_source=AssignmentSource.MANUAL_OVERRIDE,
                override_by=override.override_by,
                override_reason=override.reason,
            )

        # 2. Get strategy based on score
        strategy_id, is_default = self._config.get_strategy_for_score(signal_score)

        source = (
            AssignmentSource.DEFAULT_FALLBACK
            if is_default
            else AssignmentSource.SCORE_BASED
        )

        # Find matched range for logging
        matched_range = None
        if not is_default:
            for mapping in self._config.mappings:
                if mapping.contains(signal_score):
                    matched_range = mapping
                    break

        logger.info(
            "strategy_assigned",
            position_id=position_id[:8],
            signal_score=round(signal_score, 3),
            strategy_id=strategy_id,
            source=source.value,
            matched_range=(
                f"{matched_range.min_score:.2f}-{matched_range.max_score:.2f}"
                if matched_range
                else None
            ),
        )

        return StrategyAssignment(
            position_id=position_id,
            signal_id=signal_id,
            signal_score=signal_score,
            assigned_strategy_id=strategy_id,
            assignment_source=source,
            matched_range=matched_range,
        )

    async def get_strategy(self, strategy_id: str) -> ExitStrategy | None:
        """Get exit strategy by ID.

        Args:
            strategy_id: Strategy ID

        Returns:
            ExitStrategy or None if not found
        """
        return await self._strategy_repo.get_by_id(strategy_id)

    def apply_manual_override(
        self,
        override: ManualOverride,
        current_strategy_id: str,
    ) -> OverrideLog:
        """Apply manual strategy override to a position.

        Args:
            override: Override request
            current_strategy_id: Current strategy ID

        Returns:
            OverrideLog entry
        """
        # Store override
        self._override_cache[override.position_id] = override

        # Create log entry
        log = OverrideLog(
            position_id=override.position_id,
            previous_strategy_id=current_strategy_id,
            new_strategy_id=override.new_strategy_id,
            override_by=override.override_by,
            reason=override.reason,
        )
        self._override_logs.append(log)

        logger.info(
            "strategy_override_applied",
            position_id=override.position_id[:8],
            previous_strategy=current_strategy_id,
            new_strategy=override.new_strategy_id,
            override_by=override.override_by,
            reason=override.reason,
        )

        return log

    def clear_override(self, position_id: str) -> None:
        """Clear manual override for a position.

        Args:
            position_id: Position ID
        """
        if position_id in self._override_cache:
            del self._override_cache[position_id]
            logger.debug("strategy_override_cleared", position_id=position_id[:8])

    def has_override(self, position_id: str) -> bool:
        """Check if position has a manual override.

        Args:
            position_id: Position ID

        Returns:
            True if override exists
        """
        return position_id in self._override_cache

    def get_override_logs(self, position_id: str | None = None) -> list[OverrideLog]:
        """Get override logs.

        Args:
            position_id: Optional filter by position ID

        Returns:
            List of override logs
        """
        if position_id:
            return [log for log in self._override_logs if log.position_id == position_id]
        return self._override_logs.copy()

    def preview_assignment(self, score: float) -> tuple[str, bool, str]:
        """Preview which strategy would be assigned for a given score.

        Args:
            score: Signal conviction score

        Returns:
            Tuple of (strategy_id, is_default, source_description)
        """
        strategy_id, is_default = self._config.get_strategy_for_score(score)

        if not self._config.enabled:
            source = "disabled (using default)"
        elif is_default:
            source = "default fallback"
        else:
            for mapping in self._config.mappings:
                if mapping.contains(score):
                    source = f"range {mapping.min_score:.2f}-{mapping.max_score:.2f}"
                    break
            else:
                source = "unknown"

        return strategy_id, is_default, source


# Singleton
_strategy_assigner: StrategyAssigner | None = None


async def get_strategy_assigner() -> StrategyAssigner:
    """Get or create strategy assigner singleton."""
    global _strategy_assigner
    if _strategy_assigner is None:
        _strategy_assigner = StrategyAssigner()
        await _strategy_assigner.initialize()
    return _strategy_assigner
