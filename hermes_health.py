"""Hermes healthchecker for the local Football Blitz capture pipeline.

Hermes observes backend readiness, observer heartbeat/data freshness and the
ledger chain.  It never mutates the ledger, starts a browser or places bets.
Alerts are append-only local records emitted only when the derived health
state changes.  ``--once`` is provided for service probes and deterministic
tests; the default mode polls every 15 seconds.
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from config import BASE_DIR, OBSERVER_TOKEN
from observer_capture import capture_token

DEFAULT_BASE = "http://127.0.0.1:8766"
DEFAULT_INTERVAL = 15.0
DEFAULT_TIMEOUT = 4.0
OFFLINE_AFTER = 120.0
STALE_AFTER = 120.0


def health_of(ready: dict[str, Any], status: dict[str, Any]) -> str:
    """Derive a fail-closed state from the two backend health contracts."""
    if not ready.get("ready", False) or not all(ready.get("chain", {}).values() or [False]):
        return "backend_not_ready"
    if not status.get("observer_online", False):
        return "observer_offline"
    if status.get("data_stale", True):
        return "capture_stale"
    return "ok"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class HermesHealth:
    def __init__(
        self,
        base_url: str = DEFAULT_BASE,
        token: str = "",
        data_dir: Path | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        fetch: Callable[[str, dict[str, str], float], dict[str, Any]] | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.data_dir = data_dir or (BASE_DIR / "data")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoint = self.data_dir / "hermes-health.json"
        self.log_path = self.data_dir / "hermes-health.jsonl"
        self.timeout = timeout
        self.fetch = fetch or fetch_json
        self.state = self._load_state()

    def _load_state(self) -> dict[str, Any]:
        try:
            value = json.loads(self.checkpoint.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {}
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return {}

    def _save_state(self) -> None:
        # Replace in the same directory so a crash cannot leave a partial JSON.
        fd, temporary = tempfile.mkstemp(prefix="hermes-health-", suffix=".tmp", dir=self.data_dir)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(self.state, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.checkpoint)
        finally:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass

    def _record_transition(self, health: str, detail: dict[str, Any]) -> None:
        previous = self.state.get("health")
        if previous == health:
            return
        entry = {"at": _utc_now(), "kind": "health_changed",
                 "previous": previous, "health": health, **detail}
        with self.log_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False, separators=(",", ":")) + "\n")

    def check_once(self) -> dict[str, Any]:
        detail: dict[str, Any] = {}
        try:
            headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
            ready = self._get("/ready", headers)
            status = self._get("/api/observer/status", headers)
            health = health_of(ready, status)
            detail = {"ledger": ready.get("chain", {}),
                      "observer_online": status.get("observer_online", False),
                      "heartbeat_age_s": status.get("heartbeat_age_s"),
                      "data_stale": status.get("data_stale", True),
                      "outcome_age_s": status.get("outcome_age_s")}
        except HTTPError as exc:
            health = "authentication_failed" if exc.code == 401 else "backend_unreachable"
            detail = {"error": f"http_{exc.code}"}
        except (OSError, URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            health = "backend_unreachable"
            detail = {"error": type(exc).__name__}

        self._record_transition(health, detail)
        self.state.update({"health": health, "checked_at": _utc_now(), "base_url": self.base_url})
        self._save_state()
        return {"health": health, **detail}

    def _get(self, route: str, headers: dict[str, str]) -> dict[str, Any]:
        """GET with bounded retry/backoff; authentication errors fail fast."""
        last: Exception | None = None
        for attempt in range(3):
            try:
                return self.fetch(self.base_url + route, headers, self.timeout)
            except HTTPError as exc:
                if exc.code == 401:
                    raise
                last = exc
            except (OSError, URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
                last = exc
            if attempt < 2:
                time.sleep(0.5 * (2 ** attempt))
        assert last is not None
        raise last

    def run(self, interval: float = DEFAULT_INTERVAL) -> None:
        stopped = False

        def stop(_signum: int, _frame: Any) -> None:
            nonlocal stopped
            stopped = True

        for name in ("SIGINT", "SIGTERM"):
            signum = getattr(signal, name, None)
            if signum is not None:
                signal.signal(signum, stop)
        while not stopped:
            self.check_once()
            if not stopped:
                time.sleep(max(0.1, interval))


def fetch_json(route: str, headers: dict[str, str], timeout: float) -> dict[str, Any]:
    # The route is produced by this module; redirect handling is disabled to
    # prevent credentials being sent to another host.
    request = Request(route, headers=headers, method="GET")
    class _NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, new):
            return None

    opener = build_opener(_NoRedirect)
    with opener.open(request, timeout=timeout) as response:  # noqa: S310 - configured endpoint
        if response.geturl().split("/", 3)[:3] != route.split("/", 3)[:3]:
            raise OSError("unexpected redirect")
        value = json.loads(response.read().decode("utf-8"))
        if not isinstance(value, dict):
            raise ValueError("health response must be an object")
        return value


def main() -> None:
    parser = argparse.ArgumentParser(description="Hermes local capture healthchecker")
    parser.add_argument("--once", action="store_true", help="run one check and exit")
    parser.add_argument("--interval", type=float, default=float(os.getenv("HERMES_INTERVAL_S", DEFAULT_INTERVAL)))
    parser.add_argument("--base-url", default=os.getenv("HERMES_BASE_URL", DEFAULT_BASE))
    args = parser.parse_args()
    token = capture_token(OBSERVER_TOKEN)
    if not token:
        raise SystemExit("OBSERVER_TOKEN required")
    checker = HermesHealth(base_url=args.base_url, token=token)
    result = checker.check_once() if args.once else checker.run(args.interval)
    if args.once:
        print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
