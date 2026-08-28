#!/usr/bin/env python
"""
Solve expected-strokes baselines from shot dispersion, and grade them.

    cd backend && uv run python scripts/solve_baselines.py
    cd backend && uv run python scripts/solve_baselines.py --sensitivity
    cd backend && uv run python scripts/solve_baselines.py --emit

Compare against `scripts/audit_sg.py`, which grades the committed hand-typed
tables the same way. The headline row is scoring error: the committed tables
miss by up to 17 strokes, worsening with handicap.

One fitted parameter: approach dispersion, against gir_pct. Everything else is
read from published data. Held out: avg_score, avg_putts, up_down_pct.

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
from app.core import published
from app.core.expected_strokes import (
    MAX_PUTT_FT,
    calibrate,
    implied_penalty_strokes,
    implied_up_and_down,
    solve_putting,
)

def rule(title: str) -> None:
    print(f"\n{'─' * 76}\n{title}\n{'─' * 76}")


def solve_all():
    rule("Solving — bisecting approach dispersion per bracket")
    print("   (roughly 20s per bracket)\n")
    out = {}
    for h in BRACKETS:
        surface, pred = calibrate(h)
        out[h] = (surface, pred)
        print(f"   {h:2d} solved")
    return out


def show_accuracy(solved) -> None:
    rule("1. Fit — the one parameter that is not measured")
    print("   Approach dispersion, bisected against gir_pct. Everything else is")
    print("   read from published data.\n")
    print("   hcp      GIR pred/obs     err   approach lateral")
    print("   ───   ───────────────   ─────   ────────────────")
    for h in BRACKETS:
        s_, p = solved[h]
        o = OBSERVED[h]
        print(
            f"   {h:3d}   {p.gir_pct:6.3f} / {o.gir_pct:5.3f}  {p.gir_pct - o.gir_pct:+.3f}   "
            f"{s_.dispersion.approach.lateral:16.4f}"
        )


def show_holdout(solved) -> None:
    rule("2. Holdouts — never shown to the solver")

    print("   avg_score, avg_putts and up_down_pct are all held out. Putting comes")
    print("   from published make rates and penalties from published counts, so")
    print("   none of the three can be reached by tuning.\n")

    print("   hcp     score pred/obs     err      putts pred/obs     err     up&down pred/obs    err")
    print("   ───   ────────────────  ──────   ────────────────  ──────   ───────────────  ──────")
    se, pe, ue = [], [], []
    for h in BRACKETS:
        s_, p = solved[h]
        o = OBSERVED[h]
        ud, udo = implied_up_and_down(s_), published.UP_AND_DOWN_PCT[h]
        se.append(p.avg_score - o.avg_score)
        pe.append(p.avg_putts - o.avg_putts)
        ue.append(ud - udo)
        print(
            f"   {h:3d}   {p.avg_score:7.2f} / {o.avg_score:5.1f}  {se[-1]:+6.2f}   "
            f"{p.avg_putts:7.2f} / {o.avg_putts:5.1f}  {pe[-1]:+6.2f}   "
            f"{ud:6.3f} / {udo:5.3f}  {ue[-1]:+.3f}"
        )

    def rmse(xs):
        return (sum(x * x for x in xs) / len(xs)) ** 0.5

    print(f"\n   score    RMSE {rmse(se):6.2f}   bias {sum(se)/len(se):+6.2f}")
    print(f"   putts    RMSE {rmse(pe):6.2f}   bias {sum(pe)/len(pe):+6.2f}")
    print(f"   up&down  RMSE {rmse(ue):6.3f}   bias {sum(ue)/len(ue):+6.3f}")
    print("\n   up&down was RMSE 0.283 before the greenside model existed.")


def show_committed_comparison(solved) -> None:
    rule("3. Scoring, against the committed tables")
    print("   hcp   committed err   solved err   improvement")
    print("   ───   ─────────────   ──────────   ───────────")
    for h in BRACKETS:
        _, p = solved[h]
        o = OBSERVED[h]
        b = get_baseline_for_handicap(h)
        old = sum(b.strokes(hole.yards, "tee") for hole in REFERENCE_COURSE) - o.avg_score
        new = p.avg_score - o.avg_score
        print(f"   {h:3d}   {old:+13.2f}   {new:+10.2f}   {abs(old)/max(abs(new),1e-6):9.1f}x")


def show_first_putt(solved) -> None:
    rule("4. Where the remaining putts gap is")
    print("   What first putt would the published make rates need, to produce the")
    print("   measured putts per round? And what does the model actually produce?\n")
    print("   hcp   required   published chip proximity")
    print("   ───   ────────   ────────────────────────")
    for h in BRACKETS:
        s_, _ = solved[h]
        table = solve_putting(s_.dispersion.putting)
        target = OBSERVED[h].avg_putts / 18.0
        need = next((x for x in range(1, MAX_PUTT_FT) if table[x] >= target), None)
        prox = published.SHORT_GAME_PROXIMITY_FT[h]
        print(f"   {h:3d}   {str(need) + ' ft':>8}   {prox:19.0f} ft")
    print("\n   The required distance runs 2-5 ft beyond chip proximity and tracks")
    print("   it closely, which is what it should do: not every green is reached by")
    print("   a chip. The two published sources are coherent. A model short on putts")
    print("   is therefore finishing balls too close, not being fed bad data.")


def show_plausibility(solved) -> None:
    rule("5. Plausibility")
    print("   hcp   penalties/round   putting d50   source")
    print("   ───   ───────────────   ───────────   ──────")
    for h in BRACKETS:
        s_, _ = solved[h]
        print(
            f"   {h:3d}   {implied_penalty_strokes(s_):15.2f}   "
            f"{s_.dispersion.putting.d50_ft:8.2f} ft   measured"
        )
    print("\n   Both were fitted parameters before, and both drifted implausible")
    print("   (d50 collapsing to 2.9 ft, penalties reaching 5.9 a round). They are")
    print("   now read from published data and cannot absorb model error.")


def show_surface(solved) -> None:
    rule("6. The solved surface (15 handicap), against the committed one")
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
    rule("7. Sensitivity — how much do the ASSUMED constants matter?")
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
    show_holdout(solved)
    show_committed_comparison(solved)
    show_first_putt(solved)
    show_plausibility(solved)
    show_surface(solved)

    if args.sensitivity:
        show_sensitivity()
    if args.emit:
        emit(solved)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
