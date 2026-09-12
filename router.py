"""Router — LLM via 9Router (primary) com cache + compressão + fallback em cadeia.

Ordem: 9Router (auto: subscription→cheap→free) -> TokenRouter (free) ->
NVIDIA NIM (free) -> AIsa -> generic slot. OmniRoute legado mantido como alias.

Fail-closed: se ninguém responder, erro — nunca inventa saída.
Tudo fora do PC: 9Router é processo leve local (~150MB) mas a inferência é
100% nuvem. Compressão RTK-style ANTES de enviar + cache DEPOIS de receber.
"""
from __future__ import annotations

import hashlib
import json
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any

from config import (
    REMOTE_LLM_ENABLED,
    NINEROUTER_ENABLED, NINEROUTER_BASE_URL, NINEROUTER_MODEL,
    NINEROUTER_TIMEOUT_S, NINEROUTER_API_KEY,
    LLM_CACHE_ENABLED, LLM_CACHE_TTL_S, LLM_USAGE_LOG,
    OMNIROUTE_BASE_URL, OMNIROUTE_MODEL, OMNIROUTE_TIMEOUT_S, OMNIROUTE_API_KEY,
    TOKENROUTER_ENABLED, TOKENROUTER_BASE_URL, TOKENROUTER_MODEL, TOKENROUTER_API_KEY,
    NVIDIA_ENABLED, NVIDIA_BASE_URL, NVIDIA_MODEL, NVIDIA_API_KEY,
    AISA_ENABLED, AISA_BASE_URL, AISA_MODEL, AISA_API_KEY,
    GENERIC_PROVIDER_ENABLED, GENERIC_PROVIDER_BASE_URL, GENERIC_PROVIDER_MODEL,
    GENERIC_PROVIDER_API_KEY, GENERIC_PROVIDER_NAME,
    COMPRESSION_ENABLED, COMPRESSION_TARGET_RATIO, COMPRESSION_MIN_CHARS,
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


# --- cache em disco (0 tokens em repetição) ----------------------------------
_CACHE: dict[str, dict] = {}


def _cache_key(model: str, messages: list[dict]) -> str:
    canon = json.dumps({"m": model, "msg": messages}, sort_keys=True,
                       ensure_ascii=False)
    return hashlib.sha256(canon.encode()).hexdigest()[:24]


def _usage_log(entry: dict) -> None:
    """Observabilidade: cada chamada LLM vira 1 linha JSONL (custo/latência)."""
    try:
        p = Path(LLM_USAGE_LOG)
        if not p.is_absolute():
            from config import DATA_DIR
            p = DATA_DIR / p.name
        p.parent.mkdir(parents=True, exist_ok=True)
        entry["ts"] = time.time()
        with open(p, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass


def compress_messages(messages: list[dict]) -> tuple[list[dict], dict]:
    """Compressão RTK-style ANTES de enviar: corta 20-65% dos tokens de entrada."""
    if not COMPRESSION_ENABLED:
        return messages, {"enabled": False, "ratio": 1.0}
    try:
        from compression import compress_text
    except ImportError:
        return messages, {"enabled": False, "ratio": 1.0}
    out, total_o, total_c = [], 0, 0
    for m in messages:
        c = m.get("content", "")
        total_o += len(c)
        if len(c) >= COMPRESSION_MIN_CHARS:
            c, _ = compress_text(c, COMPRESSION_MIN_CHARS)
        total_c += len(c)
        out.append({**m, "content": c})
    ratio = round(total_c / max(1, total_o), 3)
    return out, {"enabled": True, "ratio": ratio,
                 "original_chars": total_o, "compressed_chars": total_c}


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
    """Tenta em ordem: 9Router -> TokenRouter -> NVIDIA -> AIsa -> genérico.
    Com compressão + cache + log de uso. Fail closed."""
    if not REMOTE_LLM_ENABLED:
        return RouteResult(
            ok=False, provider="none",
            error="remote LLM disabled: configure and validate a free remote provider before enabling FB_REMOTE_LLM_ENABLED",
        )
    errors: list[str] = []

    # compressão ANTES (economia de tokens de entrada)
    messages, comp = compress_messages(messages)

    # cache (0 tokens se repetido dentro do TTL)
    ckey = _cache_key(NINEROUTER_MODEL, messages)
    if LLM_CACHE_ENABLED and ckey in _CACHE:
        hit = _CACHE[ckey]
        if time.time() - hit["ts"] < LLM_CACHE_TTL_S:
            _usage_log({"provider": hit["provider"], "cached": True,
                        "compression": comp})
            return RouteResult(ok=True, provider=hit["provider"],
                               model=hit["model"], content=hit["content"],
                               latency_ms=0, cached=True, compression=comp)

    def _try(url: str, key: str, model: str, name: str) -> RouteResult | None:
        r = _post_chat(url, key, model, messages,
                       timeout or NINEROUTER_TIMEOUT_S, provider=name,
                       temperature=temperature, max_tokens=max_tokens)
        if r.ok:
            if LLM_CACHE_ENABLED:
                _CACHE[ckey] = {"ts": time.time(), "provider": name,
                                "model": model, "content": r.content}
            _usage_log({"provider": name, "model": model, "cached": False,
                        "latency_ms": r.get("latency_ms"), "compression": comp})
            r["compression"] = comp
            return r
        errors.append(f"{name}: {r.get('error')}")
        _usage_log({"provider": name, "error": r.get("error")})
        return None

    # 1) 9Router PRIMARY (3-tier: subscription→cheap→free, RTK/Caveman dentro)
    if NINEROUTER_ENABLED:
        r = _try(f"{NINEROUTER_BASE_URL}/v1/chat/completions",
                 NINEROUTER_API_KEY, NINEROUTER_MODEL, "9router")
        if r:
            return r

    # 1b) OmniRoute legado (mesmo endereço local, se ainda existir)
    if OMNIROUTE_BASE_URL != NINEROUTER_BASE_URL or OMNIROUTE_MODEL != NINEROUTER_MODEL:
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
        r = _try(f"{TOKENROUTER_BASE_URL}/v1/chat/completions",
                 TOKENROUTER_API_KEY, TOKENROUTER_MODEL, "tokenrouter")
        if r:
            return r

    # 3) NVIDIA NIM (free tier)
    if NVIDIA_ENABLED and NVIDIA_API_KEY:
        r = _try(f"{NVIDIA_BASE_URL}/v1/chat/completions",
                 NVIDIA_API_KEY, NVIDIA_MODEL, "nvidia")
        if r:
            return r

    # 4) AIsa (verified, OpenAI-compatible)
    if AISA_ENABLED and AISA_API_KEY:
        r = _try(f"{AISA_BASE_URL}/v1/chat/completions",
                 AISA_API_KEY, AISA_MODEL, "aisa")
        if r:
            return r

    # 5) generic slot (9route ou outro endpoint OpenAI-compatible)
    if GENERIC_PROVIDER_ENABLED and GENERIC_PROVIDER_BASE_URL and GENERIC_PROVIDER_MODEL:
        r = _try(f"{GENERIC_PROVIDER_BASE_URL}/v1/chat/completions",
                 GENERIC_PROVIDER_API_KEY, GENERIC_PROVIDER_MODEL,
                 GENERIC_PROVIDER_NAME)
        if r:
            return r

    return RouteResult(ok=False, provider="none",
                       error="all providers failed", detail="; ".join(errors))
