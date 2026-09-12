# Football Card Blitz — validação de ENTRADAS REAIS (2/2)
from __future__ import annotations
import json
import time
import hashlib
from pathlib import Path

CONFIRM_WINDOW_S = 8          # confirmação dupla dentro da janela
DEDUP_TTL_S = 120             # ignora outcome duplicado recente
STATE_FILE = Path(__file__).resolve().parent / "data" / "entry_state.json"
SEEN: dict[str, float] = {}   # raw_hash -> ts (memória)
PENDING: dict[str, dict] = {}  # round_id -> {outcome, ts}


def _load_seen():
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_seen(data: dict):
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(data)[-5000:], encoding="utf-8")
    except OSError:
        pass


def fingerprint(raw: str, parser_version: str) -> str:
    return hashlib.sha256(f"{parser_version}|{raw}".encode()).hexdigest()[:16]


def dedup_check(raw: str, parser_version: str, now: float | None = None) -> bool:
    """True = duplicado (rejeitar). False = novo (aceitar)."""
    now = now if now is not None else time.time()
    fp = fingerprint(raw, parser_version)
    ts = SEEN.get(fp, 0)
    if now - ts < DEDUP_TTL_S:
        return True
    SEEN[fp] = now
    for k in [k for k, v in SEEN.items() if now - v > DEDUP_TTL_S]:
        del SEEN[k]
    return False


def confirm_two_step(round_id: str | None, outcome: str,
                     now: float | None = None) -> dict:
    """Exige 2 leituras iguais do mesmo round antes de liquidar.
    Sem round_id: aprova direto (compat), mas marca unconfirmed=True."""
    now = now if now is not None else time.time()
    if not round_id:
        return {"confirmed": True, "unconfirmed": True}
    prev = PENDING.get(round_id)
    if prev and prev["outcome"] == outcome and now - prev["ts"] <= CONFIRM_WINDOW_S:
        del PENDING[round_id]
        return {"confirmed": True, "unconfirmed": False}
    PENDING[round_id] = {"outcome": outcome, "ts": now}
    for k in [k for k, v in PENDING.items() if now - v["ts"] > CONFIRM_WINDOW_S]:
        del PENDING[k]
    return {"confirmed": False, "unconfirmed": False, "waiting": True}
