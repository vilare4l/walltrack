"""Factory for generating test Trade instances."""

import factory
from faker import Faker

from walltrack.data.models.trade import Trade, TradeCreate, TradeResult, TradeStatus

fake = Faker()


class TradeFactory(factory.Factory):
    """Factory for Trade model.

    Usage:
        # Create a basic pending trade
        trade = TradeFactory()

        # Create a filled winning trade
        trade = TradeFactory(filled_win=True)

        # Create a filled losing trade
        trade = TradeFactory(filled_loss=True)

        # Create a failed trade
        trade = TradeFactory(status=TradeStatus.FAILED)
    """

    class Meta:
        model = Trade

    id = factory.LazyFunction(lambda: fake.uuid4())
    signal_id = factory.LazyFunction(lambda: fake.uuid4())
    wallet_address = factory.LazyFunction(
        lambda: "".join(fake.random_element("123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz") for _ in range(44))
    )
    token_address = factory.LazyFunction(
        lambda: "".join(fake.random_element("123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz") for _ in range(44))
    )
    token_symbol = factory.LazyFunction(
        lambda: fake.lexify(text="????", letters="ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    )
    side = "buy"
    status = TradeStatus.PENDING
    result = TradeResult.OPEN

    # Entry details
    entry_amount_sol = factory.LazyFunction(lambda: round(fake.pyfloat(min_value=0.1, max_value=10), 2))
    entry_price = None
    entry_tx = None
    entry_at = None

    # Exit details
    exit_amount_sol = None
    exit_price = None
    exit_tx = None
    exit_at = None

    # Performance
    pnl_sol = None
    pnl_percent = None
    exit_strategy = "balanced"
    moonbag_remaining = 0.0

    # Metadata
    score_at_entry = factory.LazyFunction(lambda: round(fake.pyfloat(min_value=0.7, max_value=0.95), 2))
    created_at = factory.LazyFunction(
        lambda: fake.date_time_between(start_date="-1h", end_date="now")
    )
    updated_at = factory.LazyFunction(
        lambda: fake.date_time_between(start_date="-30m", end_date="now")
    )

    class Params:
        """Factory traits for common scenarios."""

        # Create a filled winning trade
        filled_win = factory.Trait(
            status=TradeStatus.FILLED,
            result=TradeResult.WIN,
            entry_price=factory.LazyFunction(lambda: round(fake.pyfloat(min_value=0.00001, max_value=0.01), 6)),
            entry_tx=factory.LazyFunction(
                lambda: "".join(fake.random_element("123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz") for _ in range(88))
            ),
            entry_at=factory.LazyFunction(lambda: fake.date_time_between(start_date="-24h", end_date="-1h")),
            exit_price=factory.LazyAttribute(lambda obj: round(obj.entry_price * fake.pyfloat(min_value=1.5, max_value=5), 6)),
            exit_amount_sol=factory.LazyAttribute(lambda obj: round(obj.entry_amount_sol * fake.pyfloat(min_value=1.3, max_value=4), 2)),
            exit_tx=factory.LazyFunction(
                lambda: "".join(fake.random_element("123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz") for _ in range(88))
            ),
            exit_at=factory.LazyFunction(lambda: fake.date_time_between(start_date="-30m", end_date="now")),
            pnl_percent=factory.LazyFunction(lambda: round(fake.pyfloat(min_value=30, max_value=300), 1)),
            pnl_sol=factory.LazyAttribute(lambda obj: round(obj.entry_amount_sol * (obj.pnl_percent / 100), 2) if obj.pnl_percent else None),
        )

        # Create a filled losing trade
        filled_loss = factory.Trait(
            status=TradeStatus.FILLED,
            result=TradeResult.LOSS,
            entry_price=factory.LazyFunction(lambda: round(fake.pyfloat(min_value=0.00001, max_value=0.01), 6)),
            entry_tx=factory.LazyFunction(
                lambda: "".join(fake.random_element("123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz") for _ in range(88))
            ),
            entry_at=factory.LazyFunction(lambda: fake.date_time_between(start_date="-24h", end_date="-1h")),
            exit_price=factory.LazyAttribute(lambda obj: round(obj.entry_price * fake.pyfloat(min_value=0.2, max_value=0.7), 6)),
            exit_amount_sol=factory.LazyAttribute(lambda obj: round(obj.entry_amount_sol * fake.pyfloat(min_value=0.2, max_value=0.6), 2)),
            exit_tx=factory.LazyFunction(
                lambda: "".join(fake.random_element("123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz") for _ in range(88))
            ),
            exit_at=factory.LazyFunction(lambda: fake.date_time_between(start_date="-30m", end_date="now")),
            pnl_percent=factory.LazyFunction(lambda: round(fake.pyfloat(min_value=-80, max_value=-20), 1)),
            pnl_sol=factory.LazyAttribute(lambda obj: round(obj.entry_amount_sol * (obj.pnl_percent / 100), 2) if obj.pnl_percent else None),
        )

        # Create an executing trade
        executing = factory.Trait(
            status=TradeStatus.EXECUTING,
            result=TradeResult.OPEN,
        )

        # Create a trade with moonbag
        with_moonbag = factory.Trait(
            exit_strategy="moonbag_aggressive",
            moonbag_remaining=factory.LazyAttribute(lambda obj: round(obj.entry_amount_sol * 0.5, 2)),
        )


class TradeCreateFactory(factory.Factory):
    """Factory for TradeCreate schema (input data)."""

    class Meta:
        model = TradeCreate

    signal_id = factory.LazyFunction(lambda: fake.uuid4())
    wallet_address = factory.LazyFunction(
        lambda: "".join(fake.random_element("123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz") for _ in range(44))
    )
    token_address = factory.LazyFunction(
        lambda: "".join(fake.random_element("123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz") for _ in range(44))
    )
    side = "buy"
    amount_sol = factory.LazyFunction(lambda: round(fake.pyfloat(min_value=0.1, max_value=10), 2))
    exit_strategy = "balanced"
