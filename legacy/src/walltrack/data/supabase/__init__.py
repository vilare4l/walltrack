"""Supabase data access layer."""

from walltrack.data.supabase.client import (
    SupabaseClient,
    close_supabase_client,
    get_supabase_client,
)

__all__ = ["SupabaseClient", "close_supabase_client", "get_supabase_client"]
