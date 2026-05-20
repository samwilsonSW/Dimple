"""
Strokes Gained Baseline Tables for Amateur Golfers

Simplified baselines for SG calculation. Not PGA Tour — directionally correct
for amateur demo purposes. Based on Broadie's "Every Shot Counts" amateur data,
adjusted for 10-20 handicap range.

SG Formula per shot:
    SG = Baseline(before_distance, before_lie) - 1 - Baseline(after_distance, after_lie)

Positive = gained strokes vs baseline. Negative = lost strokes.
"""

from typing import Dict, Literal

# Lie types
LieType = Literal["tee", "fairway", "rough", "sand", "green", "hazard", "ob"]

# ── Baseline strokes from tee (par 4/5 tee shots) ──
# Distance = yards to pin
TEE_BASELINE: Dict[int, float] = {
    500: 4.8,
    450: 4.4,
    400: 4.0,
    350: 3.7,
    300: 3.4,
    250: 3.1,
    200: 2.9,
    150: 2.7,
    100: 2.5,
    50: 2.3,
}

# ── Baseline strokes from fairway ──
FAIRWAY_BASELINE: Dict[int, float] = {
    250: 3.4,
    225: 3.2,
    200: 3.0,
    175: 2.8,
    150: 2.6,
    125: 2.4,
    100: 2.2,
    75: 2.0,
    50: 1.8,
    40: 1.7,
    30: 1.6,
    25: 1.55,
    20: 1.5,
    15: 1.45,
    10: 1.4,
}

# ── Baseline strokes from rough ──
# Penalty: +0.4 strokes vs fairway at same distance
ROUGH_BASELINE: Dict[int, float] = {
    200: 3.4,
    175: 3.2,
    150: 3.0,
    125: 2.8,
    100: 2.6,
    75: 2.4,
    50: 2.2,
    40: 2.1,
    30: 2.0,
    25: 1.95,
    20: 1.9,
    15: 1.85,
    10: 1.8,
}

# ── Baseline strokes from sand ──
# Penalty: +0.6 strokes vs fairway at same distance
SAND_BASELINE: Dict[int, float] = {
    75: 2.8,
    60: 2.7,
    50: 2.6,
    40: 2.5,
    30: 2.4,
    25: 2.35,
    20: 2.3,
    15: 2.25,
    10: 2.2,
}

# ── Baseline strokes from green (putting) ──
# Distance = feet to pin
GREEN_BASELINE: Dict[int, float] = {
    90: 2.2,
    80: 2.1,
    70: 2.0,
    60: 1.9,
    50: 1.8,
    45: 1.75,
    40: 1.7,
    35: 1.65,
    30: 1.6,
    25: 1.55,
    20: 1.5,
    18: 1.45,
    15: 1.4,
    12: 1.35,
    10: 1.3,
    8: 1.25,
    6: 1.2,
    5: 1.15,
    4: 1.1,
    3: 1.06,
    2: 1.03,
    1: 1.01,
}

# ── Special lies ──
HAZARD_BASELINE: float = 3.5  # Water, OB recovery, etc.
OB_BASELINE: float = 4.0       # Out of bounds (stroke + distance)

# Map lie type to baseline table
BASELINE_TABLES = {
    "tee": TEE_BASELINE,
    "fairway": FAIRWAY_BASELINE,
    "rough": ROUGH_BASELINE,
    "sand": SAND_BASELINE,
    "green": GREEN_BASELINE,
}


def _interpolate(table: Dict[int, float], distance: int) -> float:
    """
    Linear interpolation for distances between table keys.
    Returns exact match if distance is in table.
    Returns boundary value if distance is outside table range.
    """
    if distance <= 0:
        return 1.0  # On the pin = 1 stroke

    # Exact match
    if distance in table:
        return table[distance]

    # Get sorted keys
    keys = sorted(table.keys())

    # Below minimum
    if distance < keys[0]:
        return table[keys[0]]

    # Above maximum
    if distance > keys[-1]:
        return table[keys[-1]]

    # Find surrounding keys
    lower = max(k for k in keys if k < distance)
    upper = min(k for k in keys if k > distance)

    # Linear interpolation
    lower_val = table[lower]
    upper_val = table[upper]
    ratio = (distance - lower) / (upper - lower)
    return lower_val + ratio * (upper_val - lower_val)


def baseline_strokes(distance: int, lie: LieType) -> float:
    """
    Get expected strokes to hole out from a given distance and lie.

    Args:
        distance: Yards to pin (or feet if lie == "green")
        lie: One of "tee", "fairway", "rough", "sand", "green", "hazard", "ob"

    Returns:
        Expected strokes from this position

    Examples:
        >>> baseline_strokes(150, "fairway")
        2.6
        >>> baseline_strokes(10, "green")
        1.3
    """
    if lie == "hazard":
        return HAZARD_BASELINE
    if lie == "ob":
        return OB_BASELINE

    table = BASELINE_TABLES.get(lie)
    if table is None:
        raise ValueError(f"Unknown lie type: {lie}")

    return _interpolate(table, distance)


def calculate_sg(
    before_distance: int,
    before_lie: LieType,
    after_distance: int,
    after_lie: LieType,
    strokes_taken: int = 1,
) -> float:
    """
    Calculate Strokes Gained for a single shot.

    Formula: SG = Baseline(before) - strokes_taken - Baseline(after)

    Args:
        before_distance: Distance to pin before shot
        before_lie: Lie before shot
        after_distance: Distance to pin after shot
        after_lie: Lie after shot
        strokes_taken: Strokes used (1 for normal, 2+ for penalties/re-hits)

    Returns:
        Strokes Gained value (positive = good, negative = bad)

    Examples:
        >>> calculate_sg(150, "fairway", 15, "green", 1)
        0.2  # Gained 0.2 strokes (good approach)
        >>> calculate_sg(150, "fairway", 150, "rough", 1)
        -0.4  # Lost 0.4 strokes (missed green, into rough)
    """
    before = baseline_strokes(before_distance, before_lie)
    after = baseline_strokes(after_distance, after_lie)
    return before - strokes_taken - after


# ── Category mapping for aggregation ──
CATEGORY_MAP = {
    "tee": "driving",
    "fairway": "approach",
    "rough": "approach",
    "sand": "short_game",
    "green": "putting",
    "hazard": "short_game",
    "ob": "driving",
}


def get_category(lie: LieType) -> str:
    """Map a lie type to a performance category for SG aggregation."""
    return CATEGORY_MAP.get(lie, "approach")


if __name__ == "__main__":
    # Quick validation
    print("=== Baseline Validation ===")
    print(f"150y fairway: {baseline_strokes(150, 'fairway'):.2f}")
    print(f"150y rough:   {baseline_strokes(150, 'rough'):.2f}")
    print(f"150y sand:    {baseline_strokes(150, 'sand'):.2f}")
    print(f"15ft green:   {baseline_strokes(15, 'green'):.2f}")
    print(f"50ft green:   {baseline_strokes(50, 'green'):.2f}")
    print()
    print("=== SG Examples ===")
    print(f"Good approach (150y fairway → 15ft green): {calculate_sg(150, 'fairway', 15, 'green'):+.2f}")
    print(f"Missed approach (150y fairway → 150y rough): {calculate_sg(150, 'fairway', 150, 'rough'):+.2f}")
    print(f"Good putt (15ft → 1ft): {calculate_sg(15, 'green', 1, 'green'):+.2f}")
    print(f"Missed putt (15ft → 3ft): {calculate_sg(15, 'green', 3, 'green'):+.2f}")
    print(f"OB drive (450y tee → 450y tee, 2 strokes): {calculate_sg(450, 'tee', 450, 'tee', 2):+.2f}")
