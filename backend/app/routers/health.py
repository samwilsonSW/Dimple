from fastapi import APIRouter
from app.services.supabase_client import get_supabase

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
def health_check():
    """Check API and database connectivity."""
    try:
        supabase = get_supabase()
        # Lightweight ping — just check connection
        result = supabase.table("rounds").select("count", count="exact").limit(0).execute()
        return {
            "status": "healthy",
            "database": "connected",
            "count": result.count if hasattr(result, "count") else "unknown"
        }
    except Exception as e:
        return {
            "status": "degraded",
            "database": "error",
            "error": str(e)
        }
