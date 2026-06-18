"""
GolfCourseAPI.com integration for course search and hole data.
Free tier: 50 requests/day
Docs: https://golfcourseapi.com

Auth: Authorization: Key <API_KEY>
"""

import requests
from typing import List, Dict, Any, Optional
from functools import lru_cache

from app.core.config import get_settings

API_BASE = "https://api.golfcourseapi.com/v1"


def _get_headers() -> Dict[str, str]:
    settings = get_settings()
    key = settings.golfcourseapi_key
    if not key:
        raise RuntimeError("GOLFCOURSEAPI_KEY not set. Add it to backend/.env or disable course search.")
    return {
        "Authorization": f"Key {key}",
        "Content-Type": "application/json",
    }


def search_courses(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Search for golf courses by name.
    Returns list of courses with id, name, location.
    """
    url = f"{API_BASE}/search"
    params = {
        "search_query": query,
        "limit": limit,
    }

    response = requests.get(url, headers=_get_headers(), params=params, timeout=10)
    response.raise_for_status()
    data = response.json()

    # Normalize response format
    courses = data.get("courses", [])
    normalized = []
    for course in courses:
        loc = course.get("location", {})
        normalized.append({
            "id": str(course.get("id", "")),
            "name": course.get("course_name", ""),
            "club_name": course.get("club_name", ""),
            "city": loc.get("city", ""),
            "state": loc.get("state", ""),
            "country": loc.get("country", ""),
            "holes": 18,
        })

    return normalized


def get_course_details(course_id: str) -> Dict[str, Any]:
    """
    Fetch full course details including tee boxes and hole data.
    """
    url = f"{API_BASE}/courses/{course_id}"
    response = requests.get(url, headers=_get_headers(), timeout=10)
    response.raise_for_status()
    data = response.json()

    course = data.get("course", {})
    loc = course.get("location", {})

    # Extract tee boxes from all gender categories
    tees = []
    for gender, tee_list in course.get("tees", {}).items():
        for tee in tee_list:
            tees.append({
                "tee_id": f"{gender}_{tee.get('tee_name', '').lower().replace(' ', '_')}",
                "tee_name": tee.get("tee_name", ""),
                "gender": gender,
                "length": tee.get("total_yards", 0),
                "par": tee.get("par_total", 72),
                "slope": tee.get("slope_rating", 0),
                "rating": tee.get("course_rating", 0.0),
            })

    # Extract hole data from first available tee set
    holes = []
    all_tees = course.get("tees", {})
    if all_tees:
        first_gender = list(all_tees.keys())[0]
        first_tee = all_tees[first_gender][0] if all_tees[first_gender] else None
        if first_tee and "holes" in first_tee:
            for i, hole in enumerate(first_tee["holes"], 1):
                holes.append({
                    "hole_number": i,
                    "par": hole.get("par", 4),
                    "yardage": hole.get("yardage", 0),
                    "handicap": hole.get("handicap", 0),
                })

    return {
        "id": str(course_id),
        "name": course.get("course_name", ""),
        "club_name": course.get("club_name", ""),
        "city": loc.get("city", ""),
        "state": loc.get("state", ""),
        "country": loc.get("country", ""),
        "holes_count": course.get("number_of_holes", 18),
        "tees": tees,
        "holes": holes,
    }


def get_course_with_tees(course_id: str) -> Dict[str, Any]:
    """Convenience: fetch course details formatted for our app."""
    return get_course_details(course_id)
