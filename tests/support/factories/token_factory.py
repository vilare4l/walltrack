"""
Token Factory

Generates realistic token test data for Solana memecoins.
"""

from __future__ import annotations

import factory
from faker import Faker

fake = Faker()


class TokenFactory(factory.Factory):
    """
    Factory for generating Token test data.

    Usage:
        token = TokenFactory.build()
        token = TokenFactory.build(market_cap=1_000_000)
    """

    class Meta:
        model = dict

    # Token address (Solana mint address)
    address = factory.LazyFunction(
        lambda: fake.pystr_format(
            string_format="?" * 44,
            letters="123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz",
        )
    )

    # Token metadata
    symbol = factory.LazyFunction(lambda: fake.pystr(min_chars=3, max_chars=6).upper())
    name = factory.LazyFunction(lambda: fake.catch_phrase())

    # Market data
    price_usd = factory.LazyFunction(lambda: round(fake.pyfloat(min_value=0.0001, max_value=10.0), 6))
    market_cap = factory.LazyFunction(lambda: fake.pyint(min_value=10_000, max_value=10_000_000))
    liquidity_usd = factory.LazyFunction(lambda: fake.pyint(min_value=5_000, max_value=500_000))
    volume_24h = factory.LazyFunction(lambda: fake.pyint(min_value=1_000, max_value=1_000_000))

    # Token characteristics
    age_hours = factory.LazyFunction(lambda: fake.pyint(min_value=1, max_value=720))  # Up to 30 days
    holder_count = factory.LazyFunction(lambda: fake.pyint(min_value=10, max_value=10_000))

    # Discovery metadata
    discovered_at = factory.LazyFunction(lambda: fake.date_time_this_month().isoformat())
    last_checked = factory.LazyFunction(lambda: fake.date_time_between(start_date="-7d", end_date="now").isoformat())
    source = factory.LazyFunction(lambda: fake.random_element(["dexscreener", "manual", "helius"]))


class NewTokenFactory(TokenFactory):
    """Factory for newly discovered tokens (< 24h old)."""

    age_hours = factory.LazyFunction(lambda: fake.pyint(min_value=1, max_value=24))
    holder_count = factory.LazyFunction(lambda: fake.pyint(min_value=10, max_value=500))
    market_cap = factory.LazyFunction(lambda: fake.pyint(min_value=10_000, max_value=500_000))


class MatureTokenFactory(TokenFactory):
    """Factory for mature tokens (> 7 days old)."""

    age_hours = factory.LazyFunction(lambda: fake.pyint(min_value=168, max_value=720))
    holder_count = factory.LazyFunction(lambda: fake.pyint(min_value=1_000, max_value=50_000))
    market_cap = factory.LazyFunction(lambda: fake.pyint(min_value=1_000_000, max_value=50_000_000))
