"""Telegram notifier — alerts for GREEN/RED events, blocks, hot streaks, reports.

Uses the bot created via @BotFather. Token/chat come from env (TELEGRAM_TOKEN /
TELEGRAM_CHAT_ID). If unset, the notifier is a no-op (never crashes the server).

Language policy (spec docs/05): neutral wording — "resultado observado",
"hipótese", "amostra". Never "sinal certeiro", "entrada garantida", "recuperar".
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone

import requests

from config import OMNIROUTE_MODEL
import config as config_mod

log = logging.getLogger("telegram")


class TelegramNotifier:
    """Fire-and-forget Telegram alerts. All sends run on a daemon thread."""

    def __init__(self) -> None:
        self.token = config_mod.TELEGRAM_TOKEN
        self.chat_id = config_mod.TELEGRAM_CHAT_ID
        self.base = f"https://api.telegram.org/bot{self.token}" if self.token else None
        self.enabled = bool(self.token and self.chat_id)
        self._stop = threading.Event()

    # -- low-level send -------------------------------------------------------
    def _post(self, method: str, data: dict) -> bool:
        if not self.enabled:
            return False
        try:
            r = requests.post(f"{self.base}/{method}", data=data, timeout=15)
            if r.status_code != 200:
                log.warning("telegram %s -> %s", r.status_code, r.text[:150])
                return False
            return True
        except requests.RequestException as e:
            log.warning("telegram send failed: %s", e)
            return False

    def send(self, text: str, silent: bool = False) -> bool:
        """Send markdown message; never raises."""
        return self._post("sendMessage", {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "Markdown",
            "disable_notification": silent,
        })

    # -- event alerts -----------------------------------------------------------
    def event_added(self, ev: dict) -> None:
        pnl = ""
        meta = ev.get("metadata") or {}
        if isinstance(meta, str):
            try:
                import json
                meta = json.loads(meta)
            except Exception:  # noqa: BLE001
                meta = {}
        if meta and "pnl" in meta:
            pnl = f" | PnL papel: R$ {float(meta['pnl']):+.2f}"
        icon = "🟢" if float(meta.get("pnl", 0) or 0) >= 0 else "🔴"
        self.send(
            f"{icon} *Resultado observado*: `{ev['outcome']}`\n"
            f"origem: {ev.get('data_origin', '—')}{pnl}\n"
            f"`{ev.get('observed_at', '')[:19]}Z`",
            silent=True,
        )

    def blocked(self, reasons: list[str]) -> None:
        self.send("🚫 *Ação bloqueada pela política:*\n" +
                  "\n".join(f"⛔ {r}" for r in reasons))

    def hot_streak(self, hot: dict) -> None:
        self.send(
            f"🔥 *Mesa quente*: `{hot['outcome']}` repetiu {hot['run']}x\n"
            f"_{HOT_MSG}_",
        )

    def session_started(self, session_id: str, state: str) -> None:
        self.send(f"▶️ Sessão iniciada em *{state}*\n`{session_id}`")

    def state_change(self, new_state: str, detail: str = "") -> None:
        self.send(f"⚠️ Estado da operação: *{new_state}* {detail}")

    def daily_report(self, stats: dict, usage: dict) -> None:
        lines = [
            "📊 *Relatório do dia* (descritivo, sem valor preditivo)",
            f"Eventos hoje: *{usage['events_today']}/{usage['daily_limit']}*",
            f"PnL papel: *R$ {usage['paper_pnl_today']:+.2f}*",
            f"Sessão: *{usage['session_minutes']}/{usage['max_session_minutes']} min*",
        ]
        if usage.get("hot_streak"):
            h = usage["hot_streak"]
            lines.append(f"Mesa quente: `{h['outcome']}` ×{h['run']}")
        if stats.get("outcome_frequency"):
            top = stats["outcome_frequency"][:3]
            lines.append("Top resultados: " + ", ".join(
                f"{f['outcome']} ({f['count']})" for f in top))
        lines.append(f"_modelo analítico: {OMNIROUTE_MODEL}_")
        self.send("\n".join(lines))

    def health(self, status: str, detail: str = "") -> None:
        icon = "✅" if status == "ok" else "🛑"
        self.send(f"{icon} Command Center: *{status}* {detail}".strip())

    # -- command polling (optional, non-blocking) --------------------------------
    def start_polling(self, handlers: dict[str, callable]) -> None:
        """Start a daemon thread answering /commands via long polling."""
        if not self.enabled:
            log.info("telegram not configured — polling disabled")
            return

        def _loop() -> None:
            offset = None
            while not self._stop.is_set():
                try:
                    params = {"timeout": 20}
                    if offset is not None:
                        params["offset"] = offset
                    r = requests.get(f"{self.base}/getUpdates", params=params, timeout=30)
                    for upd in r.json().get("result", []):
                        offset = upd["update_id"] + 1
                        msg = upd.get("message") or {}
                        text = (msg.get("text") or "").strip()
                        if not text.startswith("/"):
                            continue
                        cmd = text.split()[0].lstrip("/").split("@")[0].lower()
                        h = handlers.get(cmd)
                        if h:
                            try:
                                resp = h()
                                if resp:
                                    self.send(resp)
                            except Exception as e:  # noqa: BLE001
                                log.error("command /%s failed: %s", cmd, e)
                        else:
                            self.send("Comandos: " + " ".join(
                                "/" + c for c in sorted(handlers)))
                except requests.RequestException:
                    self._stop.wait(3)
                except Exception as e:  # noqa: BLE001
                    log.error("tg poll: %s", e)
                    self._stop.wait(3)

        threading.Thread(target=_loop, daemon=True, name="tg-poll").start()

    def stop(self) -> None:
        self._stop.set()


HOT_MSG = "Sequência anormal detectada — estatística de curto prazo fica ainda menos confiável. Pausa recomendada."

notifier = TelegramNotifier()
