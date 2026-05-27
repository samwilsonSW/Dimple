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
try:
    response = moonshot_client.chat.completions.create(
        model="kimi-k2.5",
        messages=[
            {"role": "user", "content": "Say 'hello' and nothing else."},
        ],
        max_tokens=10,
    )
    print(f"✅ Success!")
    print(f"   Response type: {type(response)}")
    print(f"   Choices count: {len(response.choices)}")
    print(f"   Message type: {type(response.choices[0].message)}")
    print(f"   Content: {repr(response.choices[0].message.content)}")
    print(f"   Finish reason: {response.choices[0].finish_reason}")
    if hasattr(response, 'usage'):
        print(f"   Usage: {response.usage}")
except Exception as e:
    print(f"❌ Failed: {type(e).__name__}: {e}")
