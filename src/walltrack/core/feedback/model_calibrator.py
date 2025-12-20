"""Scoring model calibration service."""

from datetime import UTC, datetime
from decimal import Decimal
from statistics import correlation
from uuid import UUID, uuid4

import structlog

from .calibration_models import (
    ApplyWeightsRequest,
    AutoCalibrationConfig,
    CalibrationAnalysis,
    CalibrationStatus,
    CalibrationSuggestion,
    FactorCorrelation,
    ScoringFactor,
    WeightArchive,
    WeightSet,
    WeightSuggestion,
)

logger = structlog.get_logger()


class ModelCalibrator:
    """Calibrates scoring model weights based on trade outcomes."""

    def __init__(
        self,
        supabase_client,
        auto_config: AutoCalibrationConfig | None = None,
    ):
        """Initialize ModelCalibrator.

        Args:
            supabase_client: Supabase client instance
            auto_config: Optional auto-calibration configuration
        """
        self.supabase = supabase_client
        self.auto_config = auto_config or AutoCalibrationConfig()
        self._current_weights: WeightSet | None = None
        self._suggestions_cache: dict[UUID, dict] = {}

    async def run_analysis(
        self,
        min_trades: int = 100,
    ) -> CalibrationAnalysis:
        """Run calibration analysis on trade history.

        Args:
            min_trades: Minimum trades required for valid analysis

        Returns:
            CalibrationAnalysis with correlations and suggestions
        """
        analysis_id = uuid4()

        # Load trade data with factor scores
        trades = await self._load_trade_data()

        if len(trades) < min_trades:
            logger.warning(
                "insufficient_trades_for_calibration",
                trade_count=len(trades),
                min_required=min_trades,
            )

        # Calculate correlations for each factor
        correlations = []
        for factor in ScoringFactor:
            correlation_result = self._calculate_factor_correlation(trades, factor)
            correlations.append(correlation_result)

        # Get current weights
        current_weights = await self.get_current_weights()

        # Generate suggested weights
        suggested_weights = self._generate_suggested_weights(correlations, current_weights)

        # Estimate improvement
        improvement = self._estimate_improvement(trades, current_weights, suggested_weights)

        analysis = CalibrationAnalysis(
            id=analysis_id,
            trade_count=len(trades),
            min_trades_required=min_trades,
            correlations=correlations,
            current_weights=current_weights,
            suggested_weights=suggested_weights,
            estimated_improvement=improvement,
        )

        # Persist analysis
        await self._save_analysis(analysis)

        logger.info(
            "calibration_analysis_complete",
            analysis_id=str(analysis_id),
            trade_count=len(trades),
            estimated_improvement=float(improvement),
        )

        return analysis

    async def create_suggestion(
        self,
        analysis: CalibrationAnalysis,
    ) -> CalibrationSuggestion:
        """Create a calibration suggestion from analysis.

        Args:
            analysis: Completed calibration analysis

        Returns:
            CalibrationSuggestion for operator review
        """
        suggestion_id = uuid4()

        # Build individual factor suggestions
        suggestions = []
        factor_mapping = {
            ScoringFactor.WALLET_SCORE: (
                "wallet_weight",
                analysis.current_weights.wallet_weight,
                analysis.suggested_weights.wallet_weight,
            ),
            ScoringFactor.CLUSTER_SCORE: (
                "cluster_weight",
                analysis.current_weights.cluster_weight,
                analysis.suggested_weights.cluster_weight,
            ),
            ScoringFactor.TOKEN_SCORE: (
                "token_weight",
                analysis.current_weights.token_weight,
                analysis.suggested_weights.token_weight,
            ),
            ScoringFactor.CONTEXT_SCORE: (
                "context_weight",
                analysis.current_weights.context_weight,
                analysis.suggested_weights.context_weight,
            ),
        }

        for factor, (_attr, current, suggested) in factor_mapping.items():
            if current != suggested:
                change_pct = (
                    ((suggested - current) / current * 100)
                    if current > 0
                    else Decimal("100")
                )
                correlation_info = next(
                    (c for c in analysis.correlations if c.factor == factor), None
                )

                rationale = self._generate_rationale(factor, correlation_info, change_pct)

                suggestions.append(
                    WeightSuggestion(
                        factor=factor,
                        current_weight=current,
                        suggested_weight=suggested,
                        change_percent=change_pct,
                        rationale=rationale,
                    )
                )

        suggestion = CalibrationSuggestion(
            id=suggestion_id,
            analysis_id=analysis.id,
            current_weights=analysis.current_weights,
            suggested_weights=analysis.suggested_weights,
            suggestions=suggestions,
            estimated_improvement=analysis.estimated_improvement,
        )

        await self._save_suggestion(suggestion)

        logger.info(
            "calibration_suggestion_created",
            suggestion_id=str(suggestion_id),
            num_changes=len(suggestions),
        )

        return suggestion

    async def apply_weights(
        self,
        request: ApplyWeightsRequest,
    ) -> CalibrationSuggestion:
        """Apply new weights from a suggestion.

        Args:
            request: Apply weights request

        Returns:
            Updated CalibrationSuggestion
        """
        # Load suggestion
        suggestion = await self.get_suggestion(request.suggestion_id)
        if not suggestion:
            raise ValueError(f"Suggestion {request.suggestion_id} not found")

        if suggestion.status != CalibrationStatus.PENDING:
            raise ValueError(f"Suggestion already processed: {suggestion.status}")

        # Determine final weights
        if request.modified_weights:
            final_weights = request.modified_weights
            suggestion.status = CalibrationStatus.MODIFIED
        else:
            final_weights = suggestion.suggested_weights
            suggestion.status = CalibrationStatus.APPROVED

        # Archive current weights
        await self._archive_weights(suggestion.current_weights, suggestion.id)

        # Apply new weights
        await self._update_weights(final_weights)

        # Update suggestion
        suggestion.applied_at = datetime.now(UTC)
        suggestion.applied_weights = final_weights
        suggestion.operator_notes = request.operator_notes

        await self._save_suggestion(suggestion)

        logger.info(
            "weights_applied",
            suggestion_id=str(suggestion.id),
            status=suggestion.status.value,
            weights=final_weights.model_dump(),
        )

        return suggestion

    async def reject_suggestion(
        self,
        suggestion_id: UUID,
        reason: str | None = None,
    ) -> CalibrationSuggestion:
        """Reject a calibration suggestion.

        Args:
            suggestion_id: Suggestion to reject
            reason: Optional rejection reason

        Returns:
            Updated CalibrationSuggestion
        """
        suggestion = await self.get_suggestion(suggestion_id)
        if not suggestion:
            raise ValueError(f"Suggestion {suggestion_id} not found")

        suggestion.status = CalibrationStatus.REJECTED
        suggestion.operator_notes = reason

        await self._save_suggestion(suggestion)

        logger.info(
            "suggestion_rejected",
            suggestion_id=str(suggestion_id),
            reason=reason,
        )

        return suggestion

    async def get_current_weights(self) -> WeightSet:
        """Get current scoring weights.

        Returns:
            Current WeightSet
        """
        if self._current_weights:
            return self._current_weights

        result = (
            await self.supabase.table("scoring_weights")
            .select("*")
            .eq("id", "current")
            .single()
            .execute()
        )

        if result.data:
            self._current_weights = WeightSet(
                wallet_weight=Decimal(str(result.data.get("wallet_weight", "0.35"))),
                cluster_weight=Decimal(str(result.data.get("cluster_weight", "0.25"))),
                token_weight=Decimal(str(result.data.get("token_weight", "0.25"))),
                context_weight=Decimal(str(result.data.get("context_weight", "0.15"))),
            )
        else:
            # Default weights
            self._current_weights = WeightSet(
                wallet_weight=Decimal("0.35"),
                cluster_weight=Decimal("0.25"),
                token_weight=Decimal("0.25"),
                context_weight=Decimal("0.15"),
            )

        return self._current_weights

    async def get_suggestion(self, suggestion_id: UUID) -> CalibrationSuggestion | None:
        """Get a calibration suggestion by ID.

        Args:
            suggestion_id: Suggestion ID

        Returns:
            CalibrationSuggestion if found, None otherwise
        """
        # Check cache first
        if suggestion_id in self._suggestions_cache:
            data = self._suggestions_cache[suggestion_id]
            # Cache may contain CalibrationSuggestion directly (tests) or dict (db)
            if isinstance(data, CalibrationSuggestion):
                return data
            return self._deserialize_suggestion(data)

        result = (
            await self.supabase.table("calibration_suggestions")
            .select("*")
            .eq("id", str(suggestion_id))
            .single()
            .execute()
        )

        if result.data:
            self._suggestions_cache[suggestion_id] = result.data
            return self._deserialize_suggestion(result.data)
        return None

    async def get_weight_history(self, limit: int = 10) -> list[WeightArchive]:
        """Get archived weight configurations.

        Args:
            limit: Maximum entries to return

        Returns:
            List of WeightArchive entries
        """
        result = (
            await self.supabase.table("weight_archive")
            .select("*")
            .order("active_until", desc=True)
            .limit(limit)
            .execute()
        )

        return [self._deserialize_archive(w) for w in result.data]

    async def check_auto_calibration(self) -> CalibrationSuggestion | None:
        """Check if auto-calibration should run.

        Returns:
            CalibrationSuggestion if auto-applied, None otherwise
        """
        if not self.auto_config.enabled:
            return None

        # Check trades since last calibration
        trades_since = await self._count_trades_since_calibration()

        if trades_since < self.auto_config.min_trades_between:
            return None

        # Run analysis
        analysis = await self.run_analysis()

        if not analysis.is_valid:
            return None

        if analysis.estimated_improvement < self.auto_config.min_improvement_threshold:
            logger.info(
                "auto_calibration_skipped",
                improvement=float(analysis.estimated_improvement),
                threshold=float(self.auto_config.min_improvement_threshold),
            )
            return None

        # Limit weight changes
        bounded_weights = self._bound_weight_changes(
            analysis.current_weights,
            analysis.suggested_weights,
            self.auto_config.max_weight_change,
        )

        # Create and apply suggestion
        suggestion = await self.create_suggestion(analysis)

        await self.apply_weights(
            ApplyWeightsRequest(
                suggestion_id=suggestion.id,
                modified_weights=bounded_weights,
                operator_notes="Auto-calibration applied",
            )
        )

        logger.info(
            "auto_calibration_applied",
            suggestion_id=str(suggestion.id),
            improvement=float(analysis.estimated_improvement),
        )

        return suggestion

    def _calculate_factor_correlation(
        self,
        trades: list[dict],
        factor: ScoringFactor,
    ) -> FactorCorrelation:
        """Calculate correlation between factor and trade outcome.

        Args:
            trades: List of trade data
            factor: Scoring factor to analyze

        Returns:
            FactorCorrelation result
        """
        factor_key = f"{factor.value}"
        scores = [Decimal(str(t.get(factor_key, 0))) for t in trades]
        pnls = [Decimal(str(t.get("pnl_percent", 0))) for t in trades]

        # Calculate Pearson correlation
        if len(scores) > 2:
            corr = Decimal(
                str(correlation([float(s) for s in scores], [float(p) for p in pnls]))
            )
        else:
            corr = Decimal("0")

        winners = [t for t in trades if t.get("is_win")]
        losers = [t for t in trades if not t.get("is_win")]

        avg_winners = (
            sum(Decimal(str(t.get(factor_key, 0))) for t in winners) / len(winners)
            if winners
            else Decimal("0")
        )
        avg_losers = (
            sum(Decimal(str(t.get(factor_key, 0))) for t in losers) / len(losers)
            if losers
            else Decimal("0")
        )

        return FactorCorrelation(
            factor=factor,
            correlation=corr,
            sample_size=len(trades),
            avg_score_winners=avg_winners,
            avg_score_losers=avg_losers,
        )

    def _generate_suggested_weights(
        self,
        correlations: list[FactorCorrelation],
        current: WeightSet,
    ) -> WeightSet:
        """Generate suggested weights based on correlations.

        Args:
            correlations: Factor correlation results
            current: Current weights

        Returns:
            Suggested WeightSet
        """
        # Weight factors by correlation strength
        total_corr = sum(max(c.correlation, Decimal("0.01")) for c in correlations)

        weights = {}
        factor_to_attr = {
            ScoringFactor.WALLET_SCORE: "wallet_weight",
            ScoringFactor.CLUSTER_SCORE: "cluster_weight",
            ScoringFactor.TOKEN_SCORE: "token_weight",
            ScoringFactor.CONTEXT_SCORE: "context_weight",
        }

        for corr in correlations:
            attr = factor_to_attr[corr.factor]
            # Blend current weight with correlation-based weight
            corr_weight = max(corr.correlation, Decimal("0.01")) / total_corr
            current_weight = getattr(current, attr)
            # Blend: correlation-based with current for conservative adjustment
            weights[attr] = (corr_weight * Decimal("0.7")) + (
                current_weight * Decimal("0.3")
            )

        # Normalize to sum to 1
        total = sum(weights.values())
        normalized = {k: v / total for k, v in weights.items()}

        return WeightSet(**normalized)

    def _estimate_improvement(
        self,
        trades: list[dict],
        current: WeightSet,
        suggested: WeightSet,
    ) -> Decimal:
        """Estimate win rate improvement from weight changes.

        Args:
            trades: Trade data
            current: Current weights
            suggested: Suggested weights

        Returns:
            Estimated improvement percentage
        """
        # Simple simulation: re-score trades with new weights
        current_wins = 0
        suggested_wins = 0

        threshold = Decimal("0.6")  # Assumed trading threshold

        for trade in trades:
            current_score = self._calculate_score(trade, current)
            suggested_score = self._calculate_score(trade, suggested)

            # Would have traded?
            if current_score >= threshold and trade.get("is_win"):
                current_wins += 1
            if suggested_score >= threshold and trade.get("is_win"):
                suggested_wins += 1

        if current_wins == 0:
            return Decimal("0")

        improvement = ((suggested_wins - current_wins) / current_wins) * 100
        return Decimal(str(improvement)).quantize(Decimal("0.01"))

    def _calculate_score(self, trade: dict, weights: WeightSet) -> Decimal:
        """Calculate composite score for a trade.

        Args:
            trade: Trade data
            weights: Weights to use

        Returns:
            Composite score
        """
        return (
            Decimal(str(trade.get("wallet_score", 0))) * weights.wallet_weight
            + Decimal(str(trade.get("cluster_score", 0))) * weights.cluster_weight
            + Decimal(str(trade.get("token_score", 0))) * weights.token_weight
            + Decimal(str(trade.get("context_score", 0))) * weights.context_weight
        )

    def _generate_rationale(
        self,
        factor: ScoringFactor,
        corr: FactorCorrelation | None,
        change_pct: Decimal,
    ) -> str:
        """Generate human-readable rationale for weight change.

        Args:
            factor: Scoring factor
            corr: Correlation data
            change_pct: Percentage change

        Returns:
            Rationale string
        """
        direction = "increase" if change_pct > 0 else "decrease"
        factor_name = factor.value.replace("_", " ").title()

        if not corr:
            return f"{factor_name}: Suggested {direction} based on overall model performance"

        if corr.is_predictive:
            return (
                f"Strong predictor: winners avg {corr.avg_score_winners:.2f} "
                f"vs losers {corr.avg_score_losers:.2f}"
            )
        else:
            return f"Weak correlation ({corr.correlation:.2f}), reducing weight"

    def _bound_weight_changes(
        self,
        current: WeightSet,
        suggested: WeightSet,
        max_change: Decimal,
    ) -> WeightSet:
        """Limit weight changes to maximum allowed.

        Args:
            current: Current weights
            suggested: Suggested weights
            max_change: Maximum change per weight

        Returns:
            Bounded WeightSet
        """
        return WeightSet(
            wallet_weight=self._bound_change(
                current.wallet_weight, suggested.wallet_weight, max_change
            ),
            cluster_weight=self._bound_change(
                current.cluster_weight, suggested.cluster_weight, max_change
            ),
            token_weight=self._bound_change(
                current.token_weight, suggested.token_weight, max_change
            ),
            context_weight=self._bound_change(
                current.context_weight, suggested.context_weight, max_change
            ),
        )

    def _bound_change(
        self, current: Decimal, suggested: Decimal, max_change: Decimal
    ) -> Decimal:
        """Bound a single weight change.

        Args:
            current: Current value
            suggested: Suggested value
            max_change: Maximum change

        Returns:
            Bounded value
        """
        change = suggested - current
        if abs(change) > max_change:
            return current + (max_change if change > 0 else -max_change)
        return suggested

    async def _load_trade_data(self) -> list[dict]:
        """Load trade data with factor scores.

        Returns:
            List of trade records
        """
        result = (
            await self.supabase.table("trade_outcomes")
            .select("*, signals(wallet_score, cluster_score, token_score, context_score)")
            .order("exit_timestamp", desc=True)
            .limit(1000)
            .execute()
        )

        return result.data or []

    async def _count_trades_since_calibration(self) -> int:
        """Count trades since last calibration.

        Returns:
            Trade count
        """
        last = (
            await self.supabase.table("calibration_suggestions")
            .select("applied_at")
            .eq("status", "approved")
            .order("applied_at", desc=True)
            .limit(1)
            .execute()
        )

        since = last.data[0]["applied_at"] if last.data else None

        query = self.supabase.table("trade_outcomes").select("*", count="exact")
        if since:
            query = query.gte("created_at", since)

        result = await query.execute()
        return result.count or 0

    async def _save_analysis(self, analysis: CalibrationAnalysis) -> None:
        """Save calibration analysis.

        Args:
            analysis: Analysis to save
        """
        data = {
            "id": str(analysis.id),
            "analyzed_at": analysis.analyzed_at.isoformat(),
            "trade_count": analysis.trade_count,
            "min_trades_required": analysis.min_trades_required,
            "correlations": [c.model_dump(mode="json") for c in analysis.correlations],
            "current_weights": analysis.current_weights.model_dump(mode="json"),
            "suggested_weights": analysis.suggested_weights.model_dump(mode="json"),
            "estimated_improvement": str(analysis.estimated_improvement),
        }
        await self.supabase.table("calibration_analyses").insert(data).execute()

    async def _save_suggestion(self, suggestion: CalibrationSuggestion) -> None:
        """Save or update calibration suggestion.

        Args:
            suggestion: Suggestion to save
        """
        data = {
            "id": str(suggestion.id),
            "analysis_id": str(suggestion.analysis_id),
            "created_at": suggestion.created_at.isoformat(),
            "status": suggestion.status.value,
            "current_weights": suggestion.current_weights.model_dump(mode="json"),
            "suggested_weights": suggestion.suggested_weights.model_dump(mode="json"),
            "suggestions": [s.model_dump(mode="json") for s in suggestion.suggestions],
            "estimated_improvement": str(suggestion.estimated_improvement),
            "applied_at": suggestion.applied_at.isoformat() if suggestion.applied_at else None,
            "applied_weights": suggestion.applied_weights.model_dump(mode="json")
            if suggestion.applied_weights
            else None,
            "operator_notes": suggestion.operator_notes,
        }

        # Update cache
        self._suggestions_cache[suggestion.id] = data

        await self.supabase.table("calibration_suggestions").upsert(data).execute()

    async def _archive_weights(self, weights: WeightSet, suggestion_id: UUID) -> None:
        """Archive current weights before change.

        Args:
            weights: Weights to archive
            suggestion_id: Associated suggestion ID
        """
        archive = WeightArchive(
            id=uuid4(),
            weights=weights,
            active_from=datetime.now(UTC),
            active_until=datetime.now(UTC),
            suggestion_id=suggestion_id,
        )

        data = {
            "id": str(archive.id),
            "weights": archive.weights.model_dump(mode="json"),
            "active_from": archive.active_from.isoformat(),
            "active_until": archive.active_until.isoformat(),
            "suggestion_id": str(archive.suggestion_id) if archive.suggestion_id else None,
            "performance_during": str(archive.performance_during)
            if archive.performance_during
            else None,
        }
        await self.supabase.table("weight_archive").insert(data).execute()

    async def _update_weights(self, weights: WeightSet) -> None:
        """Update current scoring weights.

        Args:
            weights: New weights
        """
        self._current_weights = weights

        await self.supabase.table("scoring_weights").upsert(
            {
                "id": "current",
                "wallet_weight": str(weights.wallet_weight),
                "cluster_weight": str(weights.cluster_weight),
                "token_weight": str(weights.token_weight),
                "context_weight": str(weights.context_weight),
                "updated_at": datetime.now(UTC).isoformat(),
            }
        ).execute()

    def _deserialize_suggestion(self, data: dict) -> CalibrationSuggestion:
        """Deserialize suggestion from database.

        Args:
            data: Raw database record

        Returns:
            CalibrationSuggestion instance
        """
        # Handle created_at - use current time if not present
        created_at_raw = data.get("created_at")
        if created_at_raw is None:
            created_at = datetime.now(UTC)
        elif isinstance(created_at_raw, str):
            created_at = datetime.fromisoformat(created_at_raw)
        else:
            created_at = created_at_raw

        return CalibrationSuggestion(
            id=UUID(data["id"]),
            analysis_id=UUID(data["analysis_id"]),
            created_at=created_at,
            status=CalibrationStatus(data["status"]),
            current_weights=WeightSet(**data["current_weights"]),
            suggested_weights=WeightSet(**data["suggested_weights"]),
            suggestions=[WeightSuggestion(**s) for s in data.get("suggestions", [])],
            estimated_improvement=Decimal(str(data.get("estimated_improvement", "0"))),
            applied_at=datetime.fromisoformat(data["applied_at"])
            if data.get("applied_at")
            else None,
            applied_weights=WeightSet(**data["applied_weights"])
            if data.get("applied_weights")
            else None,
            operator_notes=data.get("operator_notes"),
        )

    def _deserialize_archive(self, data: dict) -> WeightArchive:
        """Deserialize archive from database.

        Args:
            data: Raw database record

        Returns:
            WeightArchive instance
        """
        return WeightArchive(
            id=UUID(data["id"]),
            weights=WeightSet(**data["weights"]),
            active_from=datetime.fromisoformat(data["active_from"]),
            active_until=datetime.fromisoformat(data["active_until"]),
            suggestion_id=UUID(data["suggestion_id"]) if data.get("suggestion_id") else None,
            performance_during=Decimal(str(data["performance_during"]))
            if data.get("performance_during")
            else None,
        )


# Singleton instance
_calibrator: ModelCalibrator | None = None


async def get_model_calibrator(supabase_client) -> ModelCalibrator:
    """Get or create ModelCalibrator singleton.

    Args:
        supabase_client: Supabase client instance

    Returns:
        ModelCalibrator singleton instance
    """
    global _calibrator
    if _calibrator is None:
        _calibrator = ModelCalibrator(supabase_client)
    return _calibrator
