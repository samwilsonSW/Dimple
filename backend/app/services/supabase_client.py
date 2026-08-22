from supabase import create_client, Client
from supabase.lib.client_options import SyncClientOptions
from app.core.config import get_settings
from typing import Optional
import httpx
import logging

logger = logging.getLogger(__name__)

_supabase: Optional[Client] = None
_http_client: Optional[httpx.Client] = None


def get_http_client() -> httpx.Client:
    """Get or create reusable HTTP client with connection pooling."""
    global _http_client
    if _http_client is None:
        _http_client = httpx.Client(
            limits=httpx.Limits(
                max_keepalive_connections=20,
                max_connections=50,
                keepalive_expiry=30.0,
            ),
            timeout=httpx.Timeout(15.0, connect=5.0),
        )
        logger.debug("Created new HTTP client with connection pooling")
    return _http_client


def get_supabase() -> Client:
    """Get or create Supabase client singleton with connection pooling."""
    global _supabase
    if _supabase is None:
        settings = get_settings()
        http_client = get_http_client()
        options = SyncClientOptions(
            httpx_client=http_client,
            postgrest_client_timeout=15,
        )
        _supabase = create_client(
            settings.supabase_url,
            settings.supabase_key,
            options=options,
        )
        logger.debug("Created new Supabase client with pooled HTTP client")
    return _supabase
