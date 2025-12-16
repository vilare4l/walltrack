"""Factory for generating test Wallet instances."""

import factory
from faker import Faker

from walltrack.data.models.wallet import Wallet, WalletMetrics, WalletStatus

fake = Faker()


class WalletMetricsFactory(factory.Factory):
    """Factory for WalletMetrics model."""

    class Meta:
        model = WalletMetrics

    win_rate = factory.LazyFunction(lambda: round(fake.pyfloat(min_value=0.3, max_value=0.9), 2))
    avg_gain = factory.LazyFunction(lambda: round(fake.pyfloat(min_value=10, max_value=200), 2))
    avg_loss = factory.LazyFunction(lambda: round(fake.pyfloat(min_value=-80, max_value=-10), 2))
    total_trades = factory.LazyFunction(lambda: fake.random_int(min=5, max=500))
    profitable_trades = factory.LazyAttribute(
        lambda obj: int(obj.total_trades * obj.win_rate)
    )
    avg_hold_time_hours = factory.LazyFunction(
        lambda: round(fake.pyfloat(min_value=0.5, max_value=72), 1)
    )
    last_trade_at = factory.LazyFunction(
        lambda: fake.date_time_between(start_date="-7d", end_date="now")
    )


class WalletFactory(factory.Factory):
    """Factory for Wallet model.

    Usage:
        # Create a basic wallet
        wallet = WalletFactory()

        # Create a high-score wallet
        wallet = WalletFactory(score=0.95)

        # Create a blacklisted wallet
        wallet = WalletFactory(status=WalletStatus.BLACKLISTED)

        # Create wallet with metrics
        wallet = WalletFactory(metrics=WalletMetricsFactory())
    """

    class Meta:
        model = Wallet

    id = factory.LazyFunction(lambda: fake.uuid4())
    address = factory.LazyFunction(
        lambda: fake.hexify(text="^" * 44, upper=False).replace("^", lambda: fake.random_element("123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"))
    )
    label = factory.LazyFunction(lambda: fake.word() if fake.boolean(chance_of_getting_true=30) else None)
    status = WalletStatus.ACTIVE
    score = factory.LazyFunction(lambda: round(fake.pyfloat(min_value=0.4, max_value=0.95), 2))
    metrics = None  # Set explicitly when needed
    cluster_id = factory.LazyFunction(
        lambda: fake.uuid4() if fake.boolean(chance_of_getting_true=40) else None
    )
    source = factory.LazyFunction(
        lambda: fake.random_element(["manual", "scanner", "recommendation", "helius"])
    )
    created_at = factory.LazyFunction(
        lambda: fake.date_time_between(start_date="-30d", end_date="-1d")
    )
    updated_at = factory.LazyFunction(
        lambda: fake.date_time_between(start_date="-1d", end_date="now")
    )

    class Params:
        """Factory traits for common scenarios."""

        # Create a high-performing wallet
        high_performer = factory.Trait(
            score=factory.LazyFunction(lambda: round(fake.pyfloat(min_value=0.85, max_value=0.99), 2)),
            metrics=factory.SubFactory(
                WalletMetricsFactory,
                win_rate=factory.LazyFunction(lambda: round(fake.pyfloat(min_value=0.7, max_value=0.9), 2)),
            ),
        )

        # Create a decayed wallet
        decayed = factory.Trait(
            status=WalletStatus.DECAYED,
            score=factory.LazyFunction(lambda: round(fake.pyfloat(min_value=0.1, max_value=0.3), 2)),
        )

        # Create a blacklisted wallet
        blacklisted = factory.Trait(
            status=WalletStatus.BLACKLISTED,
            score=0.0,
        )

        # Include full metrics
        with_metrics = factory.Trait(
            metrics=factory.SubFactory(WalletMetricsFactory),
        )


def generate_valid_solana_address() -> str:
    """Generate a valid-looking Solana address (base58, 44 chars)."""
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    return "".join(fake.random_element(alphabet) for _ in range(44))
