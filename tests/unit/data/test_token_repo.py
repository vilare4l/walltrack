"""Unit tests for Token Repository.

Tests cover:
- Upserting tokens (new and update)
- Getting all tokens
- Getting token by mint address
- Getting token count
- Deleting tokens
- Error handling for database operations
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from walltrack.data.models.token import Token


class TestTokenRepositoryUpsert:
    """Tests for TokenRepository upsert operations."""

    @pytest.fixture
    def mock_supabase_client(self):
        """Create mock Supabase client."""
        client = MagicMock()
        client.client = MagicMock()
        return client

    @pytest.mark.asyncio
    async def test_upsert_tokens_with_new_tokens(self, mock_supabase_client):
        """Should insert new tokens and return correct counts."""
        from walltrack.data.supabase.repositories.token_repo import TokenRepository

        # Mock: no existing tokens
        mock_supabase_client.client.table.return_value.select.return_value.in_.return_value.execute = AsyncMock(
            return_value=MagicMock(data=[])
        )

        # Mock: upsert succeeds
        mock_supabase_client.client.table.return_value.upsert.return_value.execute = AsyncMock(
            return_value=MagicMock(data=[])
        )

        tokens = [
            Token(mint="token1", symbol="TK1", name="Token One"),
            Token(mint="token2", symbol="TK2", name="Token Two"),
        ]

        repo = TokenRepository(mock_supabase_client)
        new_count, updated_count = await repo.upsert_tokens(tokens)

        assert new_count == 2
        assert updated_count == 0
        mock_supabase_client.client.table.assert_called_with("tokens")

    @pytest.mark.asyncio
    async def test_upsert_tokens_with_existing_tokens(self, mock_supabase_client):
        """Should update existing tokens and return correct counts."""
        from walltrack.data.supabase.repositories.token_repo import TokenRepository

        # Mock: one existing token
        mock_supabase_client.client.table.return_value.select.return_value.in_.return_value.execute = AsyncMock(
            return_value=MagicMock(data=[{"mint": "token1"}])
        )

        # Mock: upsert succeeds
        mock_supabase_client.client.table.return_value.upsert.return_value.execute = AsyncMock(
            return_value=MagicMock(data=[])
        )

        tokens = [
            Token(mint="token1", symbol="TK1", name="Token One"),
            Token(mint="token2", symbol="TK2", name="Token Two"),
        ]

        repo = TokenRepository(mock_supabase_client)
        new_count, updated_count = await repo.upsert_tokens(tokens)

        assert new_count == 1
        assert updated_count == 1

    @pytest.mark.asyncio
    async def test_upsert_tokens_with_empty_list(self, mock_supabase_client):
        """Should return zeros for empty token list."""
        from walltrack.data.supabase.repositories.token_repo import TokenRepository

        repo = TokenRepository(mock_supabase_client)
        new_count, updated_count = await repo.upsert_tokens([])

        assert new_count == 0
        assert updated_count == 0

    @pytest.mark.asyncio
    async def test_upsert_tokens_raises_on_error(self, mock_supabase_client):
        """Should raise exception on database error."""
        from walltrack.data.supabase.repositories.token_repo import TokenRepository

        # Mock: existing check passes
        mock_supabase_client.client.table.return_value.select.return_value.in_.return_value.execute = AsyncMock(
            return_value=MagicMock(data=[])
        )

        # Mock: upsert fails
        mock_supabase_client.client.table.return_value.upsert.return_value.execute = AsyncMock(
            side_effect=Exception("Database connection failed")
        )

        tokens = [Token(mint="token1", symbol="TK1")]

        repo = TokenRepository(mock_supabase_client)

        with pytest.raises(Exception, match="Database connection failed"):
            await repo.upsert_tokens(tokens)


class TestTokenRepositoryGetAll:
    """Tests for TokenRepository get_all method."""

    @pytest.fixture
    def mock_supabase_client(self):
        """Create mock Supabase client."""
        client = MagicMock()
        client.client = MagicMock()
        return client

    @pytest.mark.asyncio
    async def test_get_all_returns_tokens(self, mock_supabase_client):
        """Should return list of Token models."""
        from walltrack.data.supabase.repositories.token_repo import TokenRepository

        mock_supabase_client.client.table.return_value.select.return_value.order.return_value.limit.return_value.execute = AsyncMock(
            return_value=MagicMock(
                data=[
                    {"mint": "token1", "symbol": "TK1", "name": "Token One"},
                    {"mint": "token2", "symbol": "TK2", "name": "Token Two"},
                ]
            )
        )

        repo = TokenRepository(mock_supabase_client)
        tokens = await repo.get_all()

        assert len(tokens) == 2
        assert tokens[0].mint == "token1"
        assert tokens[0].symbol == "TK1"
        assert tokens[1].mint == "token2"

    @pytest.mark.asyncio
    async def test_get_all_returns_empty_list_when_no_tokens(self, mock_supabase_client):
        """Should return empty list when no tokens in database."""
        from walltrack.data.supabase.repositories.token_repo import TokenRepository

        mock_supabase_client.client.table.return_value.select.return_value.order.return_value.limit.return_value.execute = AsyncMock(
            return_value=MagicMock(data=[])
        )

        repo = TokenRepository(mock_supabase_client)
        tokens = await repo.get_all()

        assert tokens == []

    @pytest.mark.asyncio
    async def test_get_all_returns_empty_on_error(self, mock_supabase_client):
        """Should return empty list on database error."""
        from walltrack.data.supabase.repositories.token_repo import TokenRepository

        mock_supabase_client.client.table.return_value.select.return_value.order.return_value.limit.return_value.execute = AsyncMock(
            side_effect=Exception("Database error")
        )

        repo = TokenRepository(mock_supabase_client)
        tokens = await repo.get_all()

        assert tokens == []


class TestTokenRepositoryGetByMint:
    """Tests for TokenRepository get_by_mint method."""

    @pytest.fixture
    def mock_supabase_client(self):
        """Create mock Supabase client."""
        client = MagicMock()
        client.client = MagicMock()
        return client

    @pytest.mark.asyncio
    async def test_get_by_mint_returns_token_when_exists(self, mock_supabase_client):
        """Should return Token when mint exists."""
        from walltrack.data.supabase.repositories.token_repo import TokenRepository

        mock_supabase_client.client.table.return_value.select.return_value.eq.return_value.single.return_value.execute = AsyncMock(
            return_value=MagicMock(
                data={"mint": "token1", "symbol": "TK1", "name": "Token One"}
            )
        )

        repo = TokenRepository(mock_supabase_client)
        token = await repo.get_by_mint("token1")

        assert token is not None
        assert token.mint == "token1"
        assert token.symbol == "TK1"

    @pytest.mark.asyncio
    async def test_get_by_mint_returns_none_when_not_exists(self, mock_supabase_client):
        """Should return None when mint does not exist."""
        from walltrack.data.supabase.repositories.token_repo import TokenRepository

        mock_supabase_client.client.table.return_value.select.return_value.eq.return_value.single.return_value.execute = AsyncMock(
            return_value=MagicMock(data=None)
        )

        repo = TokenRepository(mock_supabase_client)
        token = await repo.get_by_mint("nonexistent")

        assert token is None

    @pytest.mark.asyncio
    async def test_get_by_mint_returns_none_on_error(self, mock_supabase_client):
        """Should return None on database error."""
        from walltrack.data.supabase.repositories.token_repo import TokenRepository

        mock_supabase_client.client.table.return_value.select.return_value.eq.return_value.single.return_value.execute = AsyncMock(
            side_effect=Exception("Not found")
        )

        repo = TokenRepository(mock_supabase_client)
        token = await repo.get_by_mint("token1")

        assert token is None


class TestTokenRepositoryGetCount:
    """Tests for TokenRepository get_count method."""

    @pytest.fixture
    def mock_supabase_client(self):
        """Create mock Supabase client."""
        client = MagicMock()
        client.client = MagicMock()
        return client

    @pytest.mark.asyncio
    async def test_get_count_returns_count(self, mock_supabase_client):
        """Should return token count."""
        from walltrack.data.supabase.repositories.token_repo import TokenRepository

        mock_supabase_client.client.table.return_value.select.return_value.execute = AsyncMock(
            return_value=MagicMock(count=42)
        )

        repo = TokenRepository(mock_supabase_client)
        count = await repo.get_count()

        assert count == 42

    @pytest.mark.asyncio
    async def test_get_count_returns_zero_on_error(self, mock_supabase_client):
        """Should return 0 on database error."""
        from walltrack.data.supabase.repositories.token_repo import TokenRepository

        mock_supabase_client.client.table.return_value.select.return_value.execute = AsyncMock(
            side_effect=Exception("Database error")
        )

        repo = TokenRepository(mock_supabase_client)
        count = await repo.get_count()

        assert count == 0


class TestTokenRepositoryDelete:
    """Tests for TokenRepository delete operations."""

    @pytest.fixture
    def mock_supabase_client(self):
        """Create mock Supabase client."""
        client = MagicMock()
        client.client = MagicMock()
        return client

    @pytest.mark.asyncio
    async def test_delete_by_mint_returns_true_on_success(self, mock_supabase_client):
        """Should return True when delete succeeds."""
        from walltrack.data.supabase.repositories.token_repo import TokenRepository

        mock_supabase_client.client.table.return_value.delete.return_value.eq.return_value.execute = AsyncMock(
            return_value=MagicMock(data=[])
        )

        repo = TokenRepository(mock_supabase_client)
        result = await repo.delete_by_mint("token1")

        assert result is True

    @pytest.mark.asyncio
    async def test_delete_by_mint_returns_false_on_error(self, mock_supabase_client):
        """Should return False on database error."""
        from walltrack.data.supabase.repositories.token_repo import TokenRepository

        mock_supabase_client.client.table.return_value.delete.return_value.eq.return_value.execute = AsyncMock(
            side_effect=Exception("Delete failed")
        )

        repo = TokenRepository(mock_supabase_client)
        result = await repo.delete_by_mint("token1")

        assert result is False
