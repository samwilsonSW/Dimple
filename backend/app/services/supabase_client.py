from supabase import create_client, Client
from app.core.config import settings
from typing import Optional

_supabase: Optional[Client] = None


def get_supabase() -> Client:
    """Get or create Supabase client singleton."""
    global _supabase
    if _supabase is None:
        if not settings.supabase_url or not settings.supabase_service_key:
            raise ValueError(
                "Supabase URL and service key must be configured. "
                "Check your .env file."
            )
        _supabase = create_client(
            settings.supabase_url,
            settings.supabase_service_key
        )
    return _supabase


def reset_supabase():
    """Reset client (useful for testing)."""
    global _supabase
    _supabase = None
