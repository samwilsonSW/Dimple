"""Title generation for coach conversations."""
import logging
import openai
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Dedicated client for title generation (cheap model, fast)
title_client = openai.OpenAI(
    api_key=settings.moonshot_api_key,
    base_url="https://api.moonshot.ai/v1",
    timeout=30.0,
)

TITLE_SYSTEM_PROMPT = """You are a title generator for golf coaching conversations.
Given a user's first message to an AI golf coach, create a very short, descriptive title.

Rules:
- 3-5 words maximum
- No quotes, no punctuation at the end
- Capture the topic or intent
- Examples: "Putting struggles", "Driver slice fix", "Round review July", "Short game help"

Respond with ONLY the title text. No markdown, no explanation."""


def generate_title(first_message: str) -> str | None:
    """Generate a concise title from the first user message.
    
    Returns None if generation fails (caller should keep default title).
    """
    try:
        response = title_client.chat.completions.create(
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
        logger.warning(f"Title generation failed: {e}")
        return None
