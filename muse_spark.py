"""Deterministic, read-only telemetry analysis for Muse Spark.

This module deliberately does not import betting/strategy code and has no order
side effects.  It turns observer history into an auditable descriptive report.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from config import DATA_DIR, DB_PATH
from ledger import Ledger


VALID_OUTCOMES = {"home", "away", "draw"}


def _stamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _ordered(events: Iterable[dict[str, Any]], window: int) -> list[dict[str, Any]]:
    """Keep valid observer events in observed order, bounded to ``window``."""
    out = []
    for event in events:
        if event.get("outcome") not in VALID_OUTCOMES or not _stamp(event.get("observed_at")):
            continue
        out.append(event)
    return out[-max(1, min(int(window), 500)):]


def analyze_events(events: Iterable[dict[str, Any]], window: int = 200,
                   risk_threshold: float = 0.70) -> dict[str, Any]:
    """Return deterministic descriptive metrics for the most recent events.

    ``risk_score`` is explicitly descriptive: current same-side streak divided
    by the analysis window (``N_segues / T_janela``), capped at one.  It is not
    a probability and never authorizes a bet.
    """
    rows = _ordered(events, window)
    outcomes = [row["outcome"] for row in rows]
    frequency = Counter(outcomes)
    total = len(outcomes)
    side = outcomes[-1] if outcomes else None
    streak = 0
    if side in {"home", "away"}:
        for value in reversed(outcomes):
            if value != side:
                break
            streak += 1
    # Draws are valid telemetry but terminate a danger streak.
    risk_score = round(min(1.0, streak / max(1, total)), 6)
    entropy = 0.0
    if total:
        entropy = round(-sum((count / total) * math.log2(count / total)
                             for count in frequency.values()), 6)
    danger = bool(side in {"home", "away"} and streak >= 4)
    threshold_danger = risk_score >= max(0.0, min(1.0, float(risk_threshold)))
    return {
        "analyzed_at": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "window": len(rows),
        "event_ids": [row.get("event_id") for row in rows],
        "frequency": {key: frequency.get(key, 0) for key in ("home", "away", "draw")},
        "current_outcome": side,
        "current_streak": streak,
        "entropy_bits": entropy,
        "risk_score": risk_score,
        "risk_threshold": float(risk_threshold),
        "risk_danger_window": danger or threshold_danger,
        "danger_reason": ("same_outcome_streak" if danger else
                           "risk_threshold" if threshold_danger else None),
        "mode": "READONLY_ANALYSIS",
        "orders_allowed": False,
    }


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                rows.append(value)
    return rows


def monitor_danger_windows(path: Path) -> list[dict[str, Any]]:
    """Extract monitor sequence notices for correlation, without replaying them."""
    return [row for row in read_jsonl(path)
            if row.get("kind") == "historical_sequence" and row.get("count", 0) >= 4]


class MuseSpark:
    def __init__(self, data_dir: Path = DATA_DIR, db_path: Path = DB_PATH,
                 risk_threshold: float | None = None):
        self.data_dir = Path(data_dir)
        self.db_path = Path(db_path)
        self.risk_threshold = (float(risk_threshold) if risk_threshold is not None else
                               float(os.getenv("MUSE_RISK_THRESHOLD", "0.70")))
        self.report_path = self.data_dir / "muse-spark.jsonl"
        self.marker_path = self.data_dir / "muse-risk-danger.json"

    def run_once(self, events: Iterable[dict[str, Any]] | None = None,
                 window: int = 200) -> dict[str, Any]:
        if events is None:
            ledger = Ledger(self.db_path)
            try:
                session = ledger.active_session()
                events = ledger.capture_history(session["session_id"], window) if session else []
            finally:
                ledger.close()
        report = analyze_events(events, window, self.risk_threshold)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        with self.report_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(report, ensure_ascii=False, separators=(",", ":")) + "\n")
        if report["risk_danger_window"]:
            marker = {"event_id": report["event_ids"][-1] if report["event_ids"] else None,
                      "streak": report["current_streak"], "risk_score": report["risk_score"],
                      "marked_at": report["analyzed_at"], "mode": "READONLY_ANALYSIS"}
            previous = None
            if self.marker_path.exists():
                try:
                    previous = json.loads(self.marker_path.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    pass
            if not previous or previous.get("event_id") != marker["event_id"]:
                self.marker_path.write_text(json.dumps(marker, ensure_ascii=False, indent=2), encoding="utf-8")
                # Audit marker is append-only and deduplicated by the same
                # latest event marker. It records analysis state only; it
                # cannot enqueue, settle, or authorize an order.
                ledger = Ledger(self.db_path)
                try:
                    ledger.audit("risk_danger_window", json.dumps(marker, ensure_ascii=False, separators=(",", ":")))
                finally:
                    ledger.close()
        return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Muse Spark read-only ledger analysis")
    parser.add_argument("--once", action="store_true", help="analyze current ledger once")
    parser.add_argument("--window", type=int, default=200)
    args = parser.parse_args()
    report = MuseSpark().run_once(window=args.window)
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
