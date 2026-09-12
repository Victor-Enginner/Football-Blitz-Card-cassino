"""Router — LLM calls via OmniRoute (primary) with a generic OpenAI-compatible
provider slot (for 9route or any verified endpoint) as fallback.

Fail-closed: if no provider answers, returns an error — never fabricates output.
Secrets are read from env only and never logged.
"""
from __future__ import annotations

import json
import time
import urllib.request
import urllib.error
from typing import Any

from config import (
    REMOTE_LLM_ENABLED,
    OMNIROUTE_BASE_URL, OMNIROUTE_MODEL, OMNIROUTE_TIMEOUT_S, OMNIROUTE_API_KEY,
    TOKENROUTER_ENABLED, TOKENROUTER_BASE_URL, TOKENROUTER_MODEL, TOKENROUTER_API_KEY,
    NVIDIA_ENABLED, NVIDIA_BASE_URL, NVIDIA_MODEL, NVIDIA_API_KEY,
    AISA_ENABLED, AISA_BASE_URL, AISA_MODEL, AISA_API_KEY,
    GENERIC_PROVIDER_ENABLED, GENERIC_PROVIDER_BASE_URL, GENERIC_PROVIDER_MODEL,
    GENERIC_PROVIDER_API_KEY, GENERIC_PROVIDER_NAME,
)


class RouteResult(dict):
    @property
    def ok(self) -> bool:
        return bool(self.get("ok"))

    @property
    def provider(self) -> str:
        return str(self.get("provider", "none"))

    @property
    def content(self) -> str:
        return str(self.get("content", ""))


def _post_chat(url: str, api_key: str, model: str, messages: list[dict],
               timeout: float, provider: str, temperature: float = 0.2,
               max_tokens: int = 700) -> RouteResult:
    body = json.dumps({
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            **({"Authorization": f"Bearer {api_key}"} if api_key else {}),
        },
        method="POST",
    )
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            latency_ms = int((time.monotonic() - t0) * 1000)
            content = data["choices"][0]["message"]["content"]
            return RouteResult(ok=True, provider=provider, model=model,
                               content=content, latency_ms=latency_ms)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:300]
        return RouteResult(ok=False, provider=provider, error=f"HTTP {e.code}: {detail}")
    except Exception as e:
        return RouteResult(ok=False, provider=provider, error=f"{type(e).__name__}: {e}")


def route_chat(messages: list[dict], temperature: float = 0.2,
               max_tokens: int = 700, timeout: float | None = None) -> RouteResult:
    """Try providers in order:
    OmniRoute -> TokenRouter (free) -> NVIDIA NIM (free) -> AIsa -> generic slot.
    Fail closed."""
    if not REMOTE_LLM_ENABLED:
        return RouteResult(
            ok=False, provider="none",
            error="remote LLM disabled: configure and validate a free remote provider before enabling FB_REMOTE_LLM_ENABLED",
        )
    errors: list[str] = []

    # 1) OmniRoute primary
    r = _post_chat(
        f"{OMNIROUTE_BASE_URL}/v1/chat/completions",
        OMNIROUTE_API_KEY, OMNIROUTE_MODEL, messages,
        timeout or OMNIROUTE_TIMEOUT_S, provider="omniroute",
        temperature=temperature, max_tokens=max_tokens,
    )
    if r.ok:
        return r
    errors.append(f"omniroute: {r.get('error')}")

    # 2) TokenRouter (free tier)
    if TOKENROUTER_ENABLED and TOKENROUTER_API_KEY:
        r = _post_chat(
            f"{TOKENROUTER_BASE_URL}/v1/chat/completions",
            TOKENROUTER_API_KEY, TOKENROUTER_MODEL, messages,
            timeout or OMNIROUTE_TIMEOUT_S, provider="tokenrouter",
            temperature=temperature, max_tokens=max_tokens,
        )
        if r.ok:
            return r
        errors.append(f"tokenrouter: {r.get('error')}")

    # 3) NVIDIA NIM (free tier)
    if NVIDIA_ENABLED and NVIDIA_API_KEY:
        r = _post_chat(
            f"{NVIDIA_BASE_URL}/v1/chat/completions",
            NVIDIA_API_KEY, NVIDIA_MODEL, messages,
            timeout or OMNIROUTE_TIMEOUT_S, provider="nvidia",
            temperature=temperature, max_tokens=max_tokens,
        )
        if r.ok:
            return r
        errors.append(f"nvidia: {r.get('error')}")

    # 4) AIsa (verified, OpenAI-compatible)
    if AISA_ENABLED and AISA_API_KEY:
        r = _post_chat(
            f"{AISA_BASE_URL}/v1/chat/completions",
            AISA_API_KEY, AISA_MODEL, messages,
            timeout or OMNIROUTE_TIMEOUT_S, provider="aisa",
            temperature=temperature, max_tokens=max_tokens,
        )
        if r.ok:
            return r
        errors.append(f"aisa: {r.get('error')}")

    # 5) generic slot (9route or any verified OpenAI-compatible endpoint)
    if GENERIC_PROVIDER_ENABLED and GENERIC_PROVIDER_BASE_URL and GENERIC_PROVIDER_MODEL:
        r = _post_chat(
            f"{GENERIC_PROVIDER_BASE_URL}/v1/chat/completions",
            GENERIC_PROVIDER_API_KEY, GENERIC_PROVIDER_MODEL, messages,
            timeout or OMNIROUTE_TIMEOUT_S, provider=GENERIC_PROVIDER_NAME,
            temperature=temperature, max_tokens=max_tokens,
        )
        if r.ok:
            return r
        errors.append(f"{GENERIC_PROVIDER_NAME}: {r.get('error')}")

    return RouteResult(ok=False, provider="none",
                       error="all providers failed", detail="; ".join(errors))
