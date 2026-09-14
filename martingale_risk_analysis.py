"""martingale_risk_analysis — EDUCATIONAL ONLY. Simulation of ruin, never execution.

Demonstrates (Martingale critique):
- stake after each loss, cumulative exposure, failure by bankroll,
  failure by table limit, loss-sequence probability, drawdown,
  ruin risk, flat-stake comparison.
NO real-bet function. NOT linked to browser/Telegram/finance.
"""
from __future__ import annotations

import random

from risk import prob_k_losses_in_n, max_drawdown, ruin_probability


def cycle_plan(base: float = 2.50, levels: int = 3, mult: float = 2.0) -> dict:
    stakes, cum, cum_loss = [], 0.0, 0.0
    for i in range(levels + 1):
        s = round(base * (mult ** i), 2)
        stakes.append(s)
        cum += s
    # cumulative loss if all lose
    cum_loss = round(sum(stakes), 2)
    wins_to_recover = cum_loss / base if base else 0
    return {"stakes": stakes, "total_exposure": cum_loss,
            "wins_to_recover_at_base": round(wins_to_recover, 1),
            "note": "4 erros seguidos = -R$37.50 com base 2.50; exige 15 vitórias líquidas"}


def simulate(base: float = 2.50, levels: int = 3, bankroll: float = 200.0,
             p_win: float = 0.4865, rounds: int = 200, seed: int = 7,
             table_limit: float = 100.0) -> dict:
    """Flat vs martingale over `rounds` simulated even-money rounds (PAPER math)."""
    rng = random.Random(seed)
    for label, use_mg in (("flat", False), ("martingale", True)):
        bal, lvl, peak_dd, dd = bankroll, 0, 0.0, 0.0
        peak = bankroll
        max_stake, ruined = 0.0, False
        for _ in range(rounds):
            stake = base * (2 ** lvl) if use_mg else base
            if stake > table_limit:
                ruined = True
                break
            if stake > bal:
                ruined = True
                break
            max_stake = max(max_stake, stake)
            win = rng.random() < p_win
            bal += stake if win else -stake
            peak = max(peak, bal)
            dd = max(dd, peak - bal)
            if win:
                lvl = 0
            else:
                lvl = min(lvl + 1, levels) if use_mg else 0
                if use_mg and lvl >= levels:
                    # next loss would exceed plan -> stop cycle (circuit breaker demo)
                    pass
            if bal <= 0:
                ruined = True
                break
        if label == "flat":
            flat = {"final": round(bal, 2), "ruined": ruined,
                    "max_stake": round(max_stake, 2), "max_dd": round(dd, 2)}
        else:
            mg = {"final": round(bal, 2), "ruined": ruined,
                  "max_stake": round(max_stake, 2), "max_dd": round(dd, 2)}
    p4 = prob_k_losses_in_n(1 - p_win, rounds, levels + 1)
    return {"flat": flat, "martingale": mg,
            "p_4loss_in_200": round(p4, 4),
            "ruin": ruin_probability(bankroll / base, p_win),
            "verdict": "Martingale não altera EV; aumenta exposição e risco de ruína"}
