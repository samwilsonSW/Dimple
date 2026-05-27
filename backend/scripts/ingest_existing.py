#!/usr/bin/env python3
"""Ingest existing rounds from JSONL file."""
import json
import sys
from pathlib import Path
import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

API_URL = "http://localhost:8000"
ROUNDS_FILE = Path(__file__).parent.parent.parent / "data" / "test_rounds.jsonl"


def ingest_rounds(filepath: str, api_url: str = API_URL):
    path = Path(filepath)
    if not path.exists():
        print(f"❌ File not found: {path}")
        return

    url = f"{api_url.rstrip('/')}/api/v1/rounds"
    success = 0
    failed = 0

    with open(path) as f:
        rounds = [json.loads(line) for line in f if line.strip()]

    print(f"📡 Ingesting {len(rounds)} rounds to {url}...")

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
                print(f"  [{i:3d}/{len(rounds)}] ✅ {r['user_id']} | {r['round_date']} | Score: {sum(s['strokes_taken'] for s in r['shots'])}")
            else:
                failed += 1
                print(f"  [{i:3d}/{len(rounds)}] ❌ HTTP {resp.status_code}: {resp.text[:100]}")
        except Exception as e:
            failed += 1
            print(f"  [{i:3d}/{len(rounds)}] ❌ Error: {e}")

    print(f"\n📊 Done: {success} success, {failed} failed")


if __name__ == "__main__":
    filepath = sys.argv[1] if len(sys.argv) > 1 else str(ROUNDS_FILE)
    api_url = sys.argv[2] if len(sys.argv) > 2 else API_URL
    ingest_rounds(filepath, api_url)
