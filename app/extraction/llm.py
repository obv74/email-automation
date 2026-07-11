"""Ollama LLM wrapper for structured extraction."""

import json
import logging
from typing import Any, Optional

import httpx
from pydantic import ValidationError

from app.config import get_settings
from app.extraction.classify import EmailType, heuristic_booked, normalize_email_type
from app.extraction.prompt import build_extraction_prompt, build_retry_prompt
from app.extraction.schema import ExtractedJob
from app.prompts.defaults import CLASSIFY_PROMPT, CLASSIFY_SYSTEM, EXTRACTION_SYSTEM

logger = logging.getLogger(__name__)


class OllamaError(Exception):
    pass


def _parse_json_response(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [ln for ln in lines if not ln.strip().startswith("```")]
        text = "\n".join(lines).strip()
    return json.loads(text)


def _coerce_extracted(data: dict[str, Any]) -> ExtractedJob:
    """Accept slim LLM JSON and fill defaults for fields not asked in the slim schema."""
    defaults: dict[str, Any] = {
        "customer_name": None,
        "customer_phone": None,
        "customer_email": None,
        "city_state": None,
        "load_address": None,
        "unload_address": None,
        "service_requested": None,
        "move_date": None,
        "move_time": None,
        "inventory": [],
        "heaviest_item": None,
        "special_notes": None,
        "customer_requests": [],
        "promises_made": [],
        "over_250_lbs": None,
        "super_fragile": None,
        "over_1000_value": None,
        "packing": None,
        "unpacking": None,
        "assembly": None,
        "disassembly": None,
        "special_handling_notes": None,
        "minimum_hours": None,
        "minimum_price": None,
        "hourly_rate": None,
        "deposit": None,
        "balance_due": None,
        "num_movers": None,
        "truck_type": None,
        "booking_source": None,
        "summary": "",
    }
    merged = {**defaults, **{k: v for k, v in data.items() if k in defaults}}
    return ExtractedJob.model_validate(merged)


async def extract_job_from_thread(
    conversation: str,
    *,
    system_prompt: Optional[str] = None,
    user_prompt_template: Optional[str] = None,
) -> ExtractedJob:
    settings = get_settings()
    max_chars = settings.ollama_extract_max_chars
    if len(conversation) > max_chars:
        conversation = conversation[:max_chars] + "\n...[truncated]"
    prompt = build_extraction_prompt(conversation, user_prompt_template)
    system = (system_prompt or EXTRACTION_SYSTEM).strip() or EXTRACTION_SYSTEM
    last_error: Optional[str] = None
    # Prefer 1 successful pass; retry once only if JSON invalid (saves time on CPU).
    for attempt in range(2):
        user_prompt = prompt if attempt == 0 else build_retry_prompt(conversation, last_error or "invalid JSON")
        raw = await _call_ollama(
            user_prompt,
            system=system,
            num_predict=settings.ollama_extract_num_predict,
            temperature=0.0,
        )
        try:
            data = _parse_json_response(raw)
            return _coerce_extracted(data)
        except (json.JSONDecodeError, ValidationError) as exc:
            last_error = str(exc)
            logger.warning("Extraction validation failed (attempt %s): %s", attempt + 1, exc)

    raise OllamaError(f"Failed to extract valid job JSON after retries: {last_error}")


async def classify_email(
    conversation: str,
    *,
    prompt_template: Optional[str] = None,
) -> tuple[EmailType, str]:
    """
    Classify thread as booked | inquiry | ignore | unclear.
    Heuristic booked markers win over the model (Moving Helper etc.).
    """
    if heuristic_booked(conversation):
        return "booked", "matched booked-job keywords (Moving Helper / payment code / JB-)"

    settings = get_settings()
    if not settings.classify_enabled:
        return "inquiry", "classification disabled"

    snippet = conversation[: settings.classify_max_chars]
    template = (prompt_template or CLASSIFY_PROMPT).strip() or CLASSIFY_PROMPT
    if "{email}" in template:
        prompt = template.replace("{email}", snippet)
    else:
        prompt = f"{template}\n\nEmail thread:\n---\n{snippet}\n---"

    try:
        raw = await _call_ollama(
            prompt,
            system=CLASSIFY_SYSTEM,
            num_predict=80,
            temperature=0.0,
            use_json_format=True,
        )
        data = _parse_json_response(raw)
        if "email_type" in data:
            email_type = normalize_email_type(data.get("email_type"))
        elif "is_moving_inquiry" in data:
            email_type = "inquiry" if data.get("is_moving_inquiry") else "ignore"
        else:
            email_type = "unclear"
        return email_type, str(data.get("reason", ""))
    except Exception as exc:
        logger.warning("Classification failed, treating as unclear: %s", exc)
        return "unclear", "classification error — needs human"


async def is_moving_inquiry(
    conversation: str,
    *,
    prompt_template: Optional[str] = None,
) -> tuple[bool, str]:
    """Legacy helper — True for inquiry/booked, False for ignore."""
    email_type, reason = await classify_email(conversation, prompt_template=prompt_template)
    if email_type in ("inquiry", "booked", "unclear"):
        return True, reason
    return False, reason


async def _call_ollama(
    prompt: str,
    *,
    system: str = "You are a precise data extraction assistant.",
    num_predict: Optional[int] = None,
    temperature: float = 0.0,
    use_json_format: bool = True,
) -> str:
    settings = get_settings()
    url = f"{settings.ollama_base_url.rstrip('/')}/api/chat"
    payload: dict = {
        "model": settings.ollama_model,
        "stream": False,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "options": {
            "num_predict": num_predict or settings.ollama_num_predict,
            "temperature": temperature,
            # Slightly faster / more deterministic on small CPUs
            "top_p": 0.9,
            "repeat_penalty": 1.05,
        },
    }
    if use_json_format:
        payload["format"] = "json"

    read_timeout = float(settings.ollama_read_timeout_seconds)
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, read=read_timeout)) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data["message"]["content"]
    except httpx.ConnectError as exc:
        raise OllamaError(
            "Cannot connect to Ollama. Run: systemctl start ollama && ollama pull qwen2.5:3b-instruct"
        ) from exc
    except httpx.ReadTimeout as exc:
        raise OllamaError(
            f"Ollama timed out after {settings.ollama_read_timeout_seconds}s. "
            "CPU inference is slow — retry, or use a smaller model: ollama pull qwen2.5:3b-instruct"
        ) from exc
    except httpx.HTTPError as exc:
        raise OllamaError(f"Ollama HTTP error: {exc}") from exc
