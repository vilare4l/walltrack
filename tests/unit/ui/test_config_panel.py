"""Unit tests for scoring configuration panel."""

from walltrack.constants.scoring import (
    DEFAULT_CLUSTER_WEIGHT,
    DEFAULT_CONTEXT_WEIGHT,
    DEFAULT_TOKEN_WEIGHT,
    DEFAULT_WALLET_WEIGHT,
)
from walltrack.constants.threshold import (
    DEFAULT_HIGH_CONVICTION_THRESHOLD,
    DEFAULT_TRADE_THRESHOLD,
)
from walltrack.ui.components.config_panel import (
    calculate_preview_score,
    calculate_sum,
    create_weights_chart,
    normalize_weights,
)


class TestWeightCalculations:
    """Tests for weight calculation functions."""

    def test_calculate_sum_valid(self):
        """Test sum calculation with valid weights."""
        result = calculate_sum(0.3, 0.25, 0.25, 0.2)

        assert "1.000" in result
        assert "valid" in result

    def test_calculate_sum_invalid(self):
        """Test sum calculation with invalid weights."""
        result = calculate_sum(0.3, 0.3, 0.3, 0.3)

        assert "1.200" in result
        assert "must be 1.0" in result

    def test_calculate_sum_close_to_one(self):
        """Test sum calculation with floating point near 1.0."""
        result = calculate_sum(0.30, 0.25, 0.25, 0.2)

        assert "valid" in result


class TestNormalizeWeights:
    """Tests for weight normalization."""

    def test_normalize_above_one(self):
        """Test normalizing weights that sum to > 1."""
        w, c, t, x, msg, chart = normalize_weights(0.4, 0.3, 0.2, 0.1)

        total = w + c + t + x
        assert abs(total - 1.0) < 0.001
        assert "Normalized" in msg
        assert chart is not None

    def test_normalize_below_one(self):
        """Test normalizing weights that sum to < 1."""
        w, c, t, x, msg, _chart = normalize_weights(0.2, 0.15, 0.1, 0.05)

        total = w + c + t + x
        assert abs(total - 1.0) < 0.001
        assert "Normalized" in msg

    def test_normalize_zero_weights(self):
        """Test normalizing all zero weights."""
        w, c, t, x, msg, _chart = normalize_weights(0, 0, 0, 0)

        assert w == 0.25
        assert c == 0.25
        assert t == 0.25
        assert x == 0.25
        assert "equal weights" in msg

    def test_normalize_preserves_ratios(self):
        """Test normalization preserves relative ratios."""
        w, c, t, x, _msg, _chart = normalize_weights(0.4, 0.3, 0.2, 0.1)

        # Original ratio: 4:3:2:1
        assert w > c > t > x
        # Wallet should be 40% of total
        assert abs(w - 0.4) < 0.001


class TestWeightsChart:
    """Tests for weights chart creation."""

    def test_create_chart(self):
        """Test chart creation with valid weights."""
        fig = create_weights_chart(0.3, 0.25, 0.25, 0.2)

        assert fig is not None
        assert fig.layout.title.text == "Score Weight Distribution"
        assert len(fig.data) == 1
        assert fig.data[0].type == "pie"

    def test_chart_labels(self):
        """Test chart has correct labels."""
        fig = create_weights_chart(0.3, 0.25, 0.25, 0.2)

        labels = fig.data[0].labels
        assert "Wallet" in labels[0]
        assert "Cluster" in labels[1]
        assert "Token" in labels[2]
        assert "Context" in labels[3]

    def test_chart_values(self):
        """Test chart has correct values."""
        fig = create_weights_chart(0.4, 0.3, 0.2, 0.1)

        values = fig.data[0].values
        assert values[0] == 0.4
        assert values[1] == 0.3
        assert values[2] == 0.2
        assert values[3] == 0.1


class TestPreviewScoreCalculation:
    """Tests for score preview calculation."""

    def test_preview_with_defaults(self):
        """Test preview calculation with default values."""
        result = calculate_preview_score(
            win_rate=0.6,
            pnl=50,
            timing=0.5,
            is_leader=False,
            cluster_size=1,
            liquidity=10000,
            market_cap=100000,
            age_minutes=30,
        )

        assert "Final Score:" in result
        assert "Eligibility:" in result
        assert "Wallet" in result
        assert "Cluster" in result
        assert "Token" in result
        assert "Context" in result

    def test_preview_leader_bonus(self):
        """Test leader bonus increases score."""
        result_no_leader = calculate_preview_score(
            win_rate=0.6,
            pnl=50,
            timing=0.5,
            is_leader=False,
            cluster_size=1,
            liquidity=10000,
            market_cap=100000,
            age_minutes=30,
        )

        result_leader = calculate_preview_score(
            win_rate=0.6,
            pnl=50,
            timing=0.5,
            is_leader=True,
            cluster_size=1,
            liquidity=10000,
            market_cap=100000,
            age_minutes=30,
        )

        # Extract scores from markdown
        def extract_score(result: str) -> float:
            for line in result.split("\n"):
                if "Final Score:" in line:
                    return float(line.split(":")[1].strip().split("*")[0])
            return 0.0

        assert extract_score(result_leader) > extract_score(result_no_leader)

    def test_preview_cluster_size_effect(self):
        """Test cluster size affects score."""
        result_small = calculate_preview_score(
            win_rate=0.6,
            pnl=50,
            timing=0.5,
            is_leader=False,
            cluster_size=1,
            liquidity=10000,
            market_cap=100000,
            age_minutes=30,
        )

        result_large = calculate_preview_score(
            win_rate=0.6,
            pnl=50,
            timing=0.5,
            is_leader=False,
            cluster_size=10,
            liquidity=10000,
            market_cap=100000,
            age_minutes=30,
        )

        def extract_score(result: str) -> float:
            for line in result.split("\n"):
                if "Final Score:" in line:
                    return float(line.split(":")[1].strip().split("*")[0])
            return 0.0

        assert extract_score(result_large) > extract_score(result_small)

    def test_preview_high_conviction(self):
        """Test high conviction eligibility."""
        result = calculate_preview_score(
            win_rate=1.0,
            pnl=400,
            timing=1.0,
            is_leader=True,
            cluster_size=15,
            liquidity=100000,
            market_cap=1000000,
            age_minutes=60,
        )

        assert "HIGH CONVICTION" in result

    def test_preview_below_threshold(self):
        """Test below threshold eligibility."""
        result = calculate_preview_score(
            win_rate=0.3,
            pnl=-50,
            timing=0.2,
            is_leader=False,
            cluster_size=1,
            liquidity=2000,
            market_cap=20000,
            age_minutes=2,  # Age penalty
        )

        assert "BELOW THRESHOLD" in result

    def test_preview_score_bounds(self):
        """Test calculated score is between 0 and 1."""
        # Extreme low values
        result_low = calculate_preview_score(
            win_rate=0,
            pnl=-100,
            timing=0,
            is_leader=False,
            cluster_size=1,
            liquidity=0,
            market_cap=0,
            age_minutes=0,
        )

        # Extreme high values
        result_high = calculate_preview_score(
            win_rate=1.0,
            pnl=500,
            timing=1.0,
            is_leader=True,
            cluster_size=20,
            liquidity=100000,
            market_cap=1000000,
            age_minutes=60,
        )

        def extract_score(result: str) -> float:
            for line in result.split("\n"):
                if "Final Score:" in line:
                    return float(line.split(":")[1].strip().split("*")[0])
            return 0.0

        low_score = extract_score(result_low)
        high_score = extract_score(result_high)

        assert 0 <= low_score <= 1
        assert 0 <= high_score <= 1


class TestDefaultConstants:
    """Tests for default constant values."""

    def test_weights_sum_to_one(self):
        """Test default weights sum to 1.0."""
        total = (
            DEFAULT_WALLET_WEIGHT
            + DEFAULT_CLUSTER_WEIGHT
            + DEFAULT_TOKEN_WEIGHT
            + DEFAULT_CONTEXT_WEIGHT
        )
        assert abs(total - 1.0) < 0.001

    def test_thresholds_ordered(self):
        """Test high conviction > trade threshold."""
        assert DEFAULT_HIGH_CONVICTION_THRESHOLD > DEFAULT_TRADE_THRESHOLD

    def test_thresholds_valid_range(self):
        """Test thresholds are between 0 and 1."""
        assert 0 < DEFAULT_TRADE_THRESHOLD < 1
        assert 0 < DEFAULT_HIGH_CONVICTION_THRESHOLD < 1
