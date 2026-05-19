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


class CoachResponse(BaseModel):
    answer: str
    context: Optional[List[Dict[str, Any]]] = None
