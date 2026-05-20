#!/usr/bin/env python3
"""
Dimple CLI Test Tool — Interactive terminal for testing the API.

Usage:
    python test_cli.py

Commands:
    /ingest <file>          Ingest a round JSON file
    /user <user_id>         Set active player context
    /health                 Check API health
    /list                   List available test round files
    /help                   Show help
    /quit, /exit, /q        Exit the CLI

    Anything else           Ask the coach (uses active /user context)
"""
import sys
import json
import requests
from pathlib import Path

API_BASE = "http://localhost:8000"
DATA_DIR = Path(__file__).parent / "data" / "rounds"

# ── Session State ──
_current_user: str | None = None


def print_banner():
    print("""
╔══════════════════════════════════════════╗
║       Dimple API Test CLI v0.2           ║
║  Ingest rounds · Ask the AI Coach        ║
╚══════════════════════════════════════════╝
""")
    print("Type '/help' for commands, '/quit' to exit.")
    print("Just type your question to ask the coach.\n")


def cmd_help():
    print("""
Commands (prefix with /):
  /ingest <file>       Ingest a round JSON file
  /user <user_id>      Set active player context
  /health              Check if API is running
  /list                Show available test round files
  /clear               Clear the screen
  /help                Show this help
  /quit /exit /q       Exit

Examples:
  /user player_29hcp
  How do I stop pushing my 6 iron?
  /ingest round_13hcp.json
  /user player_3hcp
  What should I work on to go pro?
""")


def cmd_health():
    try:
        r = requests.get(f"{API_BASE}/health", timeout=5)
        print(f"✅ API Status: {r.json()}")
    except Exception as e:
        print(f"❌ API unreachable: {e}")
        print("   Make sure the server is running: python run.py")


def cmd_user(user_id: str):
    global _current_user
    _current_user = user_id
    print(f"👤 Active player set to: {user_id}")


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


def cmd_ingest(filename: str):
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


def cmd_ask(question: str):
    global _current_user
    if not _current_user:
        print("❌ No active player set. Use: /user <player_id>")
        return

    print(f"🤔 Asking coach about: {question}")
    try:
        r = requests.post(
            f"{API_BASE}/api/v1/coach/ask",
            json={"user_id": _current_user, "question": question},
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

        # ── Slash commands ──
        if line.startswith("/"):
            parts = line[1:].split()
            if not parts:
                continue
            cmd = parts[0].lower()

            if cmd in ("quit", "exit", "q"):
                print("👋 Goodbye!")
                break

            elif cmd == "help":
                cmd_help()

            elif cmd == "health":
                cmd_health()

            elif cmd == "user":
                if len(parts) < 2:
                    print("Usage: /user <player_id>")
                    continue
                cmd_user(parts[1])

            elif cmd == "list":
                cmd_list()

            elif cmd == "clear":
                print("\n" * 50)

            elif cmd == "ingest":
                if len(parts) < 2:
                    print("Usage: /ingest <filename>")
                    continue
                cmd_ingest(parts[1])

            else:
                print(f"Unknown command: /{cmd}")
                print("Type '/help' for available commands.")

        # ── Plain text = ask the coach ──
        else:
            cmd_ask(line)

        print()


if __name__ == "__main__":
    main()
