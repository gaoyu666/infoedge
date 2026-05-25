from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request
from typing import Any

from app.core.config import settings


class GLMError(RuntimeError):
    pass


def glm_is_configured() -> bool:
    return bool(settings.glm_api_key.strip())


def _chat_completion_sync(
    *,
    messages: list[dict[str, str]],
    temperature: float = 0.4,
    max_tokens: int = 3000,
) -> dict[str, Any]:
    if not glm_is_configured():
        raise GLMError("GLM_API_KEY is not configured")

    base_url = settings.glm_base_url.rstrip("/")
    url = f"{base_url}/chat/completions"
    payload = {
        "model": settings.glm_model,
        "messages": messages,
        "temperature": temperature,
        "top_p": 0.8,
        "max_tokens": max_tokens,
        "stream": False,
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {settings.glm_api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=settings.glm_timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        raise GLMError(f"GLM HTTP {exc.code}: {body[:500]}") from exc
    except Exception as exc:
        raise GLMError(f"GLM request failed: {exc}") from exc


async def glm_chat_completion(
    *,
    messages: list[dict[str, str]],
    temperature: float = 0.4,
    max_tokens: int = 3000,
) -> dict[str, Any]:
    return await asyncio.to_thread(
        _chat_completion_sync,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )


def _extract_content(response: dict[str, Any]) -> str:
    try:
        return str(response["choices"][0]["message"]["content"])
    except (KeyError, IndexError, TypeError) as exc:
        raise GLMError("GLM response has no choices[0].message.content") from exc


def _parse_json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start < 0 or end <= start:
            raise
        value = json.loads(cleaned[start : end + 1])
    if not isinstance(value, dict):
        raise GLMError("GLM JSON response is not an object")
    return value


async def glm_json_completion(
    *,
    messages: list[dict[str, str]],
    temperature: float = 0.35,
    max_tokens: int = 3500,
) -> dict[str, Any]:
    response = await glm_chat_completion(
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return _parse_json_object(_extract_content(response))
