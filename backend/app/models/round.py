from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class ShotModel(BaseModel):
    shot_id: str
    hole_number: int
    club: str
    distance: int = Field(
        ...,
        description="Distance the ball traveled (yards). Deprecated: use before_distance_yards + after_distance_yards for SG."
    )
    narrative: str = Field(
        ...,
        description="e.g. 'Hit 7-iron 160 yards from fairway to green'"
    )
    # ── SG fields (optional for backward compat, required for SG calc) ──
    before_distance_yards: Optional[int] = Field(
        None,
        description="Yards to pin before this shot"
    )
    before_lie: Optional[str] = Field(
        None,
        description="Lie before shot: tee, fairway, rough, sand, green, hazard, ob"
    )
    after_distance_yards: Optional[int] = Field(
        None,
        description="Yards (or feet if on green) to pin after this shot"
    )
    after_lie: Optional[str] = Field(
        None,
        description="Lie after shot: fairway, rough, sand, green, hazard, ob"
    )
    strokes_taken: int = Field(
        default=1,
        description="Strokes used (1 for normal, 2+ for penalties/re-hits)"
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
