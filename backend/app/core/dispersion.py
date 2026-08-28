"""
Physical shot-dispersion parameters — the inputs the expected-strokes surface is
solved from.

Why this exists
---------------
The committed baselines in `baselines.py` were hand-typed expected-strokes
values, and `scripts/audit_sg.py` shows they miss measured scoring by 5 to 17
strokes. Typing a *better* table has the same failure mode: six measured
aggregates cannot pin a whole surface over (distance x lie x skill), so the gaps
get filled by hand and drift.

This module inverts that. It describes where a player's shots actually finish —
a dozen physical numbers — and `expected_strokes.py` derives the surface by
recursion. All six aggregates then become *outputs* to check against, so the
problem is overdetermined and the residuals mean something.

Provenance discipline
---------------------
Every parameter is tagged:

  MEASURED  counted from real rounds (Break X, via `empirical.py`)
  DERIVED   solved from a MEASURED aggregate plus a stated geometric assumption
  ASSUMED   a physical prior standing in until published data is dropped in

`scripts/solve_baselines.py --sensitivity` reports how much each ASSUMED value
actually moves the answer, so sourcing effort goes where it matters rather than
everywhere. Do not promote an ASSUMED value to DERIVED without saying what it
was solved against.

Units
-----
Per AGENTS.md: putting distances are feet, everything else yards. Dispersions
are dimensionless fractions of the attempted shot distance, so they carry no
unit of their own.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Literal

from app.core.empirical import HandicapAggregates, aggregates_for

Lie = Literal["tee", "fairway", "rough", "sand", "recovery", "green"]


# ──────────────────────────────────────────────────────────────────────────────
# Course geometry
# ──────────────────────────────────────────────────────────────────────────────
# ASSUMED. These convert a measured hit-rate into a dispersion: knowing a player
# hits 56.5% of fairways only pins their lateral spread once you say how wide the
# fairway is. Both are ordinary values for a mid-length course and both are
# swept in the sensitivity report.


@dataclass(frozen=True)
class CourseGeometry:
    fairway_half_width_yards: float = 15.0   # ASSUMED — 30-yard fairway
    green_radius_yards: float = 11.0         # ASSUMED — ~22-yard green, GIR counts anywhere on it
    greenside_sand_share: float = 0.12       # ASSUMED — share of green misses finishing in sand
    recovery_rate_tee: float = 0.045         # ASSUMED — tee shots leaving no clean swing (trees, penalty, OB)


DEFAULT_GEOMETRY = CourseGeometry()


# ──────────────────────────────────────────────────────────────────────────────
# Skill parameters
# ──────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ShotSkill:
    """
    How one player's shots scatter, as fractions of the attempted distance.

    `lateral` and `distance` are the two axes of a dispersion ellipse. A tour
    player is roughly 0.05 lateral; a high-handicap amateur roughly 0.12.
    """

    lateral: float
    distance: float


@dataclass(frozen=True)
class PlayerDispersion:
    """The full physical description of one player's shotmaking."""

    handicap: float

    drive_distance_yards: float      # MEASURED
    drive_distance_std: float        # MEASURED
    tee: ShotSkill                   # DERIVED from fairway_pct + fairway width
    approach: ShotSkill              # DERIVED from gir_pct + green radius
    rough_penalty: float             # ASSUMED — dispersion multiplier out of rough
    sand_penalty: float              # ASSUMED — dispersion multiplier out of sand
    penalty_rate: float              # ASSUMED — per full shot: water, OB, lost ball
    sand_escape_fail_rate: float     # ASSUMED — bunker shots that stay in the bunker
    short_game_proximity_ft: float   # DERIVED from up_down_pct + putting curve
    putting: "PuttingSkill"          # DERIVED from avg_putts

    geometry: CourseGeometry = DEFAULT_GEOMETRY


@dataclass(frozen=True)
class PuttingSkill:
    """
    Make probability as a log-logistic in distance beyond a gimme radius:

        p_make(d) = 1 / (1 + ((d - d0) / (d50 - d0))^k)

    `d50` is the distance at which half the putts drop — the single number that
    most cleanly separates putters. `d0` is the radius inside which nobody
    misses; without it the curve gives away far too many tap-ins, which is what
    a plain log-logistic in distance does.

    ASSUMED shape, DERIVED level: the form, `k` and `d0` are a prior; `d50` is
    solved so the surface reproduces measured putts per round. Published
    make-rate tables by handicap (Shot Scope and Broadie both publish these)
    would replace the curve outright and make this MEASURED.
    """

    d50_ft: float
    steepness: float = 2.0           # ASSUMED — k above
    gimme_ft: float = 1.0            # ASSUMED — d0 above
    lag_fraction: float = 0.10       # ASSUMED — residual after a miss, as a fraction of the putt
    lag_floor_ft: float = 1.5        # ASSUMED — you rarely leave it closer than this

    def make_probability(self, distance_ft: float) -> float:
        if distance_ft <= self.gimme_ft:
            return 1.0
        span = max(self.d50_ft - self.gimme_ft, 1e-3)
        ratio = (distance_ft - self.gimme_ft) / span
        return 1.0 / (1.0 + ratio**self.steepness)

    def lag_distance_ft(self, distance_ft: float) -> float:
        """Expected remaining distance after a missed putt."""
        return max(self.lag_floor_ft, self.lag_fraction * distance_ft)


# ──────────────────────────────────────────────────────────────────────────────
# Deriving dispersion from measured hit rates
# ──────────────────────────────────────────────────────────────────────────────
# A hit rate is the probability the lateral miss stayed inside a target of known
# width. Inverting the normal CDF turns that into a dispersion, which is the one
# step that makes these parameters derived rather than invented.


def _lateral_from_hit_rate(hit_rate: float, half_width: float, distance: float) -> float:
    """
    Lateral dispersion implied by hitting a target of half-width `half_width`
    at `distance`, `hit_rate` of the time.

    P(|offset| < half_width) = hit_rate, offset ~ N(0, sigma * distance)
    """
    hit_rate = min(max(hit_rate, 1e-3), 1 - 1e-3)
    # Inverse standard normal CDF at (1 + hit_rate) / 2, via the error function.
    z = math.sqrt(2.0) * _erfinv(hit_rate)
    if z <= 0 or distance <= 0:
        raise ValueError(f"degenerate hit rate {hit_rate} at distance {distance}")
    return half_width / (z * distance)


def _erfinv(x: float) -> float:
    """Inverse error function (Giles' rational approximation, ~1e-7 accurate)."""
    w = -math.log((1.0 - x) * (1.0 + x))
    if w < 5.0:
        w -= 2.5
        p = 2.81022636e-08
        for c in (3.43273939e-07, -3.5233877e-06, -4.39150654e-06,
                  0.00021858087, -0.00125372503, -0.00417768164,
                  0.246640727, 1.50140941):
            p = p * w + c
    else:
        w = math.sqrt(w) - 3.0
        p = -0.000200214257
        for c in (0.000100950558, 0.00134934322, -0.00367342844,
                  0.00573950773, -0.0076224613, 0.00943887047,
                  1.00167406, 2.83297682):
            p = p * w + c
    return p * x


#: ASSUMED. A shot from rough scatters wider than the same shot from the
#: fairway; from sand, wider still. Multipliers on the approach dispersion.
ROUGH_PENALTY = 1.35
SAND_PENALTY = 1.60

#: ASSUMED. Typical approach distance used to convert `gir_pct` into approach
#: dispersion. Reference-course par 4s leave roughly this after a drive.
NOMINAL_APPROACH_YARDS = 155.0

#: ASSUMED. Distance control is tighter than direction for most amateurs;
#: expressed as a fraction of the lateral figure.
DISTANCE_TO_LATERAL_RATIO = 0.72


def nominal_penalty_rate(handicap: float) -> float:
    """
    Per-shot probability of a penalty — water, out of bounds, lost ball.

    ASSUMED starting value, solved properly by `expected_strokes.calibrate`.
    A pure dispersion model has no left tail: every shot advances the ball with
    Gaussian error, so nobody ever reloads. Real golf does, increasingly with
    handicap, and it is worth several strokes a round. Whether the solved value
    lands at a plausible penalty count is a falsifiable check on the model, not
    a free parameter to hide error in — `scripts/solve_baselines.py` reports it.
    """
    return 0.004 + 0.0011 * max(0.0, min(handicap, 25.0))


def nominal_sand_fail_rate(handicap: float) -> float:
    """ASSUMED. Bunker shots that fail to escape. Rare at scratch, common at 25."""
    return 0.01 + 0.005 * max(0.0, min(handicap, 25.0))


def dispersion_for(
    handicap: float,
    geometry: CourseGeometry = DEFAULT_GEOMETRY,
) -> PlayerDispersion:
    """
    Build a dispersion profile for a handicap from the measured aggregates.

    Tee and approach dispersion are solved from `fairway_pct` and `gir_pct`.
    Putting `d50` is left at a nominal value here and solved properly by
    `expected_strokes.calibrate_putting`, which needs the recursion to evaluate
    putts per round.
    """
    agg: HandicapAggregates = aggregates_for(handicap)

    tee_lateral = _lateral_from_hit_rate(
        agg.fairway_pct, geometry.fairway_half_width_yards, agg.avg_drive_yards
    )
    approach_lateral = _lateral_from_hit_rate(
        agg.gir_pct, geometry.green_radius_yards, NOMINAL_APPROACH_YARDS
    )

    return PlayerDispersion(
        handicap=handicap,
        drive_distance_yards=agg.avg_drive_yards,
        drive_distance_std=agg.drive_std,
        tee=ShotSkill(
            lateral=tee_lateral,
            distance=tee_lateral * DISTANCE_TO_LATERAL_RATIO,
        ),
        approach=ShotSkill(
            lateral=approach_lateral,
            distance=approach_lateral * DISTANCE_TO_LATERAL_RATIO,
        ),
        rough_penalty=ROUGH_PENALTY,
        sand_penalty=SAND_PENALTY,
        penalty_rate=nominal_penalty_rate(handicap),
        sand_escape_fail_rate=nominal_sand_fail_rate(handicap),
        short_game_proximity_ft=_nominal_short_game_proximity(agg),
        putting=PuttingSkill(d50_ft=_nominal_putting_d50(agg)),
        geometry=geometry,
    )


def _nominal_putting_d50(agg: HandicapAggregates) -> float:
    """
    Starting value for the putting solve.

    Scaled off measured putts per round so the optimiser starts near the answer;
    the real value comes from `expected_strokes.calibrate_putting`.
    """
    putts_per_hole = agg.avg_putts / 18.0
    # More putts per hole means a shorter distance at which half still drop.
    return max(3.0, 14.0 - 5.0 * (putts_per_hole - 1.70) / 0.10)


def _nominal_short_game_proximity(agg: HandicapAggregates) -> float:
    """
    Starting value for expected proximity, in feet, after a greenside shot.

    Anchored to `up_down_pct`: getting down in two means holing the putt that
    follows, so a better scrambler must be finishing closer. Refined against the
    solved putting curve in `expected_strokes.calibrate_short_game`.
    """
    # Inverting a nominal make curve: up-and-down rate maps to a proximity.
    return max(3.0, 3.0 + 34.0 * (1.0 - agg.up_down_pct) ** 1.6)


def summarise(dispersion: PlayerDispersion) -> Dict[str, float]:
    """Flat view for reporting and sensitivity sweeps."""
    return {
        "handicap": dispersion.handicap,
        "drive_yards": dispersion.drive_distance_yards,
        "tee_lateral": dispersion.tee.lateral,
        "tee_distance": dispersion.tee.distance,
        "approach_lateral": dispersion.approach.lateral,
        "approach_distance": dispersion.approach.distance,
        "putting_d50_ft": dispersion.putting.d50_ft,
        "short_game_proximity_ft": dispersion.short_game_proximity_ft,
    }
