from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from enum import Enum


class ShotResultCategory(str, Enum):
    FAIRWAY = "fairway"
    ROUGH = "rough"
    GREEN = "green"
    SAND = "sand"
    HOLE = "hole"
    PENALTY = "penalty"
    OTHER = "other"


class ShotResult(BaseModel):
    category: ShotResultCategory
    lie_quality: Optional[str] = None  # "good", "bad", "plugged", etc.
    miss_direction: Optional[str] = None  # "left", "right", "short", "long"


class GPSCoordinate(BaseModel):
    lat: Optional[float] = None
    lng: Optional[float] = None


class Shot(BaseModel):
    shot_number: int
    shot_id: str
    club: str
    distance_to_hole_before: Optional[int] = None
    distance_to_hole_after: Optional[int] = None
    shot_result: ShotResult
    gps: GPSCoordinate = Field(default_factory=GPSCoordinate)
    timestamp: datetime


class Hole(BaseModel):
    hole_number: int
    par: int = 4
    length_yards: Optional[int] = None
    handicap_stroke: Optional[int] = None
    shots: List[Shot] = Field(default_factory=list)


class CourseInfo(BaseModel):
    name: str = "Unknown Course"
    tee_box: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None


class PlayerInfo(BaseModel):
    handicap_index: Optional[float] = None
    name: Optional[str] = None


class Round(BaseModel):
    round_id: str
    user_id: str
    round_date: str  # YYYY-MM-DD
    start_time: datetime
    end_time: Optional[datetime] = None
    course: CourseInfo = Field(default_factory=CourseInfo)
    player: PlayerInfo = Field(default_factory=PlayerInfo)
    holes: List[Hole] = Field(default_factory=list)
    total_score: Optional[int] = None
    total_putts: Optional[int] = None
    fairways_hit: Optional[int] = None
    greens_in_regulation: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# Request/Response schemas
class RoundCreateRequest(BaseModel):
    course: Optional[CourseInfo] = None
    player: Optional[PlayerInfo] = None


class RoundUpdateRequest(BaseModel):
    course: Optional[CourseInfo] = None
    player: Optional[PlayerInfo] = None
    end_time: Optional[datetime] = None


class HoleCreateRequest(BaseModel):
    hole_number: int
    par: int = 4
    length_yards: Optional[int] = None
    handicap_stroke: Optional[int] = None


class ShotCreateRequest(BaseModel):
    shot_number: int
    club: str
    distance_to_hole_before: Optional[int] = None
    distance_to_hole_after: Optional[int] = None
    shot_result: ShotResult
    gps: Optional[GPSCoordinate] = None


class RoundSummary(BaseModel):
    round_id: str
    round_date: str
    course_name: str
    total_holes: int
    total_shots: int
    total_score: Optional[int] = None
    start_time: datetime
