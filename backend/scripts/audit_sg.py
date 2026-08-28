#!/usr/bin/env python
"""
Strokes-gained foundation audit.

Checks the SG stack against properties that must hold regardless of which model
you believe. Every check here is either arithmetic on the committed tables or a
comparison against measured aggregates in `app.core.empirical` — none of it
depends on the synthetic round generator.

    cd backend && uv run python scripts/audit_sg.py

Exits non-zero if any check fails, so it can be wired into the smoke test once
the failures below are fixed.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Callable, List, Optional

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))

from app.core.baselines import _BASELINE_DATA, get_baseline_for_handicap
from app.core.empirical import BRACKETS, OBSERVED, REFERENCE_COURSE, REFERENCE_PAR, REFERENCE_YARDS

# A first putt is realistically 20-40ft on average across a round. Outside that
# band, a putting table cannot reproduce observed putts-per-round from plausible
# approach play, so the table itself is wrong.
PLAUSIBLE_FIRST_PUTT_FT = (20, 40)

# Round-total tolerance. A baseline that misses observed scoring by more than a
# stroke makes every SG number derived from it wrong by that much.
ROUND_TOTAL_TOLERANCE = 1.0


@dataclass
class Check:
    name: str
    passed: bool
    detail: str


results: List[Check] = []


def report(name: str, passed: bool, detail: str = "") -> None:
    results.append(Check(name, passed, detail))


def rule(title: str) -> None:
    print(f"\n{'─' * 72}\n{title}\n{'─' * 72}")


# ──────────────────────────────────────────────────────────────────────────────
# 1. Round-total calibration
# ──────────────────────────────────────────────────────────────────────────────
# Expected strokes to hole out from the tee, summed over 18 holes, IS the
# expected score. If the baseline is calibrated to a handicap bracket, that sum
# must equal what golfers in that bracket actually shoot.
#
# This is the load-bearing check: SG is measured *against* this surface, so an
# error here is inherited by every category, every hole, every round.

def check_round_totals() -> None:
    rule("1. Round total vs. measured scoring")
    print(f"   Reference course: par {REFERENCE_PAR}, {REFERENCE_YARDS} yards\n")
    print("   hcp   baseline   observed      error   SG shown to an on-handicap round")
    print("   ───   ────────   ────────   ────────   ────────────────────────────────")

    worst = 0.0
    for h in BRACKETS:
        b = get_baseline_for_handicap(h)
        predicted = sum(b.strokes(hole.yards, "tee") for hole in REFERENCE_COURSE)
        observed = OBSERVED[h].avg_score
        err = predicted - observed
        worst = max(worst, abs(err))
        # SG_total = expected - actual. A player shooting their bracket average
        # is by definition average, so this should read 0.00.
        print(f"   {h:3d}   {predicted:8.2f}   {observed:8.1f}   {err:+8.2f}   {err:+.2f} strokes")

    ok = worst <= ROUND_TOTAL_TOLERANCE
    report(
        "round-total calibration",
        ok,
        f"worst bracket off by {worst:.2f} strokes (tolerance {ROUND_TOTAL_TOLERANCE})",
    )
    if not ok:
        print(
            "\n   A player shooting exactly their bracket average should see SG 0.00."
            "\n   The rightmost column is what they are shown instead, and it gets"
            "\n   worse as handicap rises — the players the coach exists to help."
        )


# ──────────────────────────────────────────────────────────────────────────────
# 2. Putting table plausibility
# ──────────────────────────────────────────────────────────────────────────────
# The green table claims expected putts from a distance. Invert it: what first
# putt would a player have to face, every hole, to produce their measured
# putts-per-round? If that distance is implausible, the table is too optimistic
# (or too pessimistic) by construction.

def check_putting_plausibility() -> None:
    rule("2. Putting table vs. measured putts per round")
    print("   hcp   putts/hole   implied avg first putt")
    print("   ───   ──────────   ──────────────────────")

    out_of_band: List[int] = []
    lo_ft, hi_ft = PLAUSIBLE_FIRST_PUTT_FT

    for h in BRACKETS:
        b = get_baseline_for_handicap(h)
        target = OBSERVED[h].avg_putts / 18.0
        implied: Optional[int] = next(
            (d for d in range(1, 121) if b.strokes(d, "green") >= target), None
        )
        flag = ""
        if implied is None or not (lo_ft <= implied <= hi_ft):
            out_of_band.append(h)
            flag = "  ← implausible"
        shown = f"{implied} ft" if implied is not None else "off the table"
        print(f"   {h:3d}   {target:10.2f}   {shown:>22}{flag}")

    report(
        "putting table plausibility",
        not out_of_band,
        f"brackets implying an unrealistic first putt: {out_of_band or 'none'}",
    )
    if out_of_band:
        print(
            f"\n   Plausible range is {lo_ft}-{hi_ft} ft. Higher means the table"
            "\n   under-counts putts, so SG putting reads systematically generous."
        )


# ──────────────────────────────────────────────────────────────────────────────
# 3. Structural invariants
# ──────────────────────────────────────────────────────────────────────────────

def check_monotonic_in_handicap() -> None:
    rule("3. Expected strokes rise with handicap, everywhere")
    bad = []
    for lie, table in _BASELINE_DATA[0].items():
        for d in sorted(table):
            vals = [get_baseline_for_handicap(h).strokes(d, lie) for h in BRACKETS]
            if any(vals[i] >= vals[i + 1] for i in range(len(vals) - 1)):
                bad.append((lie, d))
    print(f"   cells checked: {sum(len(t) for t in _BASELINE_DATA[0].values())}")
    print(f"   non-monotonic: {len(bad)}")
    report("monotonic in handicap", not bad, f"{len(bad)} violations")


def check_monotonic_in_distance() -> None:
    rule("4. Expected strokes rise with distance, within a lie")
    bad = []
    for h in BRACKETS:
        b = get_baseline_for_handicap(h)
        for lie, table in _BASELINE_DATA[h].items():
            ds = sorted(table)
            vals = [b.strokes(d, lie) for d in ds]
            for i in range(len(ds) - 1):
                if vals[i] >= vals[i + 1]:
                    bad.append((h, lie, ds[i]))
    print(f"   non-monotonic: {len(bad)}")
    report("monotonic in distance", not bad, f"{len(bad)} violations")


def check_lie_ordering() -> None:
    """From the same distance: fairway easier than rough easier than sand."""
    rule("5. Lie difficulty ordering (fairway < rough < sand)")
    bad = []
    for h in BRACKETS:
        b = get_baseline_for_handicap(h)
        for d in (50, 75, 100):
            f, r, s = (b.strokes(d, x) for x in ("fairway", "rough", "sand"))
            if not (f < r < s):
                bad.append((h, d, round(f, 2), round(r, 2), round(s, 2)))
    for row in bad:
        print(f"   hcp {row[0]:2d} @ {row[1]:3d}y: fairway={row[2]} rough={row[3]} sand={row[4]}")
    if not bad:
        print("   ok at 50/75/100 yards, all brackets")
    report("lie ordering", not bad, f"{len(bad)} violations")


# ──────────────────────────────────────────────────────────────────────────────
# 6. Dead arithmetic in the hole-level SG proxies
# ──────────────────────────────────────────────────────────────────────────────
# These are not style complaints. Both collapse to something other than what
# their surrounding comments claim, which is why the round-history chips
# attribute strokes to the wrong category.

def check_scorecard_proxies() -> None:
    rule("6. Hole-level SG proxies do what their comments claim")

    b = get_baseline_for_handicap(15)
    yardage = 420

    # calculate_sg_approach, par-4 branch: expected_drive + expected_approach.
    # Both terms contain baseline.strokes(150, "fairway") with opposite signs.
    drive = b.strokes(yardage, "tee") - b.strokes(150, "fairway")
    approach = b.strokes(150, "fairway") - b.strokes(20, "green")
    par4_branch = drive + approach
    par3_form = b.strokes(yardage, "tee") - b.strokes(20, "green")
    cancels = abs(par4_branch - par3_form) < 1e-9

    print(f"   par-4 branch          = {par4_branch:.4f}")
    print(f"   par-3 form            = {par3_form:.4f}")
    print(f"   150y fairway cancels  = {cancels}")
    if cancels:
        print("     → the par-4 branch is identical to the par-3 branch, and")
        print("       `drive_distance` above it is computed but never read.")
    report("par-4 approach branch is distinct", not cancels,
           "150y fairway terms cancel; drive_distance is dead code")

    # calculate_sg_putting, non-GIR branch: 1.0 + (strokes(15,"green") - 1.0)
    coded = 1.0 + (b.strokes(15, "green") - 1.0)
    bare = b.strokes(15, "green")
    noop = abs(coded - bare) < 1e-9
    print(f"\n   non-GIR expected putts = {coded:.4f}")
    print(f"   strokes(15, 'green')   = {bare:.4f}")
    print(f"   chip stroke charged    = {not noop}")
    if noop:
        print("     → `1.0 + (x - 1.0)` is a no-op. The comment says it charges a")
        print("       chip stroke; it does not. That stroke lands in score-putts,")
        print("       so short game is attributed to the approach chip.")
    report("non-GIR putting charges the chip", not noop,
           "1.0 + (x - 1.0) cancels; short game leaks into SG approach")


# ──────────────────────────────────────────────────────────────────────────────

def check_category_coverage() -> None:
    """
    Where the skill actually lives, versus where the app reports it.

    Not a property of the tables — a property of the product. It is the reason
    the two blank chips matter more than the two populated ones.
    """
    rule("7. Reported categories vs. where the skill gap lives")

    lo, hi = OBSERVED[BRACKETS[0]], OBSERVED[BRACKETS[-1]]
    gap = hi.avg_score - lo.avg_score
    putt_gap = hi.avg_putts - lo.avg_putts
    long_gap = (hi.avg_score - hi.avg_putts) - (lo.avg_score - lo.avg_putts)

    print(f"   scratch → {BRACKETS[-1]} handicap: {gap:.1f} strokes of skill\n")
    print(f"   putting        {putt_gap:5.1f} strokes  ({putt_gap / gap * 100:4.1f}%)   reported as chip 'G'")
    print(f"   tee-to-green   {long_gap:5.1f} strokes  ({long_gap / gap * 100:4.1f}%)   reported as chip 'A'")
    print()
    print("   Driving and short game are the majority of that tee-to-green share,")
    print("   and are the two chips currently rendering blank. The app resolves")
    print(f"   {long_gap / gap * 100:.0f}% of amateur skill variation into a single undifferentiated")
    print("   number, and that number is also absorbing the un-charged chip stroke")
    print("   from check 6.")

    # Informational: no threshold to fail against, but it must stay visible.
    report("category coverage", True, f"tee-to-green carries {long_gap / gap * 100:.0f}% of skill gap")


def main() -> int:
    print("Strokes-gained foundation audit")
    print("Anchors: Break X Golf, 3,788 rounds / 1,116 golfers")

    checks: List[Callable[[], None]] = [
        check_round_totals,
        check_putting_plausibility,
        check_monotonic_in_handicap,
        check_monotonic_in_distance,
        check_lie_ordering,
        check_scorecard_proxies,
        check_category_coverage,
    ]
    for c in checks:
        c()

    rule("Summary")
    failed = [c for c in results if not c.passed]
    for c in results:
        mark = "PASS" if c.passed else "FAIL"
        print(f"   [{mark}] {c.name:38} {c.detail}")

    print()
    if failed:
        print(f"   {len(failed)} of {len(results)} checks failing.")
        return 1
    print(f"   All {len(results)} checks passing.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
