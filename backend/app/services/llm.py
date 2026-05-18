"""Moonshot LLM client for coach generation."""
import openai
from app.core.config import get_settings

settings = get_settings()

# Configure Moonshot client (OpenAI-compatible API)
moonshot_client = openai.OpenAI(
    api_key=settings.moonshot_api_key,
    base_url="https://api.moonshot.cn/v1",
)


def generate_coach_response(system_prompt: str, user_prompt: str) -> str:
    """Call Moonshot kimi-k2.5 to generate a coaching response."""
    response = moonshot_client.chat.completions.create(
        model="kimi-k2.5",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,
        max_tokens=500,
    )
    return response.choices[0].message.content
