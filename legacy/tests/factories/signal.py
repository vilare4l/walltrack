"""Factory for generating test Signal instances."""

import factory
from faker import Faker

from walltrack.data.models.signal import Signal, SignalCreate, SignalScore, SignalSource, SignalType

fake = Faker()


class SignalScoreFactory(factory.Factory):
    """Factory for SignalScore model."""

    class Meta:
        model = SignalScore

    wallet_score = factory.LazyFunction(lambda: round(fake.pyfloat(min_value=0.5, max_value=0.95), 2))
    token_score = factory.LazyFunction(lambda: round(fake.pyfloat(min_value=0.4, max_value=0.9), 2))
    timing_score = factory.LazyFunction(lambda: round(fake.pyfloat(min_value=0.3, max_value=0.85), 2))
    cluster_score = factory.LazyFunction(lambda: round(fake.pyfloat(min_value=0.0, max_value=0.3), 2))
    final_score = factory.LazyAttribute(
        lambda obj: round(
            obj.wallet_score * 0.4 +
            obj.token_score * 0.3 +
            obj.timing_score * 0.2 +
            obj.cluster_score * 0.1,
            2
        )
    )


class SignalFactory(factory.Factory):
    """Factory for Signal model.

    Usage:
        # Create a basic signal
        signal = SignalFactory()

        # Create a high-score signal (above threshold)
        signal = SignalFactory(high_score=True)

        # Create a sell signal
        signal = SignalFactory(signal_type=SignalType.SELL)

        # Create a processed signal with trade
        signal = SignalFactory(processed=True, trade_id="trade-123")
    """

    class Meta:
        model = Signal

    id = factory.LazyFunction(lambda: fake.uuid4())
    wallet_id = factory.LazyFunction(lambda: fake.uuid4())
    wallet_address = factory.LazyFunction(
        lambda: "".join(fake.random_element("123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz") for _ in range(44))
    )
    token_address = factory.LazyFunction(
        lambda: "".join(fake.random_element("123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz") for _ in range(44))
    )
    token_symbol = factory.LazyFunction(
        lambda: fake.lexify(text="????", letters="ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    )
    signal_type = SignalType.BUY
    amount_sol = factory.LazyFunction(lambda: round(fake.pyfloat(min_value=0.1, max_value=50), 2))
    source = SignalSource.WEBHOOK
    tx_signature = factory.LazyFunction(
        lambda: "".join(fake.random_element("123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz") for _ in range(88))
    )
    score = None  # Set explicitly or use traits
    processed = False
    trade_id = None
    created_at = factory.LazyFunction(
        lambda: fake.date_time_between(start_date="-1h", end_date="now")
    )

    class Params:
        """Factory traits for common scenarios."""

        # Create a signal with high score (above 0.7 threshold)
        high_score = factory.Trait(
            score=factory.SubFactory(
                SignalScoreFactory,
                wallet_score=factory.LazyFunction(lambda: round(fake.pyfloat(min_value=0.8, max_value=0.95), 2)),
                token_score=factory.LazyFunction(lambda: round(fake.pyfloat(min_value=0.7, max_value=0.9), 2)),
            ),
        )

        # Create a signal below threshold
        low_score = factory.Trait(
            score=factory.SubFactory(
                SignalScoreFactory,
                wallet_score=factory.LazyFunction(lambda: round(fake.pyfloat(min_value=0.3, max_value=0.5), 2)),
                token_score=factory.LazyFunction(lambda: round(fake.pyfloat(min_value=0.2, max_value=0.4), 2)),
            ),
        )

        # Create a processed signal
        executed = factory.Trait(
            processed=True,
            trade_id=factory.LazyFunction(lambda: fake.uuid4()),
            score=factory.SubFactory(SignalScoreFactory),
        )

        # Include score
        with_score = factory.Trait(
            score=factory.SubFactory(SignalScoreFactory),
        )


class SignalCreateFactory(factory.Factory):
    """Factory for SignalCreate schema (input data)."""

    class Meta:
        model = SignalCreate

    wallet_address = factory.LazyFunction(
        lambda: "".join(fake.random_element("123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz") for _ in range(44))
    )
    token_address = factory.LazyFunction(
        lambda: "".join(fake.random_element("123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz") for _ in range(44))
    )
    signal_type = SignalType.BUY
    amount_sol = factory.LazyFunction(lambda: round(fake.pyfloat(min_value=0.1, max_value=50), 2))
    source = SignalSource.WEBHOOK
    tx_signature = factory.LazyFunction(
        lambda: "".join(fake.random_element("123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz") for _ in range(88))
    )
