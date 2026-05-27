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
    /generate <hcp> [n]     Generate n rounds for handicap (default: 1)
    /generate-all           Generate full test dataset (6 hcp x 10 rounds)
    /save-last <file>       Save last generated round(s) to file
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
_last_generated: list = []  # Store last generated round(s)


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
  /generate <hcp> [n]  Generate n rounds for handicap (with reflection)
  /generate-all        Generate full dataset: 6 hcp x 10 = 60 rounds
  /save-last <file>    Save last generated round(s) to JSON file
  /clear               Clear the screen
  /help                Show this help
  /quit /exit /q       Exit

Examples:
  /user player_29hcp
  How do I stop pushing my 6 iron?
  /ingest round_13hcp.json
  /generate 15         Generate one 15hcp round with reflection
  /generate 10 5       Generate five 10hcp rounds
  /generate-all        Generate full 60-round test dataset
  /save-last my_round.json
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


def cmd_generate(handicap: str, count: str = "1"):
    """Generate round(s) with LLM reflection."""
    global _last_generated
    _last_generated = []

    try:
        hcp = float(handicap)
        n = int(count)
    except ValueError:
        print("Usage: /generate <handicap> [count]")
        print("  Example: /generate 15")
        print("  Example: /generate 10 5")
        return

    print(f"🎲 Generating {n} round(s) for {hcp}hcp...")
    

    # Import here to avoid startup delay
    try:
        sys.path.insert(0, str(Path(__file__).parent / "backend"))
        from backend.app.core.generator import generate_round
        from backend.app.core.reflection_generator import generate_reflection
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("   Make sure you're running from the Dimple directory")
        return

    for i in range(n):
        try:
            round_data = generate_round(
                handicap=hcp,
                user_id=f"test_player_hcp{int(hcp)}",
            )

            # Generate reflection
            print(f"   [{i+1}/{n}] Generating reflection...", end=" ", flush=True)
            reflection = generate_reflection(round_data, temperature=1.0)
            round_data["reflection"] = reflection

            # Calculate score
            score = sum(s["strokes_taken"] for s in round_data["shots"])

            # Store (clean up internal meta)
            round_data.pop("_meta", None)
            _last_generated.append(round_data)

            print(f"✅ Score: {score}")
            print(f"   Reflection: {reflection[:80]}...")

        except Exception as e:
            print(f"❌ Failed: {e}")

    print(f"\n📦 Generated {len(_last_generated)} round(s)")
    print(f"   Use /save-last <file.json> to save")


def cmd_generate_all():
    """Generate full 60-round test dataset."""
    global _last_generated
    _last_generated = []

    print("🎲 Generating full test dataset (6 hcp x 10 = 60 rounds)...")
    print("   This will take ~2-3 minutes and requires MOONSHOT_API_KEY")
    print()

    try:
        sys.path.insert(0, str(Path(__file__).parent / "backend"))
        from backend.app.core.generator import generate_round
        from backend.app.core.reflection_generator import generate_reflection
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return

    handicaps = [0, 5, 10, 15, 20, 25]
    total = len(handicaps) * 10
    count = 0

    for hcp in handicaps:
        print(f"\n--- Handicap {hcp} ---")
        for i in range(10):
            count += 1
            try:
                round_data = generate_round(
                    handicap=hcp,
                    user_id=f"test_player_hcp{hcp}",
                )
                reflection = generate_reflection(round_data, temperature=1.0)
                round_data["reflection"] = reflection
                round_data.pop("_meta", None)

                score = sum(s["strokes_taken"] for s in round_data["shots"])
                _last_generated.append(round_data)

                print(f"  [{count:3d}/{total}] Score: {score:3d} | {reflection[:60]}...")

            except Exception as e:
                print(f"  [{count:3d}/{total}] ❌ Failed: {e}")

    print(f"\n📦 Generated {len(_last_generated)}/{total} rounds")
    print(f"   Use /save-last <file.jsonl> to save")


def cmd_save_last(filename: str):
    """Save last generated round(s) to file."""
    global _last_generated
    if not _last_generated:
        print("❌ No rounds generated yet. Use /generate or /generate-all first.")
        return

    filepath = Path(filename)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    # JSONL for multiple, JSON for single
    if len(_last_generated) == 1:
        with open(filepath, "w") as f:
            json.dump(_last_generated[0], f, indent=2)
    else:
        with open(filepath, "w") as f:
            for r in _last_generated:
                f.write(json.dumps(r) + "\n")

    print(f"💾 Saved {len(_last_generated)} round(s) to {filepath}")


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

            elif cmd == "generate":
                if len(parts) < 2:
                    print("Usage: /generate <handicap> [count]")
                    continue
                cmd_generate(parts[1], parts[2] if len(parts) > 2 else "1")

            elif cmd == "generate-all":
                cmd_generate_all()

            elif cmd == "save-last":
                if len(parts) < 2:
                    print("Usage: /save-last <filename>")
                    continue
                cmd_save_last(parts[1])

            else:
                print(f"Unknown command: /{cmd}")
                print("Type '/help' for available commands.")

        # ── Plain text = ask the coach ──
        else:
            cmd_ask(line)

        print()


if __name__ == "__main__":
    main()
