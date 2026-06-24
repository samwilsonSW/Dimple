#!/usr/bin/env python3
"""
Dimple Coach — Batch Test Questions
Runs 15 questions across different intents and logs responses.
"""
import requests
import json
import time
from datetime import datetime
from pathlib import Path

API_BASE = "http://localhost:8000"
RESULTS_DIR = Path(__file__).parent / "data" / "test_results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# ── Test Questions by Intent ──
TEST_CASES = [
    # --- player_29hcp (beginner, struggles) ---
    {"user_id": "player_29hcp", "question": "Why am I so bad at golf?", "intent": "frustration/general_help"},
    {"user_id": "player_29hcp", "question": "How do I stop topping my driver?", "intent": "specific_mechanic"},
    {"user_id": "player_29hcp", "question": "Why do I keep three-putting?", "intent": "putting_issue"},
    {"user_id": "player_29hcp", "question": "What should I practice this week?", "intent": "practice_plan"},
    {"user_id": "player_29hcp", "question": "Should I take lessons or just practice more?", "intent": "coaching_advice"},

    # --- player_13hcp (solid amateur) ---
    {"user_id": "player_13hcp", "question": "How do I make more birdie putts?", "intent": "scoring_improvement"},
    {"user_id": "player_13hcp", "question": "Why do I push my irons right?", "intent": "specific_mechanic"},
    {"user_id": "player_13hcp", "question": "What's the weakest part of my game?", "intent": "game_analysis"},
    {"user_id": "player_13hcp", "question": "How do I get from 13 to single digits?", "intent": "handicap_goal"},
    {"user_id": "player_13hcp", "question": "My bunker shots come out too low — what's wrong?", "intent": "specific_mechanic"},

    # --- player_3hcp (elite amateur) ---
    {"user_id": "player_3hcp", "question": "What should I work on to go pro?", "intent": "career_advice"},
    {"user_id": "player_3hcp", "question": "How do I handle pressure on tournament Sundays?", "intent": "mental_game"},
    {"user_id": "player_3hcp", "question": "My wedge distance control is inconsistent — any drills?", "intent": "specific_mechanic"},
    {"user_id": "player_3hcp", "question": "Am I losing strokes off the tee or on approach?", "intent": "strokes_gained"},
    {"user_id": "player_3hcp", "question": "What stats should I track to get to + handicap?", "intent": "analytics_advice"},
]


def ask_coach(user_id: str, question: str) -> dict:
    """Send a question to the coach endpoint."""
    r = requests.post(
        f"{API_BASE}/api/v1/coach/ask",
        json={"user_id": user_id, "question": question},
        timeout=120
    )
    r.raise_for_status()
    return r.json()


def run_tests():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = RESULTS_DIR / f"batch_test_{timestamp}.json"

    all_results = []
    total_cost = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    print(f"Running {len(TEST_CASES)} test questions...")
    print("=" * 60)

    for i, test in enumerate(TEST_CASES, 1):
        print(f"\n[{i}/{len(TEST_CASES)}] {test['user_id']} | {test['intent']}")
        print(f"Q: {test['question']}")

        start = time.time()
        try:
            response = ask_coach(test["user_id"], test["question"])
            elapsed = time.time() - start

            # Extract token usage from latest log file
            log_dir = Path(__file__).parent / "data" / "llm_responses"
            latest_log = None
            if log_dir.exists():
                logs = sorted(log_dir.glob("*.txt"), key=lambda f: f.stat().st_mtime, reverse=True)
                if logs:
                    latest_log = logs[0].read_text()

            result = {
                "test_case": test,
                "response": response,
                "elapsed_seconds": round(elapsed, 2),
                "timestamp": datetime.now().isoformat(),
            }

            # Show summary
            answer = response.get("answer", "")
            conf = response.get("confidence", "?")
            insights = response.get("key_insights", [])
            drills = response.get("drill_recommendations", [])

            print(f"Confidence: {conf}/5 | Time: {elapsed:.1f}s")
            print(f"Answer: {answer[:200]}{'...' if len(answer) > 200 else ''}")
            if insights:
                print(f"Insights: {len(insights)}")
            if drills:
                print(f"Drills: {len(drills)}")

            all_results.append(result)

        except Exception as e:
            print(f"ERROR: {e}")
            all_results.append({
                "test_case": test,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            })

        # Small delay to avoid rate limiting
        time.sleep(1)

    # Save results
    results_file.write_text(json.dumps(all_results, indent=2), encoding="utf-8")
    print(f"\n{'=' * 60}")
    print(f"Results saved to: {results_file}")
    print(f"Total questions: {len(TEST_CASES)}")
    print(f"Successful: {sum(1 for r in all_results if 'error' not in r)}")
    print(f"Failed: {sum(1 for r in all_results if 'error' in r)}")

    return all_results


if __name__ == "__main__":
    run_tests()
