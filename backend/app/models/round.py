from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class ShotModel(BaseModel):
    shot_id: str
    hole_number: int
    club: str
    distance: int
    narrative: str = Field(
        ...,
        description="e.g. 'Hit 7-iron 160 yards from fairway to green'"
    )


class RoundPayload(BaseModel):
    user_id: str
    round_date: str
    course: Dict[str, Any]
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
