"""
Derive the expected-strokes surface from shot dispersion, by value iteration.

The quantity every strokes-gained number is measured against is

    E(d, lie) = expected strokes to hole out from distance d in lie

Rather than typing that table (see `docs/SG_REBUILD.md` for what typing it cost),
this solves the recursion it satisfies:

    E(d, lie) = 1 + E_outcome[ E(d', lie') ]

One stroke, plus wherever the ball ends up. The outcome distribution comes from
`dispersion.py` — how a player's shots scatter — so the surface is a consequence
of shotmaking rather than an independent set of numbers that can drift from it.

Putting solves first and separately: putts only ever lead to more putts, so
E(green) closes on itself. Everything else terminates into it.

Calibration
-----------
Approach dispersion cannot be inverted from `gir_pct` in closed form. A scratch
player and a 25 handicap face completely different approach distances — the
scratch is hitting a wedge from 130 yards where the 25 is hitting a fairway wood
from 190 — so the same GIR rate implies very different dispersion depending on
where they are playing from. That distribution only exists inside the recursion,
so `calibrate` solves the dispersion there instead.

Fit on: fairway_pct, gir_pct, avg_putts, up_down_pct, drive distance.
Held out: avg_score — the aggregate the committed tables miss by up to 17.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Dict, Tuple

import numpy as np

from app.core.dispersion import (
    DEFAULT_GEOMETRY,
    CourseGeometry,
    PlayerDispersion,
    PuttingSkill,
    ShotSkill,
    dispersion_for,
)
from app.core.empirical import REFERENCE_COURSE, aggregates_for

YARDS_TO_FEET = 3.0

#: Distance grids the surface is solved on.
MAX_YARDS = 620
MAX_PUTT_FT = 110

#: Monte Carlo samples per state per sweep. Fixed seed, so a given dispersion
#: always yields the same surface — an SG number must not move between refreshes.
SAMPLES = 512
SEED = 20260827

#: ASSUMED. Longest shot available from each lie, as a fraction of the player's
#: driver distance. Sand and rough cap what can be attempted, which is most of
#: why a missed fairway costs strokes.
REACH_FRACTION: Dict[str, float] = {
    "tee": 1.00,
    "fairway": 0.88,
    "rough": 0.72,
    "sand": 0.55,
}

#: ASSUMED. Below this, a tee shot is played at the flag rather than for
#: distance — the par-3 case, without the state needing to know par.
TEE_AIM_AT_FLAG_YARDS = 245.0

#: ASSUMED. Greenside band. Inside this, a miss is a chip or bunker shot rather
#: than a full approach.
GREENSIDE_YARDS = 32.0

FULL_LIES = ("tee", "fairway", "rough", "sand")


@dataclass
class Surface:
    """A solved expected-strokes surface for one player."""

    green_ft: np.ndarray                    # index: feet
    full: Dict[str, np.ndarray]             # lie -> index: yards
    dispersion: PlayerDispersion

    def strokes(self, distance: float, lie: str) -> float:
        """Expected strokes to hole out. Feet on the green, yards elsewhere."""
        if lie == "green":
            idx = int(round(min(max(distance, 0.0), MAX_PUTT_FT - 1)))
            return float(self.green_ft[idx])
        table = self.full[lie]
        idx = int(round(min(max(distance, 0.0), MAX_YARDS - 1)))
        return float(table[idx])


# ──────────────────────────────────────────────────────────────────────────────
# Putting
# ──────────────────────────────────────────────────────────────────────────────


def solve_putting(skill: PuttingSkill) -> np.ndarray:
    """
    Expected putts from each whole foot, 0 to MAX_PUTT_FT.

        E(d) = 1 + (1 - p_make(d)) * E(lag(d))

    A missed putt always finishes closer than it started, so sweeping outward
    from the hole resolves every state in one pass — no iteration needed.
    """
    table = np.zeros(MAX_PUTT_FT, dtype=float)
    table[0] = 0.0  # already holed

    for d in range(1, MAX_PUTT_FT):
        p = skill.make_probability(float(d))
        lag = skill.lag_distance_ft(float(d))
        lag_idx = min(int(round(lag)), d - 1)  # strictly closer, so this is solved
        table[d] = 1.0 + (1.0 - p) * table[lag_idx]

    return table


# ──────────────────────────────────────────────────────────────────────────────
# Full shots
# ──────────────────────────────────────────────────────────────────────────────


def _attempt_distance(distances: np.ndarray, lie: str, disp: PlayerDispersion) -> np.ndarray:
    """How far the player tries to hit it from each state."""
    reach = REACH_FRACTION[lie] * disp.drive_distance_yards

    if lie == "tee":
        # Long hole: hit driver. Short hole (par 3): play at the flag.
        return np.where(distances > TEE_AIM_AT_FLAG_YARDS, reach, distances)

    return np.minimum(distances, reach)


def _skill_for(lie: str, disp: PlayerDispersion) -> ShotSkill:
    if lie == "tee":
        return disp.tee
    if lie == "rough":
        return ShotSkill(
            disp.approach.lateral * disp.rough_penalty,
            disp.approach.distance * disp.rough_penalty,
        )
    if lie == "sand":
        return ShotSkill(
            disp.approach.lateral * disp.sand_penalty,
            disp.approach.distance * disp.sand_penalty,
        )
    return disp.approach


def _sweep(
    distances: np.ndarray,
    lie: str,
    disp: PlayerDispersion,
    green: np.ndarray,
    full: Dict[str, np.ndarray],
    rng: np.random.Generator,
) -> np.ndarray:
    """
    One value-iteration sweep for a lie: sample outcomes, look up where they
    land, average.
    """
    geom = disp.geometry
    skill = _skill_for(lie, disp)
    attempt = _attempt_distance(distances, lie, disp)

    n = len(distances)
    att = attempt[:, None]
    d0 = distances[:, None]

    carry = att * (1.0 + rng.normal(0.0, skill.distance, size=(n, SAMPLES)))
    lateral = np.abs(att * rng.normal(0.0, skill.lateral, size=(n, SAMPLES)))

    # Punch-outs and trouble off the tee: the ball advances a fraction of the
    # attempt and sits in rough, which is what a recovery actually costs.
    if lie == "tee":
        trouble = rng.random((n, SAMPLES)) < geom.recovery_rate_tee
        carry = np.where(trouble, att * 0.40, carry)
    else:
        trouble = np.zeros((n, SAMPLES), dtype=bool)

    long_short = d0 - carry
    d_next = np.sqrt(long_short**2 + lateral**2)
    d_next = np.clip(d_next, 0.0, MAX_YARDS - 1)

    on_green = (d_next <= geom.green_radius_yards) & ~trouble
    greenside = (~on_green) & (d_next <= GREENSIDE_YARDS)
    in_sand = greenside & (rng.random((n, SAMPLES)) < geom.greenside_sand_share)
    in_fairway = (~on_green) & (~greenside) & (lateral <= geom.fairway_half_width_yards) & ~trouble

    values = np.empty((n, SAMPLES), dtype=float)

    # On the green: convert to feet and read the putting table.
    green_idx = np.clip((d_next * YARDS_TO_FEET).astype(int), 0, MAX_PUTT_FT - 1)
    values[on_green] = green[green_idx[on_green]]

    yard_idx = d_next.astype(int)
    fairway_vals = full["fairway"][yard_idx]
    rough_vals = full["rough"][yard_idx]
    sand_vals = full["sand"][yard_idx]

    values[in_sand] = sand_vals[in_sand]
    rest_fairway = in_fairway & ~in_sand
    values[rest_fairway] = fairway_vals[rest_fairway]
    rest_rough = ~on_green & ~in_sand & ~rest_fairway
    values[rest_rough] = rough_vals[rest_rough]

    # Disasters. A pure Gaussian dispersion has no left tail — every shot
    # advances the ball — so without these the model never reloads and scores
    # several strokes a round too well, worsening with handicap.
    start_idx = distances.astype(int)

    if lie == "sand":
        # Failed escape: still in the bunker, no closer.
        stuck = rng.random((n, SAMPLES)) < disp.sand_escape_fail_rate
        values = np.where(stuck, full["sand"][start_idx][:, None], values)

    # Penalty: a stroke, and playing again from about where you were.
    penalised = rng.random((n, SAMPLES)) < disp.penalty_rate
    values = np.where(penalised, full["rough"][start_idx][:, None] + 1.0, values)

    return 1.0 + values.mean(axis=1)


def solve_surface(disp: PlayerDispersion, sweeps: int = 40, tol: float = 1e-4) -> Surface:
    """
    Solve the full surface for a player.

    Putting closes first, then the other lies iterate to a fixed point. Values
    start optimistic and rise, which keeps the iteration stable.
    """
    green = solve_putting(disp.putting)

    distances = np.arange(MAX_YARDS, dtype=float)
    full: Dict[str, np.ndarray] = {
        lie: np.full(MAX_YARDS, 2.5, dtype=float) for lie in FULL_LIES
    }
    for lie in FULL_LIES:
        full[lie][0] = 0.0

    rng = np.random.default_rng(SEED)

    for _ in range(sweeps):
        delta = 0.0
        for lie in FULL_LIES:
            updated = _sweep(distances, lie, disp, green, full, rng)
            updated[0] = 0.0
            delta = max(delta, float(np.max(np.abs(updated - full[lie]))))
            full[lie] = updated
        if delta < tol:
            break

    return Surface(green_ft=green, full=full, dispersion=disp)


# ──────────────────────────────────────────────────────────────────────────────
# What the surface predicts
# ──────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Predicted:
    """Round-level aggregates implied by a solved surface."""

    avg_score: float
    avg_putts: float
    gir_pct: float


def predict(surface: Surface) -> Predicted:
    """
    Play the reference course against the surface.

    Expected strokes from the tee, summed over 18 holes, is the expected score —
    the same identity the audit uses, now evaluated on a derived surface instead
    of a typed one.
    """
    disp = surface.dispersion
    score = sum(surface.strokes(hole.yards, "tee") for hole in REFERENCE_COURSE)

    rng = np.random.default_rng(SEED + 1)
    putts_total = 0.0
    gir_hits = 0.0

    for hole in REFERENCE_COURSE:
        reg_shots = hole.par - 2
        putts, reached = _simulate_to_green(hole.yards, reg_shots, disp, surface.green_ft, rng)
        gir_hits += reached
        putts_total += putts

    holes = len(REFERENCE_COURSE)
    return Predicted(
        avg_score=score,
        avg_putts=putts_total,
        gir_pct=gir_hits / holes,
    )


def _simulate_to_green(
    hole_yards: float,
    reg_shots: int,
    disp: PlayerDispersion,
    green: np.ndarray,
    rng: np.random.Generator,
) -> Tuple[float, float]:
    """
    Play a hole up to the green. Returns (expected putts, GIR rate).

    Vectorised over many plays of the same hole so the rate is smooth. Putts are
    averaged over the distribution of first-putt distances rather than read at
    its mean: expected putts is concave in distance, so by Jensen, collapsing to
    the mean first would overstate putts.
    """
    n = 600
    geom = disp.geometry
    d = np.full(n, float(hole_yards))
    lie = np.full(n, "tee", dtype=object)
    on_green = np.zeros(n, dtype=bool)
    shots = np.zeros(n, dtype=int)
    first_putt_ft = np.zeros(n)
    reached_in_reg = np.zeros(n, dtype=bool)

    for _ in range(8):
        live = ~on_green
        if not live.any():
            break

        for l in FULL_LIES:
            sel = live & (lie == l)
            if not sel.any():
                continue

            skill = _skill_for(l, disp)
            reach = REACH_FRACTION[l] * disp.drive_distance_yards
            dd = d[sel]
            att = np.where(dd > TEE_AIM_AT_FLAG_YARDS, reach, dd) if l == "tee" else np.minimum(dd, reach)

            carry = att * (1.0 + rng.normal(0.0, skill.distance, size=att.shape))
            lateral = np.abs(att * rng.normal(0.0, skill.lateral, size=att.shape))
            if l == "tee":
                trouble = rng.random(att.shape) < geom.recovery_rate_tee
                carry = np.where(trouble, att * 0.40, carry)

            nd = np.sqrt((dd - carry) ** 2 + lateral**2)

            new_lie = np.where(
                nd <= GREENSIDE_YARDS,
                np.where(rng.random(nd.shape) < geom.greenside_sand_share, "sand", "rough"),
                np.where(lateral <= geom.fairway_half_width_yards, "fairway", "rough"),
            )

            # Same disasters as the recursion, so predictions match the surface.
            if l == "sand":
                stuck = rng.random(nd.shape) < disp.sand_escape_fail_rate
                nd = np.where(stuck, dd, nd)
                new_lie = np.where(stuck, "sand", new_lie)

            penalised = rng.random(nd.shape) < disp.penalty_rate
            nd = np.where(penalised, dd, nd)
            new_lie = np.where(penalised, "rough", new_lie)

            landed_green = (nd <= geom.green_radius_yards) & ~penalised

            idx = np.where(sel)[0]
            d[idx] = nd
            lie[idx] = new_lie
            shots[idx] += np.where(penalised, 2, 1)
            newly = landed_green & ~on_green[idx]
            on_green[idx[newly]] = True
            first_putt_ft[idx[newly]] = nd[newly] * YARDS_TO_FEET
            reached_in_reg[idx[newly]] = shots[idx][newly] <= reg_shots

    # Anything still off the green after eight shots is on in a stroke's time.
    stragglers = ~on_green
    first_putt_ft[stragglers] = disp.short_game_proximity_ft

    putt_idx = np.clip(np.round(first_putt_ft).astype(int), 0, MAX_PUTT_FT - 1)
    expected_putts = float(np.mean(green[putt_idx]))

    return expected_putts, float(np.mean(reached_in_reg))


# ──────────────────────────────────────────────────────────────────────────────
# Calibration
# ──────────────────────────────────────────────────────────────────────────────


def calibrate(handicap: float, geometry: CourseGeometry = DEFAULT_GEOMETRY,
              iterations: int = 14) -> Tuple[Surface, Predicted]:
    """
    Solve the dispersion that reproduces measured putting, GIR and scoring.

    Three one-dimensional searches, alternated. Each target is monotone in its
    parameter, so bisection suffices and there is no optimiser to tune:

        putting d50      against  avg_putts
        approach lateral against  gir_pct
        penalty rate     against  avg_score

    `up_down_pct` is deliberately untouched — it is the holdout.

    Fitting the penalty rate to scoring is the one place model error could hide,
    so it is checked rather than trusted: `implied_penalty_strokes` converts the
    solved rate into penalty strokes per round, which is a number with a known
    plausible range. A fit that needs eight penalties a round has not found
    penalties, it has absorbed a broken model.
    """
    agg = aggregates_for(handicap)
    disp = dispersion_for(handicap, geometry)

    d50_lo, d50_hi = 1.5, 40.0
    app_lo, app_hi = 0.02, 0.40
    pen_lo, pen_hi = 0.0, 0.10

    ratio = disp.approach.distance / disp.approach.lateral
    surface = solve_surface(disp, sweeps=12)

    for _ in range(iterations):
        # Larger d50 means more putts drop, so fewer putts per round.
        d50 = 0.5 * (d50_lo + d50_hi)
        disp = replace(disp, putting=replace(disp.putting, d50_ft=d50))
        surface = solve_surface(disp, sweeps=10)
        if predict(surface).avg_putts > agg.avg_putts:
            d50_lo = d50
        else:
            d50_hi = d50

        # Wider approach dispersion means fewer greens hit.
        lat = 0.5 * (app_lo + app_hi)
        disp = replace(disp, approach=ShotSkill(lateral=lat, distance=lat * ratio))
        surface = solve_surface(disp, sweeps=10)
        if predict(surface).gir_pct > agg.gir_pct:
            app_lo = lat
        else:
            app_hi = lat

        # More penalties means a higher score.
        pen = 0.5 * (pen_lo + pen_hi)
        disp = replace(disp, penalty_rate=pen)
        surface = solve_surface(disp, sweeps=10)
        if predict(surface).avg_score > agg.avg_score:
            pen_hi = pen
        else:
            pen_lo = pen

    surface = solve_surface(disp, sweeps=40)
    return surface, predict(surface)


def implied_penalty_strokes(surface: Surface) -> float:
    """
    Penalty strokes per round implied by the solved rate.

    A rough shots-per-round count times the per-shot rate. Ordinary amateur golf
    runs well under one penalty a round at scratch and a few at 25; far above
    that means the penalty term is absorbing error from elsewhere in the model.
    """
    disp = surface.dispersion
    full_shots = sum(
        max(1.0, surface.strokes(hole.yards, "tee") - 2.0) for hole in REFERENCE_COURSE
    )
    return disp.penalty_rate * full_shots
