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


def generate_structured_coach_response(system_prompt: str, user_prompt: str) -> dict:
    """Call Moonshot kimi-k2.5 to generate a structured JSON coaching response."""
    structured_system_prompt = (
        system_prompt + "\n\n"
        "You MUST respond with valid JSON only. No markdown, no prose outside the JSON. "
        "Use this exact structure:\n"
        "{\n"
        '  "answer": "string — full natural-language coaching response",\n'
        '  "confidence": number — integer 1-5,\n'
        '  "key_insights": ["string", "string", ...],\n'
        '  "drill_recommendations": [\n'
        '    {\n'
        '      "priority": number — integer 1+,\n'
        '      "focus_area": "string — e.g. 6-iron push, lag putting",\n'
        '      "drill_name": "string",\n'
        '      "instructions": "string — step-by-step",\n'
        '      "expected_outcome": "string — what success looks like"\n'
        '    }\n'
        '  ]\n'
        "}"
    )

    response = moonshot_client.chat.completions.create(
        model="kimi-k2.5",
        messages=[
            {"role": "system", "content": structured_system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=1.0,
        max_tokens=8000,
    )

    import json
    raw = response.choices[0].message.content.strip()

    # Moonshot sometimes wraps JSON in markdown code blocks — strip them
    if raw.startswith("```json"):
        raw = raw[7:]
    if raw.startswith("```"):
        raw = raw[3:]
    if raw.endswith("```"):
        raw = raw[:-3]
    raw = raw.strip()

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM returned invalid JSON: {e}\nRaw response:\n{raw}")

    return parsed