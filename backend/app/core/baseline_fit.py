"""
Solve strokes-gained baselines against measured aggregates.

The committed tables in `baselines.py` were typed by hand: scratch values with
small increments added per handicap bracket. `scripts/audit_sg.py` shows the
consequence — the implied round total is 5 strokes light at scratch and 17
light at 25, so every SG number in the app inherits that error, worst for the
highest handicaps.

Approach
--------
Rather than invent a new functional form, this module keeps the *shape* of the
existing tables — which audit checks 3, 4 and 5 confirm is sound (monotone in
handicap, monotone in distance, correct fairway < rough < sand ordering) — and
solves a single scale factor per bracket against a measured anchor.

    E'(d, lie) = 1 + s · (E(d, lie) - 1)

Scaling the *excess over one stroke* rather than the whole value keeps the
"you still have to hole it" floor intact, and preserves all three structural
properties automatically for any s > 0.

Fit and validation are deliberately separated, and neither touches the
synthetic round generator:

    long game   fit on avg_score   validated against gir_pct
    putting     fit on avg_putts   validated against up_down_pct

Because each layer is fit on one measured aggregate and checked against a
different one that was never shown to the solver, agreement is evidence rather
than tautology. `scripts/fit_baselines.py` reports both.

Result: REJECTED as a shippable fix
-----------------------------------
The scales hit their anchors exactly — round totals and putts per round both
land on the measured values with zero residual. The holdout says that is not
enough:

    GIR       RMSE 0.153, bias -0.141   (0.331 predicted vs 0.568 observed at scratch)
    up&down   RMSE 0.205, bias -0.204   (collapses to 0.000 at 20 and 25 handicap)

A single scale per bracket makes a player uniformly worse from every distance
and every lie. Real skill is not uniform: the gap between a scratch and a 25
handicap is enormous from 200 yards in the rough and nearly nil from three feet.
Forcing one factor to cover both over-penalises short shots to pay for the long
ones, which is exactly the up-and-down collapse above.

Two further signals point the same way. The solved putting scale runs *backwards*
(1.39 at scratch down to 1.10 at 25) because the committed green table spreads
far more across handicaps than measured putting does. And the sensitivity sweep
in `scripts/fit_baselines.py` shows holdout error falling monotonically as the
assumed first-putt distance rises past the plausible band — the fit trying to
escape a form that cannot hold both constraints at once.

So this module is kept as a recorded dead end, not a candidate. It establishes
the fit/holdout harness that the real model must clear, and it rules out the
cheapest option so the next attempt does not repeat it.

What the failure implies the real model needs: skill that varies by lie and by
distance band rather than one global factor, fit against the per-category
aggregates rather than round totals alone. See `docs/SG_REBUILD.md`.

Status: not wired into the live SG path, and should not be. Swapping baselines
changes every strokes-gained number the app displays, which AGENTS.md puts on
Sam's desk, not an agent's.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable

from app.core.baselines import _BASELINE_DATA, LieType, get_baseline_for_handicap
from app.core.empirical import BRACKETS, OBSERVED, REFERENCE_COURSE

#: Lies whose expected strokes are governed by the long game anchor.
LONG_GAME_LIES: tuple[str, ...] = ("tee", "fairway", "rough", "sand")

#: The putting surface, fit separately against putts per round.
PUTTING_LIES: tuple[str, ...] = ("green",)

#: Assumed mean first-putt distance, in feet, used to turn the green table into
#: a putts-per-round prediction. Held fixed across brackets: proximity differences
#: between handicaps are carried by `gir_pct` (a 25 handicap reaches far fewer
#: greens in regulation), not by wildly different lag putting. Sensitivity to
#: this constant is reported by `scripts/fit_baselines.py`.
ASSUMED_FIRST_PUTT_FT = 28.0


@dataclass(frozen=True)
class BracketFit:
    """The solved scale factors and their fit residuals for one bracket."""

    handicap: int
    long_game_scale: float
    putting_scale: float
    predicted_score: float
    observed_score: float
    predicted_putts: float
    observed_putts: float

    @property
    def score_error(self) -> float:
        return self.predicted_score - self.observed_score

    @property
    def putts_error(self) -> float:
        return self.predicted_putts - self.observed_putts


def _scale_excess(value: float, scale: float) -> float:
    """Scale a baseline's excess over one stroke, keeping the hole-out floor."""
    return 1.0 + scale * (value - 1.0)


def solve_long_game_scale(handicap: int) -> float:
    """
    Scale factor making the reference round sum to measured scoring.

    Expected strokes to hole out from the tee, summed over 18 holes, *is* the
    expected score, so the anchor is exact rather than approximate:

        sum[1 + s(E_tee(y) - 1)] = avg_score
        18 + s * (sum E_tee(y) - 18) = avg_score

    which solves in closed form. No optimiser needed.
    """
    baseline = get_baseline_for_handicap(handicap)
    raw_total = sum(baseline.strokes(hole.yards, "tee") for hole in REFERENCE_COURSE)
    holes = len(REFERENCE_COURSE)

    excess = raw_total - holes
    if excess <= 0:
        raise ValueError(f"degenerate tee table at handicap {handicap}: total {raw_total}")

    return (OBSERVED[handicap].avg_score - holes) / excess


def solve_putting_scale(handicap: int, first_putt_ft: float = ASSUMED_FIRST_PUTT_FT) -> float:
    """
    Scale factor making the green table reproduce measured putts per round.

    Uses a single representative first-putt distance rather than integrating a
    distribution: the green table is close to linear in log-distance over the
    20-40ft band that matters, so the difference is well inside the noise on
    `avg_putts` itself.
    """
    baseline = get_baseline_for_handicap(handicap)
    raw = baseline.strokes(int(round(first_putt_ft)), "green")
    holes = len(REFERENCE_COURSE)
    target_per_hole = OBSERVED[handicap].avg_putts / holes

    excess = raw - 1.0
    if excess <= 0:
        raise ValueError(f"degenerate green table at handicap {handicap}")

    return (target_per_hole - 1.0) / excess


def fit_bracket(handicap: int, first_putt_ft: float = ASSUMED_FIRST_PUTT_FT) -> BracketFit:
    """Solve both scales for one bracket and record what they predict."""
    long_scale = solve_long_game_scale(handicap)
    putt_scale = solve_putting_scale(handicap, first_putt_ft)

    baseline = get_baseline_for_handicap(handicap)
    holes = len(REFERENCE_COURSE)

    predicted_score = sum(
        _scale_excess(baseline.strokes(hole.yards, "tee"), long_scale)
        for hole in REFERENCE_COURSE
    )
    predicted_putts = holes * _scale_excess(
        baseline.strokes(int(round(first_putt_ft)), "green"), putt_scale
    )

    observed = OBSERVED[handicap]
    return BracketFit(
        handicap=handicap,
        long_game_scale=long_scale,
        putting_scale=putt_scale,
        predicted_score=predicted_score,
        observed_score=observed.avg_score,
        predicted_putts=predicted_putts,
        observed_putts=observed.avg_putts,
    )


def fit_all(first_putt_ft: float = ASSUMED_FIRST_PUTT_FT) -> Dict[int, BracketFit]:
    """Solve every bracket."""
    return {h: fit_bracket(h, first_putt_ft) for h in BRACKETS}


def rescaled_tables(handicap: int, fit: BracketFit) -> Dict[str, Dict[int, float]]:
    """
    Apply a bracket's solved scales to produce corrected baseline tables.

    Returns the same {lie: {distance: strokes}} structure as `_BASELINE_DATA`,
    ready to be emitted as a replacement table.
    """
    source = _BASELINE_DATA[handicap]
    out: Dict[str, Dict[int, float]] = {}

    for lie, table in source.items():
        scale = fit.putting_scale if lie in PUTTING_LIES else fit.long_game_scale
        out[lie] = {d: round(_scale_excess(v, scale), 3) for d, v in table.items()}

    return out


# ──────────────────────────────────────────────────────────────────────────────
# Held-out validation
# ──────────────────────────────────────────────────────────────────────────────
# Neither aggregate below was shown to the solver. If the rescaled surface
# reproduces them, the scaling captured something real about skill; if it does
# not, the multiplicative form is too crude and needs replacing with a fitted
# functional form. Either outcome is informative.


def implied_gir_pct(handicap: int, fit: BracketFit) -> float:
    """
    GIR rate implied by the rescaled long-game surface.

    A green is hit in regulation when the player reaches it in (par - 2) shots.
    The rescaled tee value is expected strokes to hole out; subtracting the
    rescaled putting expectation leaves expected shots to reach the green, and
    the shortfall against (par - 2) is the regulation margin. Converting that
    margin to a rate uses a logistic link whose slope is the one free constant
    here — reported, not tuned per bracket.
    """
    baseline = get_baseline_for_handicap(handicap)
    putts_per_hole = _scale_excess(
        baseline.strokes(int(round(ASSUMED_FIRST_PUTT_FT)), "green"), fit.putting_scale
    )

    import math

    rates = []
    for hole in REFERENCE_COURSE:
        to_hole_out = _scale_excess(baseline.strokes(hole.yards, "tee"), fit.long_game_scale)
        shots_to_green = to_hole_out - putts_per_hole
        margin = (hole.par - 2) - shots_to_green
        rates.append(1.0 / (1.0 + math.exp(-1.6 * margin)))

    return sum(rates) / len(rates)


def implied_up_down_pct(handicap: int, fit: BracketFit) -> float:
    """
    Up-and-down rate implied by the rescaled putting surface.

    Getting down in two from off the green means one short-game shot plus one
    putt. Taking a typical greenside pitch to finish at the same representative
    distance used in the putting fit, the rate is the probability of holing that
    putt — recovered from expected putts by treating the outcome as one or two
    putts, which holds well inside 30 feet.
    """
    baseline = get_baseline_for_handicap(handicap)
    expected = _scale_excess(
        baseline.strokes(int(round(ASSUMED_FIRST_PUTT_FT)), "green"), fit.putting_scale
    )
    # E[putts] = 1*p + 2*(1-p)  =>  p = 2 - E
    return max(0.0, min(1.0, 2.0 - expected))
