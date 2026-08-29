"""LLM client for coach generation (OpenCode Go — OpenAI-compatible)."""
import logging
import openai
import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Iterator

from app.core.config import get_settings
from app.services.coach_format import (
    FORMAT_INSTRUCTIONS,
    CoachAnswer,
    CoachStreamParser,
    collect,
)

logger = logging.getLogger(__name__)
settings = get_settings()

# Some OpenAI-compatible providers reject `stream_options`. Probed once, then cached.
_stream_usage_supported = True

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


def stream_coach_response(system_prompt: str, user_prompt: str) -> Iterator[str]:
    """Stream a coaching response as text deltas.

    The model writes in the line-tagged format (see `coach_format`), not JSON —
    so the caller can render prose the moment it arrives instead of waiting for
    a closing brace. Accumulates the full text for the response log.
    """
    global _stream_usage_supported

    messages = [
        {"role": "system", "content": system_prompt + FORMAT_INSTRUCTIONS},
        {"role": "user", "content": user_prompt},
    ]
    kwargs = dict(model=LLM_MODEL, messages=messages, temperature=1.0, max_tokens=8000, stream=True)
    if _stream_usage_supported:
        kwargs["stream_options"] = {"include_usage": True}

    try:
        stream = llm_client.chat.completions.create(**kwargs)
    except (openai.BadRequestError, TypeError) as exc:
        # Not every OpenAI-compatible provider accepts `stream_options`. Lose the
        # token accounting rather than the response, and stop asking.
        if not _stream_usage_supported:
            raise
        logger.warning(f"Provider rejected stream_options, retrying without usage: {exc}")
        _stream_usage_supported = False
        kwargs.pop("stream_options", None)
        stream = llm_client.chat.completions.create(**kwargs)

    chunks: list[str] = []
    usage = None
    model_used = LLM_MODEL
    try:
        for event in stream:
            if getattr(event, "usage", None):
                usage = event.usage.model_dump()
            if getattr(event, "model", None):
                model_used = event.model
            if not event.choices:
                continue
            delta = event.choices[0].delta
            text = getattr(delta, "content", None)
            if text:
                chunks.append(text)
                yield text
    finally:
        # Log whatever arrived, including on a mid-stream failure — a partial
        # response is exactly what we want a record of.
        if chunks:
            _log_response("".join(chunks), usage=usage, model=model_used)


def generate_coach_answer(system_prompt: str, user_prompt: str) -> CoachAnswer:
    """Non-streaming path: run the stream to completion and parse it."""
    parser = CoachStreamParser()

    def events():
        for chunk in stream_coach_response(system_prompt, user_prompt):
            yield from parser.feed(chunk)

    return collect(events(), parser)
