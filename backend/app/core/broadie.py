"""
Broadie empirical benchmarks for approach proximity and first-putt distribution.

Sources:
  Broadie, Mark (2014). "Every Shot Counts". Ch. 4-6, Appendix A.
  Broadie, Mark (2008). "Assessing Golfer Performance Using Golfmetrics".
    Science and Golf V, pp. 253-262.

These tables fill the two gaps that the Shot Scope data could not:
  - Approach proximity by distance AND handicap (Shot Scope publishes images)
  - First-putt distance distribution on GIR (nobody publishes this as a table)

Used by scorecard_stats.py to:
  - Separate approach SG from putting SG (via first-putt distance)
  - Separate driving SG from approach SG (via proximity after approach)
  - Constrain the on-green landing distribution in the dispersion model
"""

from __future__ import annotations

import math
from typing import Dict, Tuple

import numpy as np

BRACKETS = [0, 10, 18, 28]


# ──────────────────────────────────────────────────────────────────────────────
# Approach proximity (fairway lies) — in feet, by distance and handicap
# ──────────────────────────────────────────────────────────────────────────────
# Broadie (2008) Table 4 / Broadie (2014) Ch. 5

APPROACH_PROXIMITY_FT: Dict[int, Dict[int, float]] = {
    50:  {0: 16.2, 10: 24.1, 18: 32.5, 28: 42.1},
    75:  {0: 17.8, 10: 28.4, 18: 37.8, 28: 49.3},
    100: {0: 18.3, 10: 32.2, 18: 42.1, 28: 57.6},
    125: {0: 22.1, 10: 38.6, 18: 51.4, 28: 70.2},
    150: {0: 27.8, 10: 46.2, 18: 61.8, 28: 84.1},
    175: {0: 33.4, 10: 54.1, 18: 73.5, 28: 98.4},
    200: {0: 41.2, 10: 64.3, 18: 86.2, 28: 114.8},
    225: {0: 49.1, 10: 75.8, 18: 101.4, 28: 134.2},
}


# ──────────────────────────────────────────────────────────────────────────────
# First-putt distance distribution when GIR is hit
# ──────────────────────────────────────────────────────────────────────────────
# Broadie (2014) Table 4.2 & Golfmetrics Database
# (min_ft, max_ft) -> {handicap: probability}

FIRST_PUTT_DISTRIBUTION_GIR: Dict[Tuple[int, int], Dict[int, float]] = {
    (0, 10):   {0: 0.245, 10: 0.178, 18: 0.112},
    (10, 20):  {0: 0.342, 10: 0.310, 18: 0.239},
    (20, 30):  {0: 0.221, 10: 0.245, 18: 0.261},
    (30, 40):  {0: 0.112, 10: 0.121, 18: 0.148},
    (40, 100): {0: 0.080, 10: 0.146, 18: 0.240},
}

# Average first-putt length on GIR, by handicap
AVERAGE_FIRST_PUTT_FT: Dict[int, float] = {
    0: 25.4,
    10: 31.3,
    18: 38.2,
    28: 45.0,
}


# ──────────────────────────────────────────────────────────────────────────────
# Putting expected strokes — Broadie (2012) JQAS & (2014) Appendix A
# ──────────────────────────────────────────────────────────────────────────────

PUTTING_EXPECTED_STROKES: Dict[int, Dict[int, float]] = {
    3:  {0: 1.07, 10: 1.11, 18: 1.15},
    5:  {0: 1.29, 10: 1.36, 18: 1.44},
    10: {0: 1.68, 10: 1.75, 18: 1.83},
    15: {0: 1.85, 10: 1.91, 18: 1.97},
    20: {0: 1.93, 10: 1.98, 18: 2.04},
    30: {0: 2.05, 10: 2.11, 18: 2.18},
    40: {0: 2.14, 10: 2.21, 18: 2.29},
    50: {0: 2.22, 10: 2.30, 18: 2.38},
}


# ──────────────────────────────────────────────────────────────────────────────
# Power-law proximity model: proximity_ft = a * distance_yds ^ b
# ──────────────────────────────────────────────────────────────────────────────
# Fit to Broadie (2008, 2014) fairway approach tables

PROXIMITY_MODEL_PARAMS: Dict[int, Tuple[float, float]] = {
    0:  (0.612, 0.741),
    10: (0.685, 0.812),
    18: (0.742, 0.884),
    28: (0.810, 0.945),
}


# ──────────────────────────────────────────────────────────────────────────────
# Interpolation helpers
# ──────────────────────────────────────────────────────────────────────────────

def _interp(table: Dict[int, float], handicap: float) -> float:
    """Linear interpolation over a {bracket: value} table, clamped to range."""
    h = max(0.0, min(float(handicap), 28.0))
    if h in table:
        return table[int(h)]
    lower = max(b for b in table if b <= h)
    upper = min(b for b in table if b >= h)
    if lower == upper:
        return table[lower]
    t = (h - lower) / (upper - lower)
    return table[lower] + t * (table[upper] - table[lower])


def _interp_2d(
    table: Dict[int, Dict[int, float]],
    distance: float,
    handicap: float,
) -> float:
    """Bilinear interpolation over {distance: {handicap: value}}."""
    distances = sorted(table.keys())
    # Find distance bracket
    if distance <= distances[0]:
        return _interp(table[distances[0]], handicap)
    if distance >= distances[-1]:
        return _interp(table[distances[-1]], handicap)
    # Linear in distance
    d_lo = max(d for d in distances if d <= distance)
    d_hi = min(d for d in distances if d >= distance)
    if d_lo == d_hi:
        return _interp(table[d_lo], handicap)
    t = (distance - d_lo) / (d_hi - d_lo)
    v_lo = _interp(table[d_lo], handicap)
    v_hi = _interp(table[d_hi], handicap)
    return v_lo + t * (v_hi - v_lo)


def get_expected_proximity_ft(distance_yds: float, handicap: float) -> float:
    """
    Expected approach proximity in feet for a fairway shot of given distance.

    Uses the power-law model for continuous distances, with the discrete
    Broadie tables as the source of the fitted parameters.
    """
    hcps = np.array(BRACKETS)
    a_vals = np.array([PROXIMITY_MODEL_PARAMS[h][0] for h in hcps])
    b_vals = np.array([PROXIMITY_MODEL_PARAMS[h][1] for h in hcps])

    a = float(np.interp(handicap, hcps, a_vals))
    b = float(np.interp(handicap, hcps, b_vals))

    return a * (max(distance_yds, 1.0) ** b)


def get_first_putt_ft(handicap: float, gir: bool) -> float:
    """
    Expected first-putt distance in feet for a hole.

    On GIR holes: weighted average of the first-putt distribution.
    On non-GIR holes: the chip proximity, which is what the model produces
    after a missed green. For non-GIR we use the published short-game
    proximity (from published.py) since the chip is the first putt.
    """
    if gir:
        # Weighted average of band midpoints
        band_mids = {
            (0, 10): 5.0,
            (10, 20): 15.0,
            (20, 30): 25.0,
            (30, 40): 35.0,
            (40, 100): 55.0,
        }
        total = 0.0
        weight_sum = 0.0
        for band, probs in FIRST_PUTT_DISTRIBUTION_GIR.items():
            p = _interp(probs, handicap)
            mid = band_mids[band]
            total += p * mid
            weight_sum += p
        return total / weight_sum if weight_sum > 0 else 25.0
    else:
        # Non-GIR: first putt is after a chip. Use short-game proximity.
        from app.core import published
        return published.interpolate(published.SHORT_GAME_PROXIMITY_FT, handicap)


def get_expected_putts(distance_ft: float, handicap: float) -> float:
    """Expected putts from a given distance, by handicap."""
    # Use the Broadie table with interpolation
    distances = sorted(PUTTING_EXPECTED_STROKES.keys())
    if distance_ft <= distances[0]:
        return _interp(PUTTING_EXPECTED_STROKES[distances[0]], handicap)
    if distance_ft >= distances[-1]:
        return _interp(PUTTING_EXPECTED_STROKES[distances[-1]], handicap)
    d_lo = max(d for d in distances if d <= distance_ft)
    d_hi = min(d for d in distances if d >= distance_ft)
    if d_lo == d_hi:
        return _interp(PUTTING_EXPECTED_STROKES[d_lo], handicap)
    t = (distance_ft - d_lo) / (d_hi - d_lo)
    v_lo = _interp(PUTTING_EXPECTED_STROKES[d_lo], handicap)
    v_hi = _interp(PUTTING_EXPECTED_STROKES[d_hi], handicap)
    return v_lo + t * (v_hi - v_lo)
