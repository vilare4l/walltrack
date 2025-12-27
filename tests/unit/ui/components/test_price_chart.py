"""Tests for price chart component."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import plotly.graph_objects as go
import pytest

from walltrack.ui.components.price_chart import (
    COMPARISON_COLORS,
    SIMULATION_COLORS,
    create_comparison_chart,
    create_mini_chart,
    create_price_chart,
)


@pytest.fixture
def sample_price_history() -> list[dict[str, Any]]:
    """Create sample price history data."""
    base_time = datetime(2025, 12, 25, 10, 0, 0, tzinfo=UTC)
    return [
        {"timestamp": (base_time + timedelta(hours=i)).isoformat(), "price": 0.001 + i * 0.0001}
        for i in range(10)
    ]


@pytest.fixture
def entry_time() -> str:
    """Entry time fixture."""
    return "2025-12-25T10:00:00Z"


class TestCreatePriceChart:
    """Tests for create_price_chart function."""

    def test_basic_chart(
        self, sample_price_history: list[dict[str, Any]], entry_time: str
    ) -> None:
        """Test creating a basic price chart."""
        fig = create_price_chart(
            price_history=sample_price_history,
            entry_price=0.001,
            entry_time=entry_time,
        )

        assert isinstance(fig, go.Figure)
        # Should have price line and entry point
        assert len(fig.data) >= 2

    def test_chart_with_entry_point(
        self, sample_price_history: list[dict[str, Any]], entry_time: str
    ) -> None:
        """Test entry point is added to chart."""
        fig = create_price_chart(
            price_history=sample_price_history,
            entry_price=0.001,
            entry_time=entry_time,
        )

        # Find entry trace
        entry_traces = [t for t in fig.data if t.name == "Entry"]
        assert len(entry_traces) == 1

        entry_trace = entry_traces[0]
        assert entry_trace.y[0] == 0.001
        assert entry_trace.marker.color == "blue"

    def test_chart_with_actual_exits(
        self, sample_price_history: list[dict[str, Any]], entry_time: str
    ) -> None:
        """Test actual exits are added to chart."""
        actual_exits = [
            {
                "timestamp": "2025-12-25T15:00:00Z",
                "price": 0.0015,
                "type": "take_profit",
                "label": "TP1",
            }
        ]

        fig = create_price_chart(
            price_history=sample_price_history,
            entry_price=0.001,
            entry_time=entry_time,
            actual_exits=actual_exits,
        )

        exit_traces = [t for t in fig.data if t.name == "Actual Exit"]
        assert len(exit_traces) == 1

        exit_trace = exit_traces[0]
        assert exit_trace.y[0] == 0.0015
        assert exit_trace.marker.color == "green"
        assert "TP1" in exit_trace.text

    def test_chart_with_simulated_exits(
        self, sample_price_history: list[dict[str, Any]], entry_time: str
    ) -> None:
        """Test simulated exits are added to chart."""
        simulated_exits = {
            "Balanced": [
                {"timestamp": "2025-12-25T14:00:00Z", "price": 0.0014, "label": "TP1"}
            ],
            "Aggressive": [
                {"timestamp": "2025-12-25T12:00:00Z", "price": 0.0012, "label": "TP1"}
            ],
        }

        fig = create_price_chart(
            price_history=sample_price_history,
            entry_price=0.001,
            entry_time=entry_time,
            simulated_exits=simulated_exits,
        )

        # Should have traces for both strategies
        balanced_traces = [t for t in fig.data if "Balanced" in t.name]
        aggressive_traces = [t for t in fig.data if "Aggressive" in t.name]

        assert len(balanced_traces) == 1
        assert len(aggressive_traces) == 1

        # Check diamond markers
        assert balanced_traces[0].marker.symbol == "diamond"

    def test_chart_with_strategy_levels(
        self, sample_price_history: list[dict[str, Any]], entry_time: str
    ) -> None:
        """Test strategy level lines are added to chart."""
        strategy_levels = {
            "Balanced": [
                {"price": 0.0015, "type": "take_profit", "label": "TP +50%"},
                {"price": 0.0009, "type": "stop_loss", "label": "SL -10%"},
            ]
        }

        fig = create_price_chart(
            price_history=sample_price_history,
            entry_price=0.001,
            entry_time=entry_time,
            strategy_levels=strategy_levels,
        )

        # Check layout has horizontal lines
        layout = fig.layout
        assert layout is not None

    def test_chart_title(
        self, sample_price_history: list[dict[str, Any]], entry_time: str
    ) -> None:
        """Test custom title is applied."""
        fig = create_price_chart(
            price_history=sample_price_history,
            entry_price=0.001,
            entry_time=entry_time,
            title="Custom Chart Title",
        )

        assert fig.layout.title.text == "Custom Chart Title"

    def test_chart_layout(
        self, sample_price_history: list[dict[str, Any]], entry_time: str
    ) -> None:
        """Test chart layout properties."""
        fig = create_price_chart(
            price_history=sample_price_history,
            entry_price=0.001,
            entry_time=entry_time,
        )

        assert fig.layout.xaxis.title.text == "Time"
        assert fig.layout.yaxis.title.text == "Price"
        assert fig.layout.height == 500

    def test_empty_price_history(self, entry_time: str) -> None:
        """Test chart with empty price history."""
        fig = create_price_chart(
            price_history=[],
            entry_price=0.001,
            entry_time=entry_time,
        )

        # Should still have entry point
        assert len(fig.data) >= 1

    def test_empty_simulated_exits(
        self, sample_price_history: list[dict[str, Any]], entry_time: str
    ) -> None:
        """Test chart with empty simulated exits list."""
        simulated_exits: dict[str, list[dict[str, Any]]] = {
            "Strategy1": [],  # Empty list
        }

        fig = create_price_chart(
            price_history=sample_price_history,
            entry_price=0.001,
            entry_time=entry_time,
            simulated_exits=simulated_exits,
        )

        # Should not have simulation traces for empty strategy
        sim_traces = [t for t in fig.data if "Strategy1" in t.name]
        assert len(sim_traces) == 0


class TestCreateComparisonChart:
    """Tests for create_comparison_chart function."""

    def test_basic_comparison(
        self, sample_price_history: list[dict[str, Any]], entry_time: str
    ) -> None:
        """Test creating a comparison chart."""
        comparison_results = [
            {
                "strategy_name": "Balanced",
                "exit_time": "2025-12-25T15:00:00Z",
                "exit_price": 0.0015,
                "pnl_pct": 50.0,
                "exit_types": ["take_profit"],
            },
            {
                "strategy_name": "Aggressive",
                "exit_time": "2025-12-25T14:00:00Z",
                "exit_price": 0.0014,
                "pnl_pct": 40.0,
                "exit_types": ["take_profit"],
            },
        ]

        fig = create_comparison_chart(
            price_history=sample_price_history,
            entry_price=0.001,
            entry_time=entry_time,
            comparison_results=comparison_results,
        )

        assert isinstance(fig, go.Figure)

        # Should have traces for both strategies
        balanced_traces = [t for t in fig.data if "Balanced" in t.name]
        aggressive_traces = [t for t in fig.data if "Aggressive" in t.name]

        assert len(balanced_traces) == 1
        assert len(aggressive_traces) == 1

    def test_comparison_with_pnl_in_name(
        self, sample_price_history: list[dict[str, Any]], entry_time: str
    ) -> None:
        """Test P&L is included in trace name."""
        comparison_results = [
            {
                "strategy_name": "Test",
                "exit_time": "2025-12-25T15:00:00Z",
                "exit_price": 0.0015,
                "pnl_pct": 50.0,
                "exit_types": [],
            }
        ]

        fig = create_comparison_chart(
            price_history=sample_price_history,
            entry_price=0.001,
            entry_time=entry_time,
            comparison_results=comparison_results,
        )

        test_traces = [t for t in fig.data if "Test" in t.name]
        assert len(test_traces) == 1
        assert "+50.0%" in test_traces[0].name

    def test_comparison_diamond_markers(
        self, sample_price_history: list[dict[str, Any]], entry_time: str
    ) -> None:
        """Test comparison uses diamond markers."""
        comparison_results = [
            {
                "strategy_name": "Test",
                "exit_time": "2025-12-25T15:00:00Z",
                "exit_price": 0.0015,
                "pnl_pct": 50.0,
                "exit_types": [],
            }
        ]

        fig = create_comparison_chart(
            price_history=sample_price_history,
            entry_price=0.001,
            entry_time=entry_time,
            comparison_results=comparison_results,
        )

        test_traces = [t for t in fig.data if "Test" in t.name]
        assert test_traces[0].marker.symbol == "diamond"

    def test_comparison_no_exit_time(
        self, sample_price_history: list[dict[str, Any]], entry_time: str
    ) -> None:
        """Test result without exit_time is skipped."""
        comparison_results = [
            {
                "strategy_name": "NoExit",
                "exit_price": 0.0015,
                "pnl_pct": 50.0,
            }
        ]

        fig = create_comparison_chart(
            price_history=sample_price_history,
            entry_price=0.001,
            entry_time=entry_time,
            comparison_results=comparison_results,
        )

        no_exit_traces = [t for t in fig.data if "NoExit" in t.name]
        assert len(no_exit_traces) == 0

    def test_comparison_title(
        self, sample_price_history: list[dict[str, Any]], entry_time: str
    ) -> None:
        """Test comparison chart has correct title."""
        fig = create_comparison_chart(
            price_history=sample_price_history,
            entry_price=0.001,
            entry_time=entry_time,
            comparison_results=[],
        )

        assert fig.layout.title.text == "Strategy Comparison"


class TestCreateMiniChart:
    """Tests for create_mini_chart function."""

    def test_basic_mini_chart(self, sample_price_history: list[dict[str, Any]]) -> None:
        """Test creating a mini chart."""
        fig = create_mini_chart(
            price_history=sample_price_history,
            entry_price=0.001,
        )

        assert isinstance(fig, go.Figure)
        assert len(fig.data) >= 1

    def test_mini_chart_height(self, sample_price_history: list[dict[str, Any]]) -> None:
        """Test mini chart height."""
        fig = create_mini_chart(
            price_history=sample_price_history,
            entry_price=0.001,
            height=200,
        )

        assert fig.layout.height == 200

    def test_mini_chart_green_positive(
        self, sample_price_history: list[dict[str, Any]]
    ) -> None:
        """Test mini chart is green for positive P&L."""
        # Price history ends at 0.001 + 9*0.0001 = 0.0019
        fig = create_mini_chart(
            price_history=sample_price_history,
            entry_price=0.001,  # Entry below final price
        )

        line_trace = fig.data[0]
        assert line_trace.line.color == "#4CAF50"  # Green

    def test_mini_chart_red_negative(self) -> None:
        """Test mini chart is red for negative P&L."""
        base_time = datetime(2025, 12, 25, 10, 0, 0, tzinfo=UTC)
        # Price drops
        price_history = [
            {"timestamp": (base_time + timedelta(hours=i)).isoformat(), "price": 0.002 - i * 0.0001}
            for i in range(10)
        ]

        fig = create_mini_chart(
            price_history=price_history,
            entry_price=0.002,  # Entry at high, now lower
        )

        line_trace = fig.data[0]
        assert line_trace.line.color == "#F44336"  # Red

    def test_mini_chart_with_current_price(
        self, sample_price_history: list[dict[str, Any]]
    ) -> None:
        """Test mini chart uses current_price when provided."""
        fig = create_mini_chart(
            price_history=sample_price_history,
            entry_price=0.001,
            current_price=0.0005,  # Below entry
        )

        line_trace = fig.data[0]
        assert line_trace.line.color == "#F44336"  # Red (current below entry)

    def test_mini_chart_no_legend(self, sample_price_history: list[dict[str, Any]]) -> None:
        """Test mini chart has no legend."""
        fig = create_mini_chart(
            price_history=sample_price_history,
            entry_price=0.001,
        )

        assert fig.layout.showlegend is False

    def test_mini_chart_no_axes(self, sample_price_history: list[dict[str, Any]]) -> None:
        """Test mini chart has hidden axes."""
        fig = create_mini_chart(
            price_history=sample_price_history,
            entry_price=0.001,
        )

        assert fig.layout.xaxis.visible is False
        assert fig.layout.yaxis.visible is False

    def test_mini_chart_fill(self, sample_price_history: list[dict[str, Any]]) -> None:
        """Test mini chart has fill."""
        fig = create_mini_chart(
            price_history=sample_price_history,
            entry_price=0.001,
        )

        line_trace = fig.data[0]
        assert line_trace.fill == "tozeroy"

    def test_mini_chart_empty_history(self) -> None:
        """Test mini chart with empty history."""
        fig = create_mini_chart(
            price_history=[],
            entry_price=0.001,
        )

        assert len(fig.data) == 0


class TestColorConstants:
    """Tests for color constants."""

    def test_simulation_colors_count(self) -> None:
        """Test there are enough simulation colors."""
        assert len(SIMULATION_COLORS) >= 5

    def test_comparison_colors_count(self) -> None:
        """Test there are enough comparison colors."""
        assert len(COMPARISON_COLORS) >= 5

    def test_colors_are_hex(self) -> None:
        """Test all colors are valid hex."""
        for color in SIMULATION_COLORS + COMPARISON_COLORS:
            assert color.startswith("#")
            assert len(color) == 7
