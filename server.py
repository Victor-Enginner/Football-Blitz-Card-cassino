"""Command Center API + dashboard.

Security/governance invariants enforced here:
  - no route executes a bet; POST /copilot is analysis-only;
  - daily limits, stop-loss, cooldown are blocking;
  - events are append-only (no update/delete endpoints exist);
  - origins are whitelisted; state transitions are policy-driven.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel, Field, field_validator

import ledger as ledger_mod
from config import BASE_DIR, HOT_STREAK_ALERT, OMNIROUTE_HEALTH, OBSERVER_TOKEN
from config import MAX_EVENTS_PER_DAY
import risk as risk_mod
import martingale_risk_analysis as mg_mod
import progression as prog_mod

# AUTO-PAPER (simulation only, default OFF). When ON, each new observed
# outcome may open ONE paper bet following the anti-streak rule + ladder.
# Never touches real money, browser betting or Telegram orders.
AUTO = {"enabled": False, "last_anchor": None}
from ledger import Ledger
from policy import PolicyEngine
from rag import RAGIndex
from copilot import Copilot
from realtime import broadcaster
from game import GameEngine
from telegram_notify import notifier
from entry_validation import validate_outcome, validate_bet_entry
from entry_dedup import dedup_check, confirm_two_step, fingerprint

app = FastAPI(title="Football Blitz Command Center", version="2.1.0")

BUILD_VERSION = "2.1.0-real-system"
BUILD_GIT = "1012702"

db = Ledger()
policy = PolicyEngine(db)
rag = RAGIndex()
copilot = Copilot(rag)
game = GameEngine(BASE_DIR / "data" / "paper_bets.db")


@app.on_event("startup")
def _startup() -> None:
    import asyncio
    import threading
    broadcaster.attach_loop(asyncio.get_running_loop())
    if notifier.enabled:
        notifier.start_polling({
            "status": lambda: json.dumps(state(), ensure_ascii=False)[:3500],
            "saldo": lambda: f"Banca papel: R$ {game.balance():.2f}",
            "apostas": lambda: _fmt_open_bets(),
            "parar": _tg_stop,
            "voltar": _tg_resume,
            "relatorio": _tg_report,
        })
        notifier.send("🛰 Command Center online (PAPER, sem auto-execução)")

        def _daily_report_loop() -> None:
            """Envia relatório às 22:00 UTC todo dia."""
            import time as _time
            from datetime import datetime, timezone
            while True:
                now = datetime.now(timezone.utc)
                target = now.replace(hour=22, minute=0, second=0, microsecond=0)
                if target <= now:
                    target = target.replace(day=now.day + 1)
                _time.sleep((target - now).total_seconds())
                try:
                    notifier.daily_report(db.stats(), policy.check()["usage"])
                except Exception as e:  # noqa: BLE001
                    import logging
                    logging.getLogger("telegram").error("daily report: %s", e)

        threading.Thread(target=_daily_report_loop, daemon=True,
                         name="tg-daily").start()


def _fmt_open_bets() -> str:
    bets = game.open_bets()
    if not bets:
        return "Nenhuma aposta papel aberta."
    return "\n".join(f"• {b['bet_type']} R$ {b['stake']:.2f} ({b['bet_id'][:8]})"
                     for b in bets)


def _tg_stop() -> str:
    active = db.active_session()
    if active:
        policy.stop(active["session_id"])
        db.end_session(active["session_id"])
    return "⏹ KILL SWITCH: tudo parado. Intervenção humana para retomar (/voltar)."


def _tg_resume() -> str:
    active = db.active_session()
    if not active:
        sid = policy.start(note="telegram-resume")
        return f"▶️ Sessão retomada em PAPER: {sid[:10]}…"
    policy.resume(active["session_id"])
    return "▶️ Estado voltou para PAPER."


def _tg_report() -> str:
    import telegram_notify
    usage = policy.check()["usage"]
    stats = db.stats()
    lines = [
        "📊 *Relatório* (descritivo, sem valor preditivo)",
        f"Eventos hoje: *{usage['events_today']}/{usage['daily_limit']}*",
        f"PnL papel hoje: *R$ {usage['paper_pnl_today']:+.2f}*",
        f"Banca papel: *R$ {game.balance():.2f}*",
        f"Sessão: *{usage['session_minutes']}/{usage['max_session_minutes']} min*",
    ]
    if usage.get("hot_streak"):
        h = usage["hot_streak"]
        lines.append(f"Mesa quente: `{h['outcome']}` ×{h['run']}")
    if stats.get("outcome_frequency"):
        top = stats["outcome_frequency"][:3]
        lines.append("Top resultados: " + ", ".join(
            f"{f['outcome']} ({f['count']})" for f in top))
    return "\n".join(lines)

WEB_DIR = BASE_DIR / "web"


class EventIn(BaseModel):
    session_id: str = Field(min_length=8)
    observed_at: str
    outcome: str = Field(min_length=1)
    data_origin: str
    round_id: str | None = None
    metadata: dict = Field(default_factory=dict)

    @field_validator("data_origin")
    @classmethod
    def _origin(cls, v: str) -> str:
        allowed = {"manual", "fixture", "authorized_readonly", "simulated"}
        if v not in allowed:
            raise ValueError(f"data_origin must be one of {sorted(allowed)}")
        return v


class DecisionIn(BaseModel):
    session_id: str = Field(min_length=8)
    action: str = Field(min_length=1, max_length=80)
    rationale: str = Field(default="", max_length=500)


class SessionIn(BaseModel):
    note: str = Field(default="", max_length=300)


class AutoIn(BaseModel):
    enabled: bool


class HypothesisIn(BaseModel):
    text: str = Field(min_length=8, max_length=400)
    params: dict = Field(default_factory=dict)
    period: str = ""
    stop_rule: str = ""


class CopilotIn(BaseModel):
    question: str = Field(min_length=5, max_length=400)


@app.get("/api/health")
def health():
    from config import NINEROUTER_HEALTH
    chain = db.verify_chain()
    ok = all(chain.values())
    return {
        "status": "ok" if ok else "TAMPERED",
        "chain_integrity": chain,
        "omniroute": OMNIROUTE_HEALTH,
        "ninerouter": NINEROUTER_HEALTH,
        "version": BUILD_VERSION,
    }


@app.get("/ready")
def ready():
    chain = db.verify_chain()
    ok = all(chain.values())
    return {
        "ready": bool(ok),
        "version": BUILD_VERSION,
        "git": BUILD_GIT,
        "chain": chain,
        "mode": "PAPER",
    }


@app.get("/api/version")
def version():
    return {"version": BUILD_VERSION, "git": BUILD_GIT, "mode": "PAPER"}


# ── Signals (PAPER, visual 1-click) ────────────────────────────────────
# Regra anti-sequência: 4× MANDANTE seguidos → sinal VISITANTE 0.50;
# 4× VISITANTE seguidos → sinal MANDANTE 0.50. Empate quebra a sequência.
# Sinal é visual/educacional — nunca aposta sozinho.
ANTI_STREAK_RUN = 4


def ladder_now() -> dict:
    """Current ladder position from consecutive settled paper results (newest first)."""
    try:
        recent = game.recent_bets(12)
        statuses = [b["status"] for b in recent]
    except Exception:
        statuses = []
    return prog_mod.level_from_statuses(statuses)


def toggle_auto(enabled: bool) -> dict:
    AUTO["enabled"] = bool(enabled)
    if not enabled:
        AUTO["last_anchor"] = None
    db.audit("auto_paper", f"auto-paper {'ON' if enabled else 'OFF'} (simulation)")
    return {"auto_paper": AUTO["enabled"]}


def maybe_auto_paper() -> dict | None:
    """One auto PAPER bet per fresh 4x streak. Returns bet or None."""
    if not AUTO["enabled"]:
        return None
    active = db.active_session()
    if not active:
        sid = policy.start(note="auto-paper-rotation")
        db.audit("auto_paper", f"nova sessão rotacionada {sid[:8]} (PAPER)")
        active = db.get_session(sid)
    else:
        chk0 = policy.check(active["session_id"])
        if any("session time limit" in r for r in chk0["reasons"]):
            db.end_session(active["session_id"])
            sid = policy.start(note="auto-paper-rotation")
            db.audit("auto_paper", f"sessão expirada, rotacionada {sid[:8]} (PAPER)")
            active = db.get_session(sid)
    sid = active["session_id"]
    check = policy.check(sid)
    if not check["allowed"]:
        return None
    try:
        if game.open_bets():
            return None
        today = datetime.now(timezone.utc).date().isoformat()
        today_bets = [b for b in game.recent_bets(500)
                      if (b.get("opened_at", "")[:10] == today)]
        if len(today_bets) >= 200:
            AUTO["enabled"] = False
            db.audit("auto_paper", "limite 200/dia: auto-paper DESLIGADO")
            return None
        # conta perdas consecutivas (para no 1º win/push)
        consec = 0
        for b in game.recent_bets(12):
            if b["status"] == "lost":
                consec += 1
            elif b["status"] in ("won", "push"):
                break
        if consec >= 8:
            AUTO["enabled"] = False
            db.audit("auto_paper", f"loss-streak {consec}: auto-paper DESLIGADO")
            return None
    except Exception:
        return None
    evs = db.last_events(60)
    streak_out, run = None, 0
    for e in reversed(evs[-60:]):
        o = e["outcome"]
        if o not in ("home", "away"):
            break
        if streak_out is None:
            streak_out, run = o, 1
        elif o == streak_out:
            run += 1
        else:
            break
    if not (streak_out and run >= ANTI_STREAK_RUN) or not evs:
        return None
    anchor = evs[-1]["event_id"]
    if anchor == AUTO["last_anchor"]:
        return None
    side = "away" if streak_out == "home" else "home"
    lad = ladder_now()
    try:
        bet = game.open_bet(sid, side, lad["stake"])
    except ValueError:
        return None
    AUTO["last_anchor"] = anchor
    db.audit("auto_paper", f"{side} R$ {lad['stake']:.2f} nível {lad['level']}/5 (sinal {anchor[:8]})")
    return {"bet": bet, "ladder": lad, "anchor": anchor[:12]}
SIGNAL_STAKE = 0.50


@app.get("/api/signals/current")
def signal_current():
    evs = db.last_events(200)
    decisive = [e for e in evs if e["outcome"] in ("home", "away")]
    streak_out, run = None, 0
    # streak conta eventos consecutivos no ledger (empate quebra)
    for e in reversed(evs[-60:]):
        o = e["outcome"]
        if o not in ("home", "away"):
            break
        if streak_out is None:
            streak_out, run = o, 1
        elif o == streak_out:
            run += 1
        else:
            break
    orbs = [e["outcome"] for e in evs[-20:]]
    if streak_out and run >= ANTI_STREAK_RUN:
        side = "away" if streak_out == "home" else "home"
        fr = risk_mod.freq_relative([e["outcome"] for e in decisive]) if decisive else {}
        anchor = evs[-1]["event_id"] if evs else "none"
        lad = ladder_now()
        return {
            "signal": True,
            "signal_id": f"anti4-{anchor[:12]}",
            "rule": f"anti-streak-{ANTI_STREAK_RUN}",
            "base_outcome": streak_out,
            "run": run,
            "side": side,
            "stake": lad["stake"],
            "ladder": lad,
            "auto_paper": AUTO["enabled"],
            "n_decisive": len(decisive),
            "n_decisive": len(decisive),
            "freq": {k: round(v, 3) for k, v in fr.items()},
            "orbs": orbs,
            "mode": "PAPER",
            "note": "Sinal visual. Confirme manualmente — 1 clique registra paper.",
        }
    return {"signal": False, "run": run, "base_outcome": streak_out,
            "orbs": orbs, "mode": "PAPER"}
# ── Agents Brain (PAPER, dados reais) ────────────────────────────────────
# Personalidades funcionais mapeadas a subsistemas reais. Sem métrica
# inventada: tokens/latência de modelo = null (n/d); confiança sempre com n.
@app.get("/api/agents/status")
def agents_status():
    import time as _t
    t0 = _t.monotonic()
    evs = db.last_events(60)
    outs = [e["outcome"] for e in evs if e["outcome"] in ("home", "away", "draw")]
    check = policy.check()
    usage = check["usage"]
    try:
        open_bets = game.open_bets()
        recent = game.recent_bets(5)
        balance = game.balance()
    except Exception:
        open_bets, recent, balance = [], [], None
    ws_clients = broadcaster.count
    rag_chunks = len(rag.chunks)
    last = evs[-1] if evs else None
    # streak atual
    run, cur = 0, outs[-1] if outs else None
    for o in reversed(outs):
        if o == cur:
            run += 1
        else:
            break
    blocked = not check["allowed"]
    state_session = check["state"]

    def ev(e):
        return {"event_id": e["event_id"][:12], "outcome": e["outcome"],
                "origin": e["data_origin"], "at": e.get("observed_at", "")} if e else None

    agents = [
        {"id": "observador", "nome": "Sentinela", "funcao": "Monitor",
         "personalidade": "Acompanha saúde, canal e capturas. Só observa.",
         "estado": "alerta" if ws_clients == 0 else "aprovado",
         "tarefa": f"{ws_clients} cliente(s) no canal",
         "ultima_acao": ev(last),
         "confianca": None, "latencia_ms": None, "tokens": None,
         "fila": 0, "detalhe": "MutationObserver no jogo → /ws → ledger"},
        {"id": "analista", "nome": "Prisma", "funcao": "Analista",
         "personalidade": "Explica padrões e incertezas. Nunca afirma sem amostra.",
         "estado": "aguardando" if len(outs) < 4 else ("analisando" if run < 4 else "aprovado"),
         "tarefa": f"sequência atual: {cur} ×{run}" if cur else "aguardando eventos",
         "ultima_acao": ev(last),
         "confianca": {"n": len(outs), "nota": "n<60: sem conclusão"},
         "latencia_ms": None, "tokens": None,
         "fila": 0, "detalhe": f"{len(outs)} eventos na janela"},
        {"id": "matematico", "nome": "QED", "funcao": "Matemático",
         "personalidade": "Valida probabilidade, entropia e risco. Exige intervalo.",
         "estado": "aguardando" if len(outs) < 60 else "analisando",
         "tarefa": f"amostra n={len(outs)} (mín. 60)",
         "ultima_acao": ev(last),
         "confianca": risk_mod.wilson_ci(
             sum(1 for o in outs if o == "home"), len(outs)) if outs else None,
         "latencia_ms": None, "tokens": None,
         "fila": 0, "detalhe": "χ², entropia e EV em /api/risk/summary"},
        {"id": "executor", "nome": "Atlas", "funcao": "Executor",
         "personalidade": "Mostra ações simuladas e estados. Nunca executa real.",
         "estado": "analisando" if open_bets else ("concluido" if recent else "aguardando"),
         "tarefa": f"{len(open_bets)} paper aberta(s)",
         "ultima_acao": {"bet": recent[0]["bet_type"], "stake": recent[0]["stake"],
                         "status": recent[0]["status"]} if recent else None,
         "confianca": None, "latencia_ms": None, "tokens": None,
         "fila": len(open_bets), "detalhe": f"banca paper R$ {balance}"},
        {"id": "memoria", "nome": "Mnemos", "funcao": "Memória",
         "personalidade": "Mostra contexto e evidências recuperadas, com fonte.",
         "estado": "aprovado" if rag_chunks else "falha",
         "tarefa": f"{rag_chunks} fragmentos indexados",
         "ultima_acao": None,
         "confianca": None, "latencia_ms": None, "tokens": None,
         "fila": 0, "detalhe": "RAG TF-IDF local + eventos da sessão"},
        {"id": "seguranca", "nome": "Égide", "funcao": "Segurança",
         "personalidade": "Bloqueia o perigoso. Travas sempre ligadas.",
         "estado": "bloqueado" if blocked else "aprovado",
         "tarefa": f"sessão {state_session}",
         "ultima_acao": {"motivos": check["reasons"][:3]} if blocked else None,
         "confianca": None, "latencia_ms": None, "tokens": None,
         "fila": 0, "detalhe": "200/dia · loss-streak · stop-loss · kill-switch"},
        {"id": "coordenador", "nome": "Maestro", "funcao": "Coordenador",
         "personalidade": "Apresenta o fluxo geral e dependências.",
         "estado": "pausado" if state_session in ("COOLDOWN", "STOPPED") else "analisando",
         "tarefa": "observar→validar→ledger→sinal",
         "ultima_acao": ev(last),
         "confianca": None, "latencia_ms": None, "tokens": None,
         "fila": len(open_bets), "detalhe": f"{usage['events_today']}/{usage['daily_limit']} eventos hoje"},
    ]
    ms = int((_t.monotonic() - t0) * 1000)
    return {"agents": agents, "coleta_ms": ms, "mode": "PAPER",
            "nota": "tokens e latência de modelo: n/d (sem chamada LLM neste ciclo)"}
# ── Cards (observado via DOM, pode ser n/d) ────────────────────────────────
@app.get("/api/cards/summary")
def cards_summary(n: int = 200):
    evs = db.last_events(min(max(n, 10), 1000))
    seen: dict[str, int] = {}
    with_cards = 0
    for e in evs:
        try:
            meta = json.loads(e.get("metadata") or "{}")
        except ValueError:
            continue
        for k in ("home_card", "away_card"):
            v = (meta.get(k) or "").upper()
            if v:
                seen[v] = seen.get(v, 0) + 1
                with_cards += 0  # conta por carta abaixo
        if meta.get("home_card") or meta.get("away_card"):
            with_cards += 1
    return {"counts": dict(sorted(seen.items())),
            "rounds_with_cards": with_cards, "rounds": len(evs),
            "mode": "PAPER",
            "note": "Cartas lidas do DOM quando visíveis; n/d = observer não capturou. Sapato 8 baralhos c/ reshuffle ~50%: contagem parcial, sem edge assumido."}
# ── Risk (PAPER, educacional) ────────────────────────────────────────────
@app.get("/api/risk/summary")
def risk_summary(n: int = 200):
    evs = db.last_events(min(max(n, 10), 1000))
    outcomes = [e["outcome"] for e in evs if e["outcome"] in ("home", "away", "draw")]
    pnls = []
    try:
        for b in game.recent_bets(500):
            if b["status"] in ("won", "lost", "push"):
                pnls.append(float(b.get("pnl", 0.0)))
    except Exception:
        pnls = []
    s = risk_mod.summarize_session(outcomes, pnls)
    # EV estimado por entrada home/away (1:1, push_half no draw) e draw (11:1)
    fr = s["freq"]
    s["ev_home"] = risk_mod.ev_per_entry(fr.get("home", 0), 1.0,
                                         p_push=fr.get("draw", 0), push_return=-0.5)
    s["ev_draw"] = risk_mod.ev_per_entry(fr.get("draw", 0), 11.0)
    s["p_4loss_in_200"] = risk_mod.prob_k_losses_in_n(0.55, 200, 4)
    s["kelly_home"] = risk_mod.kelly_fraction(fr.get("home", 0), 1.0)
    s["mode"] = "PAPER"
    s["warning"] = ("Sem vantagem estatística confiável" if s["n"] < 60
                    else "Amostra em análise — não é recomendação")
    return s


@app.get("/api/risk/progression")
def risk_progression(base: float = 2.5, levels: int = 3):
    if base <= 0 or base > 100 or levels < 0 or levels > 6:
        raise HTTPException(422, "base 0..100, levels 0..6")
    plan = mg_mod.cycle_plan(base=base, levels=levels)
    sim = mg_mod.simulate(base=base, levels=levels)
    return {"plan": plan, "simulation_paper": sim, "mode": "PAPER_EDUCATIONAL",
            "ladder_live": prog_mod.LADDER, "ladder_exposure": prog_mod.total_exposure(),
            "note": "Demonstra risco. Não executa apostas."}


@app.get("/api/state")
def state():
    active = db.active_session()
    check = policy.check(active["session_id"] if active else None)
    return {
        "mode": "PAPER",
        "auto_execution": False,
        "auto_paper": AUTO["enabled"],
        "ladder": ladder_now(),
        "state": check["state"],
        "check": check,
        "session": active,
    }


@app.post("/api/session/auto")
def session_auto(body: AutoIn):
    """Liga/desliga AUTO-PAPER (simulation). Nunca aposta real."""
    return toggle_auto(body.enabled)


@app.post("/api/session/start")
def session_start(body: SessionIn):
    check = policy.check()
    if check["state"] == "COOLDOWN":
        raise HTTPException(423, {"error": "cooldown active", "reasons": check["reasons"]})
    if check["state"] == "STOPPED":
        raise HTTPException(423, {"error": "kill switch engaged", "reasons": check["reasons"]})
    session_id = policy.start(note=body.note)
    rag.index_events(db.last_events(200))
    return {"session_id": session_id, "state": "PAPER"}


@app.post("/api/session/stop")
def session_stop():
    active = db.active_session()
    if not active:
        raise HTTPException(404, "no active session")
    policy.stop(active["session_id"])
    db.end_session(active["session_id"])
    return {"stopped": True}


@app.post("/api/session/cooldown")
def session_cooldown():
    active = db.active_session()
    if not active:
        raise HTTPException(404, "no active session")
    policy.cooldown(active["session_id"])
    return {"cooldown": True}


@app.post("/api/session/resume")
def session_resume():
    active = db.active_session()
    if not active:
        raise HTTPException(404, "no active session")
    policy.resume(active["session_id"])
    return {"resumed": True}


@app.post("/api/events")
def add_event(body: EventIn):
    check = policy.check(body.session_id)
    hot = check["usage"].get("hot_streak")
    if not check["allowed"]:
        db.audit("event_blocked", "; ".join(check["reasons"]))
        raise HTTPException(423, {"error": "blocked by policy", "reasons": check["reasons"]})
    # VALIDACAO: outcome real precisa ser home/away/draw (normaliza alias)
    try:
        body.outcome = validate_outcome(body.outcome)
    except ValueError as e:
        db.audit("event_rejected", f"outcome inválido: {body.outcome!r}")
        raise HTTPException(422, str(e))
    # DEDUP: ignora leitura duplicada do observer (mesmo raw+parser em 120s)
    raw = (body.metadata or {}).get("raw", "") or body.outcome
    if dedup_check(raw, body.round_id or "manual", ):
        db.audit("event_duplicate", f"outcome duplicado ignorado: {body.outcome}")
        raise HTTPException(409, "duplicate outcome ignored")
    try:
        result = db.append_event(
            session_id=body.session_id,
            observed_at=body.observed_at,
            outcome=body.outcome,
            data_origin=body.data_origin,
            round_id=body.round_id,
            metadata=body.metadata,
        )
    except ValueError as e:
        raise HTTPException(422, str(e))
    db.audit("event_added", f"{body.outcome} ({body.data_origin})")
    # live fan-out + paper settlement + alerts
    ev = db.last_events(1)[0]
    broadcaster.broadcast("event", {"event": ev})
    settled = game.settle(body.outcome)
    if settled:
        for b in settled:
            notifier.send(
                f"{'🟢' if b['pnl'] >= 0 else '🔴'} Aposta papel {b['status'].upper()}: "
                f"{b['bet_type']} R$ {b['stake']:.2f} → PnL R$ {b['pnl']:+.2f}", silent=True)
    if notifier.enabled:
        notifier.event_added(ev)
    if hot:
        notifier.hot_streak(hot)
    blocking = [r for r in check["reasons"] if "HOT" not in r]
    if not check["allowed"] and blocking:
        notifier.blocked(blocking)
    auto = maybe_auto_paper()
    return {"ok": True, **result, "policy_state": check["state"], "hot_streak": hot,
            "settled_bets": len(settled),
            "auto_paper": {"bet": auto["bet"], "ladder": auto["ladder"]} if auto else None}


# ── WebSocket live channel ─────────────────────────────────────────────────
from fastapi import WebSocket, WebSocketDisconnect, Query


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket, token: str | None = Query(default=None)):
    if OBSERVER_TOKEN and token != OBSERVER_TOKEN:
        await ws.close(code=4401)
        return
    await broadcaster.connect(ws)
    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            kind = msg.get("kind")
            if kind == "outcome":
                # observer bridge: read-only DOM result (origin=authorized_readonly)
                # VALIDACAO REAL: normaliza outcome + dedup + confirmação dupla.
                try:
                    outcome = validate_outcome(str(msg.get("outcome", "")))
                except ValueError:
                    continue  # lixo do DOM nunca entra no ledger
                raw = str(msg.get("raw", "") or outcome)[:40]
                parser = msg.get("parser_version", "observer-1.0")
                if dedup_check(raw, parser):
                    continue  # leitura repetida do MutationObserver
                conf = confirm_two_step(msg.get("round_id"), outcome)
                if not conf["confirmed"]:
                    continue  # aguarda 2ª leitura igual (anti-fantasma)
                try:
                    db.append_event(
                        session_id="observer-bridge-01",
                        observed_at=msg.get("observed_at") or datetime.now(timezone.utc).isoformat(),
                        outcome=outcome,
                        data_origin="authorized_readonly",
                        parser_version=parser,
                        round_id=msg.get("round_id"),
                        metadata={"raw": raw,
                                  "home_card": msg.get("home_card"),
                                  "away_card": msg.get("away_card")},
                    )
                    ev = db.last_events(1)[0]
                    broadcaster.broadcast("event", {"event": ev})
                    game.settle(ev["outcome"])
                    maybe_auto_paper()
                except ValueError:
                    pass  # invalid outcome string etc.
            elif kind == "ping":
                pass  # keepalive
    except WebSocketDisconnect:
        broadcaster.disconnect(ws)
    except Exception:
        broadcaster.disconnect(ws)
        raise


# ── Observer bridge (events pushed from your local game observer) ─────────
class IngestIn(BaseModel):
    outcomes: list[dict] = Field(min_length=1, max_length=50)


def _auth_ok(token: str | None) -> bool:
    return (not OBSERVER_TOKEN) or token == OBSERVER_TOKEN


@app.post("/api/ingest")
def ingest(body: IngestIn, token: str | None = None):
    """Bridge for the local observer. Origin forced to authorized_readonly."""
    if not _auth_ok(token):
        raise HTTPException(401, "invalid observer token")
    accepted, rejected = 0, []
    for item in body.outcomes[:20]:
        try:
            outcome = validate_outcome(item["outcome"])
            raw = str((item.get("metadata", {}) or {}).get("raw", "") or outcome)[:40]
            parser = item.get("parser_version", "observer-1.0")
            if dedup_check(raw, parser):
                rejected.append(f"duplicate: {outcome}")
                continue
            conf = confirm_two_step(item.get("round_id"), outcome)
            if not conf["confirmed"]:
                rejected.append(f"unconfirmed (aguardando 2a leitura): {outcome}")
                continue
            db.append_event(
                session_id=item.get("session_id") or "observer-bridge-01",
                observed_at=item["observed_at"],
                outcome=outcome,
                data_origin="authorized_readonly",
                parser_version=parser,
                round_id=item.get("round_id"),
                metadata={**(item.get("metadata", {}) or {}), "raw": raw},
            )
            accepted += 1
        except (ValueError, KeyError) as e:
            rejected.append(str(e))
    if accepted:
        last = db.last_events(1)[0]
        broadcaster.broadcast("event", {"event": last})
        settled = game.settle(last["outcome"])
        maybe_auto_paper()
    return {"accepted": accepted, "rejected": rejected}


# ── Game framework (PAPER) ─────────────────────────────────────────────────
class BetIn(BaseModel):
    bet_type: str
    stake: float = Field(gt=0, le=100)


@app.get("/api/game/state")
def game_state():
    return {
        "balance": game.balance(),
        "stats": game.stats(),
        "open_bets": game.open_bets(),
        "recent": game.recent_bets(20),
    }


@app.post("/api/game/bet")
def game_bet(body: BetIn):
    active = db.active_session()
    if not active:
        raise HTTPException(409, "no active session — start one first")
    # RISK: hard cap 200 paper bets/day (server-side, never trust client)
    today_bets = [b for b in game.recent_bets(500)
                  if (b.get("opened_at", "")[:10] ==
                      datetime.now(timezone.utc).date().isoformat())]
    if len(today_bets) >= 200:
        db.audit("paper_bet_rejected", "limite diário 200 apostas paper atingido")
        raise HTTPException(423, {"error": "limite diário 200 atingido", "reasons": ["DAILY_BET_LIMIT"]})
    # RISK: loss-streak breaker — 2 ciclos martingale (~R$75) = stop
    recent = game.recent_bets(12)
    consec_losses = 0
    for b in recent:
        if b["status"] == "lost":
            consec_losses += 1
        elif b["status"] in ("won", "push"):
            break
    if consec_losses >= 8:
        db.audit("paper_bet_rejected", f"loss-streak {consec_losses} — stop loss sessão")
        raise HTTPException(423, {"error": "loss-streak breaker", "reasons": [f"{consec_losses} perdas seguidas"]})
    check = policy.check(active["session_id"])
    # VALIDACAO REAL da entrada (portão único): tipo, stake, banca, policy
    gate = validate_bet_entry(body.bet_type, body.stake, game.balance(),
                              check["allowed"], check["reasons"])
    if not gate["ok"]:
        db.audit("paper_bet_rejected", "; ".join(gate["reasons"]))
        notifier.blocked(gate["reasons"]) if notifier.enabled else None
        raise HTTPException(422, {"error": "entrada rejeitada", "reasons": gate["reasons"]})
    try:
        bet = game.open_bet(active["session_id"], body.bet_type, gate["stake"])
    except ValueError as e:
        raise HTTPException(422, str(e))
    db.audit("paper_bet_opened", f"{body.bet_type} R$ {body.stake:.2f}")
    return {"ok": True, "bet": bet, "balance": game.balance()}


@app.get("/api/game/simulate")
def simulate(shoes: int = 50, mode: str = "flat_home"):
    """Monte Carlo over 8-deck shoe with mid-shoe reshuffle (real structure).
    Reuses validated math from PLANO_FOOTBALL_BLITZ.md (RTP-verified model).
    Descriptive only — describes the simulation, never the future."""
    import random
    rng = random.Random(42)  # deterministic seed = reproducible runs
    if shoes < 1 or shoes > 2000:
        raise HTTPException(422, "shoes must be 1..2000")
    vals = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13] * 4 * 8  # A=1 low, 8 decks
    pnl = 0.0
    bets_made = 0
    for _ in range(shoes):
        deck = vals[:]
        rng.shuffle(deck)
        half = len(deck) // 2
        idx = 0
        while idx < half - 2:  # stop where real game reshuffles (~50%)
            h, a = deck[idx], deck[idx + 1]
            outcome = "home" if h > a else "away" if a > h else "draw"
            if mode == "flat_home":
                stake = 1.0
                if outcome == "home":
                    pnl += stake
                elif outcome == "draw":
                    pnl -= stake * 0.5
                else:
                    pnl -= stake
                bets_made += 1
            idx += 2
    return {
        "mode": mode, "shoes": shoes, "bets": bets_made,
        "pnl": round(pnl, 2), "pnl_per_bet": round(pnl / max(1, bets_made), 4),
        "note": "simulação descritiva (8 baralhos, reshuffle ~50%); não prevê o futuro",
    }


@app.get("/api/llm/status")
def llm_status():
    """Diagnóstico da infra LLM: 9Router vivo? quais fallbacks têm chave?"""
    import socket
    from urllib.parse import urlparse
    from config import (
        REMOTE_LLM_ENABLED, NINEROUTER_BASE_URL, NINEROUTER_MODEL,
        TOKENROUTER_ENABLED, TOKENROUTER_API_KEY, TOKENROUTER_MODEL,
        NVIDIA_ENABLED, NVIDIA_API_KEY, NVIDIA_MODEL,
        AISA_ENABLED, AISA_API_KEY, AISA_MODEL,
        GENERIC_PROVIDER_ENABLED, GENERIC_PROVIDER_BASE_URL,
        GENERIC_PROVIDER_MODEL, GENERIC_PROVIDER_NAME,
        COMPRESSION_ENABLED, LLM_CACHE_ENABLED,
    )

    def _ping(url: str) -> dict:
        try:
            host = urlparse(url).hostname or "localhost"
            port = urlparse(url).port or 80
            s = socket.create_connection((host, port), timeout=3)
            s.close()
            return {"reachable": True}
        except OSError as e:
            return {"reachable": False, "error": str(e)[:120]}

    return {
        "remote_enabled": REMOTE_LLM_ENABLED,
        "compression": COMPRESSION_ENABLED,
        "cache": LLM_CACHE_ENABLED,
        "primary": {"name": "9router", "model": NINEROUTER_MODEL,
                    **_ping(NINEROUTER_BASE_URL)},
        "fallbacks": [
            {"name": "tokenrouter", "model": TOKENROUTER_MODEL,
             "has_key": bool(TOKENROUTER_API_KEY), "on": TOKENROUTER_ENABLED},
            {"name": "nvidia", "model": NVIDIA_MODEL,
             "has_key": bool(NVIDIA_API_KEY), "on": NVIDIA_ENABLED},
            {"name": "aisa", "model": AISA_MODEL,
             "has_key": bool(AISA_API_KEY), "on": AISA_ENABLED},
            {"name": GENERIC_PROVIDER_NAME, "model": GENERIC_PROVIDER_MODEL,
             "has_key": bool(GENERIC_PROVIDER_BASE_URL),
             "on": GENERIC_PROVIDER_ENABLED},
        ],
    }


@app.get("/api/llm/usage")
def llm_usage(n: int = 50):
    """Observabilidade: últimas N chamadas LLM (provider, latência, cache)."""
    from config import DATA_DIR, LLM_USAGE_LOG
    from pathlib import Path as _P
    p = _P(LLM_USAGE_LOG)
    if not p.is_absolute():
        p = DATA_DIR / p.name
    if not p.exists():
        return {"calls": []}
    lines = p.read_text(encoding="utf-8").strip().splitlines()[-max(1, min(n, 500)):]
    import json as _j
    calls = []
    for ln in lines:
        try:
            calls.append(_j.loads(ln))
        except ValueError:
            continue
    return {"calls": calls[-max(1, min(n, 500)):]}


@app.get("/api/events")
def list_events(n: int = 30):
    return {"events": db.last_events(min(n, 500))}


@app.get("/api/events/today-count")
def today_count():
    from datetime import date, timezone
    today = datetime.now(timezone.utc).date().isoformat()
    return {"day": today, "count": db.count_events_on(today), "limit": db_check_limit()}


def db_check_limit():
    from config import MAX_EVENTS_PER_DAY
    return MAX_EVENTS_PER_DAY


@app.post("/api/decisions")
def add_decision(body: DecisionIn):
    active = db.active_session()
    check = policy.check(active["session_id"] if active else None)
    if not check["allowed"]:
        db.audit("decision_blocked", body.action)
        raise HTTPException(423, {"error": "blocked by policy", "reasons": check["reasons"]})
    if not active:
        raise HTTPException(409, "no active session — start one first")
    result = db.add_decision(active["session_id"], body.action, body.rationale)
    db.audit("decision_added", body.action)
    return {"ok": True, **result}


@app.get("/api/stats")
def stats(session_id: str | None = None):
    s = db.stats(session_id)
    s["paper_pnl_today"] = db.paper_pnl_today()
    s["hot_streak"] = db.hot_streak(HOT_STREAK_ALERT)
    return s


@app.get("/api/hypotheses")
def list_hypotheses():
    return {"hypotheses": db.list_hypotheses()}


@app.post("/api/hypotheses")
def add_hypothesis(body: HypothesisIn):
    if violates_tone(body.text):
        raise HTTPException(422, "hypothesis text violates neutral-tone policy")
    hid = db.add_hypothesis(body.text, body.params, body.period, body.stop_rule)
    return {"id": hid}


@app.post("/api/copilot")
def copilot_ask(body: CopilotIn):
    """Governed analysis endpoint. Analysis only — no execution, no advice."""
    active = db.active_session()
    s = db.stats(active["session_id"] if active else None)
    answer = copilot.summarize_session(body.question, s)
    db.audit("copilot_query", body.question[:80])
    return answer


@app.get("/api/export")
def export_events(fmt: str = "json"):
    from config import DATA_DIR
    from ledger import _now
    day = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = DATA_DIR / f"export_{day}.{fmt}"
    events = db.last_events(10_000)
    if fmt == "json":
        path.write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8")
    elif fmt == "csv":
        import csv
        cols = ["event_id", "session_id", "observed_at", "outcome", "data_origin", "parser_version"]
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
            w.writeheader()
            w.writerows(events)
    else:
        raise HTTPException(400, "fmt must be json or csv")
    return {"path": str(path), "events": len(events)}


@app.get("/")
def index():
    return FileResponse(WEB_DIR / "index.html")


@app.get("/app.js")
def app_js():
    return FileResponse(WEB_DIR / "app.js")


@app.get("/app.css")
def app_css():
    return FileResponse(WEB_DIR / "app.css")


@app.get("/manifest.webmanifest")
def manifest():
    return FileResponse(WEB_DIR / "manifest.webmanifest")


@app.get("/blitz-icon.svg")
def blitz_icon():
    return FileResponse(WEB_DIR / "blitz-icon.svg")


@app.get("/vendor/dialkit/{file_name}")
def vendor_dialkit(file_name: str):
    """Serve vendored DialKit browser bundle (no-bundler vanilla adapter)."""
    vendor_dir = (WEB_DIR / "vendor" / "dialkit").resolve()
    file_path = (vendor_dir / file_name).resolve()
    if vendor_dir not in file_path.parents or not file_path.is_file():
        raise HTTPException(404, "vendor file not found")
    return FileResponse(file_path)


@app.get("/assets/{asset_name}")
def web_asset(asset_name: str):
    """Serve only dashboard assets from the dedicated, non-executable folder."""
    assets_dir = (WEB_DIR / "assets").resolve()
    asset_path = (assets_dir / asset_name).resolve()
    if assets_dir not in asset_path.parents or not asset_path.is_file():
        raise HTTPException(404, "asset not found")
    return FileResponse(asset_path)


def violates_tone(text: str) -> bool:
    from copilot import violates_tone as vt
    return bool(vt(text))
