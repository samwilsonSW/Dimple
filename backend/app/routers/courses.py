"""
Course search and caching endpoints.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any, Optional

from app.services.course_api import search_courses, get_course_details
from app.services.supabase_client import get_supabase

router = APIRouter(prefix="/api/v1/courses", tags=["courses"])


@router.get("/search")
def search_course_by_name(
    q: str = Query(..., min_length=2, description="Course name search query"),
    limit: int = Query(10, ge=1, le=20),
):
    """
    Search for golf courses by name.
    Queries GolfCourseAPI.com and returns matching courses.
    """
    try:
        results = search_courses(q, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Course API error: {str(e)}")

    return {
        "query": q,
        "count": len(results),
        "courses": results,
    }


@router.get("/{course_id}")
def get_course(course_id: str):
    """
    Get full course details including tee boxes and hole data.
    Checks cache first, falls back to API.
    """
    supabase = get_supabase()

    # 1) Check cache
    try:
        cached = (
            supabase.table("courses")
            .select("*")
            .eq("external_id", course_id)
            .execute()
        )
        if cached.data and len(cached.data) > 0:
            return {
                "source": "cache",
                "course": cached.data[0],
            }
    except Exception:
        pass  # Not in cache or error, fetch from API

    # 2) Fetch from API
    try:
        course_data = get_course_details(course_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Course API error: {str(e)}")

    # 3) Cache in Supabase
    try:
        cache_row = {
            "external_id": course_data["id"],
            "name": course_data["name"],
            "club_name": course_data.get("club_name", ""),
            "city": course_data.get("city", ""),
            "state": course_data.get("state", ""),
            "country": course_data.get("country", ""),
            "holes_count": course_data.get("holes_count", 18),
            "tee_data": course_data.get("tees", []),
            "hole_data": course_data.get("holes", []),
        }
        supabase.table("courses").insert(cache_row).execute()
    except Exception:
        pass  # Don't fail if cache insert fails

    return {
        "source": "api",
        "course": course_data,
    }
