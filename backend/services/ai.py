from __future__ import annotations

from dataclasses import dataclass
import http.client
import json
from collections.abc import Iterator
from typing import Any
import urllib.error
import urllib.request
import ssl

try:
    import certifi
except ImportError:  # pragma: no cover
    certifi = None

from config import settings
from services.prompts import build_ajin_messages, build_ask_messages


class AIClientError(RuntimeError):
    pass


@dataclass(frozen=True)
class AIResult:
    text: str
    raw: dict[str, Any]


def _open_request(request: urllib.request.Request):
    ssl_context = None
    if request.full_url.lower().startswith("https://") and certifi is not None:
        ssl_context = ssl.create_default_context(cafile=certifi.where())
    if settings.ai_use_env_proxy:
        return urllib.request.urlopen(
            request, timeout=settings.ai_timeout_seconds, context=ssl_context
        )
    handlers = [urllib.request.ProxyHandler({})]
    if ssl_context is not None:
        handlers.append(urllib.request.HTTPSHandler(context=ssl_context))
    return urllib.request.build_opener(*handlers).open(
        request,
        timeout=settings.ai_timeout_seconds,
    )


def _build_payload(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    temperature: float | None = None,
    top_p: float | None = None,
    max_tokens: int | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model or settings.ai_model,
        "messages": messages,
    }
    if settings.ai_thinking_disabled:
        payload["thinking"] = {"type": "disabled"}
    if temperature is not None:
        payload["temperature"] = temperature
    elif settings.ai_temperature is not None:
        payload["temperature"] = settings.ai_temperature
    if top_p is not None:
        payload["top_p"] = top_p
    elif settings.ai_top_p is not None:
        payload["top_p"] = settings.ai_top_p
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    return payload


def _extract_text(raw: dict[str, Any]) -> str:
    choices = raw.get("choices") or []
    if not choices:
        return ""

    message = (choices[0] or {}).get("message") or {}
    content = message.get("content", "")
    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text") or item.get("content") or ""
                if text:
                    parts.append(str(text))
        return "".join(parts).strip()

    return str(content).strip()


def _extract_stream_delta(raw: dict[str, Any]) -> str:
    choices = raw.get("choices") or []
    if not choices:
        return ""

    delta = (choices[0] or {}).get("delta") or {}
    content = delta.get("content", "")
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text") or item.get("content") or ""
                if text:
                    parts.append(str(text))
        return "".join(parts)

    return str(content) if content else ""


def chat_completions(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    temperature: float | None = None,
    top_p: float | None = None,
    max_tokens: int | None = None,
) -> AIResult:
    if not settings.ai_api_key:
        raise AIClientError("AI_API_KEY is missing")

    payload = _build_payload(
        messages,
        model=model,
        temperature=temperature,
        top_p=top_p,
        max_tokens=max_tokens,
    )

    request = urllib.request.Request(
        settings.ai_chat_completions_url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.ai_api_key}",
        },
        method="POST",
    )

    try:
        with _open_request(request) as response:
            raw_text = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="ignore")
        raise AIClientError(f"AI API returned HTTP {exc.code}: {details or exc.reason}") from exc
    except (TimeoutError, urllib.error.URLError, OSError, http.client.HTTPException, http.client.IncompleteRead) as exc:
        raise AIClientError(f"AI API request failed: {getattr(exc, 'reason', str(exc))}") from exc

    try:
        raw = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise AIClientError(f"AI API returned invalid JSON: {raw_text[:500]}") from exc

    text = _extract_text(raw)
    return AIResult(text=text, raw=raw)


def stream_chat_completions(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    temperature: float | None = None,
    top_p: float | None = None,
    max_tokens: int | None = None,
) -> Iterator[str]:
    if not settings.ai_api_key:
        raise AIClientError("AI_API_KEY is missing")

    payload = _build_payload(
        messages,
        model=model,
        temperature=temperature,
        top_p=top_p,
        max_tokens=max_tokens,
    )
    payload["stream"] = True

    request = urllib.request.Request(
        settings.ai_chat_completions_url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.ai_api_key}",
        },
        method="POST",
    )

    try:
        with _open_request(request) as response:
            for raw_line in response:
                line = raw_line.decode("utf-8", errors="ignore").strip()
                if not line or not line.startswith("data:"):
                    continue

                data = line[len("data:") :].strip()
                if data == "[DONE]":
                    break

                try:
                    chunk = json.loads(data)
                except json.JSONDecodeError:
                    continue

                text = _extract_stream_delta(chunk)
                if text:
                    yield text
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="ignore")
        raise AIClientError(f"AI API returned HTTP {exc.code}: {details or exc.reason}") from exc
    except (TimeoutError, urllib.error.URLError, OSError, http.client.HTTPException, http.client.IncompleteRead) as exc:
        raise AIClientError(f"AI API request failed: {getattr(exc, 'reason', str(exc))}") from exc


def ask(
    question: str,
    *,
    context: str | dict[str, Any] | None = None,
    history: list[dict[str, str]] | None = None,
    model: str | None = None,
    max_tokens: int | None = None,
) -> AIResult:
    messages = build_ask_messages(question, context=context, history=history)
    return chat_completions(messages, model=model, max_tokens=max_tokens)


def ask_ajin(
    question: str,
    *,
    history: list[dict[str, str]] | None = None,
    model: str | None = None,
    max_tokens: int | None = None,
) -> AIResult:
    messages = build_ajin_messages(question, history=history)
    return chat_completions(messages, model=model, max_tokens=max_tokens)


def stream_ask(
    question: str,
    *,
    context: str | dict[str, Any] | None = None,
    history: list[dict[str, str]] | None = None,
    model: str | None = None,
) -> Iterator[str]:
    messages = build_ask_messages(question, context=context, history=history)
    return stream_chat_completions(messages, model=model)
