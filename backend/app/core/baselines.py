"""
Strokes Gained Baseline Tables for Amateur Golfers — Handicap-Adjusted

Each player is measured against baselines matched to their Handicap Index.
This answers: "How many strokes would a [N] handicapper take from here?"

Data sources:
- Scratch/0hcp: Derived from Broadie's "Every Shot Counts" amateur data
- 5-25hcp: Calibrated to Break X Golf aggregate stats (3,788 rounds, 1,116 golfers)
  https://breakxgolf.com/golf-stats-by-handicap/

SG Formula per shot:
    SG = Baseline(before_distance, before_lie) - strokes_taken - Baseline(after_distance, after_lie)

Positive = gained strokes vs your handicap peer. Negative = lost strokes.
"""

from typing import Dict, Literal, Optional
from dataclasses import dataclass

LieType = Literal["tee", "fairway", "rough", "sand", "green", "hazard", "ob"]

# ──────────────────────────────────────────────────────────────────────────────
# HANDICAP BRACKETS
# ──────────────────────────────────────────────────────────────────────────────
# We support 0, 5, 10, 15, 20, 25. For handicaps between brackets,
# we linearly interpolate between the two nearest baseline sets.

HANDICAP_BRACKETS = [0, 5, 10, 15, 20, 25]


# ──────────────────────────────────────────────────────────────────────────────
# BASELINE TABLES PER HANDICAP BRACKET
# ──────────────────────────────────────────────────────────────────────────────
#
# Derivation logic:
# - Scratch baselines from Broadie's amateur data (directionally correct)
# - Higher handicaps are worse at everything; gap scales with difficulty
# - Key stats from Break X Golf:
#     Scratch avg score: 74.6 | 25hcp avg score: 98.6  → ~24 stroke gap
#     GIR: 56.8% → 18.7%  (biggest separator)
#     Up & Down: 50% → 20%
#     Driving: 274y → 217y (57y gap, but less scoring impact)
#
# The baseline_strokes values represent expected strokes to hole out.
# Higher handicaps = higher expected strokes from every position.

_BASELINE_DATA: Dict[int, Dict[str, Dict[int, float]]] = {
    # ── Scratch (0 hcp) ──
    0: {
        "tee": {
            500: 4.80, 450: 4.40, 400: 4.00, 350: 3.65, 300: 3.30,
            250: 3.00, 200: 2.75, 150: 2.55, 100: 2.40, 50: 2.25,
        },
        "fairway": {
            250: 3.35, 225: 3.15, 200: 2.95, 175: 2.75, 150: 2.55,
            125: 2.38, 100: 2.20, 75: 2.02, 50: 1.85, 40: 1.75,
            30: 1.65, 25: 1.58, 20: 1.52, 15: 1.46, 10: 1.40,
        },
        "rough": {
            200: 3.35, 175: 3.15, 150: 2.95, 125: 2.75, 100: 2.55,
            75: 2.35, 50: 2.15, 40: 2.05, 30: 1.95, 25: 1.88,
            20: 1.82, 15: 1.76, 10: 1.70,
        },
        "sand": {
            75: 2.75, 60: 2.65, 50: 2.55, 40: 2.45, 30: 2.35,
            25: 2.28, 20: 2.22, 15: 2.16, 10: 2.10,
        },
        "green": {
            90: 2.15, 80: 2.05, 70: 1.95, 60: 1.85, 50: 1.75,
            45: 1.70, 40: 1.65, 35: 1.60, 30: 1.55, 25: 1.50,
            20: 1.45, 18: 1.40, 15: 1.35, 12: 1.30, 10: 1.25,
            8: 1.20, 6: 1.15, 5: 1.12, 4: 1.08, 3: 1.05,
            2: 1.03, 1: 1.01,
        },
    },
    # ── 5 hcp ──
    # ~4.4 strokes worse than scratch per round
    5: {
        "tee": {
            500: 4.90, 450: 4.50, 400: 4.10, 350: 3.75, 300: 3.40,
            250: 3.10, 200: 2.85, 150: 2.65, 100: 2.48, 50: 2.32,
        },
        "fairway": {
            250: 3.45, 225: 3.25, 200: 3.05, 175: 2.85, 150: 2.65,
            125: 2.47, 100: 2.28, 75: 2.10, 50: 1.92, 40: 1.82,
            30: 1.72, 25: 1.65, 20: 1.58, 15: 1.52, 10: 1.45,
        },
        "rough": {
            200: 3.50, 175: 3.28, 150: 3.08, 125: 2.87, 100: 2.67,
            75: 2.47, 50: 2.27, 40: 2.17, 30: 2.07, 25: 2.00,
            20: 1.93, 15: 1.87, 10: 1.80,
        },
        "sand": {
            75: 2.90, 60: 2.80, 50: 2.70, 40: 2.60, 30: 2.50,
            25: 2.43, 20: 2.36, 15: 2.30, 10: 2.23,
        },
        "green": {
            90: 2.22, 80: 2.12, 70: 2.02, 60: 1.92, 50: 1.82,
            45: 1.77, 40: 1.72, 35: 1.67, 30: 1.62, 25: 1.57,
            20: 1.52, 18: 1.47, 15: 1.42, 12: 1.37, 10: 1.32,
            8: 1.27, 6: 1.22, 5: 1.18, 4: 1.14, 3: 1.10,
            2: 1.06, 1: 1.02,
        },
    },
    # ── 10 hcp ──
    # ~10 strokes worse than scratch per round
    10: {
        "tee": {
            500: 5.05, 450: 4.65, 400: 4.25, 350: 3.88, 300: 3.52,
            250: 3.22, 200: 2.95, 150: 2.75, 100: 2.55, 50: 2.38,
        },
        "fairway": {
            250: 3.58, 225: 3.37, 200: 3.16, 175: 2.95, 150: 2.75,
            125: 2.55, 100: 2.35, 75: 2.15, 50: 1.98, 40: 1.88,
            30: 1.78, 25: 1.70, 20: 1.63, 15: 1.56, 10: 1.50,
        },
        "rough": {
            200: 3.65, 175: 3.42, 150: 3.20, 125: 2.98, 100: 2.78,
            75: 2.58, 50: 2.38, 40: 2.28, 30: 2.18, 25: 2.10,
            20: 2.03, 15: 1.96, 10: 1.90,
        },
        "sand": {
            75: 3.05, 60: 2.95, 50: 2.85, 40: 2.75, 30: 2.65,
            25: 2.57, 20: 2.50, 15: 2.43, 10: 2.36,
        },
        "green": {
            90: 2.30, 80: 2.20, 70: 2.10, 60: 2.00, 50: 1.90,
            45: 1.85, 40: 1.80, 35: 1.75, 30: 1.70, 25: 1.65,
            20: 1.60, 18: 1.55, 15: 1.50, 12: 1.45, 10: 1.40,
            8: 1.35, 6: 1.30, 5: 1.26, 4: 1.22, 3: 1.17,
            2: 1.12, 1: 1.06,
        },
    },
    # ── 15 hcp ──
    # ~15 strokes worse than scratch per round
    15: {
        "tee": {
            500: 5.20, 450: 4.80, 400: 4.40, 350: 4.00, 300: 3.62,
            250: 3.32, 200: 3.05, 150: 2.82, 100: 2.62, 50: 2.45,
        },
        "fairway": {
            250: 3.72, 225: 3.50, 200: 3.28, 175: 3.05, 150: 2.85,
            125: 2.65, 100: 2.45, 75: 2.25, 50: 2.08, 40: 1.97,
            30: 1.87, 25: 1.78, 20: 1.70, 15: 1.63, 10: 1.56,
        },
        "rough": {
            200: 3.80, 175: 3.57, 150: 3.35, 125: 3.12, 100: 2.92,
            75: 2.72, 50: 2.52, 40: 2.42, 30: 2.32, 25: 2.24,
            20: 2.16, 15: 2.09, 10: 2.02,
        },
        "sand": {
            75: 3.20, 60: 3.10, 50: 3.00, 40: 2.90, 30: 2.80,
            25: 2.72, 20: 2.65, 15: 2.58, 10: 2.50,
        },
        "green": {
            90: 2.38, 80: 2.28, 70: 2.18, 60: 2.08, 50: 1.98,
            45: 1.93, 40: 1.88, 35: 1.83, 30: 1.78, 25: 1.73,
            20: 1.68, 18: 1.63, 15: 1.58, 12: 1.53, 10: 1.48,
            8: 1.43, 6: 1.38, 5: 1.33, 4: 1.29, 3: 1.24,
            2: 1.18, 1: 1.10,
        },
    },
    # ── 20 hcp ──
    # ~19 strokes worse than scratch per round
    20: {
        "tee": {
            500: 5.35, 450: 4.95, 400: 4.55, 350: 4.15, 300: 3.75,
            250: 3.42, 200: 3.15, 150: 2.92, 100: 2.70, 50: 2.52,
        },
        "fairway": {
            250: 3.88, 225: 3.65, 200: 3.42, 175: 3.18, 150: 2.98,
            125: 2.78, 100: 2.58, 75: 2.38, 50: 2.20, 40: 2.08,
            30: 1.98, 25: 1.90, 20: 1.82, 15: 1.75, 10: 1.68,
        },
        "rough": {
            200: 3.98, 175: 3.75, 150: 3.52, 125: 3.28, 100: 3.08,
            75: 2.88, 50: 2.68, 40: 2.58, 30: 2.48, 25: 2.40,
            20: 2.32, 15: 2.25, 10: 2.18,
        },
        "sand": {
            75: 3.38, 60: 3.28, 50: 3.18, 40: 3.08, 30: 2.98,
            25: 2.90, 20: 2.82, 15: 2.75, 10: 2.68,
        },
        "green": {
            90: 2.48, 80: 2.38, 70: 2.28, 60: 2.18, 50: 2.08,
            45: 2.03, 40: 1.98, 35: 1.93, 30: 1.88, 25: 1.83,
            20: 1.78, 18: 1.73, 15: 1.68, 12: 1.63, 10: 1.58,
            8: 1.53, 6: 1.48, 5: 1.43, 4: 1.38, 3: 1.33,
            2: 1.26, 1: 1.18,
        },
    },
    # ── 25 hcp ──
    # ~24 strokes worse than scratch per round
    25: {
        "tee": {
            500: 5.50, 450: 5.10, 400: 4.70, 350: 4.30, 300: 3.90,
            250: 3.55, 200: 3.28, 150: 3.05, 100: 2.82, 50: 2.62,
        },
        "fairway": {
            250: 4.05, 225: 3.82, 200: 3.58, 175: 3.35, 150: 3.15,
            125: 2.95, 100: 2.75, 75: 2.55, 50: 2.35, 40: 2.23,
            30: 2.12, 25: 2.04, 20: 1.96, 15: 1.88, 10: 1.80,
        },
        "rough": {
            200: 4.15, 175: 3.92, 150: 3.70, 125: 3.45, 100: 3.25,
            75: 3.05, 50: 2.85, 40: 2.75, 30: 2.65, 25: 2.57,
            20: 2.49, 15: 2.42, 10: 2.35,
        },
        "sand": {
            75: 3.55, 60: 3.45, 50: 3.35, 40: 3.25, 30: 3.15,
            25: 3.07, 20: 3.00, 15: 2.93, 10: 2.85,
        },
        "green": {
            90: 2.58, 80: 2.48, 70: 2.38, 60: 2.28, 50: 2.18,
            45: 2.13, 40: 2.08, 35: 2.03, 30: 1.98, 25: 1.93,
            20: 1.88, 18: 1.83, 15: 1.78, 12: 1.73, 10: 1.68,
            8: 1.63, 6: 1.58, 5: 1.53, 4: 1.48, 3: 1.42,
            2: 1.35, 1: 1.25,
        },
    },
}


# ── Special lies (same across all handicaps — penalty strokes are absolute) ──
HAZARD_BASELINE: float = 3.5  # Water, OB recovery, etc.
OB_BASELINE: float = 4.0       # Out of bounds (stroke + distance)


# ──────────────────────────────────────────────────────────────────────────────
# INTERPOLATION HELPERS
# ──────────────────────────────────────────────────────────────────────────────

def _interpolate_table(table: Dict[int, float], distance: int) -> float:
    """
    Linear interpolation for distances between table keys.
    Returns exact match if distance is in table.
    Returns boundary value if distance is outside table range.
    """
    if distance <= 0:
        return 1.0  # On the pin = 1 stroke

    if distance in table:
        return table[distance]

    keys = sorted(table.keys())

    if distance < keys[0]:
        return table[keys[0]]
    if distance > keys[-1]:
        return table[keys[-1]]

    lower = max(k for k in keys if k < distance)
    upper = min(k for k in keys if k > distance)

    lower_val = table[lower]
    upper_val = table[upper]
    ratio = (distance - lower) / (upper - lower)
    return lower_val + ratio * (upper_val - lower_val)


def _interpolate_between_brackets(
    lower_table: Dict[int, float],
    upper_table: Dict[int, float],
    distance: int,
    ratio: float,
) -> float:
    """
    Interpolate a baseline value between two handicap brackets.
    ratio=0 → lower bracket, ratio=1 → upper bracket.
    """
    lower_val = _interpolate_table(lower_table, distance)
    upper_val = _interpolate_table(upper_table, distance)
    return lower_val + ratio * (upper_val - lower_val)


# ──────────────────────────────────────────────────────────────────────────────
# HANDICAP BASELINE CLASS
# ──────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class HandicapBaseline:
    """
    A baseline set for a specific (possibly interpolated) handicap.

    Use this to calculate SG relative to a player's peer group.
    """
    handicap: float
    tee: Dict[int, float]
    fairway: Dict[int, float]
    rough: Dict[int, float]
    sand: Dict[int, float]
    green: Dict[int, float]

    def strokes(self, distance: int, lie: LieType) -> float:
        """Expected strokes to hole out from this position."""
        if lie == "hazard":
            return HAZARD_BASELINE
        if lie == "ob":
            return OB_BASELINE

        table = getattr(self, lie, None)
        if table is None:
            raise ValueError(f"Unknown lie type: {lie}")

        return _interpolate_table(table, distance)

    def sg(
        self,
        before_distance: int,
        before_lie: LieType,
        after_distance: int,
        after_lie: LieType,
        strokes_taken: int = 1,
    ) -> float:
        """
        Calculate Strokes Gained for a single shot vs this handicap baseline.

        Formula: SG = Baseline(before) - strokes_taken - Baseline(after)
        """
        before = self.strokes(before_distance, before_lie)
        after = self.strokes(after_distance, after_lie)
        return before - strokes_taken - after

    def putts_per_hole(self) -> float:
        """Expected putts per hole for this handicap (from Break X Golf avg_putts / 18)."""
        # These match the avg_putts in HANDICAP_STATS in generator.py
        # 0:31.3, 5:32.5, 10:33.9, 15:34.8, 20:36.1, 25:37.0
        putts_map = {0: 31.3, 5: 32.5, 10: 33.9, 15: 34.8, 20: 36.1, 25: 37.0}
        
        if self.handicap in putts_map:
            return putts_map[self.handicap] / 18.0
        
        # Interpolate
        brackets = sorted(putts_map.keys())
        lower_h = max(h for h in brackets if h < self.handicap)
        upper_h = min(h for h in brackets if h > self.handicap)
        ratio = (self.handicap - lower_h) / (upper_h - lower_h)
        lower_val = putts_map[lower_h] / 18.0
        upper_val = putts_map[upper_h] / 18.0
        return lower_val + ratio * (upper_val - lower_val)


# ──────────────────────────────────────────────────────────────────────────────
# FACTORY: Get baseline for any handicap
# ──────────────────────────────────────────────────────────────────────────────

def get_baseline_for_handicap(handicap: float) -> HandicapBaseline:
    """
    Get a HandicapBaseline for any handicap (0–25+).

    For exact bracket matches (0, 5, 10, 15, 20, 25), returns pre-built tables.
    For intermediate handicaps, linearly interpolates between nearest brackets.
    For handicaps >25, clamps to 25. For handicaps <0, clamps to 0.

    Args:
        handicap: Player's Handicap Index (e.g. 8.4, 15.2, 3.0)

    Returns:
        HandicapBaseline configured for that handicap

    Examples:
        >>> baseline = get_baseline_for_handicap(12.5)
        >>> baseline.strokes(150, "fairway")
        2.80  # interpolated between 10hcp and 15hcp
        >>> baseline.sg(150, "fairway", 15, "green", 1)
        0.15  # gained 0.15 strokes vs a 12.5hcp peer
    """
    handicap = max(0.0, min(float(handicap), 25.0))

    # Exact bracket match
    if handicap in _BASELINE_DATA:
        data = _BASELINE_DATA[int(handicap)]
        return HandicapBaseline(
            handicap=handicap,
            tee=data["tee"],
            fairway=data["fairway"],
            rough=data["rough"],
            sand=data["sand"],
            green=data["green"],
        )

    # Find surrounding brackets
    lower_h = max(h for h in HANDICAP_BRACKETS if h < handicap)
    upper_h = min(h for h in HANDICAP_BRACKETS if h > handicap)
    ratio = (handicap - lower_h) / (upper_h - lower_h)

    lower_data = _BASELINE_DATA[lower_h]
    upper_data = _BASELINE_DATA[upper_h]

    # Interpolate each lie type
    def _interp(lie: str) -> Dict[int, float]:
        lower_table = lower_data[lie]
        upper_table = upper_data[lie]
        # Interpolate at each key from the lower table
        result = {}
        for dist in sorted(lower_table.keys()):
            result[dist] = _interpolate_between_brackets(
                lower_table, upper_table, dist, ratio
            )
        return result

    return HandicapBaseline(
        handicap=handicap,
        tee=_interp("tee"),
        fairway=_interp("fairway"),
        rough=_interp("rough"),
        sand=_interp("sand"),
        green=_interp("green"),
    )


# ──────────────────────────────────────────────────────────────────────────────
# BACKWARD-COMPATIBLE API
# ──────────────────────────────────────────────────────────────────────────────
# Keep the old functions working for code that doesn't pass a handicap.
# Default to scratch (0 hcp) baseline.

_SCRATCH_BASELINE = get_baseline_for_handicap(0)


def baseline_strokes(distance: int, lie: LieType) -> float:
    """
    Get expected strokes to hole out from a given distance and lie.
    Uses scratch (0hcp) baseline for backward compatibility.

    For handicap-adjusted baselines, use:
        baseline = get_baseline_for_handicap(handicap)
        baseline.strokes(distance, lie)
    """
    return _SCRATCH_BASELINE.strokes(distance, lie)


def calculate_sg(
    before_distance: int,
    before_lie: LieType,
    after_distance: int,
    after_lie: LieType,
    strokes_taken: int = 1,
) -> float:
    """
    Calculate Strokes Gained vs scratch baseline.
    For handicap-adjusted SG, use HandicapBaseline.sg().
    """
    return _SCRATCH_BASELINE.sg(
        before_distance, before_lie, after_distance, after_lie, strokes_taken
    )


# ── Default course par by hole (for par 3 detection) ──
# Holes 3, 7, 12, 16 are par 3s in the default course
PAR3_HOLES = {3, 7, 12, 16}


def is_par3(hole_number: int) -> bool:
    """Check if a hole is a par 3 (default course layout)."""
    return hole_number in PAR3_HOLES


# ── Category mapping for aggregation ──
# Per Broadie's "Every Shot Counts":
# - Driving: tee shots on par 4/5
# - Approach: tee shots on par 3 + shots 50+ yards not from tee
# - Short Game: any shot inside 50 yards, not on green
# - Putting: green shots
CATEGORY_MAP = {
    "tee": "driving",
    "fairway": "approach",
    "rough": "approach",
    "sand": "short_game",
    "green": "putting",
    "hazard": "short_game",
    "ob": "driving",
}


def get_category(lie: LieType, distance_yards: Optional[int] = None, hole_number: Optional[int] = None) -> str:
    """Map a lie type to a performance category for SG aggregation.
    
    Per Broadie's "Every Shot Counts":
    - Inside 50 yards and not on green = short game (chips, pitches, bunker shots)
    - 50+ yards from fairway/rough/sand/hazard = approach
    - Tee shots on par 4/5 = driving
    - Tee shots on par 3 = approach (treated as fairway lie for baseline)
    - Green shots = putting
    """
    # Putting is always putting
    if lie == "green":
        return "putting"
    
    # Inside 50 yards (and not on green) = short game per Broadie
    if distance_yards is not None and distance_yards < 50:
        return "short_game"
    
    # Tee shots: par 3 = approach, par 4/5 = driving
    if lie == "tee":
        par3 = is_par3(hole_number) if hole_number is not None else False
        return "approach" if par3 else "driving"
    
    # Everything else at 50+ yards is approach (including long bunker shots)
    return "approach"


# ──────────────────────────────────────────────────────────────────────────────
# VALIDATION / DEMO
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== Handicap-Adjusted Baseline Validation ===\n")

    # Show how baselines change by handicap
    test_cases = [
        (150, "fairway"),
        (150, "rough"),
        (30, "sand"),
        (15, "green"),
        (450, "tee"),
    ]

    for dist, lie in test_cases:
        print(f"{dist}y/ft {lie}:")
        for hcp in [0, 5, 10, 15, 20, 25]:
            baseline = get_baseline_for_handicap(hcp)
            val = baseline.strokes(dist, lie)
            print(f"  {hcp:2d}hcp: {val:.2f}")
        print()

    print("=== SG Examples (vs player's own handicap) ===\n")

    # A 15hcp player hits a good approach
    hcp15 = get_baseline_for_handicap(15)
    sg = hcp15.sg(150, "fairway", 15, "green", 1)
    print(f"15hcp: 150y fairway → 15ft green: SG = {sg:+.2f}")

    # Same shot, but a scratch player would gain more
    hcp0 = get_baseline_for_handicap(0)
    sg0 = hcp0.sg(150, "fairway", 15, "green", 1)
    print(f"0hcp:  150y fairway → 15ft green: SG = {sg0:+.2f}")

    # A 25hcp player hits a mediocre approach (into rough)
    hcp25 = get_baseline_for_handicap(25)
    sg25 = hcp25.sg(150, "fairway", 150, "rough", 1)
    print(f"25hcp: 150y fairway → 150y rough: SG = {sg25:+.2f}")

    # Interpolated handicap
    hcp12 = get_baseline_for_handicap(12.5)
    sg12 = hcp12.sg(150, "fairway", 15, "green", 1)
    print(f"12.5hcp: 150y fairway → 15ft green: SG = {sg12:+.2f}")

    print("\n=== Consistency Check ===")
    # A shot that lands exactly where it started should have SG = -1
    # (you used 1 stroke to make zero progress)
    sg_neutral = hcp15.sg(100, "fairway", 100, "fairway", 1)
    print(f"15hcp: 100y fairway → 100y fairway: SG = {sg_neutral:+.2f} (should be ~-1.0)")
