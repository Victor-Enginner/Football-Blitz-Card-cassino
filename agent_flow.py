"""Deterministic local orchestration for OpenClaw, Hermes and Muse Spark.

The flow is intentionally boring: supervisor first, health second, analysis
last. It writes an auditable local record and never sends orders or external
messages. Use ``--once`` for a reviewable cycle and ``--run`` for a daemon.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from config import BASE_DIR, OBSERVER_TOKEN
from hermes_health import HermesHealth
from muse_spark import MuseSpark
from openclaw_supervisor import OpenClawSupervisor
from observer_capture import capture_token


class AgentFlow:
    def __init__(self, data_dir: Path | None = None):
        self.data_dir = data_dir or (BASE_DIR / "data")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = self.data_dir / "agent-flow.jsonl"
        self.supervisor = OpenClawSupervisor()
        self.hermes = HermesHealth(token=capture_token(OBSERVER_TOKEN), data_dir=self.data_dir)
        self.muse = MuseSpark(data_dir=self.data_dir)

    def _record(self, payload: dict) -> None:
        row = {"at": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
               "mode": "PAPER", "orders_allowed": False, **payload}
        with self.log_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")

    def once(self) -> dict:
        if not OBSERVER_TOKEN:
            result = {"flow": "blocked", "reason": "OBSERVER_TOKEN_missing"}
            self._record(result)
            return result
        openclaw = self.supervisor.check_once()
        hermes = self.hermes.check_once()
        muse = self.muse.run_once()
        result = {"flow": "complete", "openclaw": openclaw,
                  "hermes": hermes, "muse": {
                      "window": muse["window"], "current_streak": muse["current_streak"],
                      "risk_score": muse["risk_score"],
                      "risk_danger_window": muse["risk_danger_window"]},
                  "sequence_policy": "observe_only", "orders_allowed": False}
        self._record(result)
        return result

    def run(self, interval: float = 15.0) -> None:
        stopped = False
        def stop(*_args):
            nonlocal stopped
            stopped = True
        try:
            import signal
            signal.signal(signal.SIGINT, stop)
            signal.signal(signal.SIGTERM, stop)
        except (ValueError, OSError):
            pass
        while not stopped:
            self.once()
            if not stopped:
                time.sleep(max(1.0, interval))


def main() -> int:
    parser = argparse.ArgumentParser(description="Football Blitz PAPER agent flow")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--once", action="store_true", help="run one deterministic cycle")
    mode.add_argument("--run", action="store_true", help="run cycles until stopped")
    parser.add_argument("--interval", type=float, default=float(os.getenv("AGENT_FLOW_INTERVAL_S", "15")))
    args = parser.parse_args()
    flow = AgentFlow()
    if args.run:
        flow.run(args.interval)
    else:
        print(json.dumps(flow.once(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
