"""
Published shot-level amateur golf data.

`empirical.py` holds round-level aggregates (one study, internally consistent).
This holds the *shot-level* tables the dispersion model needs — make rates by
distance, greenside proximity, penalty rates — which that study does not carry.

Source
------
Shot Scope, from on-course tracking across their user base. Individual figures
are cited at the table that uses them.

  Putting make percentage by handicap
  https://shotscope.com/blog/practice-green/stats-and-data/putting-make-percentages-by-handicap-how-do-you-compare/

  Approach proximity by lie
  https://shotscope.com/blog/practice-green/stats-and-data/approach-shots-average-proximity/

  Law of Averages, per handicap
  https://shotscope.com/blog/practice-green/game-improvement/reduce-hcp-law-of-averages-0hcp/
  (and the 5/10/15/20/25 handicap pages in the same series)

Where the two sources disagree
------------------------------
They are different populations measured different ways, and they do not always
agree. Recorded rather than reconciled, because silently averaging them would
hide the disagreement:

  metric              Break X (empirical.py)   Shot Scope (here)
  GIR, scratch        0.568                    0.59
  GIR, 15 handicap    0.264                    0.23
  fairways, scratch   0.565                    0.50
  driving, scratch    274 y                    285 y
  up and down, 15     0.251                    0.345

The up-and-down gap is the wide one and it matters, since that aggregate is a
holdout. `scripts/solve_baselines.py` reports against both.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

BRACKETS: List[int] = [0, 5, 10, 15, 20, 25]


# ──────────────────────────────────────────────────────────────────────────────
# Putting make rate by distance
# ──────────────────────────────────────────────────────────────────────────────
# MEASURED. Shot Scope, "Putting make percentages by handicap".
#
# Reported in bands. The representative distance for each band is its midpoint,
# except the open-ended top band, which is taken at 38 ft — a little above its
# 30 ft floor, since the distribution inside it falls away fast.

#: (representative distance in feet, {handicap: make probability})
PUTTING_MAKE_RATE: List[Tuple[float, Dict[int, float]]] = [
    (3.0,  {0: 0.928, 5: 0.902, 10: 0.893, 15: 0.844, 20: 0.840, 25: 0.825}),
    (9.0,  {0: 0.428, 5: 0.414, 10: 0.381, 15: 0.396, 20: 0.378, 25: 0.350}),
    (15.0, {0: 0.251, 5: 0.239, 10: 0.202, 15: 0.202, 20: 0.188, 25: 0.160}),
    (21.0, {0: 0.145, 5: 0.130, 10: 0.103, 15: 0.112, 20: 0.118, 25: 0.101}),
    (27.0, {0: 0.083, 5: 0.101, 10: 0.054, 15: 0.078, 20: 0.068, 25: 0.063}),
    (38.0, {0: 0.043, 5: 0.043, 10: 0.028, 15: 0.032, 20: 0.019, 25: 0.023}),
]

#: MEASURED. Shot Scope reports the 0-6 ft band split for scratch, which pins
#: the short end of the curve where the banded table is coarsest.
SCRATCH_SHORT_PUTTS: List[Tuple[float, float]] = [
    (1.5, 0.98),   # 0-3 ft
    (4.5, 0.76),   # 3-6 ft
]


# ──────────────────────────────────────────────────────────────────────────────
# Short game
# ──────────────────────────────────────────────────────────────────────────────
# MEASURED. Shot Scope "Law of Averages" series. Proximity is the average finish
# from a greenside shot inside 50 yards.
#
# The 5 handicap proximity is not published in the series; it is interpolated
# between the 0 and 10 handicap figures and flagged below.

SHORT_GAME_PROXIMITY_FT: Dict[int, float] = {
    0: 11.0,
    5: 13.0,   # INTERPOLATED — not published
    10: 15.0,
    15: 18.0,
    20: 20.0,
    25: 22.0,
}

#: MEASURED. Up and down conversion from inside 50 yards. Disagrees with the
#: Break X figures in `empirical.py`; see the module docstring.
UP_AND_DOWN_PCT: Dict[int, float] = {
    0: 0.54,
    5: 0.50,
    10: 0.40,
    15: 0.345,
    20: 0.31,
    25: 0.20,
}


# ──────────────────────────────────────────────────────────────────────────────
# Penalties
# ──────────────────────────────────────────────────────────────────────────────
# MEASURED. Shot Scope benchmark. This replaces the model's one fitted fudge
# parameter, which means `avg_score` goes back to being a holdout rather than a
# fit target.

PENALTY_STROKES_PER_ROUND: Dict[int, float] = {
    0: 0.56,
    5: 0.91,
    10: 1.62,
    15: 2.45,
    20: 3.03,
    25: 4.67,
}


# ──────────────────────────────────────────────────────────────────────────────
# Approach proximity
# ──────────────────────────────────────────────────────────────────────────────
# MEASURED, but only in aggregate: Shot Scope publishes the by-handicap and
# by-distance breakdowns as images, so only the all-player figures for the
# 60-100 yard band are readable as text. Enough to pin the *relative* cost of a
# bad lie, not the absolute level, so it is used as a ratio.

APPROACH_PROXIMITY_60_100_FT: Dict[str, float] = {
    "fairway": 40.0,
    "rough": 46.0,
    "sand": 56.0,
}

#: DERIVED from the table above: how much a lie widens dispersion relative to
#: the fairway. Replaces the previously ASSUMED 1.35 / 1.60 multipliers.
LIE_DISPERSION_MULTIPLIER: Dict[str, float] = {
    "fairway": 1.0,
    "rough": APPROACH_PROXIMITY_60_100_FT["rough"] / APPROACH_PROXIMITY_60_100_FT["fairway"],
    "sand": APPROACH_PROXIMITY_60_100_FT["sand"] / APPROACH_PROXIMITY_60_100_FT["fairway"],
}


# ──────────────────────────────────────────────────────────────────────────────
# Cross-checks
# ──────────────────────────────────────────────────────────────────────────────
# MEASURED. Shot Scope's own round-level figures, kept so the disagreement with
# Break X stays visible and testable rather than becoming folklore.

SHOTSCOPE_ROUND_LEVEL: Dict[int, Dict[str, float]] = {
    0:  {"fir": 0.50, "gir": 0.59, "three_putt": 0.03, "drive_yards": 285.0},
    15: {"fir": 0.47, "gir": 0.23, "three_putt": 0.10},
}


def interpolate(table: Dict[int, float], handicap: float) -> float:
    """Linear interpolation over the handicap brackets, clamped to [0, 25]."""
    h = max(0.0, min(float(handicap), 25.0))
    if h in table:
        return table[int(h)]
    lower = max(b for b in BRACKETS if b < h)
    upper = min(b for b in BRACKETS if b > h)
    t = (h - lower) / (upper - lower)
    return table[lower] + t * (table[upper] - table[lower])


def make_rates_for(handicap: float) -> List[Tuple[float, float]]:
    """
    Measured (distance_ft, make_probability) pairs for a handicap.

    Includes the extra short-putt detail for scratch, where it is published.
    """
    pairs = [(d, interpolate(row, handicap)) for d, row in PUTTING_MAKE_RATE]
    if handicap <= 2.5:
        pairs = SCRATCH_SHORT_PUTTS + [p for p in pairs if p[0] > 6.0]
    return sorted(pairs)
