#!/usr/bin/env python3
"""Quick diagnostic to verify LLM connectivity."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import get_settings
from app.services.llm import moonshot_client

settings = get_settings()

print("=== LLM Configuration ===")
print(f"Key present: {bool(settings.moonshot_api_key)}")
print(f"Key prefix: {settings.moonshot_api_key[:15]}..." if settings.moonshot_api_key else "EMPTY")
print()

print("=== Testing API Call ===")
# Test 1: Small max_tokens (may fail with length)
print("\n--- Test 1: max_tokens=10 ---")
try:
    response = moonshot_client.chat.completions.create(
        model="kimi-k2.5",
        messages=[
            {"role": "user", "content": "Say 'hello' and nothing else."},
        ],
        max_tokens=10,
    )
    print(f"   Content: {repr(response.choices[0].message.content)}")
    print(f"   Finish reason: {response.choices[0].finish_reason}")
    print(f"   Usage: {response.usage}")
except Exception as e:
    print(f"   ❌ Failed: {type(e).__name__}: {e}")

# Test 2: Larger max_tokens
print("\n--- Test 2: max_tokens=100 ---")
try:
    response = moonshot_client.chat.completions.create(
        model="kimi-k2.5",
        messages=[
            {"role": "user", "content": "Say 'hello' and nothing else."},
        ],
        max_tokens=100,
    )
    print(f"   Content: {repr(response.choices[0].message.content)}")
    print(f"   Finish reason: {response.choices[0].finish_reason}")
    print(f"   Usage: {response.usage}")
except Exception as e:
    print(f"   ❌ Failed: {type(e).__name__}: {e}")

# Test 3: No max_tokens limit
print("\n--- Test 3: no max_tokens ---")
try:
    response = moonshot_client.chat.completions.create(
        model="kimi-k2.5",
        messages=[
            {"role": "user", "content": "Say 'hello' and nothing else."},
        ],
    )
    print(f"   Content: {repr(response.choices[0].message.content)}")
    print(f"   Finish reason: {response.choices[0].finish_reason}")
    print(f"   Usage: {response.usage}")
except Exception as e:
    print(f"   ❌ Failed: {type(e).__name__}: {e}")
