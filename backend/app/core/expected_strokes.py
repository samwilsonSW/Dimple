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
from typing import Dict, Optional, Tuple

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


def _greenside_values(
    distances: np.ndarray,
    lie: str,
    disp: PlayerDispersion,
    green: np.ndarray,
    rng: np.random.Generator,
) -> np.ndarray:
    """
    Expected strokes for a shot from just off the green.

    A chip is not a short approach. Modelling it as one — which the recursion did
    before this existed — gets the up-and-down rate and the first-putt distance
    after a missed green both wrong, and the putting calibration then distorts to
    absorb the error.

    Proximity is drawn from a Gamma with the *published mean* and a right skew,
    which matters: most chips finish nearer than the average while a few finish
    far, so the average make probability is higher than the make probability at
    the average distance.
    """
    n = len(distances)
    mult = {"fairway": 1.0, "rough": disp.rough_penalty, "sand": disp.sand_penalty}.get(lie, 1.0)

    # A 30-yard pitch finishes further out than a 5-yard chip.
    scale = 0.55 + 0.45 * (distances / GREENSIDE_YARDS)
    mean_ft = disp.short_game_proximity_ft * mult * scale

    shape = disp.short_game_shape
    prox = rng.gamma(shape, size=(n, SAMPLES)) * (mean_ft / shape)[:, None]

    if lie == "sand":
        stuck = rng.random((n, SAMPLES)) < disp.sand_escape_fail_rate
    else:
        stuck = np.zeros((n, SAMPLES), dtype=bool)

    idx = np.clip(np.round(prox).astype(int), 0, MAX_PUTT_FT - 1)
    values = green[idx]

    # A failed escape leaves the same shot to play again.
    if stuck.any():
        values = np.where(stuck, values + 1.0, values)

    return 1.0 + values.mean(axis=1)


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

    greenside = distances <= GREENSIDE_YARDS

    for _ in range(sweeps):
        delta = 0.0
        for lie in FULL_LIES:
            updated = _sweep(distances, lie, disp, green, full, rng)

            # Inside the greenside band it is a chip, not a short approach.
            if lie != "tee":
                updated[greenside] = _greenside_values(
                    distances[greenside], lie, disp, green, rng
                )

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


@dataclass
class HoleSim:
    """
    Instrumented outcomes of many simulated plays of one hole.

    This is the one place hole play is simulated. The scorecard reconstruction
    in `scorecard_stats.py` compares against conditional expectations of these
    outcomes, so attribution and surface share a single generative model — the
    property every strokes-gained identity in this codebase depends on.

    Values are expected strokes looked up on the surface, with penalty strokes
    included where they occurred. `prechip_value` is NaN for plays that never
    chipped.
    """

    fw_hit: np.ndarray          # bool — tee shot finished in the fairway, clean
    value_after_tee: np.ndarray  # E(position after the tee shot), +1 if penalised
    shots_to_green: np.ndarray  # int — swings + chips + penalty strokes to reach green
    penalties: np.ndarray       # int — penalty events before reaching the green
    first_putt_ft: np.ndarray   # feet — where the ball first lay on the green
    chipped: np.ndarray         # bool — at least one greenside chip was played
    prechip_value: np.ndarray   # E(position before the first chip); NaN if none


def simulate_holes(
    surface: Surface,
    hole_yards: float,
    n: int,
    rng: np.random.Generator,
    max_shots: int = 14,
) -> HoleSim:
    """
    Play one hole `n` times under the surface's own dispersion model.

    Movement, classification, and disasters mirror `_sweep` exactly — a shot
    here must land where the recursion says shots land, or the conditional
    tables drift from the surface and the strokes-gained identities break.
    """
    disp = surface.dispersion
    geom = disp.geometry
    green = surface.green_ft

    d = np.full(n, float(hole_yards))
    lie = np.full(n, "tee", dtype=object)
    on_green = np.zeros(n, dtype=bool)
    shots = np.zeros(n, dtype=int)
    penalties = np.zeros(n, dtype=int)
    first_putt_ft = np.zeros(n)
    fw_hit = np.zeros(n, dtype=bool)
    value_after_tee = np.zeros(n)
    chipped = np.zeros(n, dtype=bool)
    prechip_value = np.full(n, np.nan)

    def state_value(dist: np.ndarray, lies: np.ndarray) -> np.ndarray:
        """E(position) for arrays of (distance, lie), green in feet handled."""
        out = np.empty(len(dist))
        for l in FULL_LIES:
            sel = lies == l
            if sel.any():
                idx = np.clip(dist[sel].astype(int), 0, MAX_YARDS - 1)
                out[sel] = surface.full[l][idx]
        sel = lies == "green"
        if sel.any():
            idx = np.clip(np.round(dist[sel] * YARDS_TO_FEET).astype(int), 0, MAX_PUTT_FT - 1)
            out[sel] = green[idx]
        return out

    for _ in range(max_shots):
        live = ~on_green
        if not live.any():
            break

        # One shot per ball per iteration. Without this, a ball landing
        # greenside during the fairway pass is picked up by the rough pass of
        # the same iteration and swings again — a full swing from 15 yards,
        # which the fraction-of-distance dispersion makes far better than the
        # chip model the recursion prices there. That bypass let simulated
        # play beat the surface by more than a stroke a round.
        acted = np.zeros(n, dtype=bool)

        # Greenside band: chip, matching `_greenside_values`.
        chip = live & (d <= GREENSIDE_YARDS) & (lie != "tee")
        if chip.any():
            idx = np.where(chip)[0]
            first = ~chipped[idx]
            if first.any():
                fi = idx[first]
                prechip_value[fi] = state_value(d[fi], lie[fi])
                chipped[fi] = True

            mult = np.array(
                [
                    {"fairway": 1.0, "rough": disp.rough_penalty, "sand": disp.sand_penalty}.get(l, 1.0)
                    for l in lie[idx]
                ]
            )
            scale = 0.55 + 0.45 * (d[idx] / GREENSIDE_YARDS)
            mean_ft = disp.short_game_proximity_ft * mult * scale
            shape = disp.short_game_shape
            prox = rng.gamma(shape, size=idx.shape) * (mean_ft / shape)

            # A failed bunker escape costs an extra stroke from the same spot,
            # exactly as `_greenside_values` charges it.
            is_sand = np.array([l == "sand" for l in lie[idx]])
            stuck = is_sand & (rng.random(idx.shape) < disp.sand_escape_fail_rate)

            shots[idx] += 1 + stuck.astype(int)
            first_putt_ft[idx] = prox
            on_green[idx] = True
            acted[idx] = True
            live = ~on_green

        for l in FULL_LIES:
            sel = live & (lie == l) & ~acted
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
            else:
                trouble = np.zeros(att.shape, dtype=bool)

            nd = np.sqrt((dd - carry) ** 2 + lateral**2)
            nd = np.clip(nd, 0.0, MAX_YARDS - 1)

            on = (nd <= geom.green_radius_yards) & ~trouble
            gside = (~on) & (nd <= GREENSIDE_YARDS)
            in_sand = gside & (rng.random(nd.shape) < geom.greenside_sand_share)
            in_fw = (~on) & (~gside) & (lateral <= geom.fairway_half_width_yards) & ~trouble

            new_lie = np.where(on, "green", np.where(in_sand, "sand", np.where(in_fw, "fairway", "rough")))

            # Disasters, mirroring `_sweep`.
            if l == "sand":
                stuck = rng.random(nd.shape) < disp.sand_escape_fail_rate
                nd = np.where(stuck, dd, nd)
                new_lie = np.where(stuck, "sand", new_lie)

            penalised = rng.random(nd.shape) < disp.penalty_rate
            nd = np.where(penalised, dd, nd)
            new_lie = np.where(penalised, "rough", new_lie)

            idx = np.where(sel)[0]
            landed = (new_lie == "green") & ~penalised

            if l == "tee":
                clean_fw = (new_lie == "fairway") & ~penalised
                fw_hit[idx] = clean_fw
                value_after_tee[idx] = state_value(nd, new_lie) + np.where(penalised, 1.0, 0.0)

            d[idx] = nd
            lie[idx] = new_lie
            shots[idx] += np.where(penalised, 2, 1)
            penalties[idx] += penalised.astype(int)
            acted[idx] = True

            li = idx[landed]
            on_green[li] = True
            first_putt_ft[li] = nd[landed] * YARDS_TO_FEET

    # Anything still off the green is put on in a stroke's time.
    stragglers = ~on_green
    if stragglers.any():
        first_putt_ft[stragglers] = disp.short_game_proximity_ft
        shots[stragglers] += 1

    return HoleSim(
        fw_hit=fw_hit,
        value_after_tee=value_after_tee,
        shots_to_green=shots,
        penalties=penalties,
        first_putt_ft=first_putt_ft,
        chipped=chipped,
        prechip_value=prechip_value,
    )


def simulate_putt_counts(
    surface: Surface, first_putt_ft: np.ndarray, rng: np.random.Generator
) -> np.ndarray:
    """Integer putt counts from first-putt distances, drawn from the make model."""
    skill = surface.dispersion.putting
    d = first_putt_ft.copy().astype(float)
    holed = d <= 0.25
    counts = np.zeros(len(d), dtype=int)
    for _ in range(5):
        live = ~holed
        if not live.any():
            break
        counts[live] += 1
        p = np.array([skill.make_probability(float(x)) for x in d[live]])
        made = rng.random(p.shape) < p
        li = np.where(live)[0]
        holed[li[made]] = True
        miss = li[~made]
        d[miss] = np.array([skill.lag_distance_ft(float(x)) for x in d[miss]])
    counts[~holed] += 1  # cap: anything still out is conceded next stroke
    return counts


def predict(surface: Surface) -> Predicted:
    """
    Play the reference course against the surface.

    Expected strokes from the tee, summed over 18 holes, is the expected score —
    the same identity the audit uses, now evaluated on a derived surface instead
    of a typed one. Putts are averaged over the distribution of first-putt
    distances rather than read at its mean: expected putts is concave in
    distance, so by Jensen, collapsing to the mean first would overstate putts.
    """
    score = sum(surface.strokes(hole.yards, "tee") for hole in REFERENCE_COURSE)

    rng = np.random.default_rng(SEED + 1)
    putts_total = 0.0
    gir_hits = 0.0

    for hole in REFERENCE_COURSE:
        sim = simulate_holes(surface, hole.yards, n=600, rng=rng)
        reached = sim.shots_to_green <= (hole.par - 2)
        gir_hits += float(np.mean(reached))
        idx = np.clip(np.round(sim.first_putt_ft).astype(int), 0, MAX_PUTT_FT - 1)
        putts_total += float(np.mean(surface.green_ft[idx]))

    holes = len(REFERENCE_COURSE)
    return Predicted(
        avg_score=score,
        avg_putts=putts_total,
        gir_pct=gir_hits / holes,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Scorecard conditionals — what the reconstruction compares against
# ──────────────────────────────────────────────────────────────────────────────

#: Yardage grids the conditionals are solved on, per par.
CONDITIONAL_GRIDS: Dict[int, np.ndarray] = {
    3: np.arange(80, 265, 5, dtype=float),
    4: np.arange(240, 505, 5, dtype=float),
    5: np.arange(400, 625, 5, dtype=float),
}

#: Simulated plays per grid point when solving conditionals.
CONDITIONAL_SAMPLES = 3000

#: First-putt distance bands, in feet — these mirror the entry UI exactly
#: ("Tap-in <3ft", "Short 3-10ft", "Mid 10-25ft", "Long 25ft+").
FIRST_PUTT_BANDS: Dict[str, Tuple[float, float]] = {
    "tap_in": (0.0, 3.0),
    "short": (3.0, 10.0),
    "mid": (10.0, 25.0),
    "long": (25.0, float("inf")),
}


@dataclass
class HoleConditionals:
    """
    Conditional expectations of hole play, per par, on a yardage grid.

    Every baseline `scorecard_stats.py` compares a player against comes from
    here — expectations under the surface's own model, conditioned on what the
    scorecard reveals. That is what makes the four categories telescope exactly
    and average to zero for a player whose game matches the model:

      p_fw            P(tee shot finishes in the fairway)
      v_hit           E[E(position after tee) | fairway hit]
      v_miss          E[E(position after tee) | fairway missed], penalties included
      e_fp_putts_gir  E[expected putts at the first-putt distance | GIR]
      v_prechip       E[E(position before the first chip) | green missed in
                      regulation and a chip was played]
      bucket_gir      E[expected putts | first putt in band, green hit in reg]
      bucket_chip     E[expected putts | first putt in band, after a chip]

    By construction  p_fw · v_hit + (1 − p_fw) · v_miss = E_tee − 1,  so a
    fairway split can move strokes between driving and the rest without
    inventing any.

    The bucket tables are the certainty equivalents of the entry UI's coarse
    bands: reading a band at a single representative distance mis-prices it
    (expected putts is nonlinear in distance and the within-band distribution
    is skewed), and that mispricing was visible as a flat bias in putting SG.
    """

    p_fw: Dict[int, np.ndarray]
    v_hit: Dict[int, np.ndarray]
    v_miss: Dict[int, np.ndarray]
    e_fp_putts_gir: Dict[int, np.ndarray]
    v_prechip: Dict[int, np.ndarray]
    bucket_gir: Dict[str, float]
    bucket_chip: Dict[str, float]

    def _lookup(self, table: Dict[int, np.ndarray], par: int, yardage: float) -> float:
        grid = CONDITIONAL_GRIDS[par]
        return float(np.interp(float(yardage), grid, table[par]))

    def fairway_probability(self, par: int, yardage: float) -> float:
        return self._lookup(self.p_fw, par, yardage)

    def value_after_drive(self, par: int, yardage: float, hit: Optional[bool]) -> float:
        if hit is True:
            return self._lookup(self.v_hit, par, yardage)
        if hit is False:
            return self._lookup(self.v_miss, par, yardage)
        p = self.fairway_probability(par, yardage)
        return p * self._lookup(self.v_hit, par, yardage) + (1 - p) * self._lookup(
            self.v_miss, par, yardage
        )

    def expected_first_putt_strokes(self, par: int, yardage: float) -> float:
        return self._lookup(self.e_fp_putts_gir, par, yardage)

    def prechip_value(self, par: int, yardage: float) -> float:
        return self._lookup(self.v_prechip, par, yardage)

    def first_putt_bucket_strokes(self, bucket: str, gir: bool) -> float:
        """Expected putts for a recorded first-putt band."""
        table = self.bucket_gir if gir else self.bucket_chip
        return table[bucket]


def solve_conditionals(surface: Surface, rng: Optional[np.random.Generator] = None) -> HoleConditionals:
    """
    Solve the scorecard conditionals for one surface by simulation.

    Cells that a bracket practically never produces (a scratch player missing
    every green on a 90-yard par 3) fall back to their unconditional
    neighbours rather than NaN, so lookups stay total.
    """
    if rng is None:
        rng = np.random.default_rng(SEED + 3)

    p_fw: Dict[int, np.ndarray] = {}
    v_hit: Dict[int, np.ndarray] = {}
    v_miss: Dict[int, np.ndarray] = {}
    e_fp: Dict[int, np.ndarray] = {}
    v_pre: Dict[int, np.ndarray] = {}

    gir_fp_samples: list = []
    chip_fp_samples: list = []

    for par, grid in CONDITIONAL_GRIDS.items():
        reg = par - 2
        n_pts = len(grid)
        arr_pfw = np.zeros(n_pts)
        arr_hit = np.zeros(n_pts)
        arr_miss = np.zeros(n_pts)
        arr_fp = np.zeros(n_pts)
        arr_pre = np.zeros(n_pts)

        for i, yards in enumerate(grid):
            sim = simulate_holes(surface, float(yards), CONDITIONAL_SAMPLES, rng)
            e_tee = surface.strokes(float(yards), "tee")

            hit = sim.fw_hit
            arr_pfw[i] = float(np.mean(hit)) if par > 3 else 0.0
            arr_hit[i] = float(np.mean(sim.value_after_tee[hit])) if hit.any() else e_tee - 1.0
            arr_miss[i] = float(np.mean(sim.value_after_tee[~hit])) if (~hit).any() else e_tee - 1.0

            gir = sim.shots_to_green <= reg
            if gir.any():
                idx = np.clip(np.round(sim.first_putt_ft[gir]).astype(int), 0, MAX_PUTT_FT - 1)
                arr_fp[i] = float(np.mean(surface.green_ft[idx]))
                gir_fp_samples.append(sim.first_putt_ft[gir])
            else:
                arr_fp[i] = float(surface.green_ft[int(min(25.0, MAX_PUTT_FT - 1))])

            pre = (~gir) & sim.chipped & ~np.isnan(sim.prechip_value)
            if pre.any():
                arr_pre[i] = float(np.mean(sim.prechip_value[pre]))
            else:
                arr_pre[i] = float(surface.strokes(15.0, "rough"))
            if ((~gir) & sim.chipped).any():
                chip_fp_samples.append(sim.first_putt_ft[(~gir) & sim.chipped])

        p_fw[par] = arr_pfw
        v_hit[par] = arr_hit
        v_miss[par] = arr_miss
        e_fp[par] = arr_fp
        v_pre[par] = arr_pre

    def band_table(samples: list) -> Dict[str, float]:
        pooled = np.concatenate(samples) if samples else np.array([15.0])
        idx = np.clip(np.round(pooled).astype(int), 0, MAX_PUTT_FT - 1)
        values = surface.green_ft[idx]
        out: Dict[str, float] = {}
        for band, (lo, hi) in FIRST_PUTT_BANDS.items():
            sel = (pooled > lo) & (pooled <= hi) if band != "tap_in" else (pooled <= hi)
            if sel.any():
                out[band] = float(np.mean(values[sel]))
            else:
                # Band the model never produces here: price its midpoint.
                mid = min(hi, lo + 10.0) if np.isfinite(hi) else lo + 10.0
                out[band] = float(surface.green_ft[int(min(mid, MAX_PUTT_FT - 1))])
        return out

    return HoleConditionals(
        p_fw=p_fw,
        v_hit=v_hit,
        v_miss=v_miss,
        e_fp_putts_gir=e_fp,
        v_prechip=v_pre,
        bucket_gir=band_table(gir_fp_samples),
        bucket_chip=band_table(chip_fp_samples),
    )


# ──────────────────────────────────────────────────────────────────────────────
# Calibration
# ──────────────────────────────────────────────────────────────────────────────


def calibrate(handicap: float, geometry: CourseGeometry = DEFAULT_GEOMETRY,
              iterations: int = 16) -> Tuple[Surface, Predicted]:
    """
    Solve the one parameter that is not measured.

    Putting comes from published make rates, penalties from published penalty
    counts, greenside proximity from published proximity, tee dispersion from
    fairway percentage, driving from measured distance. That leaves approach
    dispersion, which is bisected against `gir_pct` — it cannot be read off
    directly, because a scratch player and a 25 handicap face entirely different
    approach distances and only the recursion knows what those are.

    One fitted parameter, three holdouts: `avg_score`, `avg_putts` and
    `up_down_pct` are never shown to the solver. Reproducing them is evidence.
    """
    agg = aggregates_for(handicap)
    disp = dispersion_for(handicap, geometry)

    ratio = disp.approach.distance / disp.approach.lateral
    lo, hi = 0.02, 0.40
    surface = solve_surface(disp, sweeps=12)

    for _ in range(iterations):
        lat = 0.5 * (lo + hi)
        disp = replace(disp, approach=ShotSkill(lateral=lat, distance=lat * ratio))
        surface = solve_surface(disp, sweeps=12)
        if predict(surface).gir_pct > agg.gir_pct:
            lo = lat
        else:
            hi = lat

    surface = solve_surface(disp, sweeps=40)
    return surface, predict(surface)


def implied_up_and_down(surface: Surface, samples: int = 20000) -> float:
    """
    Up-and-down rate implied by the greenside and putting models.

    Chip on, then hole the putt. Averaged over the proximity distribution rather
    than evaluated at its mean, which matters here: make probability is convex
    across the chipping range, so the skew is worth several points of conversion.
    """
    disp = surface.dispersion
    rng = np.random.default_rng(SEED + 2)

    shape = disp.short_game_shape
    mean_ft = disp.short_game_proximity_ft
    prox = rng.gamma(shape, size=samples) * (mean_ft / shape)

    makes = np.array([disp.putting.make_probability(float(p)) for p in prox])
    return float(makes.mean())


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
