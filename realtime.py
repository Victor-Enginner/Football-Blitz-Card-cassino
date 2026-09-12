"""Realtime broadcast layer — WebSocket channel for live dashboard/agents.

Tokens: if OBSERVER_TOKEN is set in env, /ws and /api/ingest require it.
Local-first default (token unset): loopback usage without auth, as before.
"""
from __future__ import annotations

import asyncio
import json
import logging
import threading
from typing import Any

from fastapi import WebSocket

log = logging.getLogger("realtime")


class Broadcaster:
    """Thread-safe fan-out of events to connected WebSocket clients.

    Events are produced either by the FastAPI threadpool (sync routes) or by
    the observer bridge; both call broadcast() which schedules the async send
    on the server's running loop.
    """

    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None

    def attach_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        with self._lock:
            self._clients.add(ws)
        log.info("ws client connected (%d online)", len(self._clients))

    def disconnect(self, ws: WebSocket) -> None:
        with self._lock:
            self._clients.discard(ws)

    @property
    def count(self) -> int:
        with self._lock:
            return len(self._clients)

    def broadcast(self, kind: str, payload: dict[str, Any]) -> None:
        """Called from any thread; schedules async sends on the event loop."""
        message = json.dumps({"kind": kind, **payload}, ensure_ascii=False, default=str)

        async def _send_all() -> None:
            dead: list[WebSocket] = []
            with self._lock:
                targets = list(self._clients)
            for ws in targets:
                try:
                    await ws.send_text(message)
                except Exception:  # noqa: BLE001
                    dead.append(ws)
            for ws in dead:
                self.disconnect(ws)

        loop = self._loop
        if loop is None or loop.is_closed():
            return
        try:
            asyncio.run_coroutine_threadsafe(_send_all(), loop)
        except RuntimeError:
            pass


broadcaster = Broadcaster()
