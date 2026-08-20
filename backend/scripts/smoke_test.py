#!/usr/bin/env python3
"""The verification gate. Run before reporting any backend work complete.

Tiers, cheapest first — each flag adds to the previous:

    python scripts/smoke_test.py                  # offline. no creds, no server, no writes
    python scripts/smoke_test.py --live           # read-only calls against a running API
    python scripts/smoke_test.py --live --write   # also creates a round (writes to Supabase)
    python scripts/smoke_test.py --live --coach   # also asks the coach (spends LLM money)

The default tier needs only fastapi + pydantic + pydantic-settings and makes no
network calls. It is the tier an agent with no credentials can always run.

Options:
    --url URL     API base (default $DIMPLE_API_URL or http://localhost:8000)
    --user-id ID  user for live round/coach checks (default $DIMPLE_SMOKE_USER_ID)

Exit code is 0 only if every check in the selected tiers passed.
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.resolve()))

import export_openapi

DEFAULT_URL = os.environ.get("DIMPLE_API_URL", "http://localhost:8000")

_results: list[tuple[bool, str, str]] = []


def check(name: str, ok: bool, detail: str = "") -> bool:
    _results.append((ok, name, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}{f'  — {detail}' if detail else ''}")
    return ok


def section(title: str) -> None:
    print(f"\n{title}")


def request(url: str, method: str = "GET", body: dict | None = None, timeout: int = 30):
    """Return (status, parsed_json_or_text). Never raises for HTTP errors."""
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if data else {}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode()
            try:
                return response.status, json.loads(raw)
            except json.JSONDecodeError:
                return response.status, raw
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, raw
    except (urllib.error.URLError, TimeoutError) as exc:
        return None, str(exc)


# ── Tier 1: offline ───────────────────────────────────────────────────────────

def tier_offline() -> None:
    section("offline — contract and model invariants")

    try:
        rendered = export_openapi.render(export_openapi.build_schema())
    except Exception as exc:  # noqa: BLE001 — surface any import failure verbatim
        check("app imports", False, f"{type(exc).__name__}: {exc}")
        return
    check("app imports", True)

    out = export_openapi.OUTPUT
    if not out.exists():
        check("docs/openapi.json exists", False, "run scripts/export_openapi.py")
    else:
        check(
            "docs/openapi.json current",
            out.read_text() == rendered,
            "" if out.read_text() == rendered else "stale — run scripts/export_openapi.py",
        )

    from pydantic import ValidationError

    from app.models.round import ManualCourse, RoundPayload

    def rejects(name: str, build) -> None:
        try:
            build()
            check(name, False, "expected validation error, got none")
        except ValidationError:
            check(name, True)

    # Rules documented in docs/API_CONTRACT.md — these are the contract.
    rejects(
        "ManualCourse rejects par_values count mismatch",
        lambda: ManualCourse(holes=18, par_values=[4, 4, 4]),
    )
    rejects(
        "ManualCourse rejects par outside 3-5",
        lambda: ManualCourse(holes=9, par_values=[4, 4, 4, 4, 4, 4, 4, 4, 7]),
    )
    try:
        ManualCourse(holes=9, par_values=[4] * 9)
        check("ManualCourse accepts a valid 9-hole course", True)
    except ValidationError as exc:
        check("ManualCourse accepts a valid 9-hole course", False, str(exc))

    base = {
        "user_id": "550e8400-e29b-41d4-a716-446655440000",
        "round_date": "2026-01-01",
        "course": {"name": "Smoke Test GC"},
        "handicap_index": 15.0,
    }
    manual = {"holes": 9, "par_values": [4] * 9}
    rejects(
        "RoundPayload rejects manual_course + course_id",
        lambda: RoundPayload(**base, manual_course=manual, course_id="21027"),
    )
    rejects(
        "RoundPayload rejects manual_course + shots",
        lambda: RoundPayload(
            **base,
            manual_course=manual,
            shots=[{"hole": 1, "shot_number": 1, "club": "D", "before_distance_yards": 400,
                    "before_lie": "TEE", "after_distance_yards": 150, "after_lie": "FW"}],
        ),
    )


# ── Tier 2: live, read-only ───────────────────────────────────────────────────

def tier_live(url: str, user_id: str | None) -> None:
    section(f"live — read-only against {url}")

    status, payload = request(f"{url}/health", timeout=10)
    if status is None:
        check("GET /health", False, f"unreachable: {payload}")
        print("\n  server unreachable — skipping remaining live checks")
        print("  start it with:  cd backend && python run.py")
        return
    check("GET /health", status == 200 and payload == {"status": "ok"}, f"{status} {payload}")

    status, payload = request(f"{url}/api/v1/courses/search?q=Pinehurst&limit=3")
    check("GET /api/v1/courses/search", status == 200 and isinstance(payload, list),
          f"status {status}")

    status, payload = request(f"{url}/api/v1/rounds?user_id={user_id or ''}&limit=1")
    check("GET /api/v1/rounds", status in (200, 422), f"status {status}")

    # The contract says a missing user_id is a 422, not a 500.
    status, _ = request(f"{url}/api/v1/coach/conversations")
    check("GET /coach/conversations without user_id → 422", status == 422, f"status {status}")


# ── Tier 3: writes ────────────────────────────────────────────────────────────

def tier_write(url: str, user_id: str) -> int | None:
    section("write — creates a real round in Supabase")

    payload = {
        "user_id": user_id,
        "round_date": time.strftime("%Y-%m-%d"),
        "course": {"name": "Smoke Test GC", "city": "Lubbock", "state": "TX"},
        "handicap_index": 15.0,
        "manual_course": {"holes": 9, "par_values": [4, 3, 5, 4, 4, 3, 5, 4, 4]},
        "hole_data": [
            {"hole_number": i + 1, "par": p, "score": p + 1, "putts": 2}
            for i, p in enumerate([4, 3, 5, 4, 4, 3, 5, 4, 4])
        ],
        "total_score": 45,
        "total_putts": 18,
    }
    status, body = request(f"{url}/api/v1/rounds", "POST", payload, timeout=60)
    ok = status == 200 and isinstance(body, dict) and "round_stats" in body
    check("POST /api/v1/rounds (manual course)", ok, f"status {status}")

    bad = dict(payload, course_id="21027")
    status, _ = request(f"{url}/api/v1/rounds", "POST", bad, timeout=60)
    check("POST /api/v1/rounds rejects manual_course + course_id → 422", status == 422,
          f"status {status}")

    return body.get("round_id") if ok and isinstance(body, dict) else None


# ── Tier 4: coach ─────────────────────────────────────────────────────────────

def tier_coach(url: str, user_id: str) -> None:
    section("coach — spends LLM money, measures latency")

    started = time.time()
    status, body = request(
        f"{url}/api/v1/coach/chat", "POST",
        {"user_id": user_id, "message": "What should I work on?"},
        timeout=300,
    )
    elapsed = time.time() - started

    ok = status == 200 and isinstance(body, dict)
    check("POST /api/v1/coach/chat", ok, f"status {status}")
    if not ok:
        return

    for field in ("conversation_id", "answer", "confidence", "drill_recommendations"):
        check(f"response has {field}", field in body)

    print(f"\n  latency: {elapsed:.1f}s")
    if elapsed > 60:
        print("  NOTE: over 60s. Coach latency is a known UX problem — see docs/API_CONTRACT.md.")
        print("        Adding round-trips here is a taste decision, not an implementation detail.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--live", action="store_true", help="call a running API (read-only)")
    parser.add_argument("--write", action="store_true", help="also create a round (implies --live)")
    parser.add_argument("--coach", action="store_true", help="also ask the coach (implies --live)")
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--user-id", default=os.environ.get("DIMPLE_SMOKE_USER_ID"))
    args = parser.parse_args()

    live = args.live or args.write or args.coach

    tier_offline()

    if live:
        tier_live(args.url, args.user_id)
        needs_user = args.write or args.coach
        if needs_user and not args.user_id:
            section("skipped")
            print("  --write/--coach need a user: pass --user-id or set DIMPLE_SMOKE_USER_ID")
        elif needs_user:
            if args.write:
                tier_write(args.url, args.user_id)
            if args.coach:
                tier_coach(args.url, args.user_id)
    else:
        print("\n  offline tier only. add --live to exercise a running server.")

    failed = [name for ok, name, _ in _results if not ok]
    print(f"\n{len(_results) - len(failed)}/{len(_results)} passed")
    if failed:
        print("failed: " + ", ".join(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
