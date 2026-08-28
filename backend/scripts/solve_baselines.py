#!/usr/bin/env python
"""
Solve expected-strokes baselines from shot dispersion, and grade them.

    cd backend && uv run python scripts/solve_baselines.py
    cd backend && uv run python scripts/solve_baselines.py --sensitivity
    cd backend && uv run python scripts/solve_baselines.py --emit

Compare against `scripts/audit_sg.py`, which grades the committed hand-typed
tables the same way. The headline row is scoring error: the committed tables
miss by up to 17 strokes, worsening with handicap.

Fit on avg_putts, gir_pct and avg_score. Held out: up_down_pct.

Nothing here writes to `baselines.py`. Swapping baselines changes every
strokes-gained number the app shows, which AGENTS.md puts on Sam's desk.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.baselines import get_baseline_for_handicap
from app.core.dispersion import DEFAULT_GEOMETRY, CourseGeometry
from app.core.empirical import BRACKETS, OBSERVED, REFERENCE_COURSE
from app.core.expected_strokes import calibrate, implied_penalty_strokes

#: Ordinary amateur golf. Above this, the penalty term is absorbing model error
#: from elsewhere rather than describing penalties.
PLAUSIBLE_PENALTIES_PER_ROUND = 4.0

#: Below this, a player is missing half their putts from inside a yard, which no
#: golfer does. A solved d50 under it means putting is compensating for a bad
#: first-putt distance distribution, not describing a stroke.
PLAUSIBLE_MIN_D50_FT = 4.0


def rule(title: str) -> None:
    print(f"\n{'─' * 76}\n{title}\n{'─' * 76}")


def solve_all():
    rule("Solving — bisecting three parameters per bracket")
    print("   (roughly 20s per bracket)\n")
    out = {}
    for h in BRACKETS:
        surface, pred = calibrate(h)
        out[h] = (surface, pred)
        print(f"   {h:2d} solved")
    return out


def show_accuracy(solved) -> None:
    rule("1. Fit — aggregates the solver was given")
    print("   hcp      score pred/obs    err        putts pred/obs   err       GIR pred/obs    err")
    print("   ───   ─────────────────  ─────   ─────────────────  ─────   ───────────────  ─────")
    for h in BRACKETS:
        _, p = solved[h]
        o = OBSERVED[h]
        print(
            f"   {h:3d}   {p.avg_score:7.2f} / {o.avg_score:5.1f}  {p.avg_score - o.avg_score:+5.2f}   "
            f"{p.avg_putts:7.2f} / {o.avg_putts:5.1f}  {p.avg_putts - o.avg_putts:+5.2f}   "
            f"{p.gir_pct:6.3f} / {o.gir_pct:5.3f}  {p.gir_pct - o.gir_pct:+.3f}"
        )

    rule("2. Against the committed tables, on the same measure")
    print("   hcp   committed err   solved err   improvement")
    print("   ───   ─────────────   ──────────   ───────────")
    for h in BRACKETS:
        _, p = solved[h]
        o = OBSERVED[h]
        b = get_baseline_for_handicap(h)
        old = sum(b.strokes(hole.yards, "tee") for hole in REFERENCE_COURSE) - o.avg_score
        new = p.avg_score - o.avg_score
        factor = abs(old) / max(abs(new), 1e-6)
        print(f"   {h:3d}   {old:+13.2f}   {new:+10.2f}   {factor:9.1f}x")


def show_plausibility(solved) -> None:
    rule("3. Plausibility — is the fit describing golf, or absorbing error?")
    print("   Fitting a penalty rate to scoring is where a broken model would hide.")
    print("   These are the numbers that catch it.\n")
    print("   hcp   penalties/round   putting d50    verdict")
    print("   ───   ───────────────   ───────────    ───────")

    bad = []
    for h in BRACKETS:
        s, _ = solved[h]
        pen = implied_penalty_strokes(s)
        d50 = s.dispersion.putting.d50_ft
        problems = []
        if pen > PLAUSIBLE_PENALTIES_PER_ROUND:
            problems.append("too many penalties")
        if d50 < PLAUSIBLE_MIN_D50_FT:
            problems.append("d50 implausibly short")
        if problems:
            bad.append(h)
        verdict = "ok" if not problems else ", ".join(problems)
        print(f"   {h:3d}   {pen:15.2f}   {d50:8.2f} ft    {verdict}")

    if bad:
        print(f"\n   Brackets where the fit is compensating: {bad}")
        print("   The scoring match at those brackets is not earned — the solver")
        print("   bought it with parameters no real golfer has. What that points")
        print("   to is dispersion that should widen with distance and lie, which")
        print("   is exactly what published proximity tables supply.")


def show_holdout(solved) -> None:
    rule("4. Holdout — up-and-down, never shown to the solver")
    print("   hcp   implied   observed     err")
    print("   ───   ───────   ────────   ─────")
    errs = []
    for h in BRACKETS:
        s, _ = solved[h]
        # Getting down in two from greenside: one shot to the solved proximity,
        # then holing the putt that follows.
        prox = s.dispersion.short_game_proximity_ft
        p = s.dispersion.putting.make_probability(prox)
        o = OBSERVED[h].up_down_pct
        errs.append(p - o)
        print(f"   {h:3d}   {p:7.3f}   {o:8.3f}   {p - o:+.3f}")

    rmse = (sum(e * e for e in errs) / len(errs)) ** 0.5
    print(f"\n   RMSE {rmse:.3f}   bias {sum(errs) / len(errs):+.3f}")


def show_surface(solved) -> None:
    rule("5. The solved surface (15 handicap), against the committed one")
    s, _ = solved[15]
    b = get_baseline_for_handicap(15)
    print("   lie        dist   solved   committed")
    print("   ────────   ────   ──────   ─────────")
    for lie, dists in (("tee", (150, 400, 450)), ("fairway", (50, 100, 150, 200)),
                       ("rough", (50, 100, 150)), ("sand", (20, 50))):
        for d in dists:
            print(f"   {lie:8}   {d:4}   {s.strokes(d, lie):6.2f}   {b.strokes(d, lie):9.2f}")
    print("   green (ft)")
    for d in (3, 8, 15, 25, 40):
        print(f"   {'green':8}   {d:4}   {s.strokes(d, 'green'):6.2f}   {b.strokes(d, 'green'):9.2f}")


def show_sensitivity() -> None:
    rule("6. Sensitivity — how much do the ASSUMED constants matter?")
    print("   Re-solving a 15 handicap with each geometry constant moved.")
    print("   Large swings mean that constant needs measuring, not assuming.\n")
    print("   variant                       score err   penalties/round")
    print("   ───────────────────────────   ─────────   ───────────────")

    variants = [
        ("baseline", DEFAULT_GEOMETRY),
        ("fairway 24y wide", replace(DEFAULT_GEOMETRY, fairway_half_width_yards=12.0)),
        ("fairway 36y wide", replace(DEFAULT_GEOMETRY, fairway_half_width_yards=18.0)),
        ("green radius 9y", replace(DEFAULT_GEOMETRY, green_radius_yards=9.0)),
        ("green radius 13y", replace(DEFAULT_GEOMETRY, green_radius_yards=13.0)),
    ]
    o = OBSERVED[15]
    for name, geom in variants:
        surface, pred = calibrate(15, geometry=geom)
        print(
            f"   {name:27}   {pred.avg_score - o.avg_score:+9.2f}   "
            f"{implied_penalty_strokes(surface):15.2f}"
        )


def emit(solved) -> None:
    rule("Candidate tables")
    print("# Solved from dispersion. Review before replacing _BASELINE_DATA.")
    for h in BRACKETS:
        s, _ = solved[h]
        print(f"\n# ── {h} hcp ──")
        for lie in ("tee", "fairway", "rough", "sand"):
            keys = [500, 450, 400, 350, 300, 250, 200, 150, 125, 100, 75, 50, 30, 20, 10]
            entries = ", ".join(f"{d}: {s.strokes(d, lie):.2f}" for d in keys)
            print(f'"{lie}": {{{entries}}},')
        keys = [90, 80, 70, 60, 50, 40, 30, 25, 20, 15, 12, 10, 8, 6, 5, 4, 3, 2, 1]
        entries = ", ".join(f"{d}: {s.strokes(d, 'green'):.2f}" for d in keys)
        print(f'"green": {{{entries}}},')


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sensitivity", action="store_true")
    parser.add_argument("--emit", action="store_true")
    args = parser.parse_args()

    print("Expected strokes solved from dispersion")
    print("Anchors: Break X Golf, 3,788 rounds / 1,116 golfers")

    solved = solve_all()
    show_accuracy(solved)
    show_plausibility(solved)
    show_holdout(solved)
    show_surface(solved)

    if args.sensitivity:
        show_sensitivity()
    if args.emit:
        emit(solved)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
