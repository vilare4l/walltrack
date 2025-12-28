"""Unit tests for signal log models."""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from walltrack.models.signal_log import (
    SignalLogEntry,
    SignalLogFilter,
    SignalLogSummary,
    SignalStatus,
)


class TestSignalStatus:
    """Tests for SignalStatus enum."""

    def test_all_statuses_defined(self):
        """Test all expected statuses are defined."""
        expected = {
            "received",
            "filtered_out",
            "scored",
            "trade_eligible",
            "below_threshold",
            "executed",
            "failed",
        }
        actual = {s.value for s in SignalStatus}
        assert actual == expected

    def test_status_is_string_enum(self):
        """Test status values are strings."""
        assert SignalStatus.RECEIVED.value == "received"
        assert SignalStatus.EXECUTED.value == "executed"


class TestSignalLogEntry:
    """Tests for SignalLogEntry model."""

    def test_minimal_signal(self):
        """Test creating signal with minimal required fields."""
        signal = SignalLogEntry(
            tx_signature="sig123",
            wallet_address="wallet123",
            token_address="token123",
            direction="buy",
            timestamp=datetime.now(UTC),
        )

        assert signal.tx_signature == "sig123"
        assert signal.status == SignalStatus.RECEIVED
        assert signal.final_score is None
        assert signal.trade_id is None

    def test_full_signal(self):
        """Test creating signal with all fields."""
        now = datetime.now(UTC)
        signal = SignalLogEntry(
            id="uuid-123",
            tx_signature="sig123",
            wallet_address="wallet123",
            token_address="token123",
            direction="buy",
            amount_token=1000000,
            amount_sol=1.5,
            slot=123456789,
            final_score=0.85,
            wallet_score=0.90,
            cluster_score=0.80,
            token_score=0.75,
            context_score=0.95,
            status=SignalStatus.TRADE_ELIGIBLE,
            eligibility_status="trade_eligible",
            conviction_tier="high",
            filter_status="passed",
            filter_reason=None,
            trade_id="trade-uuid",
            timestamp=now,
            received_at=now,
            processing_time_ms=45.5,
            raw_factors={"factor1": 0.9},
        )

        assert signal.final_score == 0.85
        assert signal.status == SignalStatus.TRADE_ELIGIBLE
        assert signal.conviction_tier == "high"
        assert signal.raw_factors == {"factor1": 0.9}

    def test_default_received_at(self):
        """Test received_at defaults to now."""
        before = datetime.now(UTC)
        signal = SignalLogEntry(
            tx_signature="sig123",
            wallet_address="wallet123",
            token_address="token123",
            direction="buy",
            timestamp=datetime.now(UTC),
        )
        after = datetime.now(UTC)

        assert before <= signal.received_at <= after

    def test_default_amounts(self):
        """Test default values for amounts."""
        signal = SignalLogEntry(
            tx_signature="sig123",
            wallet_address="wallet123",
            token_address="token123",
            direction="buy",
            timestamp=datetime.now(UTC),
        )

        assert signal.amount_token == 0.0
        assert signal.amount_sol == 0.0
        assert signal.processing_time_ms == 0.0

    def test_raw_factors_default_empty(self):
        """Test raw_factors defaults to empty dict."""
        signal = SignalLogEntry(
            tx_signature="sig123",
            wallet_address="wallet123",
            token_address="token123",
            direction="buy",
            timestamp=datetime.now(UTC),
        )

        assert signal.raw_factors == {}


class TestSignalLogFilter:
    """Tests for SignalLogFilter model."""

    def test_default_filter(self):
        """Test filter with default values."""
        filter = SignalLogFilter()

        assert filter.start_date is None
        assert filter.end_date is None
        assert filter.wallet_address is None
        assert filter.min_score is None
        assert filter.max_score is None
        assert filter.status is None
        assert filter.limit == 100
        assert filter.offset == 0
        assert filter.sort_by == "timestamp"
        assert filter.sort_desc is True

    def test_date_range_filter(self):
        """Test filter with date range."""
        start = datetime.now(UTC) - timedelta(days=7)
        end = datetime.now(UTC)

        filter = SignalLogFilter(
            start_date=start,
            end_date=end,
        )

        assert filter.start_date == start
        assert filter.end_date == end

    def test_score_range_filter(self):
        """Test filter with score range."""
        filter = SignalLogFilter(
            min_score=0.7,
            max_score=0.9,
        )

        assert filter.min_score == 0.7
        assert filter.max_score == 0.9

    def test_status_filter(self):
        """Test filter by status."""
        filter = SignalLogFilter(
            status=SignalStatus.TRADE_ELIGIBLE,
        )

        assert filter.status == SignalStatus.TRADE_ELIGIBLE

    def test_limit_validation(self):
        """Test limit validation (max 1000)."""
        filter = SignalLogFilter(limit=500)
        assert filter.limit == 500

        with pytest.raises(ValidationError):
            SignalLogFilter(limit=1001)

    def test_offset_validation(self):
        """Test offset validation (min 0)."""
        filter = SignalLogFilter(offset=100)
        assert filter.offset == 100

        with pytest.raises(ValidationError):
            SignalLogFilter(offset=-1)

    def test_sorting_options(self):
        """Test sorting configuration."""
        filter = SignalLogFilter(
            sort_by="final_score",
            sort_desc=False,
        )

        assert filter.sort_by == "final_score"
        assert filter.sort_desc is False


class TestSignalLogSummary:
    """Tests for SignalLogSummary model."""

    def test_default_summary(self):
        """Test summary with default values."""
        summary = SignalLogSummary()

        assert summary.total_count == 0
        assert summary.trade_eligible_count == 0
        assert summary.below_threshold_count == 0
        assert summary.filtered_count == 0
        assert summary.executed_count == 0
        assert summary.avg_score is None
        assert summary.avg_processing_time_ms is None
        assert summary.period_start is None
        assert summary.period_end is None

    def test_full_summary(self):
        """Test summary with all values."""
        start = datetime.now(UTC) - timedelta(days=1)
        end = datetime.now(UTC)

        summary = SignalLogSummary(
            total_count=1000,
            trade_eligible_count=150,
            below_threshold_count=700,
            filtered_count=100,
            executed_count=50,
            avg_score=0.65,
            avg_processing_time_ms=45.2,
            period_start=start,
            period_end=end,
        )

        assert summary.total_count == 1000
        assert summary.trade_eligible_count == 150
        assert summary.below_threshold_count == 700
        assert summary.filtered_count == 100
        assert summary.executed_count == 50
        assert summary.avg_score == 0.65
        assert summary.avg_processing_time_ms == 45.2
        assert summary.period_start == start
        assert summary.period_end == end

    def test_summary_counts_consistency(self):
        """Test summary counts can represent realistic data."""
        summary = SignalLogSummary(
            total_count=500,
            trade_eligible_count=100,
            below_threshold_count=350,
            filtered_count=50,
            executed_count=75,  # Subset of trade_eligible
        )

        # Filtered + trade_eligible + below_threshold should approx equal total
        # (executed is subset of trade_eligible)
        counted = (
            summary.filtered_count
            + summary.trade_eligible_count
            + summary.below_threshold_count
        )
        assert counted == summary.total_count
