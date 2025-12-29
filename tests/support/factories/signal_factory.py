"""
Signal Factory

Generates realistic signal test data for testing the scoring pipeline.
"""

from __future__ import annotations

import factory
from faker import Faker

fake = Faker()


class SignalFactory(factory.Factory):
    """
    Factory for generating Signal test data.

    Usage:
        signal = SignalFactory.build()
        high_score = SignalFactory.build(score=0.85)
    """

    class Meta:
        model = dict

    # Signal identification
    id = factory.LazyFunction(lambda: fake.uuid4())

    # References
    wallet_address = factory.LazyFunction(
        lambda: fake.pystr_format(
            string_format="?" * 44,
            letters="123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz",
        )
    )
    token_address = factory.LazyFunction(
        lambda: fake.pystr_format(
            string_format="?" * 44,
            letters="123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz",
        )
    )

    # Signal data
    direction = factory.LazyFunction(lambda: fake.random_element(["buy", "sell"]))
    amount_sol = factory.LazyFunction(lambda: round(fake.pyfloat(min_value=0.1, max_value=100.0), 2))

    # Scoring
    score = factory.LazyFunction(lambda: round(fake.pyfloat(min_value=0.3, max_value=0.95), 2))
    score_breakdown = factory.LazyFunction(
        lambda: {
            "wallet_score": round(fake.pyfloat(min_value=0.3, max_value=1.0), 2),
            "cluster_score": round(fake.pyfloat(min_value=0.0, max_value=1.0), 2),
            "token_score": round(fake.pyfloat(min_value=0.3, max_value=1.0), 2),
            "context_score": round(fake.pyfloat(min_value=0.3, max_value=1.0), 2),
        }
    )

    # Status
    status = factory.LazyFunction(
        lambda: fake.random_element(["actionable", "below_threshold", "filtered", "position_created"])
    )

    # Metadata
    received_at = factory.LazyFunction(lambda: fake.date_time_between(start_date="-7d", end_date="now").isoformat())
    processed_at = factory.LazyFunction(lambda: fake.date_time_between(start_date="-7d", end_date="now").isoformat())


class ActionableSignalFactory(SignalFactory):
    """Factory for signals that should trigger positions."""

    score = factory.LazyFunction(lambda: round(fake.pyfloat(min_value=0.70, max_value=0.95), 2))
    direction = "buy"
    status = "actionable"


class HighConvictionSignalFactory(SignalFactory):
    """Factory for high conviction signals (score >= 0.85)."""

    score = factory.LazyFunction(lambda: round(fake.pyfloat(min_value=0.85, max_value=0.98), 2))
    direction = "buy"
    status = "actionable"
    score_breakdown = factory.LazyFunction(
        lambda: {
            "wallet_score": round(fake.pyfloat(min_value=0.8, max_value=1.0), 2),
            "cluster_score": round(fake.pyfloat(min_value=0.7, max_value=1.0), 2),
            "token_score": round(fake.pyfloat(min_value=0.7, max_value=1.0), 2),
            "context_score": round(fake.pyfloat(min_value=0.7, max_value=1.0), 2),
        }
    )
