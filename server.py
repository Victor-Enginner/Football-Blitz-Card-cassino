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
from ledger import Ledger
from policy import PolicyEngine
from rag import RAGIndex
from copilot import Copilot
from realtime import broadcaster
from game import GameEngine
from telegram_notify import notifier

app = FastAPI(title="Football Blitz Command Center", version="2.0.0")

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


class HypothesisIn(BaseModel):
    text: str = Field(min_length=8, max_length=400)
    params: dict = Field(default_factory=dict)
    period: str = ""
    stop_rule: str = ""


class CopilotIn(BaseModel):
    question: str = Field(min_length=5, max_length=400)


@app.get("/api/health")
def health():
    chain = db.verify_chain()
    ok = all(chain.values())
    return {
        "status": "ok" if ok else "TAMPERED",
        "chain_integrity": chain,
        "omniroute": OMNIROUTE_HEALTH,
    }


@app.get("/api/state")
def state():
    active = db.active_session()
    check = policy.check(active["session_id"] if active else None)
    return {
        "mode": "PAPER",
        "auto_execution": False,
        "state": check["state"],
        "check": check,
        "session": active,
    }


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
    return {"ok": True, **result, "policy_state": check["state"], "hot_streak": hot,
            "settled_bets": len(settled)}


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
                try:
                    db.append_event(
                        session_id="observer-bridge-01",
                        observed_at=msg.get("observed_at") or datetime.now(timezone.utc).isoformat(),
                        outcome=str(msg.get("outcome", ""))[:40],
                        data_origin="authorized_readonly",
                        parser_version=msg.get("parser_version", "observer-1.0"),
                        metadata={"raw": msg.get("raw", "")[:40]},
                    )
                    ev = db.last_events(1)[0]
                    broadcaster.broadcast("event", {"event": ev})
                    game.settle(ev["outcome"])
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
            db.append_event(
                session_id=item.get("session_id") or "observer-bridge-01",
                observed_at=item["observed_at"],
                outcome=item["outcome"],
                data_origin="authorized_readonly",
                parser_version=item.get("parser_version", "observer-1.0"),
                metadata=item.get("metadata", {}),
            )
            accepted += 1
        except (ValueError, KeyError) as e:
            rejected.append(str(e))
    if accepted:
        last = db.last_events(1)[0]
        broadcaster.broadcast("event", {"event": last})
        settled = game.settle(last["outcome"])
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
    check = policy.check(active["session_id"])
    if not check["allowed"]:
        notifier.blocked(check["reasons"])
        raise HTTPException(423, {"error": "blocked by policy", "reasons": check["reasons"]})
    if body.bet_type not in ("home", "away", "draw", "spread_h", "spread_a"):
        raise HTTPException(422, f"bet_type must be one of home/away/draw/spread_h/spread_a")
    try:
        bet = game.open_bet(active["session_id"], body.bet_type, body.stake)
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
