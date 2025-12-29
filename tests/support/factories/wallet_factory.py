"""
Wallet Factory

Generates realistic wallet test data using Faker.
Supports both in-memory (build) and persisted (create) modes.
"""

from __future__ import annotations

import factory
from faker import Faker

fake = Faker()


class WalletFactory(factory.Factory):
    """
    Factory for generating Wallet test data.

    Usage:
        # In-memory wallet (no DB)
        wallet = WalletFactory.build()

        # Wallet with custom values
        wallet = WalletFactory.build(
            win_rate=0.85,
            decay_status="ok"
        )

        # Multiple wallets
        wallets = WalletFactory.build_batch(10)
    """

    class Meta:
        model = dict  # Returns dict, replace with Pydantic model when available

    # Wallet address (Solana base58 format - 44 characters)
    address = factory.LazyFunction(
        lambda: fake.pystr_format(
            string_format="?" * 44,
            letters="123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz",
        )
    )

    # Performance metrics
    win_rate = factory.LazyFunction(lambda: round(fake.pyfloat(min_value=0.3, max_value=0.9), 2))
    pnl_total = factory.LazyFunction(
        lambda: round(fake.pyfloat(min_value=-100.0, max_value=500.0), 2)
    )
    timing_percentile = factory.LazyFunction(
        lambda: round(fake.pyfloat(min_value=0.1, max_value=0.95), 2)
    )

    # Behavioral profile
    activity_hours = factory.LazyFunction(
        lambda: {"peak_start": fake.pyint(min_value=8, max_value=12), "peak_end": fake.pyint(min_value=18, max_value=22)}
    )
    position_size_style = factory.LazyFunction(lambda: fake.random_element(["small", "medium", "large"]))
    hold_duration_avg_hours = factory.LazyFunction(lambda: fake.pyint(min_value=1, max_value=72))

    # Status
    decay_status = factory.LazyFunction(lambda: fake.random_element(["ok", "flagged", "downgraded", "dormant"]))
    is_blacklisted = False
    is_leader = factory.LazyFunction(lambda: fake.pybool(truth_probability=10))  # 10% chance

    # Metadata
    discovered_at = factory.LazyFunction(lambda: fake.date_time_this_month().isoformat())
    last_activity = factory.LazyFunction(lambda: fake.date_time_between(start_date="-7d", end_date="now").isoformat())

    # Cluster
    cluster_id = factory.LazyFunction(
        lambda: fake.uuid4() if fake.pybool(truth_probability=70) else None
    )


class HighPerformanceWalletFactory(WalletFactory):
    """Factory for high-performing wallets (good for testing signals)."""

    win_rate = factory.LazyFunction(lambda: round(fake.pyfloat(min_value=0.7, max_value=0.95), 2))
    pnl_total = factory.LazyFunction(lambda: round(fake.pyfloat(min_value=100.0, max_value=1000.0), 2))
    timing_percentile = factory.LazyFunction(lambda: round(fake.pyfloat(min_value=0.8, max_value=0.99), 2))
    decay_status = "ok"
    is_leader = True


class DecayedWalletFactory(WalletFactory):
    """Factory for wallets with decay issues."""

    win_rate = factory.LazyFunction(lambda: round(fake.pyfloat(min_value=0.2, max_value=0.4), 2))
    pnl_total = factory.LazyFunction(lambda: round(fake.pyfloat(min_value=-200.0, max_value=-10.0), 2))
    decay_status = factory.LazyFunction(lambda: fake.random_element(["flagged", "downgraded"]))
