"""Append-only event ledger with hash chain (tamper-evident, no destructive updates).

Every event carries: id, session_id, observed_at, outcome, data_origin,
raw_hash, parser_version. Corrections create NEW events — never overwrite.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone, date, timedelta
from typing import Any, Iterator

from config import DB_PATH, DATA_ORIGINS

_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id        TEXT NOT NULL UNIQUE,
    session_id      TEXT NOT NULL,
    round_id        TEXT,
    observed_at     TEXT NOT NULL,
    outcome         TEXT NOT NULL,
    data_origin     TEXT NOT NULL,
    raw_hash        TEXT,
    parser_version  TEXT NOT NULL,
    source_latency_ms INTEGER,
    metadata        TEXT NOT NULL DEFAULT '{}',
    prev_hash       TEXT NOT NULL,
    hash            TEXT NOT NULL,
    inserted_at     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id);
CREATE INDEX IF NOT EXISTS idx_events_day ON events(observed_at);

CREATE TABLE IF NOT EXISTS sessions (
    session_id   TEXT PRIMARY KEY,
    started_at   TEXT NOT NULL,
    ended_at     TEXT,
    state        TEXT NOT NULL DEFAULT 'PAPER',
    note         TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS hypotheses (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at   TEXT NOT NULL,
    text         TEXT NOT NULL,
    params       TEXT NOT NULL DEFAULT '{}',
    period       TEXT NOT NULL DEFAULT '',
    stop_rule    TEXT NOT NULL DEFAULT '',
    status       TEXT NOT NULL DEFAULT 'open'
);

CREATE TABLE IF NOT EXISTS manual_decisions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id   TEXT NOT NULL,
    decided_at   TEXT NOT NULL,
    action       TEXT NOT NULL,
    rationale    TEXT NOT NULL DEFAULT '',
    blocked_by   TEXT,
    prev_hash    TEXT NOT NULL,
    hash         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    at           TEXT NOT NULL,
    kind         TEXT NOT NULL,
    detail       TEXT NOT NULL,
    prev_hash    TEXT NOT NULL,
    hash         TEXT NOT NULL
);
"""

# RLock: _tx() segura o lock e métodos internos (ex.: _last_hash) reassumem
# o lock; leituras de rota quente (last_events) compartilham a mesma proteção.
_LOCK = threading.RLock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _digest(prev_hash: str, payload: dict[str, Any]) -> str:
    canon = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256((prev_hash + canon).encode("utf-8")).hexdigest()


class Ledger:
    """Append-only store. All mutations are INSERTs; hash chain detects tampering."""

    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False, timeout=15.0)
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA synchronous=NORMAL;")
        self._conn.execute("PRAGMA busy_timeout=15000;")
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        # seed audit chain ONCE (only when empty) with a properly hashed genesis row
        _empty = self._conn.execute(
            "SELECT NOT EXISTS (SELECT 1 FROM audit_log) AS empty"
        ).fetchone()["empty"]
        if _empty:
            _init_at = _now()
            _init_payload = {"kind": "ledger_init", "detail": "created", "at": _init_at}
            self._conn.execute(
                "INSERT INTO audit_log (at, kind, detail, prev_hash, hash) VALUES (?,?,?,?,?)",
                (_init_at, "ledger_init", "created", "0" * 64,
                 _digest("0" * 64, _init_payload)),
            )
        self._conn.commit()

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        with _LOCK:
            try:
                yield self._conn
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    # -- hash-chain heads -----------------------------------------------------
    _CHAIN_TABLES = frozenset({"events", "audit_log", "manual_decisions"})

    def _last_hash(self, table: str) -> str:
        if table not in self._CHAIN_TABLES:
            raise ValueError(f"unknown chain table: {table}")
        # allowlist + query fixa por tabela (Bandit B608: sem f-string em SQL)
        if table == "events":
            q = "SELECT hash FROM events ORDER BY id DESC LIMIT 1"
        elif table == "audit_log":
            q = "SELECT hash FROM audit_log ORDER BY id DESC LIMIT 1"
        else:
            q = "SELECT hash FROM manual_decisions ORDER BY id DESC LIMIT 1"
        with _LOCK:
            row = self._conn.execute(q).fetchone()
        return row["hash"] if row else "0" * 64

    # -- events ---------------------------------------------------------------
    def append_event(
        self,
        session_id: str,
        observed_at: str,
        outcome: str,
        data_origin: str,
        parser_version: str = "cc-1.0.0",
        event_id: str | None = None,
        round_id: str | None = None,
        raw_hash: str | None = None,
        source_latency_ms: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if data_origin not in DATA_ORIGINS:
            raise ValueError(f"data_origin must be one of {DATA_ORIGINS}, got {data_origin!r}")
        if not outcome or not isinstance(outcome, str):
            raise ValueError("outcome must be a non-empty string")
        if not session_id or len(session_id) < 8:
            raise ValueError("session_id must be at least 8 chars")
        if not observed_at:
            raise ValueError("observed_at is required — events without timestamp are rejected")
        event_id = event_id or uuid.uuid4().hex
        metadata = metadata or {}
        payload = {
            "event_id": event_id,
            "session_id": session_id,
            "observed_at": observed_at,
            "outcome": outcome,
            "data_origin": data_origin,
        }
        with self._tx() as conn:
            prev = self._last_hash("events")
            h = _digest(prev, payload)
            conn.execute(
                "INSERT INTO events (event_id, session_id, round_id, observed_at, outcome,"
                " data_origin, raw_hash, parser_version, source_latency_ms, metadata,"
                " prev_hash, hash, inserted_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    event_id, session_id, round_id, observed_at, outcome, data_origin,
                    raw_hash, parser_version, source_latency_ms,
                    json.dumps(metadata, ensure_ascii=False), prev, h, _now(),
                ),
            )
        return {"event_id": event_id, "hash": h, "prev_hash": prev}

    def event_by_id(self, event_id: str) -> dict[str, Any] | None:
        with _LOCK:
            row = self._conn.execute(
                "SELECT * FROM events WHERE event_id = ?", (event_id,)
            ).fetchone()
        return dict(row) if row else None

    def capture_history(self, session_id: str, limit: int = 200) -> list[dict[str, Any]]:
        with _LOCK:
            rows = self._conn.execute(
                "SELECT id, event_id, session_id, round_id, outcome, observed_at FROM events "
                "WHERE session_id = ? AND data_origin = 'authorized_readonly' "
                "AND parser_version = 'fb-banner-1.0' ORDER BY id DESC LIMIT ?",
                (session_id, max(1, min(limit, 500))),
            ).fetchall()
        return [dict(row) for row in reversed(rows)]

    def events_for_session(self, session_id: str) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM events WHERE session_id = ? ORDER BY id", (session_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def last_events(self, n: int = 20) -> list[dict[str, Any]]:
        # leitura de rota quente: mesmo lock dos writers evita corrida de threads
        # no objeto Connection compartilhado (InterfaceError/IndexError intermitente)
        with _LOCK:
            rows = self._conn.execute(
                "SELECT * FROM events ORDER BY id DESC LIMIT ?", (n,)
            ).fetchall()
        return [dict(r) for r in reversed(rows)]

    def count_events_on(self, day: str) -> int:
        """day = YYYY-MM-DD (UTC date part of observed_at)."""
        with _LOCK:
            row = self._conn.execute(
                "SELECT COUNT(*) AS c FROM events WHERE substr(observed_at, 1, 10) = ?",
                (day,),
            ).fetchone()
        return int(row["c"])

    # -- sessions ---------------------------------------------------------------
    def start_session(self, session_id: str, state: str = "PAPER", note: str = "") -> None:
        with self._tx() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO sessions (session_id, started_at, state, note)"
                " VALUES (?,?,?,?)",
                (session_id, _now(), state, note),
            )

    def set_session_state(self, session_id: str, state: str) -> None:
        with self._tx() as conn:
            conn.execute(
                "UPDATE sessions SET state = ? WHERE session_id = ?", (state, session_id)
            )

    def end_session(self, session_id: str) -> None:
        with self._tx() as conn:
            conn.execute(
                "UPDATE sessions SET ended_at = ? WHERE session_id = ?", (_now(), session_id)
            )

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        with _LOCK:
            row = self._conn.execute(
                "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
        return dict(row) if row else None

    def active_session(self) -> dict[str, Any] | None:
        with _LOCK:
            row = self._conn.execute(
                "SELECT * FROM sessions WHERE ended_at IS NULL ORDER BY started_at DESC LIMIT 1"
            ).fetchone()
        return dict(row) if row else None

    # -- hypotheses -------------------------------------------------------------
    def add_hypothesis(self, text: str, params: dict | None = None,
                       period: str = "", stop_rule: str = "") -> int:
        with self._tx() as conn:
            cur = conn.execute(
                "INSERT INTO hypotheses (created_at, text, params, period, stop_rule)"
                " VALUES (?,?,?,?,?)",
                (_now(), text, json.dumps(params or {}), period, stop_rule),
            )
            return int(cur.lastrowid)

    def list_hypotheses(self) -> list[dict[str, Any]]:
        with _LOCK:
            rows = self._conn.execute("SELECT * FROM hypotheses ORDER BY id DESC").fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["params"] = json.loads(d["params"])
            out.append(d)
        return out

    # -- manual decisions (hash-chained) ----------------------------------------
    def add_decision(self, session_id: str, action: str, rationale: str = "",
                     blocked_by: str | None = None) -> dict[str, Any]:
        payload = {"session_id": session_id, "action": action, "decided_at": _now()}
        with self._tx() as conn:
            prev = self._last_hash("manual_decisions")
            h = _digest(prev, payload)
            conn.execute(
                "INSERT INTO manual_decisions (session_id, decided_at, action, rationale,"
                " blocked_by, prev_hash, hash) VALUES (?,?,?,?,?,?,?)",
                (session_id, payload["decided_at"], action, rationale, blocked_by, prev, h),
            )
        return {"hash": h}

    def last_decision_blocked(self) -> bool:
        row = self._conn.execute(
            "SELECT blocked_by FROM manual_decisions ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return bool(row and row["blocked_by"])

    # -- audit log (hash-chained) ------------------------------------------------
    def audit(self, kind: str, detail: str) -> None:
        payload = {"kind": kind, "detail": detail, "at": _now()}
        with self._tx() as conn:
            prev = self._last_hash("audit_log")
            h = _digest(prev, payload)
            conn.execute(
                "INSERT INTO audit_log (at, kind, detail, prev_hash, hash)"
                " VALUES (?,?,?,?,?)",
                (payload["at"], kind, detail, prev, h),
            )

    # -- integrity ---------------------------------------------------------------
    def verify_chain(self) -> dict[str, Any]:
        report: dict[str, Any] = {"events": True, "audit_log": True, "manual_decisions": True}
        for table, cols in (
            ("events", ("event_id", "session_id", "observed_at", "outcome", "data_origin")),
            ("manual_decisions", ("session_id", "action", "decided_at")),
            ("audit_log", ("kind", "detail", "at")),
        ):
            prev = "0" * 64
            with _LOCK:
                iterator = self._conn.execute(
                    "SELECT * FROM events ORDER BY id" if table == "events" else
                    "SELECT * FROM audit_log ORDER BY id" if table == "audit_log" else
                    "SELECT * FROM manual_decisions ORDER BY id"
                )
                chain_rows = iterator.fetchall()
            for row in chain_rows:
                payload = {c: row[c] for c in cols}
                expected = _digest(prev, payload)
                if row["prev_hash"] != prev or row["hash"] != expected:
                    report[table] = False
                    break
                prev = row["hash"]
        return report

    # -- analytics ----------------------------------------------------------------
    def stats(self, session_id: str | None = None) -> dict[str, Any]:
        where, args = ("WHERE session_id = ?", [session_id]) if session_id else ("", [])
        with _LOCK:
            if where:
                row = self._conn.execute("SELECT COUNT(*) AS n FROM events WHERE session_id = ?", args).fetchone()
            else:
                row = self._conn.execute("SELECT COUNT(*) AS n FROM events", []).fetchone()
            total = int(row["n"])
            if where:
                freq = self._conn.execute(
                    "SELECT outcome, COUNT(*) AS c FROM events WHERE session_id = ? GROUP BY outcome ORDER BY c DESC LIMIT 15", args
                ).fetchall()
            else:
                freq = self._conn.execute(
                    "SELECT outcome, COUNT(*) AS c FROM events GROUP BY outcome ORDER BY c DESC LIMIT 15", []
                ).fetchall()
        return {
            "total_events": total,
            "outcome_frequency": [{"outcome": r["outcome"], "count": r["c"]} for r in freq],
        }

    def hot_streak(self, threshold: int) -> dict[str, Any] | None:
        """Longest run of identical trailing outcomes."""
        with _LOCK:
            rows = self._conn.execute(
                "SELECT outcome FROM events ORDER BY id DESC LIMIT 200"
            ).fetchall()
        if not rows:
            return None
        first = rows[0]["outcome"]
        run = 0
        for r in rows:
            if r["outcome"] == first:
                run += 1
            else:
                break
        if run >= threshold:
            return {"outcome": first, "run": run}
        return None

    def paper_pnl_today(self, day: str | None = None) -> float:
        """Sum of paper PnL recorded in event metadata.pnl for the given UTC day."""
        day = day or datetime.now(timezone.utc).date().isoformat()
        with _LOCK:
            rows = self._conn.execute(
                "SELECT metadata FROM events WHERE substr(observed_at,1,10) = ?",
                (day,),
            ).fetchall()
        total = 0.0
        for r in rows:
            try:
                meta = json.loads(r["metadata"])
                total += float(meta.get("pnl", 0.0))
            except (ValueError, TypeError):
                continue
        return round(total, 2)

    def close(self) -> None:
        self._conn.close()
