"""
Observed amateur golf aggregates, by handicap bracket.

This module holds **measured data only**. No simulation, no derived values, no
model. Everything here is an observable that was counted on real rounds, and it
is the anchor set that `baseline_fit.py` solves the strokes-gained baselines
against.

Provenance
----------
Break X Golf aggregate stats — 3,788 rounds across 1,116 golfers.
https://breakxgolf.com/golf-stats-by-handicap/

Why this file exists
--------------------
These figures previously lived inside `generator.py`, mixed in with a synthetic
shot sampler. The sampler is a naive first draft and is not trustworthy (it
re-applies a handicap penalty on top of already handicap-specific rates, and its
approach-proximity model has no handicap term at all — see `scripts/audit_sg.py`).
The aggregates are not the sampler's output; they are its input, and they are
the one genuinely empirical thing in the SG stack.

Separating them means a model can be calibrated against measured behaviour
without importing anything that simulates.

Units
-----
Per AGENTS.md: putting distances are **feet**, everything else is **yards**.
`avg_putts` is putts per 18 holes, not per hole.
"""

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class HandicapAggregates:
    """Measured round-level averages for one handicap bracket."""

    avg_score: float          # strokes per 18 holes
    avg_drive_yards: float    # carry+roll, driver only
    drive_std: float          # yards
    fairway_pct: float        # fairways hit / fairways possible (par 4 and 5)
    gir_pct: float            # greens in regulation / holes
    up_down_pct: float        # got down in 2 from off the green, given a miss
    avg_putts: float          # putts per 18 holes
    putts_std: float          # putts per 18 holes


#: Measured aggregates at each handicap bracket. Intermediate handicaps are
#: linearly interpolated by :func:`aggregates_for`.
OBSERVED: Dict[int, HandicapAggregates] = {
    0:  HandicapAggregates(74.6, 274, 18, 0.565, 0.568, 0.500, 31.3, 2.5),
    5:  HandicapAggregates(79.0, 258, 20, 0.510, 0.461, 0.377, 32.5, 2.8),
    10: HandicapAggregates(84.6, 247, 22, 0.493, 0.373, 0.316, 33.9, 3.0),
    15: HandicapAggregates(89.3, 226, 24, 0.481, 0.264, 0.251, 34.8, 3.2),
    20: HandicapAggregates(93.7, 219, 25, 0.428, 0.224, 0.217, 36.1, 3.5),
    25: HandicapAggregates(98.6, 217, 26, 0.430, 0.187, 0.203, 37.0, 3.8),
}

BRACKETS = sorted(OBSERVED.keys())


# ──────────────────────────────────────────────────────────────────────────────
# Reference course
# ──────────────────────────────────────────────────────────────────────────────
# The aggregates above are round totals, so turning them into a per-shot
# constraint needs a course to sum over. This is a par-71, 6,750-yard layout —
# an ordinary mid-length course, close to the median the source rounds were
# played on. It is a *calibration fixture*, not a real course.


@dataclass(frozen=True)
class RefHole:
    par: int
    yards: int


REFERENCE_COURSE = (
    RefHole(4, 420), RefHole(4, 380), RefHole(3, 175),
    RefHole(4, 440), RefHole(5, 520), RefHole(4, 400),
    RefHole(3, 160), RefHole(4, 410), RefHole(4, 390),
    RefHole(4, 430), RefHole(4, 370), RefHole(3, 185),
    RefHole(5, 540), RefHole(4, 405), RefHole(4, 395),
    RefHole(3, 170), RefHole(4, 450), RefHole(5, 510),
)

REFERENCE_PAR = sum(h.par for h in REFERENCE_COURSE)
REFERENCE_YARDS = sum(h.yards for h in REFERENCE_COURSE)


def aggregates_for(handicap: float) -> HandicapAggregates:
    """
    Measured aggregates for any handicap index, linearly interpolated between
    brackets. Clamps to [0, 25] — the range the source data covers.
    """
    h = max(0.0, min(float(handicap), 25.0))

    if h in OBSERVED:
        return OBSERVED[int(h)]

    lower = max(b for b in BRACKETS if b < h)
    upper = min(b for b in BRACKETS if b > h)
    t = (h - lower) / (upper - lower)

    lo, hi = OBSERVED[lower], OBSERVED[upper]

    def blend(a: float, b: float) -> float:
        return a + t * (b - a)

    return HandicapAggregates(
        avg_score=blend(lo.avg_score, hi.avg_score),
        avg_drive_yards=blend(lo.avg_drive_yards, hi.avg_drive_yards),
        drive_std=blend(lo.drive_std, hi.drive_std),
        fairway_pct=blend(lo.fairway_pct, hi.fairway_pct),
        gir_pct=blend(lo.gir_pct, hi.gir_pct),
        up_down_pct=blend(lo.up_down_pct, hi.up_down_pct),
        avg_putts=blend(lo.avg_putts, hi.avg_putts),
        putts_std=blend(lo.putts_std, hi.putts_std),
    )
