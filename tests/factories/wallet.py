"""Factory for generating test Wallet instances."""

import factory
from faker import Faker

from walltrack.data.models.wallet import (
    TokenLaunch,
    Wallet,
    WalletProfile,
    WalletStatus,
)

fake = Faker()


def generate_valid_solana_address() -> str:
    """Generate a valid-looking Solana address (base58, 44 chars)."""
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    return "".join(fake.random_element(alphabet) for _ in range(44))


class WalletProfileFactory(factory.Factory):
    """Factory for WalletProfile model."""

    class Meta:
        model = WalletProfile

    win_rate = factory.LazyFunction(
        lambda: round(fake.pyfloat(min_value=0.3, max_value=0.9), 2)
    )
    total_pnl = factory.LazyFunction(
        lambda: round(fake.pyfloat(min_value=-1000, max_value=10000), 2)
    )
    avg_pnl_per_trade = factory.LazyFunction(
        lambda: round(fake.pyfloat(min_value=-50, max_value=200), 2)
    )
    total_trades = factory.LazyFunction(lambda: fake.random_int(min=5, max=500))
    timing_percentile = factory.LazyFunction(
        lambda: round(fake.pyfloat(min_value=0.1, max_value=0.9), 2)
    )
    avg_hold_time_hours = factory.LazyFunction(
        lambda: round(fake.pyfloat(min_value=0.5, max_value=72), 1)
    )
    preferred_hours = factory.LazyFunction(
        lambda: fake.random_elements(elements=list(range(24)), length=4, unique=True)
    )
    avg_position_size_sol = factory.LazyFunction(
        lambda: round(fake.pyfloat(min_value=0.1, max_value=10), 2)
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

        # Create wallet with profile
        wallet = WalletFactory(profile=WalletProfileFactory())
    """

    class Meta:
        model = Wallet

    address = factory.LazyFunction(generate_valid_solana_address)
    status = WalletStatus.ACTIVE
    score = factory.LazyFunction(
        lambda: round(fake.pyfloat(min_value=0.4, max_value=0.95), 2)
    )
    profile = factory.SubFactory(WalletProfileFactory)

    # Discovery metadata
    discovered_at = factory.LazyFunction(
        lambda: fake.date_time_between(start_date="-30d", end_date="-1d")
    )
    discovery_count = factory.LazyFunction(lambda: fake.random_int(min=1, max=10))
    discovery_tokens = factory.LazyFunction(
        lambda: [generate_valid_solana_address() for _ in range(fake.random_int(1, 3))]
    )

    # Decay tracking
    decay_detected_at = None
    consecutive_losses = 0
    rolling_win_rate = None

    # Blacklist
    blacklisted_at = None
    blacklist_reason = None

    # Timestamps
    last_profiled_at = factory.LazyFunction(
        lambda: fake.date_time_between(start_date="-7d", end_date="now")
    )
    last_signal_at = None
    updated_at = factory.LazyFunction(
        lambda: fake.date_time_between(start_date="-1d", end_date="now")
    )

    class Params:
        """Factory traits for common scenarios."""

        # Create a high-performing wallet
        high_performer = factory.Trait(
            score=factory.LazyFunction(
                lambda: round(fake.pyfloat(min_value=0.85, max_value=0.99), 2)
            ),
            profile=factory.SubFactory(
                WalletProfileFactory,
                win_rate=factory.LazyFunction(
                    lambda: round(fake.pyfloat(min_value=0.7, max_value=0.9), 2)
                ),
                total_pnl=factory.LazyFunction(
                    lambda: round(fake.pyfloat(min_value=5000, max_value=20000), 2)
                ),
            ),
        )

        # Create a decayed wallet
        decayed = factory.Trait(
            status=WalletStatus.DECAY_DETECTED,
            score=factory.LazyFunction(
                lambda: round(fake.pyfloat(min_value=0.1, max_value=0.3), 2)
            ),
            decay_detected_at=factory.LazyFunction(
                lambda: fake.date_time_between(start_date="-7d", end_date="now")
            ),
            consecutive_losses=factory.LazyFunction(lambda: fake.random_int(3, 10)),
        )

        # Create a blacklisted wallet
        blacklisted = factory.Trait(
            status=WalletStatus.BLACKLISTED,
            score=0.0,
            blacklisted_at=factory.LazyFunction(
                lambda: fake.date_time_between(start_date="-7d", end_date="now")
            ),
            blacklist_reason="Detected as bot",
        )

        # Wallet with insufficient data
        insufficient_data = factory.Trait(
            status=WalletStatus.INSUFFICIENT_DATA,
            profile=factory.SubFactory(WalletProfileFactory, total_trades=3),
        )


class TokenLaunchFactory(factory.Factory):
    """Factory for TokenLaunch model."""

    class Meta:
        model = TokenLaunch

    mint = factory.LazyFunction(generate_valid_solana_address)
    symbol = factory.LazyFunction(
        lambda: fake.lexify(text="????", letters="ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    )
    launch_time = factory.LazyFunction(
        lambda: fake.date_time_between(start_date="-30d", end_date="-1d")
    )
    peak_mcap = factory.LazyFunction(
        lambda: round(fake.pyfloat(min_value=100000, max_value=10000000), 2)
    )
    current_mcap = factory.LazyFunction(
        lambda: round(fake.pyfloat(min_value=10000, max_value=1000000), 2)
    )
    volume_24h = factory.LazyFunction(
        lambda: round(fake.pyfloat(min_value=1000, max_value=500000), 2)
    )
