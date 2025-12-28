"""Unit tests for simplified scoring configuration panel.

Epic 14 Simplification: Tests updated for 2-component scoring model.
"""

from walltrack.constants.scoring import (
    DEFAULT_LEADER_BONUS,
    DEFAULT_MAX_CLUSTER_BOOST,
    DEFAULT_MIN_CLUSTER_BOOST,
    DEFAULT_PNL_NORMALIZE_MAX,
    DEFAULT_PNL_NORMALIZE_MIN,
    DEFAULT_TRADE_THRESHOLD,
    DEFAULT_WALLET_PNL_WEIGHT,
    DEFAULT_WALLET_WIN_RATE_WEIGHT,
)
from walltrack.ui.components.config_panel import (
    calculate_preview_score,
    create_scoring_chart,
    validate_wallet_weights,
)


class TestWalletWeightValidation:
    """Tests for wallet weight validation."""

    def test_validate_weights_valid(self):
        """Test validation with valid weights that sum to 1.0."""
        result = validate_wallet_weights(0.6, 0.4)

        assert "1.00" in result
        assert "valid" in result

    def test_validate_weights_invalid(self):
        """Test validation with invalid weights that don't sum to 1.0."""
        result = validate_wallet_weights(0.5, 0.3)

        assert "0.80" in result
        assert "should be 1.0" in result

    def test_validate_weights_exact_match(self):
        """Test validation with exact default weights."""
        result = validate_wallet_weights(
            DEFAULT_WALLET_WIN_RATE_WEIGHT,
            DEFAULT_WALLET_PNL_WEIGHT,
        )

        assert "valid" in result


class TestScoringChart:
    """Tests for scoring chart creation."""

    def test_create_chart_basic(self):
        """Test chart creation with valid weights."""
        fig = create_scoring_chart(0.6, 0.4)

        assert fig is not None
        assert fig.layout.title.text == "Wallet Score Composition"
        assert len(fig.data) == 1
        assert fig.data[0].type == "bar"

    def test_chart_values(self):
        """Test chart has correct values."""
        fig = create_scoring_chart(0.7, 0.3)

        values = fig.data[0].x
        assert len(values) == 2
        assert values[0] == 0.7
        assert values[1] == 0.3

    def test_chart_labels(self):
        """Test chart has correct labels."""
        fig = create_scoring_chart(0.6, 0.4)

        labels = fig.data[0].y
        assert "Win Rate" in labels[0]
        assert "PnL" in labels[1]


class TestPreviewScoreCalculation:
    """Tests for score preview calculation."""

    def test_preview_with_defaults(self):
        """Test preview calculation with default values."""
        result = calculate_preview_score(
            win_rate=0.6,
            pnl=50,
            is_leader=False,
            cluster_boost=1.0,
            win_rate_weight=0.6,
            pnl_weight=0.4,
            leader_bonus=1.15,
            trade_threshold=0.65,
        )

        assert "Final Score:" in result
        assert "Wallet Score" in result
        assert "Cluster Boost" in result

    def test_preview_leader_bonus(self):
        """Test leader bonus increases wallet score."""
        result_no_leader = calculate_preview_score(
            win_rate=0.6,
            pnl=50,
            is_leader=False,
            cluster_boost=1.0,
            win_rate_weight=0.6,
            pnl_weight=0.4,
            leader_bonus=1.15,
            trade_threshold=0.65,
        )

        result_leader = calculate_preview_score(
            win_rate=0.6,
            pnl=50,
            is_leader=True,
            cluster_boost=1.0,
            win_rate_weight=0.6,
            pnl_weight=0.4,
            leader_bonus=1.15,
            trade_threshold=0.65,
        )

        def extract_score(result: str) -> float:
            for line in result.split("\n"):
                if "**Final Score:" in line and "Wallet" not in line:
                    # Extract from format: **Final Score: 0.5290**
                    import re
                    match = re.search(r"Final Score:\s*([\d.]+)", line)
                    if match:
                        return float(match.group(1))
            return 0.0

        assert extract_score(result_leader) > extract_score(result_no_leader)

    def test_preview_cluster_boost_effect(self):
        """Test cluster boost increases final score."""
        result_no_boost = calculate_preview_score(
            win_rate=0.6,
            pnl=50,
            is_leader=False,
            cluster_boost=1.0,
            win_rate_weight=0.6,
            pnl_weight=0.4,
            leader_bonus=1.15,
            trade_threshold=0.65,
        )

        result_with_boost = calculate_preview_score(
            win_rate=0.6,
            pnl=50,
            is_leader=False,
            cluster_boost=1.5,
            win_rate_weight=0.6,
            pnl_weight=0.4,
            leader_bonus=1.15,
            trade_threshold=0.65,
        )

        def extract_score(result: str) -> float:
            import re
            for line in result.split("\n"):
                if "**Final Score:" in line and "Wallet" not in line:
                    match = re.search(r"Final Score:\s*([\d.]+)", line)
                    if match:
                        return float(match.group(1))
            return 0.0

        assert extract_score(result_with_boost) > extract_score(result_no_boost)

    def test_preview_trade_eligible(self):
        """Test trade eligible outcome."""
        result = calculate_preview_score(
            win_rate=0.8,
            pnl=200,
            is_leader=True,
            cluster_boost=1.5,
            win_rate_weight=0.6,
            pnl_weight=0.4,
            leader_bonus=1.15,
            trade_threshold=0.65,
        )

        assert "TRADE ELIGIBLE" in result

    def test_preview_below_threshold(self):
        """Test below threshold outcome."""
        result = calculate_preview_score(
            win_rate=0.3,
            pnl=-50,
            is_leader=False,
            cluster_boost=1.0,
            win_rate_weight=0.6,
            pnl_weight=0.4,
            leader_bonus=1.15,
            trade_threshold=0.65,
        )

        assert "BELOW THRESHOLD" in result

    def test_preview_score_bounds(self):
        """Test calculated score is between 0 and 1."""
        # Extreme low values
        result_low = calculate_preview_score(
            win_rate=0,
            pnl=-100,
            is_leader=False,
            cluster_boost=1.0,
            win_rate_weight=0.6,
            pnl_weight=0.4,
            leader_bonus=1.15,
            trade_threshold=0.65,
        )

        # Extreme high values
        result_high = calculate_preview_score(
            win_rate=1.0,
            pnl=500,
            is_leader=True,
            cluster_boost=1.8,
            win_rate_weight=0.6,
            pnl_weight=0.4,
            leader_bonus=1.15,
            trade_threshold=0.65,
        )

        def extract_score(result: str) -> float:
            import re
            for line in result.split("\n"):
                if "**Final Score:" in line and "Wallet" not in line:
                    match = re.search(r"Final Score:\s*([\d.]+)", line)
                    if match:
                        return float(match.group(1))
            return 0.0

        low_score = extract_score(result_low)
        high_score = extract_score(result_high)

        assert 0 <= low_score <= 1
        assert 0 <= high_score <= 1


class TestDefaultConstants:
    """Tests for default constant values."""

    def test_wallet_weights_sum_to_one(self):
        """Test default wallet weights sum to 1.0."""
        total = DEFAULT_WALLET_WIN_RATE_WEIGHT + DEFAULT_WALLET_PNL_WEIGHT
        assert abs(total - 1.0) < 0.001

    def test_trade_threshold_valid_range(self):
        """Test trade threshold is between 0 and 1."""
        assert 0 < DEFAULT_TRADE_THRESHOLD < 1

    def test_leader_bonus_valid_range(self):
        """Test leader bonus is >= 1.0."""
        assert DEFAULT_LEADER_BONUS >= 1.0

    def test_cluster_boost_range_valid(self):
        """Test cluster boost range is valid."""
        assert DEFAULT_MIN_CLUSTER_BOOST >= 1.0
        assert DEFAULT_MAX_CLUSTER_BOOST >= DEFAULT_MIN_CLUSTER_BOOST

    def test_pnl_normalize_range_valid(self):
        """Test PnL normalization range is valid."""
        assert DEFAULT_PNL_NORMALIZE_MIN < DEFAULT_PNL_NORMALIZE_MAX
