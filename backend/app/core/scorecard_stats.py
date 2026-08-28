"""
Scorecard Statistics Calculator — four-category strokes gained.

Derives Strokes Gained (G, P, F, A) and aggregate stats from simple scorecard
data using Mark Broadie's methodology and a dispersion-derived expected-strokes
surface.

Categories
----------
  G  Putting       — expected vs actual putts, using first-putt distance
  P  Short game    — chips/pitches around the green (non-GIR holes)
  F  Driving       — tee shot quality on par 4s and par 5s
  A  Approach      — shots from fairway/rough to the green

Telescoping
-----------
For any reconstructed shot path, per-shot SG telescopes:

    (E_tee − 1 − E₁) + (E₁ − 1 − E₂) + … + (E_k − putts) = E_tee − score

Every intermediate expected-strokes term cancels. So the four category numbers
sum to exactly (E_tee − actual_score) for each hole, regardless of how we
attribute shots to categories. The attribution only decides *which bucket*
each stroke lands in; the total is fixed.

Implementation: we reconstruct the shot path for each hole from scorecard data,
then split the telescoped strokes into the four categories at the natural
breakpoints (tee shot → driving, approach shot → approach, chip → short game,
putts → putting).

Units
-----
Per AGENTS.md: putting distances are feet, everything else yards.
"""

from typing import List, Dict, Any, Optional
from app.models.round import HoleResult
from app.core.surface_cache import get_surface
from app.core import broadie

# Representative distance for each first-putt bucket, in feet.
_BUCKET_FT = {
    "tap_in": 2.0,
    "short": 6.0,
    "mid": 16.0,
    "long": 35.0,
}

# Default yardages when the scorecard doesn't provide one.
_DEFAULT_YARDAGE = {3: 150, 4: 400, 5: 500}


def _first_putt_ft(hole: HoleResult, handicap: float) -> float:
    """Resolve the first-putt distance in feet for a hole."""
    if hole.first_putt and hole.first_putt in _BUCKET_FT:
        return _BUCKET_FT[hole.first_putt]
    return broadie.get_first_putt_ft(handicap, gir=bool(hole.gir))


def _drive_yards(handicap: float) -> float:
    """Measured average drive distance for a handicap."""
    from app.core.empirical import aggregates_for
    return aggregates_for(handicap).avg_drive_yards


def calculate_hole_sg(
    hole: HoleResult,
    surface,
    handicap: float,
) -> Dict[str, float]:
    """
    Calculate all four SG categories for a single hole.

    Returns a dict with 'g', 'p', 'f', 'a' keys (floats).

    The reconstruction uses the scorecard signals:
      - par, yardage → tee position
      - fairway (hit/miss) → drive landing lie
      - gir → whether the green was reached in regulation
      - first_putt → where the ball finished on/near the green
      - putts → actual putt count
      - penalty_strokes → strokes lost to penalties
      - score → total strokes

    Penalty attribution: penalties are split 50/50 between driving and
    approach on par 4/5 (we can't tell which shot caused them). On par 3s,
    penalties go to approach (the only full shot).
    """
    yardage = hole.yardage or _DEFAULT_YARDAGE[hole.par]
    e_tee = surface.strokes(yardage, "tee")
    actual_putts = hole.putts
    first_putt_ft = _first_putt_ft(hole, handicap)
    e_putts = surface.strokes(first_putt_ft, "green")

    # ── Putting (G) ──────────────────────────────────────────────────────
    # SG_putting = E_putts(first_putt) - actual_putts
    sg_putting = e_putts - actual_putts

    # ── Non-GIR: there's a chip shot ─────────────────────────────────────
    # On a non-GIR hole, the player took (score - putts) strokes to reach
    # the green, and one of those is a chip from off the green.
    #
    # The chip's SG is measured against the baseline expectation from a
    # greenside position. The baseline chip finishes at the published average
    # proximity for this handicap; the actual chip finished at first_putt_ft.
    if not hole.gir:
        from app.core import published
        baseline_proximity_ft = published.interpolate(
            published.SHORT_GAME_PROXIMITY_FT, handicap
        )
        e_putts_baseline = surface.strokes(baseline_proximity_ft, "green")
        e_putts_actual = surface.strokes(first_putt_ft, "green")

        # SG_short = (1 + E_putts_baseline) - (1 + E_putts_actual)
        #          = E_putts_baseline - E_putts_actual
        # The chip stroke (1) cancels — both baseline and actual took one chip.
        sg_short = e_putts_baseline - e_putts_actual
        chip_strokes = 1  # one chip shot was taken
    else:
        sg_short = 0.0
        chip_strokes = 0

    # ── Driving (F) and Approach (A) ─────────────────────────────────────
    # We need to figure out how many strokes went to driving vs approach,
    # and what the baseline expectations are for each.

    # Penalty strokes: attributed to driving and approach. We do NOT pull
    # them out of strokes_to_green — they're in the score, and leaving them in
    # means the penalty cost shows up naturally in the SG categories (more
    # strokes than expected = negative SG). The split is a heuristic since we
    # can't tell which shot caused the penalty.
    penalties = hole.penalty_strokes

    # Actual strokes to reach the green (excluding putts and chip, but
    # INCLUDING penalty strokes — they're real strokes on the scorecard)
    strokes_to_green = hole.score - actual_putts - chip_strokes

    if hole.par == 3:
        # ── Par 3: tee shot IS the approach ──
        if hole.gir:
            # On the green in 1: SG = (E_tee - strokes_to_green) - E_putts
            sg_approach = (e_tee - strokes_to_green) - e_putts
        else:
            # Missed the green. The tee shot got us to a greenside position,
            # then we chipped on (handled by P).
            e_greenside = surface.strokes(20.0, "rough")
            sg_approach = (e_tee - strokes_to_green) - e_greenside
        sg_driving = 0.0

    elif hole.par == 4:
        # ── Par 4: drive + approach ──
        drive_yds = _drive_yards(handicap)
        remaining = max(yardage - drive_yds, 50)

        # Expected position after a baseline drive: weighted average of
        # fairway and rough based on the player's fairway percentage.
        from app.core.empirical import aggregates_for
        agg = aggregates_for(handicap)
        fw_pct = agg.fairway_pct
        e_after_drive_expected = (
            fw_pct * surface.strokes(remaining, "fairway")
            + (1 - fw_pct) * surface.strokes(remaining, "rough")
        )

        # Where did the drive actually land?
        if hole.fairway is True:
            drive_lie = "fairway"
        elif hole.fairway is False:
            drive_lie = "rough"
        else:
            drive_lie = "fairway"  # unrecorded → assume average

        e_after_drive = surface.strokes(remaining, drive_lie)

        # SG_driving = (E_tee - 1) - E_after_drive
        # This telescopes: E_tee includes the expected drive outcome,
        # and E_after_drive is where the actual drive left us.
        sg_driving = (e_tee - 1.0) - e_after_drive

        if hole.gir:
            # GIR par 4: reached green in 2 (1 drive + 1 approach)
            approach_strokes = strokes_to_green - 1  # subtract the drive
            sg_approach = (e_after_drive - approach_strokes) - e_putts
        else:
            # Non-GIR par 4: approach missed green, chip is separate (P)
            approach_strokes = strokes_to_green - 1  # subtract the drive
            e_greenside = surface.strokes(20.0, "rough")
            sg_approach = (e_after_drive - approach_strokes) - e_greenside

    else:  # par 5
        # ── Par 5: drive + 2 shots to reach green ──
        drive_yds = _drive_yards(handicap)
        remaining = max(yardage - drive_yds, 100)

        if hole.fairway is True:
            drive_lie = "fairway"
        elif hole.fairway is False:
            drive_lie = "rough"
        else:
            drive_lie = "fairway"

        e_after_drive = surface.strokes(remaining, drive_lie)

        # SG_driving = (E_tee - 1) - E_after_drive
        sg_driving = (e_tee - 1.0) - e_after_drive

        if hole.gir:
            # GIR par 5: reached green in 3 (1 drive + 2 approach shots)
            approach_strokes = strokes_to_green - 1  # subtract the drive
            sg_approach = (e_after_drive - approach_strokes) - e_putts
        else:
            # Non-GIR par 5: drive + approach shots + chip
            approach_strokes = strokes_to_green - 1  # subtract the drive
            e_greenside = surface.strokes(20.0, "rough")
            sg_approach = (e_after_drive - approach_strokes) - e_greenside

    return {"g": sg_putting, "p": sg_short, "f": sg_driving, "a": sg_approach}


def calculate_round_stats(
    hole_data: List[HoleResult],
    handicap: float,
    course_rating: Optional[float] = None,
    course_slope: Optional[int] = None,
    manual_par_values: Optional[List[int]] = None,
) -> Dict[str, Any]:
    """
    Calculate all aggregate stats from simple scorecard.

    Args:
        hole_data: List of HoleResult from scorecard
        handicap: Player's Handicap Index
        course_rating: Optional course rating for differential calc
        course_slope: Optional course slope for differential calc
        manual_par_values: Optional per-hole par for a manually entered course.

    Returns:
        Dict with all calculated stats including four-category SG
    """
    surface = get_surface(handicap)

    total_score = sum(h.score for h in hole_data)
    total_putts = sum(h.putts for h in hole_data)
    gir_count = sum(1 for h in hole_data if h.gir)
    gir_percentage = gir_count / len(hole_data) if hole_data else 0

    fairways_hit = sum(1 for h in hole_data if h.fairway is True)
    fairways_possible = sum(1 for h in hole_data if h.par > 3)
    fairway_percentage = fairways_hit / fairways_possible if fairways_possible > 0 else 0

    # Four-category SG
    sg_g = 0.0
    sg_p = 0.0
    sg_f = 0.0
    sg_a = 0.0
    for h in hole_data:
        cat = calculate_hole_sg(h, surface, handicap)
        sg_g += cat["g"]
        sg_p += cat["p"]
        sg_f += cat["f"]
        sg_a += cat["a"]

    # Strokes over/under (vs expected score)
    if manual_par_values:
        total_par = sum(
            manual_par_values[h.hole_number - 1]
            if 1 <= h.hole_number <= len(manual_par_values) else h.par
            for h in hole_data
        )
    else:
        total_par = sum(h.par for h in hole_data)

    if course_rating and course_slope:
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
        "sg_putting": round(sg_g, 2),
        "sg_short": round(sg_p, 2),
        "sg_driving": round(sg_f, 2),
        "sg_approach": round(sg_a, 2),
        "strokes_over_under": round(strokes_over_under, 2),
        "avg_putts_per_hole": round(avg_putts_per_hole, 2),
        "avg_score_to_par": round(avg_score_to_par, 2),
        **_new_input_rollups(hole_data),
    }


def _new_input_rollups(hole_data: List[HoleResult]) -> Dict[str, Any]:
    """Roll up the inputs added in migration 020."""
    out: Dict[str, Any] = {}

    if any(h.penalty_strokes for h in hole_data):
        out["total_penalty_strokes"] = sum(h.penalty_strokes for h in hole_data)
    elif hole_data:
        out["total_penalty_strokes"] = 0

    recorded = [h.first_putt_ft for h in hole_data if h.first_putt_ft is not None]
    if recorded:
        out["avg_first_putt_ft"] = round(sum(recorded) / len(recorded), 1)

    return out


def get_trend_summary(
    recent_rounds: List[Dict[str, Any]],
    num_rounds: int = 5,
) -> Dict[str, Any]:
    """Calculate trend summary from recent round stats."""
    rounds_to_analyze = recent_rounds[:num_rounds]
    if not rounds_to_analyze:
        return {}

    n = len(rounds_to_analyze)

    avg_gir = sum(r["gir_percentage"] for r in rounds_to_analyze) / n
    avg_fairway = sum(r["fairway_percentage"] for r in rounds_to_analyze) / n
    avg_putts = sum(r["total_putts"] for r in rounds_to_analyze) / n
    avg_sg_putting = sum(r.get("sg_putting", 0) for r in rounds_to_analyze) / n
    avg_sg_approach = sum(r.get("sg_approach", 0) for r in rounds_to_analyze) / n

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
