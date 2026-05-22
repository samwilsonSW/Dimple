"""
Statistical Golf Shot Generator

Generates realistic synthetic round data by sampling from handicap-matched
distributions derived from Break X Golf aggregate stats.

Usage:
    from app.core.generator import generate_round
    round_data = generate_round(handicap=15.2, user_id="player_15hcp")
"""

import random
import uuid
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass

from app.models.round import ShotModel


# ──────────────────────────────────────────────────────────────────────────────
# STATISTICAL DISTRIBUTIONS (from Break X Golf data)
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class HandicapStats:
    """Aggregate stats for a handicap bracket."""
    avg_score: float
    avg_drive_yards: float
    drive_std: float
    fairway_pct: float
    gir_pct: float
    up_down_pct: float
    avg_putts: float
    putts_std: float


# Score variance increases with handicap — higher handicaps have more "bad days"
# σ (std dev) scales linearly: 0hcp ±3, 25hcp ±11
# This reflects real golf: beginners are wildly inconsistent, scratch players are steady
SCORE_VARIANCE = {
    0: 3.0,
    5: 4.5,
    10: 6.0,
    15: 7.5,
    20: 9.0,
    25: 11.0,
}

HANDICAP_STATS = {
    0: HandicapStats(avg_score=74.6, avg_drive_yards=274, drive_std=18, fairway_pct=0.565, gir_pct=0.568, up_down_pct=0.500, avg_putts=31.3, putts_std=2.5),
    5: HandicapStats(avg_score=79.0, avg_drive_yards=258, drive_std=20, fairway_pct=0.510, gir_pct=0.461, up_down_pct=0.377, avg_putts=32.5, putts_std=2.8),
    10: HandicapStats(avg_score=84.6, avg_drive_yards=247, drive_std=22, fairway_pct=0.493, gir_pct=0.373, up_down_pct=0.316, avg_putts=33.9, putts_std=3.0),
    15: HandicapStats(avg_score=89.3, avg_drive_yards=226, drive_std=24, fairway_pct=0.481, gir_pct=0.264, up_down_pct=0.251, avg_putts=34.8, putts_std=3.2),
    20: HandicapStats(avg_score=93.7, avg_drive_yards=219, drive_std=25, fairway_pct=0.428, gir_pct=0.224, up_down_pct=0.217, avg_putts=36.1, putts_std=3.5),
    25: HandicapStats(avg_score=98.6, avg_drive_yards=217, drive_std=26, fairway_pct=0.430, gir_pct=0.187, up_down_pct=0.203, avg_putts=37.0, putts_std=3.8),
}


def _get_stats(handicap: float) -> HandicapStats:
    """Get interpolated stats for any handicap (0-25)."""
    handicap = max(0.0, min(float(handicap), 25.0))
    brackets = sorted(HANDICAP_STATS.keys())

    if int(handicap) in HANDICAP_STATS:
        return HANDICAP_STATS[int(handicap)]

    lower_h = max(h for h in brackets if h < handicap)
    upper_h = min(h for h in brackets if h > handicap)
    ratio = (handicap - lower_h) / (upper_h - lower_h)

    lower = HANDICAP_STATS[lower_h]
    upper = HANDICAP_STATS[upper_h]

    def _interp(a, b):
        return a + ratio * (b - a)

    return HandicapStats(
        avg_score=_interp(lower.avg_score, upper.avg_score),
        avg_drive_yards=_interp(lower.avg_drive_yards, upper.avg_drive_yards),
        drive_std=_interp(lower.drive_std, upper.drive_std),
        fairway_pct=_interp(lower.fairway_pct, upper.fairway_pct),
        gir_pct=_interp(lower.gir_pct, upper.gir_pct),
        up_down_pct=_interp(lower.up_down_pct, upper.up_down_pct),
        avg_putts=_interp(lower.avg_putts, upper.avg_putts),
        putts_std=_interp(lower.putts_std, upper.putts_std),
    )


def _get_score_variance(handicap: float) -> float:
    """Get score standard deviation for a handicap.
    
    Higher handicaps have more variance — more "bad days".
    0hcp: ±3 strokes, 25hcp: ±11 strokes.
    """
    handicap = max(0.0, min(float(handicap), 25.0))
    brackets = sorted(SCORE_VARIANCE.keys())
    
    if int(handicap) in SCORE_VARIANCE:
        return SCORE_VARIANCE[int(handicap)]
    
    lower_h = max(h for h in brackets if h < handicap)
    upper_h = min(h for h in brackets if h > handicap)
    ratio = (handicap - lower_h) / (upper_h - lower_h)
    
    lower = SCORE_VARIANCE[lower_h]
    upper = SCORE_VARIANCE[upper_h]
    return lower + ratio * (upper - lower)


# ──────────────────────────────────────────────────────────────────────────────
# COURSE TEMPLATE
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class HoleTemplate:
    par: int
    distance_yards: int


DEFAULT_COURSE = [
    HoleTemplate(4, 420), HoleTemplate(4, 380), HoleTemplate(3, 175),
    HoleTemplate(4, 440), HoleTemplate(5, 520), HoleTemplate(4, 400),
    HoleTemplate(3, 160), HoleTemplate(4, 410), HoleTemplate(4, 390),
    HoleTemplate(4, 430), HoleTemplate(4, 370), HoleTemplate(3, 185),
    HoleTemplate(5, 540), HoleTemplate(4, 405), HoleTemplate(4, 395),
    HoleTemplate(3, 170), HoleTemplate(4, 450), HoleTemplate(5, 510),
]


# ──────────────────────────────────────────────────────────────────────────────
# SAMPLING HELPERS
# ──────────────────────────────────────────────────────────────────────────────

def _drive_dist(stats: HandicapStats) -> int:
    return max(180, min(350, int(random.gauss(stats.avg_drive_yards, stats.drive_std))))


def _fairway(stats: HandicapStats) -> bool:
    return random.random() < stats.fairway_pct


def _gir(stats: HandicapStats, difficulty: float = 1.0) -> bool:
    """
    Sample GIR with difficulty adjustment.
    Higher difficulty for longer approaches, tighter lies, etc.
    """
    # Scale difficulty by handicap — higher handicaps struggle more
    handicap_factor = 1.0 - (stats.avg_score - 74) * 0.012
    adjusted = stats.gir_pct * difficulty * handicap_factor
    return random.random() < adjusted


def _up_down(stats: HandicapStats) -> bool:
    # Scale by handicap — higher handicaps are worse at scrambling
    factor = 1.0 - (stats.avg_score - 74) * 0.005
    return random.random() < (stats.up_down_pct * factor)


def _putts(stats: HandicapStats) -> int:
    p = random.gauss(stats.avg_putts / 18, stats.putts_std / 4)
    return max(1, min(5, int(round(p))))


def _approach_dist() -> int:
    """Distance from pin after approach (feet if on green, yards if missed)."""
    r = random.random()
    if r < 0.45:
        return random.randint(3, 15)
    elif r < 0.75:
        return random.randint(15, 30)
    elif r < 0.90:
        return random.randint(30, 50)
    else:
        return random.randint(50, 80)


def _club(distance: int, lie: str) -> str:
    """Select club code."""
    if lie == "T":
        return "D" if distance >= 350 else "3W" if distance >= 280 else "H"
    if distance >= 220:
        return "3" if distance >= 230 else "4"
    elif distance >= 190:
        return "5"
    elif distance >= 170:
        return "6"
    elif distance >= 150:
        return "7"
    elif distance >= 130:
        return "8"
    elif distance >= 110:
        return "9"
    elif distance >= 80:
        return "G"
    else:
        return "L"


# ──────────────────────────────────────────────────────────────────────────────
# HOLE GENERATOR
# ──────────────────────────────────────────────────────────────────────────────

def generate_hole(hole_num: int, template: HoleTemplate, stats: HandicapStats, user_id: str, round_id: str) -> Tuple[List[ShotModel], int]:
    """
    Generate shots for one hole.
    Returns (shots, score).
    """
    shots: List[ShotModel] = []
    shot_num = 1
    strokes = 0

    def add_shot(before_dist, before_lie, club, after_dist, after_lie, taken=1):
        nonlocal shot_num, strokes
        shots.append(ShotModel(
            shot_id=f"{round_id}_h{hole_num}_s{shot_num}",
            hole_number=hole_num,
            shot_number=shot_num,
            before_distance_yards=before_dist,
            before_lie=before_lie,
            club=club,
            after_distance_yards=after_dist,
            after_lie=after_lie,
            strokes_taken=taken,
        ))
        shot_num += 1
        strokes += taken

    def maybe_penalty():
        """Higher handicaps hit more penalties (water, OB)."""
        penalty_prob = max(0, (stats.avg_score - 80) * 0.004)
        if random.random() < penalty_prob:
            return True
        return False

    remaining = template.distance_yards

    if template.par == 3:
        # Tee shot
        diff = 0.95 if remaining > 170 else 1.0
        if _gir(stats, diff):
            dist = _approach_dist()
            add_shot(remaining, "T", _club(remaining, "T"), dist, "G")
            p = _putts(stats)
            add_shot(dist, "G", "P", 0, "HOLE", p)
        else:
            miss = random.choices(["R", "B", "F"], weights=[0.6, 0.25, 0.15])[0]
            dist = random.randint(10, 35)
            add_shot(remaining, "T", _club(remaining, "T"), dist, miss)
            strokes += _short_game(hole_num, shots, dist, miss, stats, round_id, shot_num)

    elif template.par == 4:
        # Drive
        if maybe_penalty():
            # Penalty — re-tee
            add_shot(template.distance_yards, "T", "D", template.distance_yards, "T", 2)

        drive = _drive_dist(stats)
        fairway = _fairway(stats)
        after = "F" if fairway else random.choices(["R", "B", "F"], weights=[0.7, 0.1, 0.2])[0]
        remaining -= drive
        remaining = max(80, remaining)
        add_shot(template.distance_yards, "T", "D", remaining, after)

        # Approach
        diff = 0.85 if after == "R" else 0.90 if after == "B" else 1.0
        if _gir(stats, diff):
            dist = _approach_dist()
            add_shot(remaining, after, _club(remaining, after), dist, "G")
            p = _putts(stats)
            add_shot(dist, "G", "P", 0, "HOLE", p)
        else:
            miss = random.choices(["R", "B", "F"], weights=[0.5, 0.3, 0.2])[0]
            dist = random.randint(10, 35)
            add_shot(remaining, after, _club(remaining, after), dist, miss)
            strokes += _short_game(hole_num, shots, dist, miss, stats, round_id, shot_num)

    elif template.par == 5:
        # Drive
        if maybe_penalty():
            add_shot(template.distance_yards, "T", "D", template.distance_yards, "T", 2)

        drive = _drive_dist(stats)
        fairway = _fairway(stats)
        after = "F" if fairway else random.choices(["R", "B", "F"], weights=[0.7, 0.1, 0.2])[0]
        remaining -= drive
        remaining = max(200, remaining)
        add_shot(template.distance_yards, "T", "D", remaining, after)

        # Go for green or layup
        go_green = random.random() < max(0.1, 0.5 - (stats.avg_score - 74) * 0.015)

        if go_green and remaining < 260:
            diff = 0.80 if after == "R" else 0.85 if after == "B" else 0.90
            if _gir(stats, diff):
                dist = _approach_dist()
                add_shot(remaining, after, _club(remaining, after), dist, "G")
                p = _putts(stats)
                add_shot(dist, "G", "P", 0, "HOLE", p)
            else:
                miss = random.choices(["R", "B", "F"], weights=[0.5, 0.3, 0.2])[0]
                dist = random.randint(10, 35)
                add_shot(remaining, after, _club(remaining, after), dist, miss)
                strokes += _short_game(hole_num, shots, dist, miss, stats, round_id, shot_num)
        else:
            # Layup
            layup = random.randint(80, 120)
            remaining -= layup
            remaining = max(80, remaining)
            add_shot(remaining + layup, after, "7" if layup > 100 else "8", remaining, "F")

            # Approach from layup
            if _gir(stats, 1.05):
                dist = _approach_dist()
                add_shot(remaining, "F", _club(remaining, "F"), dist, "G")
                p = _putts(stats)
                add_shot(dist, "G", "P", 0, "HOLE", p)
            else:
                miss = random.choices(["R", "B", "F"], weights=[0.5, 0.3, 0.2])[0]
                dist = random.randint(10, 35)
                add_shot(remaining, "F", _club(remaining, "F"), dist, miss)
                strokes += _short_game(hole_num, shots, dist, miss, stats, round_id, shot_num)

    return shots, strokes


def _short_game(hole_num: int, shots: List[ShotModel], distance: int, lie: str, stats: HandicapStats, round_id: str, start_shot_num: int) -> int:
    """Add chip/pitch and putt. Returns strokes added."""
    shot_num = start_shot_num
    strokes = 0

    # Higher handicaps sometimes chunk or skull chips
    chunk_prob = max(0, (stats.avg_score - 80) * 0.02)

    if _up_down(stats):
        dist = random.randint(3, 12)
        shots.append(ShotModel(
            shot_id=f"{round_id}_h{hole_num}_s{shot_num}",
            hole_number=hole_num,
            shot_number=shot_num,
            before_distance_yards=distance,
            before_lie=lie,
            club="L" if lie == "B" else "G",
            after_distance_yards=dist,
            after_lie="G",
            strokes_taken=1,
        ))
        shot_num += 1
        strokes += 1
        shots.append(ShotModel(
            shot_id=f"{round_id}_h{hole_num}_s{shot_num}",
            hole_number=hole_num,
            shot_number=shot_num,
            before_distance_yards=dist,
            before_lie="G",
            club="P",
            after_distance_yards=0,
            after_lie="HOLE",
            strokes_taken=1,
        ))
        strokes += 1
    else:
        # Miss chip — sometimes chunk it
        if random.random() < chunk_prob:
            # Chunked chip — still on same lie or barely advanced
            dist = max(5, distance - random.randint(2, 8))
            shots.append(ShotModel(
                shot_id=f"{round_id}_h{hole_num}_s{shot_num}",
                hole_number=hole_num,
                shot_number=shot_num,
                before_distance_yards=distance,
                before_lie=lie,
                club="L" if lie == "B" else "G",
                after_distance_yards=dist,
                after_lie=lie,
                strokes_taken=1,
            ))
            shot_num += 1
            strokes += 1
            # Try again
            dist2 = random.randint(15, 30)
            shots.append(ShotModel(
                shot_id=f"{round_id}_h{hole_num}_s{shot_num}",
                hole_number=hole_num,
                shot_number=shot_num,
                before_distance_yards=dist,
                before_lie=lie,
                club="L" if lie == "B" else "G",
                after_distance_yards=dist2,
                after_lie="G",
                strokes_taken=1,
            ))
            shot_num += 1
            strokes += 1
            shots.append(ShotModel(
                shot_id=f"{round_id}_h{hole_num}_s{shot_num}",
                hole_number=hole_num,
                shot_number=shot_num,
                before_distance_yards=dist2,
                before_lie="G",
                club="P",
                after_distance_yards=0,
                after_lie="HOLE",
                strokes_taken=2,
            ))
            strokes += 2
        else:
            dist = random.randint(15, 30)
            shots.append(ShotModel(
                shot_id=f"{round_id}_h{hole_num}_s{shot_num}",
                hole_number=hole_num,
                shot_number=shot_num,
                before_distance_yards=distance,
                before_lie=lie,
                club="L" if lie == "B" else "G",
                after_distance_yards=dist,
                after_lie="G",
                strokes_taken=1,
            ))
            shot_num += 1
            strokes += 1
            shots.append(ShotModel(
                shot_id=f"{round_id}_h{hole_num}_s{shot_num}",
                hole_number=hole_num,
                shot_number=shot_num,
                before_distance_yards=dist,
                before_lie="G",
                club="P",
                after_distance_yards=0,
                after_lie="HOLE",
                strokes_taken=2,
            ))
            strokes += 2

    return strokes


# ──────────────────────────────────────────────────────────────────────────────
# ROUND ASSEMBLER
# ──────────────────────────────────────────────────────────────────────────────

def generate_round(
    handicap: float,
    user_id: str,
    course_name: str = "Pine Valley Golf Club",
    round_date: str = "2026-05-21",
) -> Dict[str, Any]:
    """Generate a complete synthetic round.
    
    Score variance increases with handicap — higher handicaps have more "bad days".
    A 0hcp might shoot 72-78, while a 25hcp might shoot 88-132.
    """
    stats = _get_stats(handicap)
    variance = _get_score_variance(handicap)
    round_id = f"round_{uuid.uuid4().hex[:8]}"

    all_shots: List[ShotModel] = []
    total_score = 0

    for i, template in enumerate(DEFAULT_COURSE, 1):
        hole_shots, hole_score = generate_hole(i, template, stats, user_id, round_id)
        all_shots.extend(hole_shots)
        total_score += hole_score

    # Apply score variance: shift total score based on handicap-adjusted std dev
    # Higher handicaps get more negative variance (more bad days)
    # We use a skewed distribution: bad days are worse than good days are good
    if variance > 0:
        raw_shift = random.gauss(0, variance)
        # Apply skew: shift distribution toward higher scores (bad days)
        if raw_shift > 0:
            shift = raw_shift * 0.6  # Good days are modestly better
        else:
            shift = raw_shift * 1.4  # Bad days are significantly worse
        
        # For very high handicaps, occasional meltdown rounds
        if handicap >= 20 and random.random() < 0.15:
            shift -= variance * 1.5  # Extra bad day
        
        # Cap the shift to prevent absurd scores (no one shoots 45 or 150)
        max_shift = int(variance * 2.5)
        shift = max(-max_shift, min(max_shift, shift))
        
        # Apply shift by adding/removing penalty strokes to random holes
        shift_strokes = int(round(shift))
        if shift_strokes != 0:
            # Distribute extra strokes across holes (penalties, chunks, etc.)
            direction = 1 if shift_strokes > 0 else -1
            holes_to_penalize = random.sample(range(1, 19), min(abs(shift_strokes), 18))
            for hole_num in holes_to_penalize:
                # Find a shot on this hole and add/remove a stroke
                for shot in all_shots:
                    if shot.hole_number == hole_num:
                        if direction > 0 and shot.strokes_taken >= 1:
                            # Add a penalty stroke
                            shot.strokes_taken += 1
                            total_score += 1
                            break
                        elif direction < 0 and shot.strokes_taken > 1:
                            # Remove a stroke (career round — holed out, etc.)
                            shot.strokes_taken -= 1
                            total_score -= 1
                            break

    return {
        "user_id": user_id,
        "round_date": round_date,
        "course": {
            "name": course_name,
            "city": "Pine Valley",
            "state": "NJ",
            "par": sum(h.par for h in DEFAULT_COURSE),
            "total_yards": sum(h.distance_yards for h in DEFAULT_COURSE),
        },
        "handicap_index": handicap,
        "shots": [s.model_dump() for s in all_shots],
        "_meta": {
            "total_score": total_score,
            "score_variance_applied": variance,
            "round_id": round_id,
        },
    }


# ──────────────────────────────────────────────────────────────────────────────
# VALIDATION
# ──────────────────────────────────────────────────────────────────────────────

def validate_round(round_data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate generated round against target stats."""
    shots = round_data["shots"]
    handicap = round_data["handicap_index"]
    stats = _get_stats(handicap)

    # Count key stats
    drives = [s for s in shots if s["before_lie"] == "T"]
    fairways = [s for s in drives if s["after_lie"] == "F"]
    approaches = [s for s in shots if s["before_lie"] in ["F", "R"] and s["after_lie"] in ["G", "R", "B", "F"]]
    greens = [s for s in approaches if s["after_lie"] == "G"]
    putts = sum(s["strokes_taken"] for s in shots if s["club"] == "P")

    # Up & downs: chip from R/B to G, then 1 putt
    up_downs = 0
    for i, s in enumerate(shots):
        if s["before_lie"] in ["R", "B"] and s["after_lie"] == "G":
            if i + 1 < len(shots) and shots[i + 1]["strokes_taken"] == 1:
                up_downs += 1

    return {
        "handicap": handicap,
        "total_score": round_data["_meta"]["total_score"],
        "target_score": round(stats.avg_score),
        "drives": len(drives),
        "fairways_hit": len(fairways),
        "fairway_pct": round(len(fairways) / len(drives), 3) if drives else 0,
        "target_fairway_pct": round(stats.fairway_pct, 3),
        "greens_hit": len(greens),
        "gir_pct": round(len(greens) / len(approaches), 3) if approaches else 0,
        "target_gir_pct": round(stats.gir_pct, 3),
        "putts": putts,
        "target_putts": round(stats.avg_putts),
        "up_downs": up_downs,
    }


if __name__ == "__main__":
    for hcp in [3, 15, 25]:
        print(f"\n=== {hcp}hcp Round ===")
        round_data = generate_round(handicap=hcp, user_id=f"player_{hcp}hcp")
        v = validate_round(round_data)
        for k, val in v.items():
            print(f"  {k}: {val}")
        print(f"  Sample shots:")
        for shot in round_data["shots"][:6]:
            print(f"    H{shot['hole_number']} S{shot['shot_number']}: {shot['before_distance_yards']}y {shot['before_lie']} -> {shot['after_distance_yards']}y/ft {shot['after_lie']} ({shot['club']}, {shot['strokes_taken']}st)")
