#!/usr/bin/env python3
"""
Generate 60 test rounds (6 handicaps × 10) with LLM-generated reflections.

Usage:
    # Generate and save to file
    python -m scripts.generate_test_dataset --output data/test_rounds.jsonl

    # Generate and ingest directly to API
    python -m scripts.generate_test_dataset --ingest --api-url http://localhost:8000

    # Generate single round for testing
    python -m scripts.generate_test_dataset --generate 15 --output single_round.json

Requirements:
    - MOONSHOT_API_KEY in backend/.env (real key, not placeholder)
    - Server running if using --ingest
"""

import argparse
import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.generator import generate_round
from app.core.reflection_generator import generate_reflection


# ── Config ──
HANDICAPS = [0, 5, 10, 15, 20, 25]
ROUNDS_PER_HANDICAP = 10
COURSE_NAMES = [
    "Pine Valley Golf Club",
    "Augusta National Golf Club",
    "Pebble Beach Golf Links",
    "TPC Sawgrass",
    "Oakmont Country Club",
    "Bethpage Black",
    "Torrey Pines South",
    "Bandon Dunes",
    "Whistling Straits",
    "Shinnecock Hills",
]


def generate_single(handicap: float) -> Dict[str, Any]:
    """Generate one round with reflection."""
    round_data = generate_round(
        handicap=handicap,
        user_id=f"test_player_hcp{int(handicap)}",
    )
    reflection = generate_reflection(round_data, temperature=1.0)
    round_data["reflection"] = reflection
    round_data.pop("_meta", None)
    return round_data


def generate_dataset() -> List[Dict[str, Any]]:
    """Generate 60 rounds with reflections."""
    all_rounds = []
    total = len(HANDICAPS) * ROUNDS_PER_HANDICAP

    print(f"Generating {total} test rounds...")
    print(f"Handicaps: {HANDICAPS}")
    print(f"Rounds per handicap: {ROUNDS_PER_HANDICAP}")
    print("-" * 50)

    count = 0
    for hcp in HANDICAPS:
        print(f"\n--- Handicap {hcp} ---")
        for i in range(ROUNDS_PER_HANDICAP):
            count += 1
            course = COURSE_NAMES[i % len(COURSE_NAMES)]
            days_ago = (count * 3) % 60
            round_date = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")

            try:
                round_data = generate_round(
                    handicap=hcp,
                    user_id=f"test_player_hcp{hcp}",
                    course_name=course,
                    round_date=round_date,
                )

                reflection = generate_reflection(round_data, temperature=1.0)
                round_data["reflection"] = reflection
                round_data.pop("_meta", None)

                score = sum(s["strokes_taken"] for s in round_data["shots"])
                all_rounds.append(round_data)

                print(f"  [{count:3d}/{total}] {hcp}hcp | {course[:25]:25s} | Score: {score:3d}")
                print(f"         Reflection: {reflection[:70]}...")

            except Exception as e:
                print(f"  [{count:3d}/{total}] ❌ Failed: {e}")

            time.sleep(0.5)

    print(f"\n✅ Generated {len(all_rounds)}/{total} rounds")
    return all_rounds


def save_to_jsonl(rounds: List[Dict[str, Any]], output_path: str):
    """Save rounds to JSONL file."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w") as f:
        for r in rounds:
            f.write(json.dumps(r) + "\n")

    print(f"💾 Saved to {path}")


def save_to_json(round_data: Dict[str, Any], output_path: str):
    """Save single round to JSON file."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w") as f:
        json.dump(round_data, f, indent=2)

    print(f"💾 Saved to {path}")


def ingest_to_api(rounds: List[Dict[str, Any]], api_url: str):
    """POST rounds to the ingestion endpoint."""
    import requests

    url = f"{api_url.rstrip('/')}/api/v1/rounds"
    success = 0
    failed = 0

    print(f"\n📡 Ingesting to {url}...")
    for i, r in enumerate(rounds, 1):
        try:
            payload = {
                "user_id": r["user_id"],
                "round_date": r["round_date"],
                "course": r["course"],
                "handicap_index": r["handicap_index"],
                "shots": r["shots"],
                "reflection": r.get("reflection"),
            }
            resp = requests.post(url, json=payload, timeout=30)
            if resp.status_code == 200:
                success += 1
                print(f"  [{i:3d}/{len(rounds)}] ✅ {r['user_id']} | {r['round_date']}")
            else:
                failed += 1
                print(f"  [{i:3d}/{len(rounds)}] ❌ HTTP {resp.status_code}: {resp.text[:100]}")
        except Exception as e:
            failed += 1
            print(f"  [{i:3d}/{len(rounds)}] ❌ Error: {e}")

    print(f"\n📊 Ingested: {success} success, {failed} failed")


def main():
    parser = argparse.ArgumentParser(description="Generate test rounds with reflections")
    parser.add_argument("--output", "-o", help="Save to JSONL/JSON file")
    parser.add_argument("--ingest", action="store_true", help="POST to API")
    parser.add_argument("--api-url", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--generate", type=float, metavar="HCP", help="Generate single round for handicap")
    args = parser.parse_args()

    if args.generate is not None:
        # Single round mode
        print(f"Generating single round for {args.generate}hcp...")
        round_data = generate_single(args.generate)
        score = sum(s["strokes_taken"] for s in round_data["shots"])
        print(f"\nScore: {score}")
        print(f"Reflection: {round_data['reflection']}")

        if args.output:
            save_to_json(round_data, args.output)
        return

    # Full dataset mode
    rounds = generate_dataset()

    if args.output:
        save_to_jsonl(rounds, args.output)

    if args.ingest:
        ingest_to_api(rounds, args.api_url)


if __name__ == "__main__":
    main()
