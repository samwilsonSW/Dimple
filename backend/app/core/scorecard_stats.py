"""
Scorecard Statistics Calculator

Derives Strokes Gained and aggregate stats from simple scorecard data
using Mark Broadie's methodology and handicap-adjusted baselines.
"""

from typing import List, Dict, Any, Optional
from app.models.round import HoleResult
from app.core.baselines import get_baseline_for_handicap, HandicapBaseline


def calculate_sg_putting(hole: HoleResult, baseline: HandicapBaseline) -> float:
    """
    Calculate SG Putting for a single hole.
    
    SG Putting = Expected putts - Actual putts
    
    For GIR: expected putts from ~20ft (avg first putt after approach)
    For non-GIR: expected putts = chip + putt from ~15ft
    """
    actual_putts = hole.putts
    
    if hole.gir:
        # On green in regulation, average first putt ~20ft
        expected_putts = baseline.strokes(20, "green")
    else:
        # Missed green: chip to ~15ft, then putt
        # Chip stroke (1) + putt expectation from 15ft - 1 (the chip itself)
        expected_putts = 1.0 + (baseline.strokes(15, "green") - 1.0)
    
    return expected_putts - actual_putts


def calculate_sg_approach(hole: HoleResult, baseline: HandicapBaseline) -> float:
    """
    Calculate SG Approach proxy for a single hole from scorecard data.
    
    This is an approximation since we don't have shot-by-shot data.
    We estimate strokes to reach green based on par and yardage.
    """
    strokes_to_green = hole.score - hole.putts
    yardage = hole.yardage or _default_yardage(hole.par)
    
    # Expected strokes to reach green
    if hole.par == 3:
        # Par 3: tee shot should reach green
        # Expected = baseline from tee - baseline on green (20ft)
        expected_to_green = baseline.strokes(yardage, "tee") - baseline.strokes(20, "green")
    elif hole.par == 4:
        # Par 4: drive + approach
        # Assume drive leaves 150y approach
        drive_distance = yardage - 150
        if drive_distance < 100:
            drive_distance = 100  # minimum drive
        
        expected_drive = baseline.strokes(yardage, "tee") - baseline.strokes(150, "fairway")
        expected_approach = baseline.strokes(150, "fairway") - baseline.strokes(20, "green")
        expected_to_green = expected_drive + expected_approach
    else:  # par 5
        # Par 5: drive + 2 shots to reach green
        # Simplified: total expected - green expectation - 1 (for the extra stroke)
        expected_to_green = baseline.strokes(yardage, "tee") - baseline.strokes(20, "green") - 1.0
    
    return expected_to_green - strokes_to_green


def _default_yardage(par: int) -> int:
    """Default yardage when not provided."""
    defaults = {3: 150, 4: 400, 5: 500}
    return defaults.get(par, 400)


def calculate_round_stats(
    hole_data: List[HoleResult],
    handicap: float,
    course_rating: Optional[float] = None,
    course_slope: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Calculate all aggregate stats from simple scorecard.
    
    Args:
        hole_data: List of HoleResult from scorecard
        handicap: Player's Handicap Index
        course_rating: Optional course rating for differential calc
        course_slope: Optional course slope for differential calc
    
    Returns:
        Dict with all calculated stats
    """
    baseline = get_baseline_for_handicap(handicap)
    
    total_score = sum(h.score for h in hole_data)
    total_putts = sum(h.putts for h in hole_data)
    gir_count = sum(1 for h in hole_data if h.gir)
    gir_percentage = gir_count / len(hole_data) if hole_data else 0
    
    fairways_hit = sum(1 for h in hole_data if h.fairway is True)
    fairways_possible = sum(1 for h in hole_data if h.par > 3)
    fairway_percentage = fairways_hit / fairways_possible if fairways_possible > 0 else 0
    
    # SG calculations
    sg_putting = sum(calculate_sg_putting(h, baseline) for h in hole_data)
    sg_approach = sum(calculate_sg_approach(h, baseline) for h in hole_data)
    
    # Strokes over/under (vs expected score)
    total_par = sum(h.par for h in hole_data)
    # Expected score = par + handicap (rough approximation)
    # More precise: use course rating if available
    if course_rating and course_slope:
        # Handicap differential formula
        expected_score = course_rating + (handicap * course_slope / 113)
    else:
        expected_score = total_par + handicap
    
    strokes_over_under = total_score - expected_score
    
    # Per-hole averages
    avg_putts_per_hole = total_putts / len(hole_data) if hole_data else 0
    avg_score_to_par = (total_score - total_par) / len(hole_data) if hole_data else 0
    
    return {
        "total_score": total_score,
        "total_putts": total_putts,
        "gir_count": gir_count,
        "gir_percentage": round(gir_percentage, 3),
        "fairways_hit": fairways_hit,
        "fairways_possible": fairways_possible,
        "fairway_percentage": round(fairway_percentage, 3),
        "sg_putting": round(sg_putting, 2),
        "sg_approach": round(sg_approach, 2),
        "strokes_over_under": round(strokes_over_under, 2),
        "avg_putts_per_hole": round(avg_putts_per_hole, 2),
        "avg_score_to_par": round(avg_score_to_par, 2),
    }


def get_trend_summary(
    recent_rounds: List[Dict[str, Any]],
    num_rounds: int = 5,
) -> Dict[str, Any]:
    """
    Calculate trend summary from recent round stats.
    
    Args:
        recent_rounds: List of round_stats dicts, ordered by date (newest first)
        num_rounds: Number of rounds to include in trend
    
    Returns:
        Trend summary with averages and direction
    """
    rounds_to_analyze = recent_rounds[:num_rounds]
    if not rounds_to_analyze:
        return {}
    
    n = len(rounds_to_analyze)
    
    # Calculate averages
    avg_gir = sum(r["gir_percentage"] for r in rounds_to_analyze) / n
    avg_fairway = sum(r["fairway_percentage"] for r in rounds_to_analyze) / n
    avg_putts = sum(r["total_putts"] for r in rounds_to_analyze) / n
    avg_sg_putting = sum(r["sg_putting"] for r in rounds_to_analyze) / n
    avg_sg_approach = sum(r["sg_approach"] for r in rounds_to_analyze) / n
    
    # Trend direction (compare last round vs average of previous)
    if n >= 2:
        last = rounds_to_analyze[0]
        previous_avg = sum(r["total_score"] for r in rounds_to_analyze[1:]) / (n - 1)
        score_trend = last["total_score"] - previous_avg
    else:
        score_trend = 0
    
    return {
        "rounds_analyzed": n,
        "avg_gir_percentage": round(avg_gir, 3),
        "avg_fairway_percentage": round(avg_fairway, 3),
        "avg_putts_per_round": round(avg_putts, 1),
        "avg_sg_putting": round(avg_sg_putting, 2),
        "avg_sg_approach": round(avg_sg_approach, 2),
        "score_trend": round(score_trend, 1),
        "trend_direction": "improving" if score_trend < -1 else "declining" if score_trend > 1 else "stable",
    }
