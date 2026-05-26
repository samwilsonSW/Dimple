#!/usr/bin/env python3
"""
Dimple Round Generation Test Tool

Generates a synthetic round for a given handicap, displays the round summary,
shows the total score, and prompts for a human-written reflection.
Then outputs the exact coach prompt that would be sent to the LLM.

Usage:
    python test_round_generation.py                    # Interactive mode
    python test_round_generation.py 15                 # Auto mode: handicap=15
    python test_round_generation.py 15 "reflection"    # Auto mode with reflection
    python test_round_generation.py 15 "reflection" "question"  # Full auto

No LLM calls are made — this is purely for inspecting the prompt.
"""

import sys
import json
from pathlib import Path

# Add backend to path so we can import app modules
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from app.core.generator import generate_round
from app.core.baselines import get_baseline_for_handicap, get_category


def print_banner():
    print("""
╔═══════════════════════════════════════════════════════════════╗
║     Dimple Round Generation & Prompt Preview Tool             ║
║  Generate a round → Write reflection → See coach prompt       ║
╚═══════════════════════════════════════════════════════════════╝
""")


def get_handicap_input() -> float:
    while True:
        try:
            h = input("Enter handicap (0-25): ").strip()
            handicap = float(h)
            if 0 <= handicap <= 25:
                return handicap
            print("Handicap must be between 0 and 25.")
        except ValueError:
            print("Please enter a valid number.")


def display_round_summary(round_data: dict):
    print("\n" + "=" * 60)
    print("📊 ROUND SUMMARY")
    print("=" * 60)
    print(f"Player:     {round_data['user_id']}")
    print(f"Handicap:   {round_data['handicap_index']}")
    print(f"Course:     {round_data['course']['name']}")
    print(f"Par:        {round_data['course']['par']}")
    total_score = round_data['_meta']['total_score']
    print(f"Total Score: {total_score} ({total_score - round_data['course']['par']:+d})")
    print(f"Total Shots: {len(round_data['shots'])}")
    print("=" * 60)


def display_shots(round_data: dict):
    print("\n🏌️  SHOT-BY-SHOT:")
    print("-" * 60)
    current_hole = 0
    for shot in round_data['shots']:
        if shot['hole_number'] != current_hole:
            current_hole = shot['hole_number']
            print(f"\n  Hole {current_hole}:")
        
        lie_map = {"T": "tee", "F": "fairway", "R": "rough", "B": "bunker", "G": "green"}
        club_map = {
            "D": "Driver", "3W": "3-wood", "5W": "5-wood", "H": "Hybrid",
            "3": "3-iron", "4": "4-iron", "5": "5-iron", "6": "6-iron",
            "7": "7-iron", "8": "8-iron", "9": "9-iron",
            "G": "Gap wedge", "L": "Lob wedge", "P": "Putter"
        }
        
        before_lie = lie_map.get(shot['before_lie'], shot['before_lie'])
        club = club_map.get(shot['club'], shot['club'])
        after_lie = shot['after_lie']
        if after_lie == "HOLE":
            after_str = "holed"
        elif after_lie == "G" and shot['before_lie'] == "G":
            after_str = "missed"
        elif after_lie == "G":
            after_str = "on green"
        elif after_lie in lie_map:
            after_str = f"{shot['after_distance_yards']}y to {lie_map[after_lie]}"
        else:
            after_str = f"{shot['after_distance_yards']}y"
        
        strokes = f" ({shot['strokes_taken']} strokes)" if shot['strokes_taken'] > 1 else ""
        print(f"    Shot {shot['shot_number']}: {club} from {shot['before_distance_yards']}y ({before_lie}) → {after_str}{strokes}")


def calculate_sg_summary(round_data: dict) -> str:
    """Calculate SG category totals for the generated round."""
    baseline = get_baseline_for_handicap(round_data['handicap_index'])
    
    sg_categories = {"driving": 0.0, "approach": 0.0, "short_game": 0.0, "putting": 0.0}
    category_counts = {"driving": 0, "approach": 0, "short_game": 0, "putting": 0}
    
    # Pre-compute hole-level putting SG
    putts_by_hole = {}
    for shot in round_data['shots']:
        if shot['club'] == "P":
            putts_by_hole.setdefault(shot['hole_number'], []).append(shot)
    
    putting_sg_by_hole = {}
    for hole_num, putts in putts_by_hole.items():
        total_putts = len(putts)
        expected_putts = baseline.putts_per_hole()
        putting_sg_by_hole[hole_num] = expected_putts - total_putts
    
    for shot in round_data['shots']:
        before_lie = shot['before_lie']
        after_lie = shot['after_lie']
        
        # Putting: only count the "holed" putt with hole-level SG
        if shot['club'] == "P":
            if shot['after_lie'] == "HOLE":
                sg = putting_sg_by_hole.get(shot['hole_number'], 0)
                sg_categories["putting"] += sg
                category_counts["putting"] += 1
            # Missed putts: don't count in summary
            continue
        
        # Map to full lie names for SG calc
        lie_full = {"T": "tee", "F": "fairway", "R": "rough", "B": "sand", "G": "green"}.get(before_lie, before_lie)
        after_full = None
        if after_lie == "HOLE":
            after_full = "hole"
        elif after_lie in {"T": "tee", "F": "fairway", "R": "rough", "B": "sand", "G": "green"}:
            after_full = {"T": "tee", "F": "fairway", "R": "rough", "B": "sand", "G": "green"}[after_lie]
        
        if after_full and shot['after_distance_yards'] is not None:
            try:
                if after_full == "hole":
                    before = baseline.strokes(shot['before_distance_yards'], lie_full)
                    sg = before - shot['strokes_taken']
                else:
                    sg = baseline.sg(
                        shot['before_distance_yards'], lie_full,
                        shot['after_distance_yards'], after_full,
                        shot['strokes_taken']
                    )
                
                cat = get_category(lie_full, shot['before_distance_yards'])
                sg_categories[cat] += sg
                category_counts[cat] += 1
            except Exception:
                pass
    
    lines = []
    for cat, total in sg_categories.items():
        count = category_counts[cat]
        if count > 0:
            lines.append(f"{cat}: {total:+.2f} SG ({count} shots)")
    
    return "\n".join(lines) if lines else "No SG data available."


def get_reflection() -> str:
    print("\n" + "=" * 60)
    print("📝 ROUND REFLECTION")
    print("=" * 60)
    print("Write 3-5 sentences about this round.")
    print("What stood out, what was good, what was bad, tendencies noticed.")
    print("(Press Enter twice to finish)")
    print("-" * 60)
    
    lines = []
    while True:
        try:
            line = input()
            if line.strip() == "" and lines and lines[-1].strip() == "":
                # Two empty lines = done
                break
            lines.append(line)
        except EOFError:
            break
    
    reflection = "\n".join(lines).strip()
    return reflection


def build_prompt_preview(round_data: dict, reflection: str, question: str = "How did I play today?") -> str:
    """Build the exact prompt that would be sent to the LLM coach."""
    
    # Generate narratives for each shot (same as main.py)
    lie_map = {"T": "tee", "F": "fairway", "R": "rough", "B": "bunker", "G": "green"}
    club_map = {
        "D": "Driver", "3W": "3-wood", "5W": "5-wood", "H": "Hybrid",
        "3": "3-iron", "4": "4-iron", "5": "5-iron", "6": "6-iron",
        "7": "7-iron", "8": "8-iron", "9": "9-iron",
        "G": "Gap wedge", "L": "Lob wedge", "P": "Putter"
    }
    
    # Calculate per-shot SG (same as main.py ingestion)
    baseline = get_baseline_for_handicap(round_data['handicap_index'])
    
    # Pre-compute putting SG per hole
    putts_by_hole = {}
    for shot in round_data['shots']:
        if shot['club'] == "P":
            putts_by_hole.setdefault(shot['hole_number'], []).append(shot)
    
    putting_sg_by_hole = {}
    for hole_num, putts in putts_by_hole.items():
        total_putts = len(putts)
        expected_putts = baseline.putts_per_hole()
        putting_sg_by_hole[hole_num] = expected_putts - total_putts
    
    context_blocks = []
    for i, shot in enumerate(round_data['shots'], 1):
        club = club_map.get(shot['club'], shot['club'])
        before_lie = lie_map.get(shot['before_lie'], shot['before_lie'])
        
        # Before-state: distance to pin + lie
        if shot['before_lie'] == "T":
            before_phrase = f"{shot['before_distance_yards']} yards to pin, tee shot"
        elif shot['before_lie'] == "G":
            before_phrase = "putt"
        else:
            before_phrase = f"{shot['before_distance_yards']} yards to pin, in {before_lie}"
        
        # After-state
        if shot['after_lie'] == "HOLE":
            after_phrase = "holed"
        elif shot['after_lie'] == "G" and shot['before_lie'] == "G":
            after_phrase = "missed"
        elif shot['after_lie'] == "G":
            after_phrase = "on green"
        elif shot['after_lie'] in lie_map:
            after_phrase = f"to {shot['after_distance_yards']} yards to pin, in {lie_map[shot['after_lie']]}"
        else:
            after_phrase = "result pending"
        
        narrative = f"{club}: {before_phrase} → {after_phrase}"
        if shot['strokes_taken'] > 1 and shot['before_lie'] != "G":
            narrative += f" (penalty: {shot['strokes_taken']} strokes)"
        
        # Calculate per-shot SG (same as main.py)
        sg = None
        
        # Putting: hole-level SG assigned ONLY to the "holed" putt
        # Missed putts show no SG to avoid confusing the LLM
        if shot['club'] == "P":
            if shot['after_lie'] == "HOLE":
                sg = putting_sg_by_hole.get(shot['hole_number'])
            # Missed putts: no SG shown
        elif shot['after_lie'] == "HOLE":
            # Non-putt holed out (chip-in, etc.)
            try:
                before = baseline.strokes(shot['before_distance_yards'], before_lie)
                sg = before - shot['strokes_taken']
            except Exception:
                pass
        elif shot['after_lie'] in lie_map:
            # Non-putting shot
            after_lie_full = lie_map[shot['after_lie']]
            if shot['after_distance_yards'] is not None:
                try:
                    sg = baseline.sg(
                        shot['before_distance_yards'], before_lie,
                        shot['after_distance_yards'], after_lie_full,
                        shot['strokes_taken']
                    )
                except Exception:
                    pass
        
        sg_note = f" (SG: {sg:+.2f})" if sg is not None else ""
        context_blocks.append(f"Shot {i}: {narrative}{sg_note}")
    
    context_text = "\n".join(context_blocks)
    sg_summary = calculate_sg_summary(round_data)
    
    system_prompt = (
        "You are Dimple Coach, an expert golf coach. You have access to the player's "
        "historical shot data with Strokes Gained values. Be direct, data-driven, and actionable. "
        "Ground every insight in the provided context. If you don't have enough data, say so."
    )
    
    user_prompt_parts = [
        f"Player Question: {question}",
        "",
        "Strokes Gained Summary (from retrieved shots):",
        sg_summary,
        "",
        "Relevant Shot History:",
        context_text,
    ]
    
    if reflection:
        user_prompt_parts.extend([
            "",
            "Player's Recent Round Reflections:",
            f"Round ({round_data['round_date']}): {reflection}",
        ])
    
    user_prompt_parts.extend([
        "",
        "Based on the shot history, SG summary, and any player reflections above, provide a helpful coaching response. "
        "Connect the quantitative data (SG) with the qualitative observations (reflections) when both are available."
    ])
    
    user_prompt = "\n".join(user_prompt_parts)
    
    return f"""{'='*70}
SYSTEM PROMPT:
{'='*70}
{system_prompt}

{'='*70}
USER PROMPT:
{'='*70}
{user_prompt}

{'='*70}
TOTAL PROMPT LENGTH: {len(system_prompt) + len(user_prompt)} characters
{'='*70}"""


def run_auto_mode(handicap: float, reflection: str = "", question: str = "How did I play today?", show_shots: bool = False):
    """Non-interactive mode for testing."""
    print_banner()
    
    print(f"\n🔄 Generating round for {handicap} handicap...")
    round_data = generate_round(
        handicap=handicap,
        user_id=f"player_{handicap}hcp",
        round_date="2026-05-22"
    )
    
    display_round_summary(round_data)
    
    if show_shots:
        display_shots(round_data)
    
    if reflection:
        print(f"\n📝 Reflection: {reflection[:80]}...")
    else:
        reflection = ""
    
    print(f"\n❓ Question: {question}")
    
    print("\n" + "=" * 70)
    print("📋 COACH PROMPT PREVIEW")
    print("=" * 70)
    print("(This is the exact prompt that would be sent to the LLM)")
    print()
    
    prompt_preview = build_prompt_preview(round_data, reflection, question)
    print(prompt_preview)
    
    return round_data, prompt_preview


def main():
    # Check for command-line args (auto mode)
    if len(sys.argv) > 1:
        try:
            handicap = float(sys.argv[1])
            reflection = sys.argv[2] if len(sys.argv) > 2 else ""
            question = sys.argv[3] if len(sys.argv) > 3 else "How did I play today?"
            run_auto_mode(handicap, reflection, question)
            return
        except ValueError:
            print(f"Usage: python {sys.argv[0]} [handicap] [reflection] [question]")
            sys.exit(1)
    
    # Interactive mode
    print_banner()
    
    # 1) Get handicap
    handicap = get_handicap_input()
    
    # 2) Generate round
    print(f"\n🔄 Generating round for {handicap} handicap...")
    round_data = generate_round(
        handicap=handicap,
        user_id=f"player_{handicap}hcp",
        round_date="2026-05-22"
    )
    
    # 3) Display summary
    display_round_summary(round_data)
    
    # 4) Ask if they want to see all shots
    show_shots = input("\nShow all shots? (y/n): ").strip().lower()
    if show_shots == 'y':
        display_shots(round_data)
    
    # 5) Get reflection
    reflection = get_reflection()
    
    # 6) Ask for a question (or use default)
    print("\n" + "=" * 60)
    question = input("Ask the coach a question (or press Enter for 'How did I play today?'): ").strip()
    if not question:
        question = "How did I play today?"
    
    # 7) Build and display prompt
    print("\n" + "=" * 70)
    print("📋 COACH PROMPT PREVIEW")
    print("=" * 70)
    print("(This is the exact prompt that would be sent to the LLM)")
    print()
    
    prompt_preview = build_prompt_preview(round_data, reflection, question)
    print(prompt_preview)
    
    # 8) Optionally save to file
    print("\n" + "=" * 60)
    save = input("Save prompt to file? (y/n): ").strip().lower()
    if save == 'y':
        filename = f"prompt_{round_data['user_id']}_{round_data['round_date']}.txt"
        filepath = Path(__file__).parent / "data" / "prompts" / filename
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(prompt_preview, encoding="utf-8")
        print(f"✅ Saved to: {filepath}")
    
    print("\n👋 Done!")


if __name__ == "__main__":
    main()
