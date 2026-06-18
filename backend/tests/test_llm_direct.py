#!/usr/bin/env python3
"""
Test Moonshot LLM directly — bypass Supabase to verify response generation works.
This tests the core issue: empty LLM responses.
"""
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_dir))

from app.services.llm import generate_structured_coach_response

SYSTEM_PROMPT = (
    "You are Dimple Coach, an expert golf coach. You have access to the player's "
    "historical shot data. Be direct, data-driven, and actionable. "
    "Ground every insight in the provided context. If you don't have enough data, say so."
)

# Fake context (no Supabase needed)
FAKE_CONTEXT = """Shot 1: Driver 280 yards down the right side of the fairway, slight fade but playable (Club: Driver, Distance: 280y, Hole: 1)
Shot 2: 8-iron from 145 yards in the fairway, landed on the front edge of the green (Club: 8-iron, Distance: 145y, Hole: 1)
Shot 3: Two-putt from 25 feet for a comfortable par (Club: Putter, Distance: 25y, Hole: 1)
Shot 4: 3-wood off the tee 230 yards, pulled slightly left into the first cut of rough (Club: 3-wood, Distance: 230y, Hole: 2)
Shot 5: Pitching wedge from 95 yards in light rough, landed 12 feet from the pin (Club: Pitching Wedge, Distance: 95y, Hole: 2)"""

QUESTIONS = [
    "How do I make more birdie putts?",
    "Why do I push my irons right?",
    "What should I practice this week?",
]


def test_llm_direct():
    print("Testing Moonshot LLM directly (no Supabase)...")
    print("=" * 60)

    for i, question in enumerate(QUESTIONS, 1):
        print(f"\n[{i}/{len(QUESTIONS)}] Q: {question}")

        user_prompt = (
            f"Player Question: {question}\n\n"
            f"Relevant Shot History:\n{FAKE_CONTEXT}\n\n"
            f"Based strictly on the shot history above, provide a helpful coaching response."
        )

        try:
            response = generate_structured_coach_response(SYSTEM_PROMPT, user_prompt)
            print(f"✅ SUCCESS")
            print(f"   Answer: {response.get('answer', '')[:150]}...")
            print(f"   Confidence: {response.get('confidence', '?')}/5")
            print(f"   Insights: {len(response.get('key_insights', []))}")
            print(f"   Drills: {len(response.get('drill_recommendations', []))}")
        except Exception as e:
            print(f"❌ FAILED: {e}")

    print("\n" + "=" * 60)
    print("Check data/llm_responses/ for detailed logs with token usage.")


if __name__ == "__main__":
    test_llm_direct()
