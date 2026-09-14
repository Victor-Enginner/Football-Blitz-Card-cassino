"""Game framework — PAPER bet engine over observed events.

Honesty first (spec docs/05): this engine NEVER places real bets and never
talks to the casino. It records *what the human decided* and *what the shoe
actually produced*, then settles PnL on the observed outcome. It exists to
measure hypotheses, not to automate anything.

Bet types (Football Blitz Top Card):
  home/away  -> 1:1, push half on draw (validated RTP 96.27% in PLANO doc)
  draw       -> 11:1 (RTP 89.64%)
  spread_h/spread_a -> 1:1 base (random multiplier phase ignored — cannot be
  predicted; treat spreads as 1:1 unless user records the multiplier)
"""
from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from realtime import broadcaster

# payouts: (net_multiplier_on_stake, draw_treatment)
#   draw_treatment: "lose" (full loss), "push_half" (half stake returned)
PAYOUTS: dict[str, dict[str, Any]] = {
    "home":     {"mult": 1.0,  "draw": "push_half"},
    "away":     {"mult": 1.0,  "draw": "push_half"},
    "draw":     {"mult": 11.0, "draw": "lose"},
}

BET_TYPES = ("home", "away", "draw", "spread_h", "spread_a")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class GameEngine:
    """Append-only paper bets, settled when the observed outcome arrives."""

    def __init__(self, db_path, bankroll_start: float = 200.0):
        self.db_path = db_path
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False, timeout=15.0)
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA synchronous=NORMAL;")
        self._conn.execute("PRAGMA busy_timeout=15000;")
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS paper_bets (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                bet_id      TEXT NOT NULL UNIQUE,
                session_id  TEXT NOT NULL,
                bet_type    TEXT NOT NULL,
                stake       REAL NOT NULL,
                status      TEXT NOT NULL DEFAULT 'open',  -- open|won|lost|push|void
                payout      REAL NOT NULL DEFAULT 0,
                pnl         REAL NOT NULL DEFAULT 0,
                outcome     TEXT,
                opened_at   TEXT NOT NULL,
                settled_at  TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_bets_status ON paper_bets(status);
            CREATE TABLE IF NOT EXISTS bankroll (
                id         INTEGER PRIMARY KEY CHECK (id = 1),
                balance    REAL NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)
        self._conn.execute(
            "INSERT OR IGNORE INTO bankroll (id, balance, updated_at) VALUES (1, ?, ?)",
            (bankroll_start, _now()),
        )
        self._conn.commit()
        self.bankroll_start = bankroll_start
        self._lock = threading.Lock()

    # -- open/settle ----------------------------------------------------------------
    def open_bet(self, session_id: str, bet_type: str, stake: float) -> dict:
        if bet_type not in BET_TYPES:
            raise ValueError(f"bet_type must be one of {BET_TYPES}")
        if stake <= 0:
            raise ValueError("stake must be positive")
        with self._lock:
            bal = self.balance()
            if stake > bal:
                raise ValueError(
                    f"stake R$ {stake:.2f} exceeds paper bankroll R$ {bal:.2f}")
            bet_id = uuid.uuid4().hex
            self._conn.execute(
                "INSERT INTO paper_bets (bet_id, session_id, bet_type, stake, opened_at)"
                " VALUES (?,?,?,?,?)",
                (bet_id, session_id, bet_type, stake, _now()),
            )
            self._conn.execute(
                "INSERT INTO bankroll (id, balance, updated_at) VALUES (1, ?, ?)"
                " ON CONFLICT(id) DO UPDATE SET balance = balance - ?, updated_at = ?",
                (bal - stake, _now(), stake, _now()),
            )
            self._conn.commit()
        bet = self.get_bet(bet_id)
        broadcaster.broadcast("bet_opened", {"bet": bet, "bankroll": self.balance()})
        return bet

    def settle(self, outcome: str) -> list[dict]:
        """Settle all open bets against an observed outcome ('home'|'away'|'draw')."""
        if outcome not in PAYOUTS:
            return []
        with self._lock:
            open_bets = [dict(r) for r in self._conn.execute(
                "SELECT * FROM paper_bets WHERE status = 'open'")]
            settled: list[dict] = []
            delta = 0.0
            for b in open_bets:
                if b["bet_type"] not in PAYOUTS:
                    # spreads: base 1:1; spread_h wins on 'home', spread_a on 'away'; draw loses
                    wins = (b["bet_type"] == "spread_h" and outcome == "home") or \
                           (b["bet_type"] == "spread_a" and outcome == "away")
                    status = "won" if wins else "lost"
                    payout = b["stake"] * 2.0 if wins else 0.0
                else:
                    p = PAYOUTS[b["bet_type"]]
                    if outcome == b["bet_type"]:
                        status, payout = "won", b["stake"] * (1 + p["mult"])
                    elif outcome == "draw" and p["draw"] == "push_half":
                        status, payout = "push", b["stake"] * 0.5
                    else:
                        status, payout = "lost", 0.0
                pnl = payout - b["stake"]
                delta += payout
                self._settle_one(b["bet_id"], status, payout, pnl, outcome)
                settled.append({**b, "status": status, "payout": payout,
                                "pnl": pnl, "outcome": outcome})
            if delta > 0 or settled:
                bal = self._read_balance()
                self._conn.execute(
                    "UPDATE bankroll SET balance = balance + ?, updated_at = ? WHERE id = 1",
                    (delta, _now()))
                self._conn.commit()
            for b in settled:
                broadcaster.broadcast("bet_settled", {"bet": b, "bankroll": self.balance()})
        return settled

    def _settle_one(self, bet_id: str, status: str, payout: float, pnl: float,
                    outcome: str) -> None:
        self._conn.execute(
            "UPDATE paper_bets SET status=?, payout=?, pnl=?, outcome=?, settled_at=?"
            " WHERE bet_id=? AND status='open'",
            (status, payout, pnl, outcome, _now(), bet_id))

    def _read_balance(self) -> float:
        row = self._conn.execute("SELECT balance FROM bankroll WHERE id=1").fetchone()
        return float(row["balance"]) if row and row["balance"] is not None else self.bankroll_start

    # -- queries --------------------------------------------------------------------
    def balance(self) -> float:
        return round(self._read_balance(), 2)

    def get_bet(self, bet_id: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM paper_bets WHERE bet_id = ?", (bet_id,)).fetchone()
        return dict(row) if row else None

    def open_bets(self) -> list[dict]:
        return [dict(r) for r in self._conn.execute(
            "SELECT * FROM paper_bets WHERE status='open' ORDER BY id")]

    def recent_bets(self, n: int = 30) -> list[dict]:
        return [dict(r) for r in self._conn.execute(
            "SELECT * FROM paper_bets ORDER BY id DESC LIMIT ?", (n,))]

    def stats(self) -> dict:
        row = self._conn.execute("""
            SELECT
              COUNT(*)                                   AS total,
              SUM(CASE WHEN status='won'  THEN 1 ELSE 0 END) AS wins,
              SUM(CASE WHEN status='lost' THEN 1 ELSE 0 END) AS losses,
              SUM(CASE WHEN status='push' THEN 1 ELSE 0 END) AS pushes,
              SUM(pnl)                                   AS pnl_total,
              SUM(CASE WHEN status='open' THEN stake ELSE 0 END) AS at_risk
            FROM paper_bets
        """).fetchone()
        d = dict(row)
        for k in ("pnl_total", "at_risk"):
            d[k] = round(d[k] or 0.0, 2)
        bal = self.balance()
        d["bankroll"] = bal
        d["roi_pct"] = round(
            100 * d["pnl_total"] / max(1e-9, self.bankroll_start), 2)
        return d
