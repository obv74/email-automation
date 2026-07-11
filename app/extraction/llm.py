"""LLM wrapper for structured extraction (local Ollama by default, optional cloud)."""

import json
import logging
from typing import Any, Optional

import httpx
from pydantic import ValidationError

from app.config import get_settings
from app.extraction.classify import EmailType, heuristic_booked, normalize_email_type
from app.extraction.cloud_llm import CloudLLMError, call_cloud_chat, cloud_configured
from app.extraction.prompt import build_extraction_prompt, build_retry_prompt
from app.extraction.schema import ExtractedJob
from app.prompts.defaults import CLASSIFY_PROMPT, CLASSIFY_SYSTEM, EXTRACTION_SYSTEM

logger = logging.getLogger(__name__)


class OllamaError(Exception):
    pass


class LLMError(Exception):
    pass


def normalize_extract_engine(value: Optional[str]) -> str:
    v = (value or "").strip().lower()
    if v in {"cloud", "remote", "hosted", "fast"}:
        return "cloud"
    return "local"


def resolve_extract_engine(tenant_engine: Optional[str] = None) -> str:
    """Server .env LLM_ENGINE controls backend. Optional silent DB override if set."""
    if tenant_engine and str(tenant_engine).strip():
        return normalize_extract_engine(tenant_engine)
    return normalize_extract_engine(get_settings().llm_engine)


def _parse_json_response(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [ln for ln in lines if not ln.strip().startswith("```")]
        text = "\n".join(lines).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        repaired = _repair_truncated_json(text)
        return json.loads(repaired)


def _repair_truncated_json(text: str) -> str:
    """
    Ollama often hits num_predict mid-string on weak CPUs ("Unterminated string").
    Close open quotes / arrays / objects so we can still use partial extraction.
    """
    s = text.strip()
    if not s:
        raise json.JSONDecodeError("empty", text, 0)

    # If model returned leading junk before {
    start = s.find("{")
    if start > 0:
        s = s[start:]

    in_string = False
    escape = False
    stack: list[str] = []
    last_good = 0

    for i, ch in enumerate(s):
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
                last_good = i
            continue

        if ch == '"':
            in_string = True
            continue
        if ch in "{[":
            stack.append("}" if ch == "{" else "]")
            last_good = i
        elif ch in "}]":
            if stack and stack[-1] == ch:
                stack.pop()
            last_good = i
        elif ch in ",:":
            last_good = i

    # Cut back to a safer point if we died mid-string / mid-value
    if in_string:
        # close the string, then drop dangling incomplete key if needed
        s = s + '"'
        # if we closed a string that was a key waiting for ":", leave as incomplete — trim to last comma/brace
        trimmed = s.rstrip()
        # remove trailing comma or colon leftovers
        while trimmed and trimmed[-1] in ",:":
            trimmed = trimmed[:-1].rstrip()
        s = trimmed
        # rebuild stack by re-scan
        in_string = False
        escape = False
        stack = []
        for ch in s:
            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_string = False
                continue
            if ch == '"':
                in_string = True
            elif ch == "{":
                stack.append("}")
            elif ch == "[":
                stack.append("]")
            elif ch in "}]" and stack and stack[-1] == ch:
                stack.pop()

    # Remove trailing incomplete ", "key"" without value
    s = s.rstrip()
    if s.endswith(","):
        s = s[:-1].rstrip()

    # Close open arrays/objects
    while stack:
        s += stack.pop()

    return s


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
    extract_engine: Optional[str] = None,
) -> ExtractedJob:
    settings = get_settings()
    engine = resolve_extract_engine(extract_engine)
    max_chars = settings.ollama_extract_max_chars
    if engine == "cloud":
        max_chars = max(max_chars, 8000)
    if len(conversation) > max_chars:
        conversation = conversation[:max_chars] + "\n...[truncated]"
    prompt = build_extraction_prompt(conversation, user_prompt_template)
    system = (system_prompt or EXTRACTION_SYSTEM).strip() or EXTRACTION_SYSTEM
    last_error: Optional[str] = None
    last_raw: Optional[str] = None
    for attempt in range(2):
        user_prompt = prompt if attempt == 0 else build_retry_prompt(conversation, last_error or "invalid JSON")
        predict = settings.ollama_extract_num_predict
        if attempt == 1:
            predict = max(predict, 450)
        try:
            raw = await _call_llm(
                user_prompt,
                system=system,
                engine=engine,
                num_predict=predict,
                temperature=0.0,
            )
        except (OllamaError, CloudLLMError) as exc:
            raise LLMError(str(exc)) from exc
        last_raw = raw
        try:
            data = _parse_json_response(raw)
            return _coerce_extracted(data)
        except (json.JSONDecodeError, ValidationError) as exc:
            last_error = str(exc)
            logger.warning(
                "Extraction validation failed (attempt %s, engine=%s): %s | raw_tail=%r",
                attempt + 1,
                engine,
                exc,
                (raw or "")[-180:],
            )

    raise LLMError(
        f"Failed to extract valid job JSON after retries: {last_error}. "
        f"Raw tail: {(last_raw or '')[-120:]!r}"
    )


async def classify_email(
    conversation: str,
    *,
    prompt_template: Optional[str] = None,
    extract_engine: Optional[str] = None,
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

    engine = resolve_extract_engine(extract_engine)
    try:
        raw = await _call_llm(
            prompt,
            system=CLASSIFY_SYSTEM,
            engine=engine,
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


async def _call_llm(
    prompt: str,
    *,
    system: str,
    engine: str = "local",
    num_predict: Optional[int] = None,
    temperature: float = 0.0,
    use_json_format: bool = True,
) -> str:
    if normalize_extract_engine(engine) == "cloud":
        if not cloud_configured():
            raise CloudLLMError("Cloud extract is not configured on the server.")
        return await call_cloud_chat(
            prompt,
            system=system,
            temperature=temperature,
            json_object=use_json_format,
            max_tokens=num_predict,
        )
    return await _call_ollama(
        prompt,
        system=system,
        num_predict=num_predict,
        temperature=temperature,
        use_json_format=use_json_format,
    )


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
            "Cannot connect to the on-server model. Check that the local AI service is running."
        ) from exc
    except httpx.ReadTimeout as exc:
        raise OllamaError(
            f"On-server model timed out after {settings.ollama_read_timeout_seconds}s. "
            "Retry, or switch Extract engine to Cloud in Settings."
        ) from exc
    except httpx.HTTPError as exc:
        raise OllamaError(f"On-server model HTTP error: {exc}") from exc
