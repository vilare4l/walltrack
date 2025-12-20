"""Tests for scoring model calibrator."""

from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from walltrack.core.feedback.calibration_models import (
    ApplyWeightsRequest,
    CalibrationStatus,
    FactorCorrelation,
    ScoringFactor,
    WeightSet,
)
from walltrack.core.feedback.model_calibrator import ModelCalibrator


class ChainableMock(MagicMock):
    """Mock that supports Supabase's chainable API pattern."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._execute_result = MagicMock(data=None, count=0)

    def table(self, _table_name: str) -> "ChainableMock":
        return ChainableMock()

    def select(self, *_args, **_kwargs) -> "ChainableMock":
        return self

    def insert(self, _data) -> "ChainableMock":
        return self

    def upsert(self, _data) -> "ChainableMock":
        return self

    def eq(self, *_args) -> "ChainableMock":
        return self

    def gte(self, *_args) -> "ChainableMock":
        return self

    def single(self) -> "ChainableMock":
        return self

    def order(self, *_args, **_kwargs) -> "ChainableMock":
        return self

    def limit(self, _n: int) -> "ChainableMock":
        return self

    async def execute(self):
        return self._execute_result


@pytest.fixture
def mock_supabase():
    """Create mock Supabase client."""
    return ChainableMock()


@pytest.fixture
def calibrator(mock_supabase):
    """Create ModelCalibrator instance."""
    return ModelCalibrator(mock_supabase)


@pytest.fixture
def sample_trades():
    """Create sample trade data."""
    return [
        {
            "wallet_score": 0.8,
            "cluster_score": 0.7,
            "token_score": 0.6,
            "context_score": 0.5,
            "pnl_percent": 50,
            "is_win": True,
        },
        {
            "wallet_score": 0.9,
            "cluster_score": 0.8,
            "token_score": 0.7,
            "context_score": 0.6,
            "pnl_percent": 30,
            "is_win": True,
        },
        {
            "wallet_score": 0.3,
            "cluster_score": 0.4,
            "token_score": 0.5,
            "context_score": 0.3,
            "pnl_percent": -20,
            "is_win": False,
        },
        {
            "wallet_score": 0.4,
            "cluster_score": 0.3,
            "token_score": 0.4,
            "context_score": 0.4,
            "pnl_percent": -30,
            "is_win": False,
        },
    ] * 25  # 100 trades


class TestCalibrationModels:
    """Tests for calibration models."""

    def test_weight_set_total(self):
        """Test WeightSet total calculation."""
        weights = WeightSet(
            wallet_weight=Decimal("0.35"),
            cluster_weight=Decimal("0.25"),
            token_weight=Decimal("0.25"),
            context_weight=Decimal("0.15"),
        )
        assert weights.total_weight == Decimal("1.00")
        assert weights.is_normalized is True

    def test_weight_set_not_normalized(self):
        """Test WeightSet that doesn't sum to 1."""
        weights = WeightSet(
            wallet_weight=Decimal("0.40"),
            cluster_weight=Decimal("0.30"),
            token_weight=Decimal("0.30"),
            context_weight=Decimal("0.20"),
        )
        assert weights.is_normalized is False

    def test_factor_correlation_is_predictive(self):
        """Test is_predictive computed field."""
        predictive = FactorCorrelation(
            factor=ScoringFactor.WALLET_SCORE,
            correlation=Decimal("0.3"),
            sample_size=100,
            avg_score_winners=Decimal("0.75"),
            avg_score_losers=Decimal("0.45"),
        )
        assert predictive.is_predictive is True

    def test_factor_correlation_not_predictive_low_corr(self):
        """Test not predictive with low correlation."""
        not_predictive = FactorCorrelation(
            factor=ScoringFactor.CONTEXT_SCORE,
            correlation=Decimal("0.05"),
            sample_size=100,
            avg_score_winners=Decimal("0.5"),
            avg_score_losers=Decimal("0.48"),
        )
        assert not_predictive.is_predictive is False

    def test_factor_correlation_not_predictive_small_diff(self):
        """Test not predictive with small score difference."""
        not_predictive = FactorCorrelation(
            factor=ScoringFactor.TOKEN_SCORE,
            correlation=Decimal("0.3"),
            sample_size=100,
            avg_score_winners=Decimal("0.52"),
            avg_score_losers=Decimal("0.50"),
        )
        assert not_predictive.is_predictive is False


class TestFactorCorrelation:
    """Tests for factor correlation calculation."""

    def test_correlation_calculation(self, calibrator, sample_trades):
        """Test correlation is calculated correctly."""
        corr = calibrator._calculate_factor_correlation(
            sample_trades, ScoringFactor.WALLET_SCORE
        )
        assert corr.factor == ScoringFactor.WALLET_SCORE
        assert corr.sample_size == 100
        assert corr.correlation > 0  # Positive correlation expected

    def test_winner_loser_averages(self, calibrator, sample_trades):
        """Test winner/loser average calculation."""
        corr = calibrator._calculate_factor_correlation(
            sample_trades, ScoringFactor.WALLET_SCORE
        )
        assert corr.avg_score_winners > corr.avg_score_losers

    def test_all_factors_calculated(self, calibrator, sample_trades):
        """Test correlation for all factors."""
        for factor in ScoringFactor:
            corr = calibrator._calculate_factor_correlation(sample_trades, factor)
            assert corr.factor == factor
            assert corr.sample_size == 100


class TestWeightGeneration:
    """Tests for weight suggestion generation."""

    def test_generated_weights_normalized(self, calibrator):
        """Test that generated weights sum to 1."""
        correlations = [
            FactorCorrelation(
                factor=ScoringFactor.WALLET_SCORE,
                correlation=Decimal("0.4"),
                sample_size=100,
                avg_score_winners=Decimal("0.7"),
                avg_score_losers=Decimal("0.4"),
            ),
            FactorCorrelation(
                factor=ScoringFactor.CLUSTER_SCORE,
                correlation=Decimal("0.3"),
                sample_size=100,
                avg_score_winners=Decimal("0.6"),
                avg_score_losers=Decimal("0.4"),
            ),
            FactorCorrelation(
                factor=ScoringFactor.TOKEN_SCORE,
                correlation=Decimal("0.2"),
                sample_size=100,
                avg_score_winners=Decimal("0.5"),
                avg_score_losers=Decimal("0.4"),
            ),
            FactorCorrelation(
                factor=ScoringFactor.CONTEXT_SCORE,
                correlation=Decimal("0.1"),
                sample_size=100,
                avg_score_winners=Decimal("0.5"),
                avg_score_losers=Decimal("0.45"),
            ),
        ]

        current = WeightSet(
            wallet_weight=Decimal("0.35"),
            cluster_weight=Decimal("0.25"),
            token_weight=Decimal("0.25"),
            context_weight=Decimal("0.15"),
        )

        suggested = calibrator._generate_suggested_weights(correlations, current)
        assert suggested.is_normalized

    def test_higher_correlation_gets_higher_weight(self, calibrator):
        """Test that factors with higher correlation get higher weights."""
        correlations = [
            FactorCorrelation(
                factor=ScoringFactor.WALLET_SCORE,
                correlation=Decimal("0.5"),
                sample_size=100,
                avg_score_winners=Decimal("0.8"),
                avg_score_losers=Decimal("0.3"),
            ),
            FactorCorrelation(
                factor=ScoringFactor.CLUSTER_SCORE,
                correlation=Decimal("0.1"),
                sample_size=100,
                avg_score_winners=Decimal("0.5"),
                avg_score_losers=Decimal("0.45"),
            ),
            FactorCorrelation(
                factor=ScoringFactor.TOKEN_SCORE,
                correlation=Decimal("0.1"),
                sample_size=100,
                avg_score_winners=Decimal("0.5"),
                avg_score_losers=Decimal("0.45"),
            ),
            FactorCorrelation(
                factor=ScoringFactor.CONTEXT_SCORE,
                correlation=Decimal("0.1"),
                sample_size=100,
                avg_score_winners=Decimal("0.5"),
                avg_score_losers=Decimal("0.45"),
            ),
        ]

        current = WeightSet(
            wallet_weight=Decimal("0.25"),
            cluster_weight=Decimal("0.25"),
            token_weight=Decimal("0.25"),
            context_weight=Decimal("0.25"),
        )

        suggested = calibrator._generate_suggested_weights(correlations, current)
        assert suggested.wallet_weight > suggested.cluster_weight


class TestWeightBounding:
    """Tests for weight change bounding."""

    def test_bounds_large_increase(self, calibrator):
        """Test that large increases are bounded."""
        current = WeightSet(
            wallet_weight=Decimal("0.25"),
            cluster_weight=Decimal("0.25"),
            token_weight=Decimal("0.25"),
            context_weight=Decimal("0.25"),
        )

        suggested = WeightSet(
            wallet_weight=Decimal("0.50"),  # +0.25 change
            cluster_weight=Decimal("0.20"),
            token_weight=Decimal("0.20"),
            context_weight=Decimal("0.10"),
        )

        bounded = calibrator._bound_weight_changes(current, suggested, Decimal("0.10"))
        assert bounded.wallet_weight == Decimal("0.35")  # Only +0.10

    def test_bounds_large_decrease(self, calibrator):
        """Test that large decreases are bounded."""
        current = WeightSet(
            wallet_weight=Decimal("0.50"),
            cluster_weight=Decimal("0.20"),
            token_weight=Decimal("0.20"),
            context_weight=Decimal("0.10"),
        )

        suggested = WeightSet(
            wallet_weight=Decimal("0.20"),  # -0.30 change
            cluster_weight=Decimal("0.30"),
            token_weight=Decimal("0.30"),
            context_weight=Decimal("0.20"),
        )

        bounded = calibrator._bound_weight_changes(current, suggested, Decimal("0.10"))
        assert bounded.wallet_weight == Decimal("0.40")  # Only -0.10

    def test_small_changes_pass_through(self, calibrator):
        """Test that small changes are not modified."""
        current = WeightSet(
            wallet_weight=Decimal("0.30"),
            cluster_weight=Decimal("0.25"),
            token_weight=Decimal("0.25"),
            context_weight=Decimal("0.20"),
        )

        suggested = WeightSet(
            wallet_weight=Decimal("0.32"),  # +0.02 change
            cluster_weight=Decimal("0.25"),
            token_weight=Decimal("0.24"),
            context_weight=Decimal("0.19"),
        )

        bounded = calibrator._bound_weight_changes(current, suggested, Decimal("0.10"))
        assert bounded.wallet_weight == Decimal("0.32")


class TestImprovementEstimation:
    """Tests for improvement estimation."""

    def test_estimate_improvement(self, calibrator):
        """Test improvement estimation."""
        trades = [
            {
                "wallet_score": 0.8,
                "cluster_score": 0.7,
                "token_score": 0.6,
                "context_score": 0.5,
                "is_win": True,
            },
            {
                "wallet_score": 0.3,
                "cluster_score": 0.4,
                "token_score": 0.5,
                "context_score": 0.3,
                "is_win": False,
            },
        ] * 50

        current = WeightSet(
            wallet_weight=Decimal("0.25"),
            cluster_weight=Decimal("0.25"),
            token_weight=Decimal("0.25"),
            context_weight=Decimal("0.25"),
        )

        suggested = WeightSet(
            wallet_weight=Decimal("0.40"),
            cluster_weight=Decimal("0.20"),
            token_weight=Decimal("0.25"),
            context_weight=Decimal("0.15"),
        )

        improvement = calibrator._estimate_improvement(trades, current, suggested)
        assert isinstance(improvement, Decimal)

    def test_score_calculation(self, calibrator):
        """Test composite score calculation."""
        trade = {
            "wallet_score": 0.8,
            "cluster_score": 0.6,
            "token_score": 0.4,
            "context_score": 0.2,
        }

        weights = WeightSet(
            wallet_weight=Decimal("0.4"),
            cluster_weight=Decimal("0.3"),
            token_weight=Decimal("0.2"),
            context_weight=Decimal("0.1"),
        )

        score = calibrator._calculate_score(trade, weights)
        expected = Decimal("0.8") * Decimal("0.4") + Decimal("0.6") * Decimal("0.3")
        expected += Decimal("0.4") * Decimal("0.2") + Decimal("0.2") * Decimal("0.1")
        assert score == expected


class TestWeightApplication:
    """Tests for weight application."""

    @pytest.mark.asyncio
    async def test_apply_suggestion_approved(self, calibrator, mock_supabase):
        """Test applying a suggestion marks it as approved."""
        suggestion_id = uuid4()

        # Pre-populate cache with suggestion
        calibrator._suggestions_cache[suggestion_id] = {
            "id": str(suggestion_id),
            "analysis_id": str(uuid4()),
            "status": CalibrationStatus.PENDING.value,
            "current_weights": {
                "wallet_weight": "0.35",
                "cluster_weight": "0.25",
                "token_weight": "0.25",
                "context_weight": "0.15",
            },
            "suggested_weights": {
                "wallet_weight": "0.40",
                "cluster_weight": "0.25",
                "token_weight": "0.20",
                "context_weight": "0.15",
            },
            "suggestions": [],
            "estimated_improvement": "5.0",
        }

        result = await calibrator.apply_weights(
            ApplyWeightsRequest(suggestion_id=suggestion_id)
        )
        assert result.status == CalibrationStatus.APPROVED
        assert result.applied_at is not None

    @pytest.mark.asyncio
    async def test_apply_modified_suggestion(self, calibrator, mock_supabase):
        """Test applying modified weights."""
        suggestion_id = uuid4()

        calibrator._suggestions_cache[suggestion_id] = {
            "id": str(suggestion_id),
            "analysis_id": str(uuid4()),
            "status": CalibrationStatus.PENDING.value,
            "current_weights": {
                "wallet_weight": "0.35",
                "cluster_weight": "0.25",
                "token_weight": "0.25",
                "context_weight": "0.15",
            },
            "suggested_weights": {
                "wallet_weight": "0.40",
                "cluster_weight": "0.25",
                "token_weight": "0.20",
                "context_weight": "0.15",
            },
            "suggestions": [],
            "estimated_improvement": "5.0",
        }

        modified = WeightSet(
            wallet_weight=Decimal("0.38"),
            cluster_weight=Decimal("0.27"),
            token_weight=Decimal("0.22"),
            context_weight=Decimal("0.13"),
        )

        result = await calibrator.apply_weights(
            ApplyWeightsRequest(
                suggestion_id=suggestion_id,
                modified_weights=modified,
            )
        )
        assert result.status == CalibrationStatus.MODIFIED
        assert result.applied_weights == modified

    @pytest.mark.asyncio
    async def test_reject_suggestion(self, calibrator):
        """Test rejecting a suggestion."""
        suggestion_id = uuid4()

        calibrator._suggestions_cache[suggestion_id] = {
            "id": str(suggestion_id),
            "analysis_id": str(uuid4()),
            "status": CalibrationStatus.PENDING.value,
            "current_weights": {
                "wallet_weight": "0.35",
                "cluster_weight": "0.25",
                "token_weight": "0.25",
                "context_weight": "0.15",
            },
            "suggested_weights": {
                "wallet_weight": "0.40",
                "cluster_weight": "0.25",
                "token_weight": "0.20",
                "context_weight": "0.15",
            },
            "suggestions": [],
            "estimated_improvement": "5.0",
        }

        result = await calibrator.reject_suggestion(suggestion_id, "Not enough data")
        assert result.status == CalibrationStatus.REJECTED
        assert result.operator_notes == "Not enough data"

    @pytest.mark.asyncio
    async def test_apply_not_found(self, calibrator):
        """Test applying non-existent suggestion."""
        with pytest.raises(ValueError, match="not found"):
            await calibrator.apply_weights(
                ApplyWeightsRequest(suggestion_id=uuid4())
            )


class TestRationale:
    """Tests for rationale generation."""

    def test_rationale_for_predictive_factor(self, calibrator):
        """Test rationale for predictive factor."""
        corr = FactorCorrelation(
            factor=ScoringFactor.WALLET_SCORE,
            correlation=Decimal("0.4"),
            sample_size=100,
            avg_score_winners=Decimal("0.75"),
            avg_score_losers=Decimal("0.40"),
        )

        rationale = calibrator._generate_rationale(
            ScoringFactor.WALLET_SCORE, corr, Decimal("20")
        )
        assert "Strong predictor" in rationale
        assert "winners" in rationale

    def test_rationale_for_weak_factor(self, calibrator):
        """Test rationale for weak factor."""
        corr = FactorCorrelation(
            factor=ScoringFactor.CONTEXT_SCORE,
            correlation=Decimal("0.05"),
            sample_size=100,
            avg_score_winners=Decimal("0.50"),
            avg_score_losers=Decimal("0.48"),
        )

        rationale = calibrator._generate_rationale(
            ScoringFactor.CONTEXT_SCORE, corr, Decimal("-10")
        )
        assert "Weak" in rationale

    def test_rationale_without_correlation(self, calibrator):
        """Test rationale without correlation data."""
        rationale = calibrator._generate_rationale(
            ScoringFactor.TOKEN_SCORE, None, Decimal("15")
        )
        assert "Suggested" in rationale
