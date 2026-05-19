"""Moonshot LLM client for coach generation."""
import openai
from app.core.config import get_settings

settings = get_settings()

# Configure Moonshot client (OpenAI-compatible API)
moonshot_client = openai.OpenAI(
    api_key=settings.moonshot_api_key,
    base_url="https://api.moonshot.ai/v1",
)

# ORIGINAL generator (No coach response)
# def generate_coach_response(system_prompt: str, user_prompt: str) -> str:
#     """Call Moonshot kimi-k2.5 to generate a coaching response."""
#     response = moonshot_client.chat.completions.create(
#         model="kimi-k2.5",
#         messages=[
#             {"role": "system", "content": system_prompt},
#             {"role": "user", "content": user_prompt},
#         ],
#         temperature=1,
#         max_tokens=500,
#     )
#     return response.choices[0].message.content

# Second try, switch to instant to reduce token expenditure. Could result in less in depth analysis
# def generate_coach_response(system_prompt: str, user_prompt: str) -> str:
#     """Call Moonshot kimi-k2.5 to generate a coaching response in Instant Mode."""
#     response = moonshot_client.chat.completions.create(
#         model="kimi-k2.5",
#         messages=[
#             {"role": "system", "content": system_prompt},
#             {"role": "user", "content": user_prompt},
#         ],
#         temperature=0.6,
#         max_tokens=1000,
#         extra_body={"chat_template_kwargs": {"thinking": False}}
#     )
#     return response.choices[0].message.content


# Third option, 8000 tokens, use thinking (more expensive), so increase token budget.
def generate_coach_response(system_prompt: str, user_prompt: str) -> str:
    """Call Moonshot kimi-k2.5 to generate a coaching response in Thinking Mode."""
    response = moonshot_client.chat.completions.create(
        model="kimi-k2.5",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=1.0,
        max_tokens=8000, # Increased to allow for reasoning overhead
    )
    return response.choices[0].message.content