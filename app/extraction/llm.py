"""Ollama LLM wrapper for structured extraction."""

import json
import logging
from typing import Optional

import httpx
from pydantic import ValidationError

from app.config import get_settings
from app.extraction.prompt import build_extraction_prompt, build_retry_prompt
from app.extraction.schema import ExtractedJob

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


async def extract_job_from_thread(conversation: str) -> ExtractedJob:
    settings = get_settings()
    if len(conversation) > settings.ollama_max_thread_chars:
        conversation = conversation[: settings.ollama_max_thread_chars] + "\n...[truncated]"
    prompt = build_extraction_prompt(conversation)
    last_error: Optional[str] = None

    for attempt in range(2):
        user_prompt = prompt if attempt == 0 else build_retry_prompt(conversation, last_error or "invalid JSON")
        raw = await _call_ollama(user_prompt)
        try:
            data = _parse_json_response(raw)
            return ExtractedJob.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as exc:
            last_error = str(exc)
            logger.warning("Extraction validation failed (attempt %s): %s", attempt + 1, exc)

    raise OllamaError(f"Failed to extract valid job JSON after retries: {last_error}")


async def _call_ollama(prompt: str) -> str:
    settings = get_settings()
    url = f"{settings.ollama_base_url.rstrip('/')}/api/chat"
    payload = {
        "model": settings.ollama_model,
        "messages": [
            {"role": "system", "content": "You are a precise data extraction assistant."},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0.1,
            "num_predict": 800,
        },
    }

    read_timeout = float(settings.ollama_read_timeout_seconds)
    timeout = httpx.Timeout(connect=10.0, read=read_timeout, write=30.0, pool=10.0)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            body = response.json()
    except httpx.ConnectError as exc:
        raise OllamaError(
            "Cannot connect to Ollama. Run: systemctl start ollama && ollama pull qwen2.5:7b-instruct"
        ) from exc
    except httpx.ReadTimeout as exc:
        raise OllamaError(
            f"Ollama timed out after {settings.ollama_read_timeout_seconds}s. "
            "CPU inference is slow — retry, or use a smaller model: ollama pull qwen2.5:3b-instruct"
        ) from exc

    message = body.get("message", {})
    content = message.get("content", "")
    if not content:
        raise OllamaError("Empty response from Ollama")
    return content
