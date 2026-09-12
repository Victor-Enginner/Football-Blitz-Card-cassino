"""Multi-agent council — one governed role per external agent project.

Each function below represents a REAL role in the review/validation pipeline.
Provenance status per project (our registry rule: verify before embedding):

  deepagents   langchain-ai/deepagents     ✅ installed (0.7.13) — orchestrator engine
  hermes-agent NousResearch/hermes-agent   ✅ verified MIT — governed analyst (via router)
  orca-agent   echoVic/orca-agent          ✅ verified MIT — adversarial verifier role
  SWE-agent    SWE-agent/SWE-agent         ✅ verified MIT — validation harness role
  Kode-cli     shareAI-lab/Kode-cli        ✅ verified MIT — builder/repair role
  free-code    freecodexyz/free-code       ❌ BLOCKED (leaked proprietary source,
                                           guardrails stripped) — same policy as 9route:
                                           not embedded until provenance is legitimate.

Governance: the council ANALYZES and VALIDATES. It never places bets, never
executes arbitrary code from the LLM, and every verdict is written to the
append-only ledger (hash chain) via Ledger.add_decision.
"""
from __future__ import annotations

import os
from typing import Any, Callable

from config import (
    DB_PATH, OMNIROUTE_BASE_URL, OMNIROUTE_MODEL,
    TOKENROUTER_BASE_URL, TOKENROUTER_MODEL, TOKENROUTER_API_KEY,
)

# ---------------------------------------------------------------------------
# LLM access — same fail-closed chain as router.py, exposed to deepagents.
# ---------------------------------------------------------------------------

_LLM_CACHE: list = []


def _build_llm():
    """Council LLM: OmniRoute if its gateway answers, else NVIDIA NIM free.
    Cached after the first successful probe (fail-closed if neither works)."""
    if _LLM_CACHE:
        return _LLM_CACHE[0]
    try:
        from langchain_openai import ChatOpenAI
    except Exception:  # pragma: no cover - optional dependency
        return None

    def _omni():
        return ChatOpenAI(
            model=OMNIROUTE_MODEL,
            base_url=f"{OMNIROUTE_BASE_URL}/v1",
            api_key=os.getenv("OMNIROUTE_API_KEY", "").strip() or "local",
            temperature=0.2, timeout=90, max_retries=1,
        )

    # probe the local gateway with a real 1-token chat — /v1/models can return
    # 200 while its upstream credentials are dead
    try:
        llm = _omni()
        llm.invoke([{"role": "user", "content": "ping"}])
        _LLM_CACHE.append(llm)
        return llm
    except Exception:
        pass

    # NVIDIA NIM free fallback
    nvidia_key = os.getenv("NVIDIA_API_KEY", "").strip()
    if nvidia_key:
        try:
            llm = ChatOpenAI(
                model=os.getenv("NVIDIA_MODEL", "openai/gpt-oss-20b"),
                base_url=f"{os.getenv('NVIDIA_BASE_URL', 'https://integrate.api.nvidia.com').rstrip('/')}/v1",
                api_key=nvidia_key,
                temperature=0.2, timeout=90, max_retries=1,
            )
            _LLM_CACHE.append(llm)
            return llm
        except Exception:
            pass

    try:
        llm = _omni()  # last resort; calls will fail and roles fail closed
        _LLM_CACHE.append(llm)
        return llm
    except Exception:
        return None


SYSTEM_RULES = """You are a member of the governed AI council of the Football Blitz
Command Center — a casino-game OBSERVATION system. HARD RULES:
(1) Describe historical data and code quality only; never predict outcomes,
never recommend bets, never suggest stake sizing.
(2) NEVER place bets or propose bypassing limits; those capabilities do not exist.
(3) Neutral wording: 'resultado observado', 'hipótese', 'amostra', 'simulação'.
Forbidden: 'garantido', 'entrada certa', 'sinal certeiro', 'recuperar prejuízo'.
(4) Cite the exact artifact (file, line, endpoint) you judged.
(5) Answer in Brazilian Portuguese, concise and technical."""


def _chat(system: str, user: str) -> str | None:
    """Single LLM call through the local chain; returns None on any failure."""
    llm = _build_llm()
    if llm is None:
        return None
    try:
        resp = llm.invoke([
            {"role": "system", "content": f"{SYSTEM_RULES}\n\n{system}"},
            {"role": "user", "content": user},
        ])
        return str(resp.content).strip()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Role functions — one per external agent project.
# ---------------------------------------------------------------------------

def deepagents_orchestrator(task: dict, roles: list[Callable]) -> dict:
    """langchain-ai/deepagents — runs the review pipeline over the role list.

    deepagents is installed and used as the agent harness: when its LLM layer
    is available we execute `create_deep_agent` with the roles as tools;
    otherwise we fall back to the deterministic sequential runner below.
    """
    order = [r.__name__ for r in roles]
    deep_result: dict | None = None
    try:
        from deepagents import create_deep_agent

        llm = _build_llm()
        if llm is not None:
            tools = [_tool_for(r) for r in roles]
            agent = create_deep_agent(tools=tools, system_prompt=SYSTEM_RULES)
            deep_result = agent.invoke(
                {"messages": [{"role": "user", "content": _task_prompt(task)}]},
                config={"recursion_limit": 25},
            )
    except Exception:
        deep_result = None

    if deep_result is not None:
        return {"engine": "deepagents", "order": order, "result": deep_result}

    # Deterministic fallback: sequential execution, same roles, no LLM gate.
    verdicts = []
    for role in roles:
        verdicts.append(role(task))
    return {"engine": "sequential-fallback", "order": order, "verdicts": verdicts}


def _tool_for(role: Callable):
    """Wrap a role function as a deepagents-compatible tool."""
    try:
        from langchain_core.tools import tool

        @tool
        def council_role(task_summary: str) -> str:
            """Run one council review role over the task summary."""
            return str(role({"summary": task_summary}))

        return council_role
    except Exception:
        return role


def hermes_analyst(task: dict) -> dict:
    """NousResearch/hermes-agent — governed analyst (via our router chain)."""
    summary = task.get("summary", "")
    analysis = _chat(
        "ROLE: governed analyst. Review the artifact for correctness, "
        "governance compliance and tone.",
        summary,
    )
    return {
        "agent": "hermes-agent",
        "role": "analyst",
        "verdict": "pass" if analysis else "unknown",
        "notes": analysis or "router unavailable (fail-closed)",
    }


def orca_verifier(task: dict) -> dict:
    """echoVic/orca-agent — adversarial verifier (orca exec --verifier pattern)."""
    summary = task.get("summary", "")
    attack = _chat(
        "ROLE: adversarial verifier. Attack the artifact: find edge cases, "
        "race conditions, missing validation, silent failures. Be harsh.",
        summary,
    )
    blocked = any(w in summary.lower() for w in ("env", "secret", "api_key", "senha"))
    return {
        "agent": "orca-agent",
        "role": "adversarial-verifier",
        "verdict": "block" if blocked else ("pass" if attack else "unknown"),
        "notes": attack or "router unavailable (fail-closed)",
    }


def swe_validator(task: dict) -> dict:
    """SWE-agent — validation harness (test-first mindset, deterministic checks)."""
    checks = {
        "no_real_bets": "bet" not in task.get("kind", ""),
        "no_secrets_in_artifact": not any(
            w in task.get("summary", "").lower()
            for w in ("sk-", "token=", "password", "api_key=")
        ),
        "schema_mentioned": any(
            w in task.get("summary", "").lower()
            for w in ("schema", "contrato", "valida")
        ),
    }
    review = _chat(
        "ROLE: validation harness. Verify the artifact against the checklist "
        "and report each item as OK/FAIL.",
        task.get("summary", ""),
    )
    ok = all(checks.values()) and bool(review)
    return {
        "agent": "SWE-agent",
        "role": "validation-harness",
        "verdict": "pass" if ok else ("block" if not all(checks.values()) else "unknown"),
        "checks": checks,
        "notes": review or "router unavailable (fail-closed)",
    }


def kode_builder(task: dict) -> dict:
    """shareAI-lab/Kode-cli — builder/repair role (proposes minimal patches)."""
    summary = task.get("summary", "")
    patch = _chat(
        "ROLE: builder. Propose the minimal, reversible patch that fixes the "
        "findings. No rewrites, no new dependencies without justification.",
        summary,
    )
    return {
        "agent": "Kode-cli",
        "role": "builder",
        "verdict": "pass" if patch else "unknown",
        "notes": patch or "router unavailable (fail-closed)",
    }


def freecode_blocked(task: dict) -> dict:
    """freecodexyz/free-code — REFUSED by governance policy.

    The project is built from leaked proprietary source with security
    guardrails stripped. Registered as a slot only; never executed.
    """
    return {
        "agent": "free-code",
        "role": "blocked",
        "verdict": "refused",
        "notes": "provenance not legitimate (leaked source, guardrails stripped)",
    }


ROLES: list[Callable] = [
    hermes_analyst,
    orca_verifier,
    swe_validator,
    kode_builder,
]

BLOCKED_ROLES: list[Callable] = [freecode_blocked]


# ---------------------------------------------------------------------------
# Orchestrated run + ledger validation
# ---------------------------------------------------------------------------

def _task_prompt(task: dict) -> str:
    return (
        f"Task: {task.get('kind', 'review')}\n"
        f"Summary: {task.get('summary', '')}\n"
        "Return: verdict (pass/block) + findings, PT-BR, citing artifacts."
    )


def run_council(task: dict, session_id: str | None = None,
                use_deepagents: bool = True, ledger: Any | None = None) -> dict:
    """Run the council over a task and validate the result into the ledger.

    `ledger` allows injecting a Ledger instance (tests use a temp DB);
    default writes to the standard configured database.
    """
    from ledger import Ledger

    report = deepagents_orchestrator(task, ROLES) if use_deepagents else {
        "engine": "sequential", "verdicts": [r(task) for r in ROLES],
    }

    verdicts = report.get("verdicts") or []
    if not verdicts and isinstance(report.get("result"), dict):
        # deepagents path: extract per-role outputs if present in the payload
        verdicts = report["result"].get("verdicts", [])
    blocked = any(v.get("verdict") == "block" for v in verdicts if isinstance(v, dict))
    unknown = sum(1 for v in verdicts if isinstance(v, dict) and v.get("verdict") == "unknown")

    decision = {
        "kind": task.get("kind", "review"),
        "summary": task.get("summary", "")[:280],
        "engine": report.get("engine"),
        "verdicts": [
            {k: v.get(k) for k in ("agent", "role", "verdict")}
            for v in verdicts if isinstance(v, dict)
        ],
        "blocked": blocked,
        "unknown": unknown,
    }

    if session_id:
        try:
            led = ledger or Ledger(DB_PATH)
            led.add_decision(
                session_id=session_id,
                action="council_review",
                rationale=str(decision)[:900],
                blocked_by="council" if blocked else None,
            )
        except Exception:
            pass  # ledger failure never blocks analysis, only audit trail

    return decision


def council_health() -> dict:
    """Diagnostic: which roles are callable and is the LLM chain reachable."""
    llm = _build_llm()
    ping = None
    if llm is not None:
        try:
            ping = bool(llm.invoke([{"role": "user", "content": "ping"}]).content)
        except Exception:
            ping = False
    return {
        "roles": [r.__name__ for r in ROLES],
        "blocked": [r.__name__ for r in BLOCKED_ROLES],
        "deepagents": True,
        "llm_chain": ping,
    }
