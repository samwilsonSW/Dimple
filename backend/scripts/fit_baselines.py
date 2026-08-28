#!/usr/bin/env python
"""
Solve and grade candidate strokes-gained baselines.

    cd backend && uv run python scripts/fit_baselines.py

Reports three things:

  1. Fit    — does the rescaled surface reproduce the anchors it was solved on?
  2. Holdout — does it also reproduce aggregates the solver never saw?
  3. Sensitivity — how much does the one free assumption move the answer?

Nothing here writes to `baselines.py`. Use `--emit` to print a replacement
table for review.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.baseline_fit import (
    ASSUMED_FIRST_PUTT_FT,
    fit_all,
    implied_gir_pct,
    implied_up_down_pct,
    rescaled_tables,
)
from app.core.empirical import BRACKETS, OBSERVED


def rule(title: str) -> None:
    print(f"\n{'─' * 74}\n{title}\n{'─' * 74}")


def show_fit() -> dict:
    rule("1. Fit — anchors the solver was given")
    fits = fit_all()

    print("   hcp   long scale   putt scale     score pred/obs      putts pred/obs")
    print("   ───   ──────────   ──────────   ─────────────────   ─────────────────")
    for h in BRACKETS:
        f = fits[h]
        print(
            f"   {h:3d}   {f.long_game_scale:10.4f}   {f.putting_scale:10.4f}   "
            f"{f.predicted_score:7.2f} / {f.observed_score:5.1f}   "
            f"{f.predicted_putts:7.2f} / {f.observed_putts:5.1f}"
        )

    worst_score = max(abs(f.score_error) for f in fits.values())
    worst_putts = max(abs(f.putts_error) for f in fits.values())
    print(f"\n   worst residual: {worst_score:.4f} strokes, {worst_putts:.4f} putts")
    print("   (exact by construction — these anchors define the scales)")
    return fits


def show_holdout(fits: dict) -> None:
    rule("2. Holdout — aggregates the solver never saw")

    print("   hcp     GIR pred/obs   err       up&down pred/obs   err")
    print("   ───   ───────────────  ─────   ───────────────────  ─────")

    gir_errs, ud_errs = [], []
    for h in BRACKETS:
        f = fits[h]
        obs = OBSERVED[h]
        gir_p = implied_gir_pct(h, f)
        ud_p = implied_up_down_pct(h, f)
        gir_e = gir_p - obs.gir_pct
        ud_e = ud_p - obs.up_down_pct
        gir_errs.append(gir_e)
        ud_errs.append(ud_e)
        print(
            f"   {h:3d}   {gir_p:6.3f} / {obs.gir_pct:5.3f}  {gir_e:+.3f}   "
            f"{ud_p:6.3f} / {obs.up_down_pct:5.3f}  {ud_e:+.3f}"
        )

    def rmse(xs):
        return (sum(x * x for x in xs) / len(xs)) ** 0.5

    print(f"\n   GIR      RMSE {rmse(gir_errs):.3f}   bias {sum(gir_errs)/len(gir_errs):+.3f}")
    print(f"   up&down  RMSE {rmse(ud_errs):.3f}   bias {sum(ud_errs)/len(ud_errs):+.3f}")

    corr_note = (
        "   Direction matters more than level here: if predicted GIR falls as\n"
        "   handicap rises, the rescaled long-game surface is tracking real skill."
    )
    print("\n" + corr_note)

    gir_preds = [implied_gir_pct(h, fits[h]) for h in BRACKETS]
    monotone = all(gir_preds[i] > gir_preds[i + 1] for i in range(len(gir_preds) - 1))
    print(f"   predicted GIR strictly decreasing with handicap: {monotone}")


def show_sensitivity() -> None:
    rule("3. Sensitivity — the one free assumption")
    print(f"   ASSUMED_FIRST_PUTT_FT is {ASSUMED_FIRST_PUTT_FT} ft. Re-solving across")
    print("   the plausible band, and reporting how far the putting scale moves:\n")

    print("   first putt   putt scale @0hcp   @25hcp   up&down RMSE")
    print("   ──────────   ────────────────   ──────   ────────────")
    for ft in (20.0, 24.0, 28.0, 32.0, 36.0, 40.0):
        fits = fit_all(first_putt_ft=ft)
        errs = [implied_up_down_pct(h, fits[h]) - OBSERVED[h].up_down_pct for h in BRACKETS]
        rmse = (sum(e * e for e in errs) / len(errs)) ** 0.5
        print(
            f"   {ft:8.0f}ft   {fits[0].putting_scale:16.4f}   "
            f"{fits[25].putting_scale:6.4f}   {rmse:12.3f}"
        )

    print("\n   A flat RMSE column means the holdout cannot discriminate between")
    print("   these values, and the constant needs measuring rather than assuming.")


def emit_tables() -> None:
    rule("Candidate replacement tables")
    fits = fit_all()
    print("_BASELINE_DATA = {")
    for h in BRACKETS:
        tables = rescaled_tables(h, fits[h])
        print(f"    {h}: {{")
        for lie, table in tables.items():
            entries = ", ".join(f"{d}: {v:.2f}" for d, v in sorted(table.items(), reverse=True))
            print(f'        "{lie}": {{{entries}}},')
        print("    },")
    print("}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--emit", action="store_true", help="print replacement tables")
    args = parser.parse_args()

    print("Baseline refit against measured aggregates")
    print("Anchors: Break X Golf, 3,788 rounds / 1,116 golfers")

    fits = show_fit()
    show_holdout(fits)
    show_sensitivity()

    if args.emit:
        emit_tables()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
