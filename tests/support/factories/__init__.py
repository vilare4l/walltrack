"""
Test Data Factories

Factory-boy based factories for generating test data.
Follows the pattern: Faker + overrides + auto-cleanup.

Usage:
    from tests.support.factories import WalletFactory

    wallet = WalletFactory.build()  # In-memory only
    wallet = WalletFactory.create()  # Persisted to database

Pattern:
    - Use build() for unit tests (no DB)
    - Use create() for integration tests (with DB)
    - Always clean up created entities
"""

from tests.support.factories.wallet_factory import WalletFactory
from tests.support.factories.token_factory import TokenFactory
from tests.support.factories.signal_factory import SignalFactory

__all__ = ["WalletFactory", "TokenFactory", "SignalFactory"]
