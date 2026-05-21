from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class ShotModel(BaseModel):
    """
    Structured shot data from user input.

    The user provides 3 things per shot:
    1. Distance to pin (yards, or feet if on green)
    2. Lie type: F/R/B/G
    3. Club code: D/H/3W/5W/3-9/G/L/P

    For putting (previous lie = G):
    - Input initial putt distance (feet)
    - Input how many putts to hole
    """
    shot_id: str
    hole_number: int
    shot_number: int = Field(..., description="1 = tee shot, 2 = approach, etc.")

    # ── User input ──
    before_distance_yards: int = Field(
        ...,
        description="Yards to pin before this shot (feet if on green)"
    )
    before_lie: str = Field(
        ...,
        description="Lie before shot: tee, fairway, rough, sand, green"
    )
    club: str = Field(
        ...,
        description="Club used: Driver, 3-wood, 5-wood, Hybrid, 3-9 iron, PW, GW, SW, LW, Putter"
    )

    # ── Derived from next shot (or 0 if holed) ──
    after_distance_yards: Optional[int] = Field(
        None,
        description="Yards to pin after this shot (NULL if not yet known)"
    )
    after_lie: Optional[str] = Field(
        None,
        description="Lie after shot: fairway, rough, sand, green, hole"
    )

    # ── Strokes ──
    strokes_taken: int = Field(
        default=1,
        description="Strokes used (1 for normal, 2+ for penalties, putt count for putting)"
    )

    # ── Auto-generated narrative for embedding ──
    narrative: Optional[str] = Field(
        None,
        description="Auto-generated from structured data. Leave null — backend generates this."
    )


class RoundPayload(BaseModel):
    user_id: str
    round_date: str
    course: Dict[str, Any]
    handicap_index: float = Field(
        ...,
        description="Player's Handicap Index at time of round (e.g. 15.2, 8.4)"
    )
    shots: List[ShotModel]


class CoachQuery(BaseModel):
    user_id: str
    question: str


class DrillRecommendation(BaseModel):
    priority: int = Field(..., description="Priority order: 1 = highest")
    focus_area: str = Field(..., description="e.g. '6-iron push', 'lag putting'")
    drill_name: str = Field(..., description="Name of the drill")
    instructions: str = Field(..., description="Step-by-step drill instructions")
    expected_outcome: str = Field(..., description="What success looks like")


class CoachResponse(BaseModel):
    answer: str = Field(..., description="Full natural-language coaching response")
    confidence: int = Field(
        ...,
        ge=1,
        le=5,
        description="Confidence in the advice: 1=speculative, 5=highly data-backed"
    )
    key_insights: List[str] = Field(
        default_factory=list,
        description="2-4 bullet-point insights extracted from the data"
    )
    drill_recommendations: List[DrillRecommendation] = Field(
        default_factory=list,
        description="Ordered list of drills to address identified issues"
    )
    context: Optional[List[Dict[str, Any]]] = None
