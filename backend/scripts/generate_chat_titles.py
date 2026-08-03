#!/usr/bin/env python3
"""
Background job: Generate titles for untitled conversations.

Runs every 5 minutes via cron/launchd. Finds conversations with no title
(or default "Coach Chat"), takes the first user message, sends to LLM for
a concise title, and updates the conversation.

Usage:
    python scripts/generate_chat_titles.py

Environment:
    Requires SUPABASE_URL, SUPABASE_KEY, MOONSHOT_API_KEY in .env
"""

import sys
import os
from pathlib import Path

# Add project root to path
backend_dir = Path(__file__).parent.parent.resolve()
project_root = backend_dir.parent
for path in [str(backend_dir), str(project_root)]:
    if path not in sys.path:
        sys.path.insert(0, path)

import time
import logging
from datetime import datetime, timezone

from app.services.supabase_client import get_supabase
from app.core.config import get_settings
import openai

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()

# Moonshot client
moonshot_client = openai.OpenAI(
    api_key=settings.moonshot_api_key,
    base_url="https://api.moonshot.ai/v1",
)

TITLE_SYSTEM_PROMPT = """You are a title generator for golf coaching conversations.
Given a user's first message to an AI golf coach, create a very short, descriptive title.

Rules:
- 3-5 words maximum
- No quotes, no punctuation at the end
- Capture the topic or intent
- Examples: "Putting struggles", "Driver slice fix", "Round review July", "Short game help"

Respond with ONLY the title text. No markdown, no explanation."""


def generate_title(first_message: str) -> str:
    """Send first user message to LLM, get back a concise title."""
    try:
        response = moonshot_client.chat.completions.create(
            model="moonshot-v1-8k",
            messages=[
                {"role": "system", "content": TITLE_SYSTEM_PROMPT},
                {"role": "user", "content": first_message},
            ],
            temperature=1.0,
            max_tokens=20,
        )
        title = response.choices[0].message.content.strip()
        # Clean up: remove quotes, trim
        title = title.strip('"\'').strip()
        if len(title) > 60:
            title = title[:57] + "..."
        return title
    except Exception as e:
        logger.error(f"LLM title generation failed: {e}")
        return None


def find_untitled_conversations(supabase, batch_size: int = 50):
    """Find conversations that need titles."""
    try:
        result = supabase.table("conversations").select("*").or_("title.is.null,title.eq.Coach Chat").limit(batch_size).execute()
        return result.data or []
    except Exception as e:
        logger.error(f"Failed to fetch untitled conversations: {e}")
        return []


def get_first_user_message(supabase, conversation_id: int) -> str:
    """Get the first user message from a conversation."""
    try:
        result = (
            supabase.table("messages")
            .select("content")
            .eq("conversation_id", conversation_id)
            .eq("role", "user")
            .order("created_at", desc=False)
            .limit(1)
            .execute()
        )
        if result.data:
            return result.data[0]["content"]
        return None
    except Exception as e:
        logger.error(f"Failed to fetch first message for conv {conversation_id}: {e}")
        return None


def update_conversation_title(supabase, conversation_id: int, title: str):
    """Update the conversation with the generated title."""
    try:
        supabase.table("conversations").update({"title": title}).eq("id", conversation_id).execute()
        return True
    except Exception as e:
        logger.error(f"Failed to update title for conv {conversation_id}: {e}")
        return False


def process_batch():
    """Main job: find untitled conversations, generate titles, update them."""
    supabase = get_supabase()
    conversations = find_untitled_conversations(supabase)

    if not conversations:
        logger.info("No untitled conversations found.")
        return 0

    logger.info(f"Found {len(conversations)} untitled conversations.")
    processed = 0

    for conv in conversations:
        conv_id = conv["id"]
        first_msg = get_first_user_message(supabase, conv_id)

        if not first_msg:
            logger.warning(f"No user message found for conv {conv_id}, skipping.")
            continue

        title = generate_title(first_msg)
        if not title:
            logger.warning(f"Title generation failed for conv {conv_id}, skipping.")
            continue

        if update_conversation_title(supabase, conv_id, title):
            logger.info(f"Conv {conv_id}: '{title}' (from: '{first_msg[:50]}...')")
            processed += 1
        else:
            logger.warning(f"Failed to update title for conv {conv_id}")

        # Small delay to avoid rate limiting
        time.sleep(0.5)

    return processed


def main():
    logger.info("=" * 50)
    logger.info("Chat title generation job started")
    logger.info(f"Time: {datetime.now(timezone.utc).isoformat()}")

    start = time.time()
    processed = process_batch()
    elapsed = time.time() - start

    logger.info(f"Processed {processed} conversations in {elapsed:.1f}s")
    logger.info("Job complete.")


if __name__ == "__main__":
    main()
