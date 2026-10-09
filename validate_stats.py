"""Validacao estatistica T9-T12 — SOMENTE dados reais (authorized_readonly).

T9  chi-square de uniformidade home/away/draw + p-valor (df=2: p=exp(-x/2)).
T10 hit-rate da regra anti-4x em PAPER vs baseline aleatório (Monte Carlo,
    mesma série embaralhada, seed fixa) — sem aposta, só acerto de lado.
T11 walk-forward: primeira metade -> segunda metade.
T12 veredito binário: "vantagem confiável" OU "sem evidência".

Uso: python validate_stats.py [--min-n 200]
Só stdlib. Nunca simula resultado: lê o ledger real.
"""
from __future__ import annotations

import argparse
import math
import random
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ledger import Ledger
from config import BASE_DIR, DATA_DIR

RUN = 4  # mesma regra do servidor: 4x dispara anti-streak


def real_outcomes(db: Ledger, limit: int = 10000) -> list[str]:
    evs = db.last_events(limit)
    return [e["outcome"] for e in evs
            if e.get("data_origin") == "authorized_readonly"
            and e.get("outcome") in ("home", "away", "draw")]


def chi_square_uniform(counts: Counter) -> tuple[float, float]:
    cats = ["home", "away", "draw"]
    n = sum(counts.get(c, 0) for c in cats)
    if n == 0:
        return 0.0, 1.0
    exp = n / 3.0
    x2 = sum((counts.get(c, 0) - exp) ** 2 / exp for c in cats)
    p = math.exp(-x2 / 2.0)  # df = 3-1 = 2
    return x2, p


def anti4_hits(outcomes: list[str]) -> tuple[int, int, int]:
    """(sinais, acertos, pushes): 4x frescas de X -> aposta o oposto na rodada i+4.

    Sem lookahead: o gatilho usa só outcomes[i..i+3]; a rodada apostada (i+4)
    está sempre no futuro do gatilho. Draw na rodada apostada = push (fora
    do hit-rate). Fresca = outcomes[i-1] != X (sem duplicata por streak).
    """
    signals = hits = pushes = 0
    n = len(outcomes)
    for i in range(n - 4):
        x = outcomes[i]
        if x == "draw":
            continue
        if any(o != x for o in outcomes[i:i + 4]):
            continue
        if i > 0 and outcomes[i - 1] == x:
            continue  # continuação, não streak fresca
        nxt = outcomes[i + 4]
        if nxt == "draw":
            pushes += 1
            continue
        signals += 1
        if nxt != x:
            hits += 1
    return signals, hits, pushes


def baseline(outcomes: list[str], trials: int = 2000, seed: int = 42) -> tuple[float, float]:
    """Mesma regra sobre a série embaralhada: média e desvio do hit-rate."""
    rng = random.Random(seed)
    rates = []
    for _ in range(trials):
        s = outcomes[:]
        rng.shuffle(s)
        sg, ht, _ = anti4_hits(s)
        rates.append(ht / sg if sg else 0.0)
    mean = sum(rates) / len(rates)
    var = sum((r - mean) ** 2 for r in rates) / len(rates)
    return mean, math.sqrt(var)


def main() -> int:
    ap = argparse.ArgumentParser(description="T9-T12 sobre dados reais")
    ap.add_argument("--min-n", type=int, default=200)
    args = ap.parse_args()

    db = Ledger(DATA_DIR / "command_center.db")
    try:
        outs = real_outcomes(db)
    finally:
        db.close()
    n = len(outs)
    print(f"amostra real: n={n} (mínimo sugerido {args.min_n})")
    if n < 20:
        print("VEREDITO: sem evidência (amostra insuficiente — capture mais rodadas reais)")
        return 2

    counts = Counter(outs)
    x2, p = chi_square_uniform(counts)
    print(f"T9 chi-square: home={counts['home']} away={counts['away']} draw={counts['draw']} "
          f"x2={x2:.3f} p={p:.4f} "
          f"({'REJEITA uniformidade' if p < 0.05 else 'não rejeita uniformidade'})")

    sg, ht, pushes = anti4_hits(outs)
    rate = ht / sg if sg else 0.0
    mean, sd = baseline(outs)
    z = (rate - mean) / sd if sd > 0 else 0.0
    print(f"T10 anti-4x: sinais={sg} acertos={ht} pushes={pushes} hit-rate={rate:.3f} | "
          f"baseline={mean:.3f}±{sd:.3f} z={z:.2f}")

    half = n // 2
    sg1, ht1, _ = anti4_hits(outs[:half])
    sg2, ht2, _ = anti4_hits(outs[half:])
    r1 = ht1 / sg1 if sg1 else 0.0
    r2 = ht2 / sg2 if sg2 else 0.0
    print(f"T11 walk-forward: treino[0:{half}] sinais={sg1} hit={r1:.3f} | "
          f"teste[{half}:{n}] sinais={sg2} hit={r2:.3f}")

    # T12: vantagem confiável exige hit-rate > baseline + 2sd E replicado no walk-forward
    edge = (sg >= 5 and z > 2.0 and sg2 >= 3 and r2 > mean)
    print("T12 VEREDITO:", "vantagem confiável" if edge else "sem evidência")
    if n < args.min_n:
        print(f"NOTA: n={n} < {args.min_n} — veredito parcial; complete a amostra real.")
    return 0 if edge else 1


if __name__ == "__main__":
    raise SystemExit(main())
