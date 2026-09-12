"""Governed AI Copilot.

Hard rules (from the spec, non-negotiable):
  - can summarize sessions, find inconsistencies, explain metrics;
  - can NOT decide or execute bets, raise stakes, recover losses, bypass limits;
  - output outside the JSON schema is discarded;
  - every answer cites internal sources (RAG provenance);
  - neutral tone: never promises profit, never urgency language.
"""
from __future__ import annotations

import json
import re
from typing import Any

from rag import RAGIndex
from router import route_chat
import config as config_mod

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["summary", "observations", "caveats", "sources"],
    "properties": {
        "summary": {"type": "string", "maxLength": 1200},
        "observations": {"type": "array", "items": {"type": "string"}, "maxItems": 8},
        "caveats": {"type": "array", "items": {"type": "string"}, "maxItems": 6},
        "sources": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["source"],
                "properties": {"source": {"type": "string"}, "line": {"type": "integer"}},
            },
        },
    },
}

FORBIDDEN_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in (
        r"garantid[oa]s?", r"garanteed", r"garantia de (lucro|ganho)",
        r"entrada certa", r"sinal certeiro",
        r"recuperar (o )?preju[ií]zo", r"recover losses", r"aposte agora",
        r"bet now", r"pr[oó]xima entrada (vai|ir[aá])", r"100% (de )?acerto",
        r"win guaranteed", r"sure (win|bet|thing)",
    )
]

SYSTEM_PROMPT = """You are the analytics copilot of a casino-game OBSERVATION system.
You describe historical data only. You never predict outcomes, never recommend bets,
never promise profit, never use urgency language. You always cite the internal
sources given to you. Respond ONLY with a JSON object matching:
{"summary": str, "observations": [str], "caveats": [str], "sources": [{"source": str, "line": int}]}
Write the summary in Brazilian Portuguese. Be neutral and brief."""


def _redact(text: str) -> str:
    """Strip tokens/secrets patterns before anything leaves the process."""
    patterns = [
        re.compile(r"\b\d{8,10}:[A-Za-z0-9_-]{30,}\b"),        # telegram-style tokens
        re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),               # api keys
        re.compile(r"\bBearer\s+[A-Za-z0-9._-]{15,}\b"),
        re.compile(r"\b[0-9a-f]{64}\b"),                        # raw sha256
    ]
    for p in patterns:
        text = p.sub("[REDACTED]", text)
    return text


def validate_output(obj: Any) -> dict | None:
    """Manual JSON-Schema validation (subset) — discard anything out of schema."""
    if not isinstance(obj, dict):
        return None
    required = {"summary", "observations", "caveats", "sources"}
    if not required.issubset(obj.keys()):
        return None
    if not isinstance(obj["summary"], str) or not obj["summary"]:
        return None
    for k in ("observations", "caveats", "sources"):
        if not isinstance(obj[k], list):
            return None
    clean_sources = []
    for s in obj["sources"]:
        if isinstance(s, dict) and isinstance(s.get("source"), str):
            clean_sources.append({"source": s["source"], "line": int(s.get("line") or 0)})
    if not clean_sources:
        return None
    return {
        "summary": obj["summary"][:1200],
        "observations": [str(x) for x in obj["observations"]][:8],
        "caveats": [str(x) for x in obj["caveats"]][:6],
        "sources": clean_sources,
    }


def violates_tone(text: str) -> bool:
    return any(p.search(text) for p in FORBIDDEN_PATTERNS)


class Copilot:
    def __init__(self, rag: RAGIndex):
        self.rag = rag

    def summarize_session(self, question: str, session_stats: dict) -> dict:
        """Full governed pipeline: retrieve -> compress -> LLM -> validate -> answer.
        Fails closed: if AI is disabled or output invalid, returns local-only answer."""
        context, comp_report = self.rag.retrieve_compressed(question, k=6)

        if not config_mod.AI_COPILOT_ENABLED:
            return {
                "summary": "AI copilot disabled (FB_AI_COPILOT=false). Local stats only.",
                "observations": [f"Total events: {session_stats.get('total_events', 0)}"],
                "caveats": ["Descriptive statistics only — no prediction possible."],
                "sources": [{"source": "local:stats", "line": 0}],
                "meta": {"ai": False, "compression": comp_report},
            }

        ctx_block = "\n---\n".join(
            f"[{c['source']}:{c.get('line', 0)}] {c['text']}" for c in context
        )
        stats_block = json.dumps(session_stats, ensure_ascii=False)[:1500]
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content":
                f"Question: {question}\n\nLocal session stats (JSON): {stats_block}\n\n"
                f"Internal context chunks:\n{ctx_block[:6000]}"},
        ]
        result = route_chat(messages, temperature=0.1, max_tokens=800)
        if not result.ok:
            return {
                "summary": "AI unavailable — local answer only.",
                "observations": [f"Router error: {_redact(result.get('detail', result.get('error', '')))[:200]}"],
                "caveats": ["System fails closed: no AI output was used."],
                "sources": [{"source": "local:stats", "line": 0}],
                "meta": {"ai": False, "compression": comp_report},
            }

        raw = result.content.strip()
        # extract JSON object even if wrapped in ```json fences; one retry —
        # small free models occasionally answer non-JSON (e.g. bare "None")
        # or drop required schema fields
        obj = None
        reason = "AI output had no JSON object"
        for attempt in range(2):
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            parsed = None
            if m:
                try:
                    parsed = json.loads(m.group(0))
                except json.JSONDecodeError:
                    reason = "AI output was not valid JSON"
            if parsed is not None:
                if validate_output(parsed) is not None:
                    obj = parsed
                    break
                reason = "AI output failed schema validation — discarded"
            if attempt == 0:
                retry = route_chat(messages, temperature=0.1, max_tokens=800)
                if retry.ok:
                    raw = retry.content.strip()
                    continue
            break

        if obj is None:
            return self._reject(reason, comp_report)

        validated = validate_output(obj)
        if validated is None:
            return self._reject("AI output failed schema validation — discarded", comp_report)
        joined = json.dumps(validated, ensure_ascii=False)
        if violates_tone(joined):
            return self._reject("AI output violated neutral-tone policy — discarded", comp_report)

        validated["meta"] = {
            "ai": True,
            "provider": result.provider,
            "latency_ms": result.get("latency_ms"),
            "compression": comp_report,
        }
        return validated

    @staticmethod
    def _reject(reason: str, comp_report: dict) -> dict:
        return {
            "summary": "AI response discarded by governance pipeline.",
            "observations": [reason],
            "caveats": ["All AI output is schema-validated and tone-checked before display."],
            "sources": [{"source": "local:governance", "line": 0}],
            "meta": {"ai": False, "compression": comp_report},
        }
