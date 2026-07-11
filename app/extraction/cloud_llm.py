"""Hosted chat-completions client for optional cloud extract.

User-facing copy should say "cloud" / "on-server" only.
"""

from __future__ import annotations

import logging
from typing import Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


class CloudLLMError(Exception):
    pass


def cloud_configured() -> bool:
    settings = get_settings()
    return bool((settings.cloud_llm_api_key or "").strip())


async def call_cloud_chat(
    prompt: str,
    *,
    system: str = "You are a precise data extraction assistant.",
    temperature: float = 0.0,
    json_object: bool = True,
    max_tokens: Optional[int] = None,
) -> str:
    settings = get_settings()
    key = (settings.cloud_llm_api_key or "").strip()
    if not key:
        raise CloudLLMError("Cloud extract is not configured on the server.")

    base = (settings.cloud_llm_base_url or "").rstrip("/")
    url = f"{base}/chat/completions"
    payload: dict = {
        "model": settings.cloud_llm_model,
        "temperature": temperature,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
    }
    if max_tokens:
        payload["max_tokens"] = max_tokens
    if json_object:
        payload["response_format"] = {"type": "json_object"}

    timeout = float(settings.cloud_llm_timeout_seconds)
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(15.0, read=timeout)) as client:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code >= 400:
                detail = (resp.text or "")[:240]
                raise CloudLLMError(f"Cloud extract failed ({resp.status_code}): {detail}")
            data = resp.json()
            choices = data.get("choices") or []
            if not choices:
                raise CloudLLMError("Cloud extract returned no choices.")
            content = (choices[0].get("message") or {}).get("content") or ""
            if not content.strip():
                raise CloudLLMError("Cloud extract returned empty content.")
            return content
    except CloudLLMError:
        raise
    except httpx.TimeoutException as exc:
        raise CloudLLMError(f"Cloud extract timed out after {settings.cloud_llm_timeout_seconds}s.") from exc
    except httpx.HTTPError as exc:
        raise CloudLLMError(f"Cloud extract network error: {exc}") from exc
