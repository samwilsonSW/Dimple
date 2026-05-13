from fastapi import APIRouter, HTTPException, Header
from typing import List, Optional
from app.models.round import (
    Round, RoundCreateRequest, RoundUpdateRequest,
    HoleCreateRequest, ShotCreateRequest, RoundSummary
)
from app.services.round_service import RoundService

router = APIRouter(prefix="/rounds", tags=["rounds"])


def get_user_id(authorization: Optional[str] = Header(None)) -> str:
    """Extract user ID from auth header.
    
    For now, this is a simple placeholder. In production, validate JWT
    from Supabase Auth or your auth provider.
    
    Expected header: "Bearer <user_id>" for development
    or "Bearer <jwt_token>" for production.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")
    
    parts = authorization.split(" ")
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid authorization format")
    
    # TODO: In production, verify JWT token here
    # For development, the token IS the user_id
    return parts[1]


@router.post("", response_model=Round, status_code=201)
def create_round(
    req: RoundCreateRequest,
    authorization: Optional[str] = Header(None)
):
    """Start a new round."""
    user_id = get_user_id(authorization)
    return RoundService.create_round(user_id, req)


@router.get("", response_model=List[RoundSummary])
def list_rounds(
    limit: int = 50,
    authorization: Optional[str] = Header(None)
):
    """List all rounds for the authenticated user."""
    user_id = get_user_id(authorization)
    return RoundService.list_rounds(user_id, limit)


@router.get("/{round_id}", response_model=Round)
def get_round(
    round_id: str,
    authorization: Optional[str] = Header(None)
):
    """Get a specific round by ID."""
    user_id = get_user_id(authorization)
    round_data = RoundService.get_round(round_id, user_id)
    if not round_data:
        raise HTTPException(status_code=404, detail="Round not found")
    return round_data


@router.patch("/{round_id}", response_model=Round)
def update_round(
    round_id: str,
    req: RoundUpdateRequest,
    authorization: Optional[str] = Header(None)
):
    """Update round metadata."""
    user_id = get_user_id(authorization)
    return RoundService.update_round(round_id, user_id, req)


@router.delete("/{round_id}", status_code=204)
def delete_round(
    round_id: str,
    authorization: Optional[str] = Header(None)
):
    """Delete a round."""
    user_id = get_user_id(authorization)
    success = RoundService.delete_round(round_id, user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Round not found")
    return None


@router.post("/{round_id}/holes", response_model=Round)
def add_hole(
    round_id: str,
    req: HoleCreateRequest,
    authorization: Optional[str] = Header(None)
):
    """Add a hole to a round."""
    user_id = get_user_id(authorization)
    return RoundService.add_hole(round_id, user_id, req)


@router.post("/{round_id}/holes/{hole_number}/shots", response_model=Round)
def add_shot(
    round_id: str,
    hole_number: int,
    req: ShotCreateRequest,
    authorization: Optional[str] = Header(None)
):
    """Record a shot for a specific hole."""
    user_id = get_user_id(authorization)
    return RoundService.add_shot(round_id, user_id, hole_number, req)


@router.post("/{round_id}/finish", response_model=Round)
def finish_round(
    round_id: str,
    authorization: Optional[str] = Header(None)
):
    """Mark a round as complete."""
    user_id = get_user_id(authorization)
    return RoundService.finish_round(round_id, user_id)
