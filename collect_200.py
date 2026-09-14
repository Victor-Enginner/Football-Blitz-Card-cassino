"""Collector: 200 giros reais Football Blitz (somente leitura).
Uso:
  python collect_200.py --target 200
Monitora o ledger via /api/events, conta apenas data_origin=authorized_readonly
da sessão de coleta, exibe progresso e roda validação chi-square ao final.
Não injeta dados, não aposta. PAPER.
"""
from __future__ import annotations

import argparse
import csv
import sys
import time
import urllib.request
import json
from pathlib import Path

BASE = "http://127.0.0.1:8766"


def api(path: str, method: str = "GET", body: dict | None = None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=200)
    ap.add_argument("--poll", type=float, default=1.0)
    ap.add_argument("--timeout-min", type=float, default=180.0)
    ap.add_argument("--max-retries", type=int, default=5)
    args = ap.parse_args()

    st = api("/api/state")
    session = (st.get("session") or {}).get("session_id")
    if not session:
        print("Sem sessão ativa. Inicie no dashboard (INICIAR) e rode de novo.")
        return 2
    print(f"Sessão de coleta: {session[:12]}…  alvo={args.target} giros authorized_readonly")
    print("No console da aba do jogo: fbObserverCreate({server:'ws://localhost:8766/ws', token:'<OBSERVER_TOKEN>'})")

    seen: set[str] = set()
    rows: list[dict] = []
    t0 = time.time()
    retries = 0
    backoff = 1.0
    while len(rows) < args.target:
        if (time.time() - t0) / 60 > args.timeout_min:
            print(f"Timeout: {len(rows)}/{args.target} coletados.")
            break
        try:
            evs = api("/api/events?n=500")["events"]
            retries = 0
            backoff = 1.0
        except Exception as e:
            retries += 1
            if retries > args.max_retries:
                print(f"API erro persistente após {retries} tentativas: {e}")
                break
            wait = min(backoff * (1.5 ** (retries - 1)), 15.0)
            print(f"API erro: {e}; retry {retries}/{args.max_retries} em {wait:.1f}s")
            time.sleep(wait)
            continue
        for e in evs:
            eid = e.get("event_id")
            if eid in seen:
                continue
            seen.add(eid)
            if (e.get("data_origin") == "authorized_readonly"
                    and e.get("session_id") == session
                    and len(rows) < args.target):
                rows.append(e)
        print(f"\rColetados: {len(rows)}/{args.target}", end="", flush=True)
        if len(rows) >= args.target:
            break
        time.sleep(args.poll)
    print()

    out = Path(__file__).parent / "data" / f"collect_{session[:8]}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["event_id", "observed_at", "outcome",
                                          "data_origin", "round_id"])
        w.writeheader()
        for e in rows:
            w.writerow({k: e.get(k, "") for k in
                        ["event_id", "observed_at", "outcome", "data_origin", "round_id"]})
    print(f"CSV: {out} ({len(rows)} linhas)")

    # validação imediata
    sys.path.insert(0, str(Path(__file__).parent))
    from risk import summarize_session
    outcomes = [e["outcome"] for e in rows]
    s = summarize_session(outcomes, [])
    print(f"n={s['n']} freq={s['freq']} entropia={s['entropy_bits']}bits")
    print(f"uniformidade: {s['uniformity']}")
    print(f"streaks: {s['streaks']}")
    if s["n"] < 60:
        print("Sem vantagem estatística confiável (amostra pequena).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
