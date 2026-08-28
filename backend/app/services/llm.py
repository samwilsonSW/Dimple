"""LLM client for coach generation (OpenCode Go — OpenAI-compatible)."""
import openai
import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from app.core.config import get_settings

settings = get_settings()

# ── Response logging ──
LLM_LOG_DIR = Path(__file__).parent.parent.parent.parent / "data" / "llm_responses"
ARCHIVE_DIR = LLM_LOG_DIR / "archive"
MAX_KEEP = 20


def _archive_old_logs():
    """Keep only MAX_KEEP most recent logs; move older ones to archive/."""
    LLM_LOG_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    files = sorted(LLM_LOG_DIR.glob("*.txt"), key=lambda f: f.stat().st_mtime, reverse=True)
    for old in files[MAX_KEEP:]:
        shutil.move(str(old), str(ARCHIVE_DIR / old.name))


def _log_response(raw_response: str, parsed: dict | None = None, usage: dict | None = None, model: str = "unknown"):
    """Save raw Moonshot response to disk with rotation, including token cost."""
    _archive_old_logs()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filepath = LLM_LOG_DIR / f"llm_response_{timestamp}.txt"

    lines = [
        f"Timestamp: {datetime.now().isoformat()}",
        f"Model: {model}",
        "=" * 50,
        "RAW RESPONSE:",
        raw_response,
    ]
    if parsed:
        lines += ["", "PARSED JSON:", json.dumps(parsed, indent=2)]
    if usage:
        lines += [
            "",
            "USAGE / COST:",
            f"  prompt_tokens:     {usage.get('prompt_tokens', 'N/A')}",
            f"  completion_tokens: {usage.get('completion_tokens', 'N/A')}",
            f"  total_tokens:      {usage.get('total_tokens', 'N/A')}",
        ]

    filepath.write_text("\n".join(lines), encoding="utf-8")
    return filepath

# Configure LLM client (OpenCode Go — OpenAI-compatible API)
# Uses OPENCODE_API_KEY from env or .env file via settings
# Note: pydantic-settings loads .env into settings.opencode_api_key,
# but an empty env var would override it to "". Handle both cases.
_env_key = os.environ.get("OPENCODE_API_KEY", "")
llm_api_key = _env_key if _env_key else (settings.opencode_api_key or settings.moonshot_api_key)
if not llm_api_key:
    raise RuntimeError("No LLM API key found. Set OPENCODE_API_KEY in env or .env file.")
llm_client = openai.OpenAI(
    api_key=llm_api_key,
    base_url=os.environ.get("OPENCODE_BASE_URL", "https://opencode.ai/zen/go/v1"),
    timeout=120.0,
)
# Model for coach responses — Kimi K2.6 via OpenCode Go
# (deepseek-v4-flash is better/cheaper but requires China region opt-in)
LLM_MODEL = os.environ.get("OPENCODE_MODEL", "kimi-k2.6")

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
    """Call LLM to generate a coaching response in Thinking Mode."""
    response = llm_client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=1.0,
        max_tokens=8000,
    )
    raw = response.choices[0].message.content
    usage = response.usage.model_dump() if response.usage else None
    model_used = response.model if response.model else LLM_MODEL
    _log_response(raw, usage=usage, model=model_used)
    return raw


def generate_structured_coach_response(system_prompt: str, user_prompt: str) -> dict:
    """Call LLM to generate a structured JSON coaching response."""
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

    response = llm_client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": structured_system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=1.0,
        max_tokens=8000,
    )

    raw = response.choices[0].message.content.strip()
    usage = response.usage.model_dump() if response.usage else None
    model_used = response.model if response.model else LLM_MODEL

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
        _log_response(raw, parsed=None, usage=usage, model=model_used)
        raise ValueError(f"LLM returned invalid JSON: {e}\nRaw response:\n{raw}")

    _log_response(raw, parsed=parsed, usage=usage, model=model_used)
    return parsed