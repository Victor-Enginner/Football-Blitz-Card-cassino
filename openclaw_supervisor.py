"""OpenClaw local supervisor for the Football Blitz PAPER pipeline.

The supervisor owns process liveness only: it keeps the local API and the
read-only telemetry monitor alive.  It never places or authorises a bet.
Use ``--once`` for a scheduler and ``--run`` for a long lived daemon.
"""
from __future__ import annotations

import argparse
import calendar
import json
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from config import BASE_DIR, OBSERVER_TOKEN
from observer_capture import capture_token


@dataclass(frozen=True)
class SupervisorConfig:
    base_url: str = "http://127.0.0.1:8766"
    interval_s: float = 60.0
    maintenance_s: float = 1800.0
    monitor_stale_s: float = 150.0
    data_dir: Path = BASE_DIR / "data"


class SingleInstance:
    """Small cross-platform lock, held for the lifetime of the supervisor."""
    def __init__(self, path: Path):
        self.path = path
        self.handle = None

    def acquire(self) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = self.path.open("a+")
        locked = False
        try:
            if os.name == "nt":
                import msvcrt
                self.handle.seek(0)
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            locked = True
            self.handle.seek(0)
            self.handle.truncate()
            self.handle.write(str(os.getpid()))
            self.handle.flush()
            return True
        except (OSError, IOError):
            # Windows may reject close/flush while another handle owns the
            # byte range. Do not attempt an unlock unless this call acquired it.
            try:
                if locked and os.name == "nt":
                    import msvcrt
                    self.handle.seek(0)
                    msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
            except OSError:
                pass
            try:
                self.handle.close()
            except OSError:
                pass
            self.handle = None
            return False

    def close(self) -> None:
        if not self.handle:
            return
        try:
            if os.name == "nt":
                import msvcrt
                self.handle.seek(0)
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
        finally:
            self.handle.close()
            self.handle = None


class OpenClawSupervisor:
    def __init__(self, config: SupervisorConfig | None = None,
                 *, now: Callable[[], float] = time.time):
        self.config = config or SupervisorConfig()
        self.now = now
        self.config.data_dir.mkdir(parents=True, exist_ok=True)
        self.pid_file = self.config.data_dir / "openclaw-supervisor.json"
        self.log_file = self.config.data_dir / "openclaw-supervisor.jsonl"
        self.monitor_pid_file = self.config.data_dir / "capture-monitor.pid"
        self.last_maintenance = self.now()

    def _log(self, kind: str, **fields: Any) -> None:
        record = {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                  "kind": kind, "mode": "PAPER", **fields}
        with self.log_file.open("a", encoding="utf8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _get_json(self, route: str) -> dict[str, Any]:
        request = urllib.request.Request(self.config.base_url + route,
                                          headers={"Accept": "application/json"})
        with urllib.request.urlopen(request, timeout=5) as response:
            return json.loads(response.read().decode("utf8"))

    def backend_ready(self) -> bool:
        try:
            payload = self._get_json("/ready")
            return payload.get("ready") is True
        except (OSError, ValueError, urllib.error.URLError):
            return False

    def ensure_backend(self) -> bool:
        if self.backend_ready():
            return False
        project_python = BASE_DIR.parents[1] / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        python_executable = str(project_python) if project_python.exists() else sys.executable
        command = [python_executable, "-m", "uvicorn", "server:app",
                   "--host", "127.0.0.1", "--port", "8766"]
        output = (self.config.data_dir / "capture-backend.log").open("ab")
        subprocess.Popen(command, cwd=BASE_DIR, stdout=output, stderr=output,
                         stdin=subprocess.DEVNULL,
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                         start_new_session=os.name != "nt")
        self._log("backend_started")
        return True

    def _monitor_pid(self) -> int | None:
        try:
            value = json.loads(self.monitor_pid_file.read_text(encoding="utf8"))
            return int(value["pid"] if isinstance(value, dict) else value)
        except (OSError, ValueError, KeyError, TypeError):
            return None

    @staticmethod
    def _alive(pid: int | None) -> bool:
        if not pid or pid == os.getpid():
            return False
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ValueError):
            return False

    def monitor_stale(self) -> bool:
        checkpoint = self.config.data_dir / "capture-monitor.json"
        try:
            checked = json.loads(checkpoint.read_text(encoding="utf8")).get("checked_at")
            stamp = calendar.timegm(time.strptime(checked[:19], "%Y-%m-%dT%H:%M:%S"))
            return self.now() - stamp > self.config.monitor_stale_s
        except (OSError, ValueError, TypeError, AttributeError):
            return True

    def ensure_monitor(self, *, force: bool = False) -> bool:
        pid = self._monitor_pid()
        if not force and self._alive(pid) and not self.monitor_stale():
            return False
        if force and self._alive(pid):
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                pass
        if not OBSERVER_TOKEN:
            self._log("monitor_blocked", reason="OBSERVER_TOKEN_missing")
            return False
        env = os.environ.copy()
        env["BLITZ_CAPTURE_TOKEN"] = capture_token(OBSERVER_TOKEN)
        log = (self.config.data_dir / "capture-monitor-process.log").open("ab")
        child = subprocess.Popen(["node", str(BASE_DIR / "observer" / "monitor.mjs")],
                                 cwd=BASE_DIR, env=env, stdin=subprocess.DEVNULL,
                                 stdout=log, stderr=log,
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                                 start_new_session=os.name != "nt")
        # The monitor owns a named OS lock; only claim the PID after the child
        # survives its startup window. A competing instance exits fail-closed.
        time.sleep(0.15)
        if child.poll() is not None:
            self._log("monitor_not_started", reason="another_instance_or_lock")
            return False
        self.monitor_pid_file.write_text(json.dumps({"pid": child.pid,
                                                      "started_at": time.time()}), encoding="utf8")
        self._log("monitor_started", pid=child.pid, forced=force)
        return True

    def maintenance(self) -> bool:
        if self.now() - self.last_maintenance < self.config.maintenance_s:
            return False
        self.last_maintenance = self.now()
        changed = self.ensure_monitor(force=True)
        self._log("maintenance", monitor_restarted=changed)
        return changed

    def check_once(self) -> dict[str, Any]:
        backend_started = self.ensure_backend()
        monitor_started = self.ensure_monitor()
        maintenance = self.maintenance()
        state = {"mode": "PAPER", "backend_ready": self.backend_ready(),
                 "monitor_pid": self._monitor_pid(),
                 "monitor_stale": self.monitor_stale(),
                 "backend_started": backend_started,
                 "monitor_started": monitor_started,
                 "maintenance": maintenance, "checked_at": time.time()}
        self.pid_file.write_text(json.dumps(state, indent=2), encoding="utf8")
        return state

    def run(self) -> None:
        lock = SingleInstance(self.config.data_dir / "openclaw-supervisor.lock")
        if not lock.acquire():
            raise SystemExit("OpenClaw supervisor already running")
        try:
            while True:
                self.check_once()
                time.sleep(self.config.interval_s)
        except KeyboardInterrupt:
            self._log("stopped")
        finally:
            lock.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="OpenClaw PAPER supervisor")
    parser.add_argument("--once", action="store_true", help="run one health cycle")
    args = parser.parse_args()
    supervisor = OpenClawSupervisor()
    if args.once:
        print(json.dumps(supervisor.check_once(), indent=2))
    else:
        supervisor.run()


if __name__ == "__main__":
    main()
