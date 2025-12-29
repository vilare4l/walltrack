"""Token repository for Supabase.

This module provides a repository pattern for accessing the tokens table
in Supabase, storing discovered tokens from DexScreener and other sources.

Table schema expected:
    tokens (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        mint TEXT UNIQUE NOT NULL,
        symbol TEXT,
        name TEXT,
        price_usd NUMERIC,
        market_cap NUMERIC,
        volume_24h NUMERIC,
        liquidity_usd NUMERIC,
        age_minutes INTEGER,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW(),
        last_checked TIMESTAMPTZ
    )
"""

from datetime import UTC, datetime

import structlog

from walltrack.data.models.token import Token
from walltrack.data.supabase.client import SupabaseClient

log = structlog.get_logger(__name__)


class TokenRepository:
    """Repository for accessing tokens table in Supabase.

    Provides CRUD operations for token records, with specialized
    methods for discovery upsert and querying.

    Attributes:
        _client: SupabaseClient instance for database operations.

    Example:
        client = await get_supabase_client()
        repo = TokenRepository(client)
        await repo.upsert_tokens([token1, token2])
        tokens = await repo.get_all()
    """

    TABLE_NAME = "tokens"

    def __init__(self, client: SupabaseClient) -> None:
        """Initialize repository with Supabase client.

        Args:
            client: Connected SupabaseClient instance.
        """
        self._client = client

    async def upsert_tokens(self, tokens: list[Token]) -> tuple[int, int]:
        """Upsert multiple tokens (insert or update on conflict).

        Args:
            tokens: List of Token models to upsert.

        Returns:
            Tuple of (new_count, updated_count).

        Note:
            Uses mint as the unique constraint for conflict resolution.
        """
        if not tokens:
            return 0, 0

        try:
            # Get existing mints to count new vs updated
            mints = [t.mint for t in tokens]
            existing = await self._get_existing_mints(mints)
            existing_set = set(existing)

            # Prepare records for upsert
            records = []
            now = datetime.now(UTC).isoformat()

            for token in tokens:
                record = {
                    "mint": token.mint,
                    "symbol": token.symbol,
                    "name": token.name,
                    "price_usd": token.price_usd,
                    "market_cap": token.market_cap,
                    "volume_24h": token.volume_24h,
                    "liquidity_usd": token.liquidity_usd,
                    "age_minutes": token.age_minutes,
                    "last_checked": now,
                }
                records.append(record)

            # Perform bulk upsert
            await (
                self._client.client.table(self.TABLE_NAME)
                .upsert(records, on_conflict="mint")
                .execute()
            )

            # Count new vs updated
            new_count = sum(1 for t in tokens if t.mint not in existing_set)
            updated_count = len(tokens) - new_count

            log.info(
                "tokens_upserted",
                total=len(tokens),
                new=new_count,
                updated=updated_count,
            )

            return new_count, updated_count

        except Exception as e:
            log.error("tokens_upsert_failed", error=str(e), count=len(tokens))
            raise

    async def _get_existing_mints(self, mints: list[str]) -> list[str]:
        """Get list of mints that already exist in database.

        Args:
            mints: List of mint addresses to check.

        Returns:
            List of mints that already exist.
        """
        if not mints:
            return []

        try:
            result = await (
                self._client.client.table(self.TABLE_NAME)
                .select("mint")
                .in_("mint", mints)
                .execute()
            )

            return [r["mint"] for r in (result.data or [])]

        except Exception as e:
            log.warning("get_existing_mints_failed", error=str(e))
            return []

    async def get_all(self, limit: int = 1000) -> list[Token]:
        """Get all tokens from database.

        Args:
            limit: Maximum number of tokens to return.

        Returns:
            List of Token models.
        """
        try:
            result = await (
                self._client.client.table(self.TABLE_NAME)
                .select("*")
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )

            tokens = []
            for row in result.data or []:
                tokens.append(Token(**row))

            return tokens

        except Exception as e:
            log.warning("tokens_get_all_failed", error=str(e))
            return []

    async def get_by_mint(self, mint: str) -> Token | None:
        """Get single token by mint address.

        Args:
            mint: Solana token mint address.

        Returns:
            Token if found, None otherwise.
        """
        try:
            result = await (
                self._client.client.table(self.TABLE_NAME)
                .select("*")
                .eq("mint", mint)
                .single()
                .execute()
            )

            if result.data:
                return Token(**result.data)
            return None

        except Exception as e:
            log.warning("token_get_by_mint_failed", mint=mint, error=str(e))
            return None

    async def get_count(self) -> int:
        """Get total count of tokens in database.

        Returns:
            Number of tokens stored.
        """
        try:
            result = await (
                self._client.client.table(self.TABLE_NAME)
                .select("id", count="exact")
                .execute()
            )

            return result.count or 0

        except Exception as e:
            log.warning("tokens_count_failed", error=str(e))
            return 0

    async def get_latest_checked_time(self) -> str | None:
        """Get the most recent last_checked timestamp.

        Returns:
            ISO format timestamp string of the most recent check,
            or None if no tokens exist.
        """
        try:
            result = await (
                self._client.client.table(self.TABLE_NAME)
                .select("last_checked")
                .order("last_checked", desc=True)
                .limit(1)
                .execute()
            )

            if result.data and result.data[0].get("last_checked"):
                return result.data[0]["last_checked"]
            return None

        except Exception as e:
            log.warning("get_latest_checked_time_failed", error=str(e))
            return None

    async def delete_by_mint(self, mint: str) -> bool:
        """Delete token by mint address.

        Args:
            mint: Solana token mint address.

        Returns:
            True if deleted, False otherwise.
        """
        try:
            await (
                self._client.client.table(self.TABLE_NAME)
                .delete()
                .eq("mint", mint)
                .execute()
            )
            log.info("token_deleted", mint=mint)
            return True

        except Exception as e:
            log.warning("token_delete_failed", mint=mint, error=str(e))
            return False
