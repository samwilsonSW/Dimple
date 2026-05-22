from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any


# ── Code mappings ──
LIE_CODES = {
    "T": "tee",
    "F": "fairway",
    "R": "rough",
    "B": "sand",      # bunker
    "G": "green",
}

CLUB_CODES = {
    "D": "Driver",
    "3W": "3-wood",
    "5W": "5-wood",
    "H": "Hybrid",
    "3": "3-iron",
    "4": "4-iron",
    "5": "5-iron",
    "6": "6-iron",
    "7": "7-iron",
    "8": "8-iron",
    "9": "9-iron",
    "G": "Gap wedge",
    "L": "Lob wedge",
    "P": "Putter",
}


class ShotModel(BaseModel):
    """
    Structured shot data from user input.

    The user provides 5 things per shot:
    { before_distance, lie_type, club_used, after_distance, after_lie }

    Lie codes: T = tee, F = fairway, R = rough, B = bunker, G = green
    Club codes: D, 3W, 5W, H, 3-9, G (gap), L (lob), P (putter)

    For putting (previous lie = G):
    - Input initial putt distance (feet)
    - Input how many putts to hole (as strokes_taken)
    """
    shot_id: str
    hole_number: int
    shot_number: int = Field(..., description="1 = tee shot, 2 = approach, etc.")

    # ── User input: { before_distance, lie_type, club_used, after_distance, after_lie } ──
    before_distance_yards: int = Field(
        ...,
        description="Yards to pin before this shot (feet if on green)"
    )
    before_lie: str = Field(
        ...,
        description="Lie code: T=tee, F=fairway, R=rough, B=bunker, G=green"
    )
    club: str = Field(
        ...,
        description="Club code: D, 3W, 5W, H, 3-9, G=gap, L=lob, P=putter"
    )
    after_distance_yards: Optional[int] = Field(
        None,
        description="Yards/feet to pin after this shot (NULL if not yet known)"
    )
    after_lie: Optional[str] = Field(
        None,
        description="Lie code after shot: T, F, R, B, G, or HOLE"
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

    @field_validator("before_lie", "after_lie")
    @classmethod
    def validate_lie_code(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.upper()
        if v == "HOLE":
            return v
        if v not in LIE_CODES:
            raise ValueError(f"Invalid lie code: {v}. Must be one of: {', '.join(LIE_CODES.keys())}, HOLE")
        return v

    @field_validator("club")
    @classmethod
    def validate_club_code(cls, v: str) -> str:
        v = v.upper()
        if v not in CLUB_CODES:
            raise ValueError(f"Invalid club code: {v}. Must be one of: {', '.join(CLUB_CODES.keys())}")
        return v

    def before_lie_full(self) -> str:
        """Get full lie name for SG calculation."""
        return LIE_CODES.get(self.before_lie, self.before_lie.lower())

    def after_lie_full(self) -> Optional[str]:
        """Get full lie name for SG calculation."""
        if self.after_lie is None:
            return None
        if self.after_lie.upper() == "HOLE":
            return "hole"
        return LIE_CODES.get(self.after_lie, self.after_lie.lower())

    def club_full(self) -> str:
        """Get full club name for narrative."""
        return CLUB_CODES.get(self.club, self.club)


class RoundPayload(BaseModel):
    user_id: str
    round_date: str
    course: Dict[str, Any]
    handicap_index: float = Field(
        ...,
        description="Player's Handicap Index at time of round (e.g. 15.2, 8.4)"
    )
    shots: List[ShotModel]
    reflection: Optional[str] = Field(
        None,
        description="Player's 3-5 sentence reflection on the round. What stood out, what was good/bad, tendencies noticed."
    )


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
