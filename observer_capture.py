"""Authenticated, idempotent DOM collection. Never settles or opens bets."""
from datetime import datetime, timezone
import hashlib
import hmac
import sqlite3
import threading
import time
from typing import Literal

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, AwareDatetime


def capture_token(secret: str) -> str:
    return hmac.new(secret.encode(), b"football-blitz:readonly-capture:v1", hashlib.sha256).hexdigest() if secret else ""


class Observation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    round_id: str = Field(pattern=r"^[0-9]{8,24}$")
    outcome: Literal["home", "away", "draw"]
    observed_at: AwareDatetime
    parser_version: Literal["fb-banner-1.0"]


def create_capture_router(db, broadcaster, secret: str):
    router = APIRouter(prefix="/api/observer")
    token = capture_token(secret)
    lock = threading.RLock()
    pending = {}
    health = {"heartbeat": None, "last_outcome": None}

    def authenticate(authorization):
        if not token or not hmac.compare_digest(authorization or "", "Bearer " + token):
            raise HTTPException(401, "capture authentication required")

    @router.post("/heartbeat")
    def heartbeat(authorization: str | None = Header(default=None)):
        authenticate(authorization)
        with lock:
            health["heartbeat"] = time.time()
        return {"ok": True, "mode": "READONLY"}

    @router.get("/status")
    def status(authorization: str | None = Header(default=None)):
        authenticate(authorization)
        with lock:
            age = None if health["heartbeat"] is None else time.time() - health["heartbeat"]
            session = db.active_session()
            rows = db.capture_history(session["session_id"], 1) if session else []
            last_at = rows[-1]["observed_at"] if rows else None
            outcome_age = (datetime.now(timezone.utc) - datetime.fromisoformat(last_at)).total_seconds() if last_at else None
            return {"mode": "READONLY", "observer_online": age is not None and age <= 120,
                    "heartbeat_age_s": age, "last_outcome": last_at,
                    "outcome_age_s": outcome_age,
                    "data_stale": outcome_age is None or outcome_age > 120}

    @router.get("/history")
    def history(limit: int = Query(default=200, ge=1, le=500),
                authorization: str | None = Header(default=None)):
        authenticate(authorization)
        session = db.active_session()
        return {"mode": "READONLY", "session_id": session["session_id"] if session else None,
                "events": db.capture_history(session["session_id"], limit) if session else [],
                "continuity": "observed_only"}

    @router.put("/outcomes")
    def outcome(body: Observation, authorization: str | None = Header(default=None)):
        authenticate(authorization)
        now = datetime.now(timezone.utc)
        age = (now - body.observed_at).total_seconds()
        if age < -10 or age > 120:
            raise HTTPException(422, "observation timestamp outside capture window")
        eid = hashlib.sha256(("football-blitz:round:" + body.round_id).encode()).hexdigest()
        with lock:
            # Persistent uniqueness survives reconnects, parallel tabs and restarts.
            existing = db.event_by_id(eid)
            if existing:
                if existing["outcome"] != body.outcome:
                    raise HTTPException(409, "conflicting outcome for recorded round")
                return {"accepted": True, "duplicate": True, "event_id": eid}
            tick = time.monotonic()
            for rid in list(pending):
                if tick - pending[rid][1] > 8:
                    del pending[rid]
            previous = pending.get(body.round_id)
            if not previous or previous[0] != body.outcome:
                if len(pending) >= 128:
                    raise HTTPException(429, "too many pending rounds")
                pending[body.round_id] = (body.outcome, tick)
                return {"accepted": False, "waiting_confirmation": True}
            if tick - previous[1] < 0.5:
                return {"accepted": False, "waiting_confirmation": True}
            session = db.active_session()
            if not session or session["state"] != "PAPER":
                raise HTTPException(423, "active PAPER session required")
            try:
                db.append_event(session_id=session["session_id"], event_id=eid,
                    round_id=body.round_id, outcome=body.outcome,
                    observed_at=body.observed_at.isoformat(), data_origin="authorized_readonly",
                    parser_version=body.parser_version,
                    metadata={"capture_only": True, "confirmed_readings": 2,
                              "source": "visible_result_banner"})
            except sqlite3.IntegrityError:
                existing = db.event_by_id(eid)
                if not existing or existing["outcome"] != body.outcome:
                    raise HTTPException(409, "round conflict")
                return {"accepted": True, "duplicate": True, "event_id": eid}
            pending.pop(body.round_id, None)
            health["last_outcome"] = now.isoformat()
            event = db.event_by_id(eid)
            broadcaster.broadcast("event", {"event": event})
            return {"accepted": True, "duplicate": False, "event_id": eid}

    return router
