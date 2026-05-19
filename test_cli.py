#!/usr/bin/env python3
"""
Dimple CLI Test Tool — Interactive terminal for testing the API.

Usage:
    python test_cli.py

Commands:
    ingest <file>          Ingest a round JSON file
    ask <user_id> <question>   Ask the coach a question
    health                 Check API health
    list                   List available test round files
    quit / exit            Exit the CLI
"""
import sys
import json
import requests
from pathlib import Path

API_BASE = "http://localhost:8000"
DATA_DIR = Path(__file__).parent / "data" / "rounds"


def print_banner():
    print("""
╔══════════════════════════════════════════╗
║       Dimple API Test CLI v0.1           ║
║  Ingest rounds · Ask the AI Coach        ║
╚══════════════════════════════════════════╝
""")
    print("Type 'help' for commands, 'quit' to exit.\n")


def cmd_help():
    print("""
Commands:
  ingest <file>              Ingest a round JSON file
  ask <user_id> <question>   Ask the coach (use quotes for questions)
  health                     Check if API is running
  list                       Show available test round files
  clear                      Clear the screen
  help                       Show this help
  quit / exit                Exit

Examples:
  ingest round_13hcp.json
  ask player_29hcp "Why am I so bad at golf?"
  ask player_3hcp "How do I hit more fairways?"
""")


def cmd_health():
    try:
        r = requests.get(f"{API_BASE}/health", timeout=5)
        print(f"✅ API Status: {r.json()}")
    except Exception as e:
        print(f"❌ API unreachable: {e}")
        print("   Make sure the server is running: python run.py")


def cmd_list():
    if not DATA_DIR.exists():
        print(f"❌ Data directory not found: {DATA_DIR}")
        return
    files = sorted(DATA_DIR.glob("*.json"))
    if not files:
        print("No round files found.")
        return
    print("Available round files:")
    for f in files:
        size = f.stat().st_size
        print(f"  • {f.name:<20} ({size:,} bytes)")


def cmd_ingest(filename):
    # Resolve file path
    filepath = Path(filename)
    if not filepath.exists():
        filepath = DATA_DIR / filename
    if not filepath.exists():
        print(f"❌ File not found: {filename}")
        print(f"   Tried: {filepath}")
        return

    print(f"📤 Ingesting {filepath.name}...")
    try:
        with open(filepath) as f:
            data = json.load(f)
        r = requests.post(
            f"{API_BASE}/api/v1/rounds",
            json=data,
            timeout=30
        )
        if r.status_code == 200:
            result = r.json()
            print(f"✅ Round ingested!")
            print(f"   Round ID: {result.get('round_id')}")
            print(f"   Shots: {result.get('shots_ingested')}")
        else:
            print(f"❌ Error {r.status_code}: {r.text}")
    except Exception as e:
        print(f"❌ Failed: {e}")


def cmd_ask(user_id, question):
    print(f"🤔 Asking coach about: {question}")
    try:
        r = requests.post(
            f"{API_BASE}/api/v1/coach/ask",
            json={"user_id": user_id, "question": question},
            timeout=60
        )
        if r.status_code == 200:
            result = r.json()

            # ── Main Answer ──
            print(f"\n🏌️ Coach says:\n{'─' * 50}")
            print(result.get("answer", "No response"))
            print(f"{'─' * 50}")

            # ── Confidence ──
            confidence = result.get("confidence", 3)
            conf_emoji = "🔥" if confidence >= 4 else "⚡" if confidence == 3 else "🤔"
            print(f"\n{conf_emoji} Confidence: {confidence}/5")

            # ── Key Insights ──
            insights = result.get("key_insights", [])
            if insights:
                print(f"\n💡 Key Insights:")
                for insight in insights:
                    print(f"   • {insight}")

            # ── Drill Recommendations ──
            drills = result.get("drill_recommendations", [])
            if drills:
                print(f"\n🎯 Recommended Drills:")
                for d in drills:
                    priority = d.get("priority", 1)
                    focus = d.get("focus_area", "")
                    name = d.get("drill_name", "")
                    instructions = d.get("instructions", "")
                    outcome = d.get("expected_outcome", "")
                    print(f"\n   #{priority} — {focus}")
                    print(f"   Drill: {name}")
                    print(f"   How: {instructions}")
                    if outcome:
                        print(f"   Goal: {outcome}")

            # ── Context (retrieved shots) ──
            context = result.get("context", [])
            if context:
                print(f"\n📊 Based on {len(context)} retrieved shots:")
                for i, shot in enumerate(context, 1):
                    print(f"   {i}. {shot.get('narrative', 'N/A')[:60]}...")
        else:
            print(f"❌ Error {r.status_code}: {r.text}")
    except Exception as e:
        print(f"❌ Failed: {e}")


def main():
    print_banner()
    cmd_health()
    print()

    while True:
        try:
            line = input("dimple> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 Goodbye!")
            break

        if not line:
            continue

        parts = line.split()
        cmd = parts[0].lower()

        if cmd in ("quit", "exit", "q"):
            print("👋 Goodbye!")
            break

        elif cmd == "help":
            cmd_help()

        elif cmd == "health":
            cmd_health()

        elif cmd == "list":
            cmd_list()

        elif cmd == "clear":
            print("\n" * 50)

        elif cmd == "ingest":
            if len(parts) < 2:
                print("Usage: ingest <filename>")
                continue
            cmd_ingest(parts[1])

        elif cmd == "ask":
            if len(parts) < 3:
                print("Usage: ask <user_id> \"<question>\"")
                continue
            user_id = parts[1]
            # Join remaining parts as question (handles spaces)
            question_start = line.find(user_id) + len(user_id)
            question = line[question_start:].strip().strip('"\'')
            if not question:
                print("Usage: ask <user_id> \"<question>\"")
                continue
            cmd_ask(user_id, question)

        else:
            print(f"Unknown command: {cmd}")
            print("Type 'help' for available commands.")

        print()


if __name__ == "__main__":
    main()
