"""
Reflection Generator for Synthetic Rounds

Generates realistic post-round reflections by:
1. Summarizing round stats (SG categories, key moments)
2. Calling LLM with a compact prompt
3. Returning a 2-3 sentence player narrative

Usage:
    from app.core.reflection_generator import generate_reflection
    reflection = generate_reflection(round_data, stats_summary)
"""

import json
from typing import Dict, Any, List
from app.services.llm import moonshot_client


# ──────────────────────────────────────────────────────────────────────────────
# ROUND SUMMARIZER
# ──────────────────────────────────────────────────────────────────────────────

def summarize_round(round_data: Dict[str, Any]) -> Dict[str, Any]:
    """Extract key stats from a generated round for reflection prompting."""
    shots = round_data["shots"]
    handicap = round_data["handicap_index"]
    total_score = round_data.get("_meta", {}).get("total_score", 0)
    course_par = round_data.get("course", {}).get("par", 72)

    # Basic counting
    drives = [s for s in shots if s["before_lie"] == "T"]
    fairways = [s for s in drives if s["after_lie"] == "F"]
    penalties = len([s for s in shots if s["strokes_taken"] > 1 and s["before_lie"] != "G"])

    # GIR: approach that ends on green (before_lie in F/R, after_lie = G)
    approaches = [s for s in shots if s["before_lie"] in ["F", "R"] and s["club"] != "P"]
    greens = [s for s in approaches if s["after_lie"] == "G"]

    # Putts
    putt_shots = [s for s in shots if s["club"] == "P"]
    total_putts = sum(s["strokes_taken"] for s in putt_shots)

    # Up & downs: chip from R/B to G, then 1 putt
    up_downs = 0
    up_down_opps = 0
    for i, s in enumerate(shots):
        if s["before_lie"] in ["R", "B"]:
            up_down_opps += 1
            if s["after_lie"] == "G":
                # Check next shot is 1 putt
                if i + 1 < len(shots) and shots[i + 1]["strokes_taken"] == 1 and shots[i + 1]["club"] == "P":
                    up_downs += 1

    # Score by 9
    front_9 = _score_for_holes(shots, range(1, 10))
    back_9 = _score_for_holes(shots, range(10, 19))

    # Best/worst holes
    hole_scores = _hole_scores(shots)
    best_holes = sorted(hole_scores.items(), key=lambda x: x[1])[:2]
    worst_holes = sorted(hole_scores.items(), key=lambda x: x[1], reverse=True)[:2]

    # Identify specific issues
    issues = []
    if len(fairways) / len(drives) < 0.4:
        issues.append("driving accuracy")
    if len(greens) / len(approaches) < 0.3:
        issues.append("approach play")
    if total_putts > 34:
        issues.append("putting")
    if penalties >= 2:
        issues.append("penalty shots")
    if up_down_opps > 0 and up_downs / up_down_opps < 0.3:
        issues.append("short game")

    return {
        "handicap": handicap,
        "score": total_score,
        "par": course_par,
        "fairways": f"{len(fairways)}/{len(drives)}",
        "gir": f"{len(greens)}/{len(approaches)}",
        "putts": total_putts,
        "penalties": penalties,
        "up_downs": f"{up_downs}/{up_down_opps}",
        "front_9": front_9,
        "back_9": back_9,
        "best_holes": best_holes,
        "worst_holes": worst_holes,
        "issues": issues,
    }


def _score_for_holes(shots: List[Dict], hole_numbers) -> int:
    """Calculate total strokes for a range of holes."""
    return sum(s["strokes_taken"] for s in shots if s["hole_number"] in hole_numbers)


def _hole_scores(shots: List[Dict]) -> Dict[int, int]:
    """Return dict of hole_number -> total strokes."""
    scores = {}
    for s in shots:
        scores.setdefault(s["hole_number"], 0)
        scores[s["hole_number"]] += s["strokes_taken"]
    return scores


# ──────────────────────────────────────────────────────────────────────────────
# REFLECTION PROMPT BUILDER
# ──────────────────────────────────────────────────────────────────────────────

REFLECTION_SYSTEM_PROMPT = """You are a golfer writing a brief, authentic post-round reflection.
Write 2-3 sentences that sound like a real person, not a stat sheet.
Be specific but casual. Mention 1-2 things that actually happened.
Use first person. Avoid golf jargon unless it's natural.
Vary your tone — sometimes frustrated, sometimes analytical, sometimes hopeful."""


def build_reflection_prompt(summary: Dict[str, Any]) -> str:
    """Build a compact prompt from round summary."""
    relative = summary["score"] - summary["par"]
    relative_str = f"+{relative}" if relative > 0 else str(relative)

    lines = [
        f"Handicap: {summary['handicap']}",
        f"Score: {summary['score']} ({relative_str} to par)",
        f"Fairways: {summary['fairways']}",
        f"Greens in reg: {summary['gir']}",
        f"Putts: {summary['putts']}",
        f"Penalties: {summary['penalties']}",
        f"Up & downs: {summary['up_downs']}",
        f"Front 9: {summary['front_9']}, Back 9: {summary['back_9']}",
    ]

    if summary["best_holes"]:
        best = summary["best_holes"][0]
        lines.append(f"Best hole: #{best[0]} (score: {best[1]})")

    if summary["worst_holes"]:
        worst = summary["worst_holes"][0]
        lines.append(f"Worst hole: #{worst[0]} (score: {worst[1]})")

    if summary["issues"]:
        lines.append(f"Struggled with: {', '.join(summary['issues'])}")

    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────────────
# LLM CALL
# ──────────────────────────────────────────────────────────────────────────────

def generate_reflection(round_data: Dict[str, Any], temperature: float = 1.0) -> str:
    """Generate a realistic reflection for a synthetic round.

    Args:
        round_data: Output from generate_round()
        temperature: Higher = more varied reflections

    Returns:
        2-3 sentence reflection string
    """
    summary = summarize_round(round_data)
    user_prompt = build_reflection_prompt(summary)

    # Debug: log what we're sending
    print(f"   [reflection] Prompt length: {len(user_prompt)} chars")

    try:
        response = moonshot_client.chat.completions.create(
            model="kimi-k2.5",
            messages=[
                {"role": "system", "content": REFLECTION_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=200,
        )

        reflection = response.choices[0].message.content.strip()
        # Clean up quotes if LLM wraps in them
        if reflection.startswith('"') and reflection.endswith('"'):
            reflection = reflection[1:-1]

        print(f"   [reflection] Got response: {len(reflection)} chars")
        return reflection

    except Exception as e:
        print(f"   [reflection] LLM call failed: {type(e).__name__}: {str(e)[:100]}")
        raise


# ──────────────────────────────────────────────────────────────────────────────
# BATCH GENERATOR
# ──────────────────────────────────────────────────────────────────────────────

def generate_round_with_reflection(
    handicap: float,
    user_id: str,
    course_name: str = "Pine Valley Golf Club",
    round_date: str = "2026-05-27",
    temperature: float = 1.0,
) -> Dict[str, Any]:
    """Generate a complete round with LLM-generated reflection.

    Returns round data ready for ingestion (includes reflection field).
    """
    from app.core.generator import generate_round

    round_data = generate_round(
        handicap=handicap,
        user_id=user_id,
        course_name=course_name,
        round_date=round_date,
    )

    reflection = generate_reflection(round_data, temperature=temperature)
    round_data["reflection"] = reflection

    return round_data
