from datetime import datetime
from typing import List, Optional
from app.services.supabase_client import get_supabase
from app.models.round import (
    Round, RoundCreateRequest, RoundUpdateRequest,
    HoleCreateRequest, ShotCreateRequest, RoundSummary
)


class RoundService:
    """Service layer for round CRUD operations via Supabase."""
    
    TABLE = "rounds"
    
    @staticmethod
    def create_round(user_id: str, req: RoundCreateRequest) -> Round:
        """Create a new round for a user."""
        supabase = get_supabase()
        
        now = datetime.utcnow()
        round_data = {
            "user_id": user_id,
            "round_date": now.strftime("%Y-%m-%d"),
            "start_time": now.isoformat(),
            "course": req.course.model_dump() if req.course else {"name": "Unknown Course"},
            "player": req.player.model_dump() if req.player else {},
            "holes": [],
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }
        
        result = supabase.table(RoundService.TABLE).insert(round_data).execute()
        data = result.data[0] if result.data else None
        if not data:
            raise ValueError("Failed to create round")
        
        return Round(**data)
    
    @staticmethod
    def get_round(round_id: str, user_id: str) -> Optional[Round]:
        """Get a single round by ID, verifying ownership."""
        supabase = get_supabase()
        
        result = (
            supabase.table(RoundService.TABLE)
            .select("*")
            .eq("round_id", round_id)
            .eq("user_id", user_id)
            .single()
            .execute()
        )
        
        if not result.data:
            return None
        return Round(**result.data)
    
    @staticmethod
    def list_rounds(user_id: str, limit: int = 50) -> List[RoundSummary]:
        """List all rounds for a user, newest first."""
        supabase = get_supabase()
        
        result = (
            supabase.table(RoundService.TABLE)
            .select("round_id, round_date, course, holes, start_time, total_score")
            .eq("user_id", user_id)
            .order("start_time", desc=True)
            .limit(limit)
            .execute()
        )
        
        summaries = []
        for row in result.data or []:
            holes = row.get("holes", []) or []
            total_shots = sum(len(h.get("shots", []) or []) for h in holes)
            course = row.get("course", {}) or {}
            
            summaries.append(RoundSummary(
                round_id=row["round_id"],
                round_date=row["round_date"],
                course_name=course.get("name", "Unknown Course"),
                total_holes=len(holes),
                total_shots=total_shots,
                total_score=row.get("total_score"),
                start_time=row["start_time"],
            ))
        
        return summaries
    
    @staticmethod
    def update_round(round_id: str, user_id: str, req: RoundUpdateRequest) -> Round:
        """Update round metadata."""
        supabase = get_supabase()
        
        update_data = {"updated_at": datetime.utcnow().isoformat()}
        if req.course:
            update_data["course"] = req.course.model_dump()
        if req.player:
            update_data["player"] = req.player.model_dump()
        if req.end_time:
            update_data["end_time"] = req.end_time.isoformat()
        
        result = (
            supabase.table(RoundService.TABLE)
            .update(update_data)
            .eq("round_id", round_id)
            .eq("user_id", user_id)
            .execute()
        )
        
        if not result.data:
            raise ValueError("Round not found or not owned by user")
        
        return Round(**result.data[0])
    
    @staticmethod
    def delete_round(round_id: str, user_id: str) -> bool:
        """Delete a round."""
        supabase = get_supabase()
        
        result = (
            supabase.table(RoundService.TABLE)
            .delete()
            .eq("round_id", round_id)
            .eq("user_id", user_id)
            .execute()
        )
        
        return len(result.data or []) > 0
    
    @staticmethod
    def add_hole(round_id: str, user_id: str, req: HoleCreateRequest) -> Round:
        """Add a hole to an existing round."""
        supabase = get_supabase()
        
        # Fetch current round
        round_data = RoundService.get_round(round_id, user_id)
        if not round_data:
            raise ValueError("Round not found")
        
        # Add hole
        hole = {
            "hole_number": req.hole_number,
            "par": req.par,
            "length_yards": req.length_yards,
            "handicap_stroke": req.handicap_stroke,
            "shots": [],
        }
        holes = [h.model_dump() if hasattr(h, "model_dump") else h for h in round_data.holes]
        holes.append(hole)
        
        result = (
            supabase.table(RoundService.TABLE)
            .update({
                "holes": holes,
                "updated_at": datetime.utcnow().isoformat(),
            })
            .eq("round_id", round_id)
            .eq("user_id", user_id)
            .execute()
        )
        
        return Round(**result.data[0])
    
    @staticmethod
    def add_shot(round_id: str, user_id: str, hole_number: int, req: ShotCreateRequest) -> Round:
        """Add a shot to a specific hole in a round."""
        supabase = get_supabase()
        
        round_data = RoundService.get_round(round_id, user_id)
        if not round_data:
            raise ValueError("Round not found")
        
        # Find hole
        holes = [h.model_dump() if hasattr(h, "model_dump") else dict(h) for h in round_data.holes]
        hole = next((h for h in holes if h["hole_number"] == hole_number), None)
        if not hole:
            raise ValueError(f"Hole {hole_number} not found in round")
        
        # Add shot
        shot = {
            "shot_number": req.shot_number,
            "shot_id": f"{round_id}_{hole_number}_{req.shot_number}_{datetime.utcnow().timestamp()}",
            "club": req.club,
            "distance_to_hole_before": req.distance_to_hole_before,
            "distance_to_hole_after": req.distance_to_hole_after,
            "shot_result": req.shot_result.model_dump(),
            "gps": req.gps.model_dump() if req.gps else {"lat": None, "lng": None},
            "timestamp": datetime.utcnow().isoformat(),
        }
        hole["shots"] = hole.get("shots", [])
        hole["shots"].append(shot)
        
        # Recalculate totals
        total_shots = sum(len(h.get("shots", [])) for h in holes)
        total_score = sum(
            len(h.get("shots", [])) - h.get("par", 4) + h.get("par", 4)
            for h in holes
        )
        # Actually: score is just total shots. Par is for comparison.
        total_par = sum(h.get("par", 4) for h in holes)
        
        # Count stats
        fairways_hit = 0
        gir = 0
        total_putts = 0
        
        for h in holes:
            shots = h.get("shots", [])
            if not shots:
                continue
            
            # Fairways: par 4/5, first shot result is fairway
            if h.get("par", 4) >= 4 and len(shots) > 0:
                first_result = shots[0].get("shot_result", {}).get("category", "")
                if first_result == "fairway":
                    fairways_hit += 1
            
            # GIR: on green in regulation (par - 2 strokes or less)
            non_putts = [s for s in shots if s.get("club", "").lower() != "putter"]
            putts = [s for s in shots if s.get("club", "").lower() == "putter"]
            if len(non_putts) <= h.get("par", 4) - 2:
                gir += 1
            total_putts += len(putts)
        
        result = (
            supabase.table(RoundService.TABLE)
            .update({
                "holes": holes,
                "total_score": total_shots,
                "total_putts": total_putts,
                "fairways_hit": fairways_hit,
                "greens_in_regulation": gir,
                "updated_at": datetime.utcnow().isoformat(),
            })
            .eq("round_id", round_id)
            .eq("user_id", user_id)
            .execute()
        )
        
        return Round(**result.data[0])
    
    @staticmethod
    def finish_round(round_id: str, user_id: str) -> Round:
        """Mark a round as complete."""
        supabase = get_supabase()
        
        result = (
            supabase.table(RoundService.TABLE)
            .update({
                "end_time": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
            })
            .eq("round_id", round_id)
            .eq("user_id", user_id)
            .execute()
        )
        
        if not result.data:
            raise ValueError("Round not found")
        
        return Round(**result.data[0])
