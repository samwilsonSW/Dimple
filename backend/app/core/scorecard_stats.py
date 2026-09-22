"""
Scorecard Statistics Calculator — four-category strokes gained.

Derives Strokes Gained (G, P, F, A) and aggregate stats from simple scorecard
data using Mark Broadie's telescoping decomposition over a dispersion-derived
expected-strokes surface.

Categories
----------
  G  Putting       — expected vs actual putts, from the first-putt distance
  P  Short game    — the chip/pitch around the green on non-GIR holes
  F  Driving       — tee shot quality on par 4s and par 5s
  A  Approach      — full swings from tee-shot landing position to the green

The one rule
------------
Every baseline a player is compared against is a conditional expectation of
the *same generative model the surface was solved from* (`HoleConditionals`,
solved by `expected_strokes.solve_conditionals`). No baseline in this file is
typed by hand, and none comes from any other model. Two properties follow:

1. **Conservation** (exact, per hole):  g + p + f + a = E_tee − score.
   Every intermediate position value appears once positively and once
   negatively, so attribution can move strokes between categories but can
   never invent or lose one.

2. **Zero-mean** (statistical): a player whose game matches the model's
   dispersion averages 0.00 in every category, because each phase's baseline
   is the model's own expectation of that phase. Deviations mean the player
   differs from the model — which is the thing being measured.

Penalties
---------
Penalty strokes are real strokes in `score`, and a scorecard cannot say which
swing incurred them, so they get no separate term: they flow into the
approach phase's stroke count. The baselines already price model-average
penalty exposure — the conditional tables are solved on paths that include
penalties — so a player with ordinary penalty frequency nets zero from them.
Charging them explicitly as well was tried and double-counted the cost; the
self-play gate caught it as a driving bias. Shot-level entry is what makes
per-phase penalty attribution honest, and `total_penalty_strokes` is already
surfaced separately for display.

Units
-----
Per AGENTS.md: putting distances are feet, everything else yards.
"""

from typing import Any, Dict, List, Optional

from app.models.round import HoleResult
from app.core.expected_strokes import HoleConditionals, Surface
from app.core.surface_cache import get_conditionals, get_surface

# Default yardages when the scorecard doesn't provide one.
_DEFAULT_YARDAGE = {3: 150, 4: 400, 5: 500}

# First-putt buckets accepted from the client. Band edges live in
# expected_strokes.FIRST_PUTT_BANDS and mirror the entry UI copy.
_BUCKETS = ("tap_in", "short", "mid", "long")


def calculate_hole_sg(
    hole: HoleResult,
    surface: Surface,
    cond: HoleConditionals,
) -> Dict[str, float]:
    """
    Calculate all four SG categories for a single hole.

    Returns a dict with 'g', 'p', 'f', 'a' keys (floats).

    Reconstruction from scorecard signals:
      par, yardage → tee state; fairway → drive landing (None stays neutral:
      the unconditional expectation, so an unrecorded flag contributes zero
      driving SG rather than assuming a hit); gir → whether a chip exists;
      first_putt → where the ball first lay on the green; putts and score →
      stroke counts; penalty_strokes → inside the counts, see module docstring.
    """
    par = hole.par
    yardage = float(hole.yardage or _DEFAULT_YARDAGE[par])
    putts = hole.putts
    gir = bool(hole.gir)

    e_tee = surface.strokes(yardage, "tee")

    # ── Where the ball first lay on the green, as expected putts ─────────
    # Holed from off the green (or holed the approach): no putts remained.
    if putts == 0:
        e_first_putt = 0.0
    elif hole.first_putt and hole.first_putt in _BUCKETS:
        # The band's certainty equivalent under the model — not a midpoint
        # read, which mis-prices a skewed within-band distribution.
        e_first_putt = cond.first_putt_bucket_strokes(hole.first_putt, gir)
    elif gir:
        # Unrecorded: the model's own first-putt expectation given GIR.
        e_first_putt = cond.expected_first_putt_strokes(par, yardage)
    else:
        # Unrecorded, after a chip: the model's chip finishes this well.
        e_first_putt = cond.prechip_value(par, yardage) - 1.0

    # ── Putting (G) ──────────────────────────────────────────────────────
    sg_putting = e_first_putt - putts

    # ── Short game (P): the chip on a non-GIR hole ───────────────────────
    # Baseline: the model's value of the position the ball lies in before
    # the chip on holes like this one. One chip is reconstructed per missed
    # green — a second duffed chip cannot be told apart from an extra
    # approach swing on a scorecard, and lands in A.
    if not gir:
        chip_strokes = 1
        v_prechip = cond.prechip_value(par, yardage)
        sg_short = v_prechip - 1.0 - e_first_putt
        arrival = v_prechip
    else:
        chip_strokes = 0
        sg_short = 0.0
        arrival = e_first_putt

    # ── Full swings before the green ─────────────────────────────────────
    # Penalty strokes stay inside this count, per the module docstring.
    to_green = max(hole.score - putts - chip_strokes, 1)

    if par == 3:
        # The tee shot is the approach. No driving category.
        sg_driving = 0.0
        sg_approach = e_tee - to_green - arrival
    else:
        # Driving (F): baseline is E_tee − 1 — the model's expectation over
        # all tee-shot outcomes. The actual outcome is the conditional value
        # given the fairway flag. Because p·v_hit + (1−p)·v_miss = E_tee − 1,
        # an average mix of hits and misses nets exactly zero.
        v_drive = cond.value_after_drive(par, yardage, hole.fairway)

        approach_swings = to_green - 1
        sg_driving = (e_tee - 1.0) - v_drive
        sg_approach = v_drive - approach_swings - arrival

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
    cond = get_conditionals(handicap)

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
        cat = calculate_hole_sg(h, surface, cond)
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
        # Course rating/slope is for 18 holes. If only 9 were played,
        # halve the rating and the handicap contribution.
        num_holes = len(hole_data)
        if num_holes <= 9:
            expected_score = (course_rating / 2) + (handicap * course_slope / 113 / 2)
        else:
            expected_score = course_rating + (handicap * course_slope / 113)
    else:
        # No course rating/slope — use par + handicap.
        # Handicap index is an 18-hole measure; prorate for 9-hole rounds.
        num_holes = len(hole_data)
        hcp_adjusted = handicap * (num_holes / 18) if num_holes < 18 else handicap
        expected_score = total_par + hcp_adjusted

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


def _mean(rounds: List[Dict[str, Any]], key: str) -> float | None:
    """Average `key` over the rounds that actually have it.

    Columns added by a later migration are NULL on older rounds — migration 021
    made `sg_short` and `sg_driving` nullable on purpose. Treating a NULL as 0
    would drag the average toward zero and hand the coach a number the player
    never shot, so absent values are skipped and an all-NULL column averages to
    None for the caller to render as unknown.
    """
    present = [r.get(key) for r in rounds]
    present = [v for v in present if v is not None]
    if not present:
        return None
    return sum(present) / len(present)


def _round(value: float | None, digits: int) -> float | None:
    return None if value is None else round(value, digits)


def get_trend_summary(
    recent_rounds: List[Dict[str, Any]],
    num_rounds: int = 5,
) -> Dict[str, Any]:
    """Calculate trend summary from recent round stats."""
    rounds_to_analyze = recent_rounds[:num_rounds]
    if not rounds_to_analyze:
        return {}

    n = len(rounds_to_analyze)

    avg_gir = _mean(rounds_to_analyze, "gir_percentage")
    avg_fairway = _mean(rounds_to_analyze, "fairway_percentage")
    avg_putts = _mean(rounds_to_analyze, "total_putts")
    avg_sg_putting = _mean(rounds_to_analyze, "sg_putting")
    avg_sg_approach = _mean(rounds_to_analyze, "sg_approach")

    scores = [r.get("total_score") for r in rounds_to_analyze]
    earlier = [s for s in scores[1:] if s is not None]
    if scores[0] is not None and earlier:
        score_trend = scores[0] - sum(earlier) / len(earlier)
    else:
        score_trend = 0

    return {
        "rounds_analyzed": n,
        "avg_gir_percentage": _round(avg_gir, 3),
        "avg_fairway_percentage": _round(avg_fairway, 3),
        "avg_putts_per_round": _round(avg_putts, 1),
        "avg_sg_putting": _round(avg_sg_putting, 2),
        "avg_sg_approach": _round(avg_sg_approach, 2),
        "score_trend": round(score_trend, 1),
        "trend_direction": "improving" if score_trend < -1 else "declining" if score_trend > 1 else "stable",
    }
