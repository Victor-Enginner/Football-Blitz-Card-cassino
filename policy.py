"""Policy engine — hard limits, cooldown and operational state machine.

States: OFFLINE -> PAPER -> MANUAL_REVIEW -> COOLDOWN -> STOPPED.
There is NO auto-execution state and there never will be: every check here
returns a BLOCK or an ALLOW for *human-recorded* operations only.
"""
from __future__ import annotations

from datetime import datetime, timezone, date, timedelta

from config import (
    MAX_EVENTS_PER_DAY, STOP_LOSS, STOP_WIN, MAX_SESSION_MINUTES,
    COOLDOWN_MINUTES, HOT_STREAK_ALERT, STATES,
)
import ledger as ledger_mod


class PolicyEngine:
    def __init__(self, db: ledger_mod.Ledger):
        self.db = db

    # -- helpers ---------------------------------------------------------------
    @staticmethod
    def _today() -> str:
        return datetime.now(timezone.utc).date().isoformat()

    @staticmethod
    def _parse(ts: str) -> datetime:
        return datetime.fromisoformat(ts)

    def _minutes_since(self, ts: str | None) -> float | None:
        if not ts:
            return None
        started = self._parse(ts)
        now = datetime.now(timezone.utc)
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        return (now - started).total_seconds() / 60.0

    # -- main gate ---------------------------------------------------------------
    def check(self, session_id: str | None = None) -> dict:
        """Return {'allowed': bool, 'reasons': [..], 'state': str, 'usage': {...}}."""
        reasons: list[str] = []
        session = self.db.get_session(session_id) if session_id else self.db.active_session()

        # 1. kill switch state
        state = session["state"] if session else "OFFLINE"
        if state == "STOPPED":
            reasons.append("state=STOPPED (kill switch)")

        # 2. daily volume hard limit (the 200-bet circuit breaker)
        events_today = self.db.count_events_on(self._today())
        if events_today >= MAX_EVENTS_PER_DAY:
            reasons.append(f"daily limit reached ({events_today}/{MAX_EVENTS_PER_DAY})")

        # 3. stop-loss / stop-win on paper PnL
        pnl = self.db.paper_pnl_today()
        if pnl <= -abs(STOP_LOSS):
            reasons.append(f"stop-loss hit (paper PnL {pnl:+.2f} <= -{abs(STOP_LOSS):.2f})")
        if STOP_WIN > 0 and pnl >= STOP_WIN:
            reasons.append(f"stop-win hit (paper PnL {pnl:+.2f} >= {STOP_WIN:.2f})")

        # 4. session duration
        minutes = self._minutes_since(session["started_at"]) if session else None
        if minutes is not None and minutes >= MAX_SESSION_MINUTES:
            reasons.append(f"session time limit ({minutes:.0f}/{MAX_SESSION_MINUTES} min)")

        # 5. cooldown after forced stop
        last = self._last_session_today()
        if last and last["state"] == "COOLDOWN" and not session:
            ended = last.get("ended_at") or last["started_at"]
            since = self._minutes_since(ended)
            if since is not None and since < COOLDOWN_MINUTES:
                reasons.append(f"cooldown active ({since:.0f}/{COOLDOWN_MINUTES} min)")

        # 6. hot-streak filter (anti-trend guard): >= threshold identical outcomes
        hot = self.db.hot_streak(HOT_STREAK_ALERT)
        if hot:
            reasons.append(
                f"HOT STREAK: '{hot['outcome']}' repeated {hot['run']}x — pause recommended"
            )
            # advisory only: does not block by itself, but is surfaced everywhere

        usage = {
            "events_today": events_today,
            "daily_limit": MAX_EVENTS_PER_DAY,
            "paper_pnl_today": pnl,
            "stop_loss": abs(STOP_LOSS),
            "stop_win": STOP_WIN,
            "session_minutes": round(minutes, 1) if minutes is not None else 0,
            "max_session_minutes": MAX_SESSION_MINUTES,
            "cooldown_minutes": COOLDOWN_MINUTES,
            "hot_streak": hot,
        }
        state = self.derive_state(reasons)
        return {"allowed": not reasons, "reasons": reasons, "state": state, "usage": usage}

    def derive_state(self, reasons: list[str]) -> str:
        if any("kill switch" in r for r in reasons):
            return "STOPPED"
        if any("cooldown" in r for r in reasons):
            return "COOLDOWN"
        if any(("stop-loss" in r or "stop-win" in r or "daily limit" in r or
                "session time" in r) for r in reasons):
            return "MANUAL_REVIEW"
        if any("HOT STREAK" in r for r in reasons):
            return "PAPER"
        return "PAPER"

    def _last_session_today(self) -> dict | None:
        today = self._today()
        rows = self.db._conn.execute(
            "SELECT * FROM sessions WHERE substr(started_at,1,10) = ?"
            " ORDER BY started_at DESC LIMIT 1", (today,)
        ).fetchone()
        return dict(rows) if rows else None

    # -- actions -------------------------------------------------------------------
    def stop(self, session_id: str) -> None:
        """Kill switch: STOPPED blocks everything until human intervention."""
        self.db.set_session_state(session_id, "STOPPED")
        self.db.audit("policy_stop", f"session {session_id} stopped by kill switch")

    def cooldown(self, session_id: str) -> None:
        self.db.set_session_state(session_id, "COOLDOWN")
        self.db.audit("policy_cooldown", f"session {session_id} in cooldown")

    def resume(self, session_id: str) -> None:
        self.db.set_session_state(session_id, "PAPER")
        self.db.audit("policy_resume", f"session {session_id} resumed to PAPER")

    def start(self, note: str = "") -> str:
        import uuid
        session_id = uuid.uuid4().hex
        self.db.start_session(session_id, state="PAPER", note=note)
        self.db.audit("policy_start", f"session {session_id} started (PAPER)")
        return session_id
