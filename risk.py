"""Risk engine — PAPER only. Educational risk math, no execution.

Implements: frequencies, mean/median/variance/std, Wilson CI,
entropy, streaks, autocorrelation (lag-1..5), chi-square uniformity,
EV per entry, drawdown, ruin probability (closed-form gambler),
loss-streak probability, max exposure, Kelly (study only),
baseline comparison, walk-forward split helper.

Never places bets. Never enables REAL. All stakes are simulated.
"""
from __future__ import annotations

import math
from collections import Counter
from typing import Any


def freq_absolute(items: list) -> dict:
    return dict(Counter(items))


def freq_relative(items: list) -> dict:
    n = len(items)
    if not n:
        return {}
    c = Counter(items)
    return {k: v / n for k, v in c.items()}


def mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def median(xs: list[float]) -> float:
    if not xs:
        return 0.0
    s = sorted(xs)
    n = len(s)
    m = n // 2
    return float(s[m]) if n % 2 else (s[m - 1] + s[m]) / 2


def variance(xs: list[float]) -> float:
    if len(xs) < 2:
        return 0.0
    m = mean(xs)
    return sum((x - m) ** 2 for x in xs) / (len(xs) - 1)


def stdev(xs: list[float]) -> float:
    return math.sqrt(variance(xs))


def wilson_ci(wins: int, n: int, z: float = 1.96) -> dict:
    """Wilson score interval for a proportion. Bernoulli/Fisher-Neyman-Pearson."""
    if n <= 0:
        return {"low": 0.0, "high": 1.0, "n": 0}
    p = wins / n
    den = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return {"low": max(0.0, (c - m) / den), "high": min(1.0, (c + m) / den), "n": n}


def entropy(probs: list[float]) -> float:
    """Shannon entropy in bits. Measures predictability."""
    h = 0.0
    for p in probs:
        if p > 0:
            h -= p * math.log2(p)
    return h


def streaks(outcomes: list[str]) -> dict:
    """Current run + longest run per outcome. De Moivre sequence risk."""
    if not outcomes:
        return {"current": None, "longest": {}}
    cur_out, cur_run = outcomes[-1], 1
    for o in reversed(outcomes[:-1]):
        if o == cur_out:
            cur_run += 1
        else:
            break
    longest: dict[str, int] = {}
    run_out, run_n = outcomes[0], 1
    for o in outcomes[1:]:
        if o == run_out:
            run_n += 1
        else:
            longest[run_out] = max(longest.get(run_out, 0), run_n)
            run_out, run_n = o, 1
    longest[run_out] = max(longest.get(run_out, 0), run_n)
    return {"current": {"outcome": cur_out, "run": cur_run}, "longest": longest}


def autocorr(xs: list[float], max_lag: int = 5) -> dict[int, float]:
    """Lag-k autocorrelation. Markov dependence test (approx)."""
    n = len(xs)
    if n < 3:
        return {}
    m = mean(xs)
    den = sum((x - m) ** 2 for x in xs)
    out: dict[int, float] = {}
    for k in range(1, min(max_lag, n - 1) + 1):
        num = sum((xs[i] - m) * (xs[i + k] - m) for i in range(n - k))
        out[k] = num / den if den else 0.0
    return out


def chi_square_uniformity(items: list, categories: list) -> dict:
    """Kolmogorov-style consistency: chi-square vs uniform. Small-sample guarded (Chebyshev)."""
    n = len(items)
    k = len(categories)
    if n == 0 or k == 0:
        return {"chi2": 0.0, "df": 0, "n": 0, "verdict": "SEM AMOSTRA"}
    c = Counter(items)
    exp = n / k
    chi2 = sum((c.get(cat, 0) - exp) ** 2 / exp for cat in categories)
    # critical value approx for df=k-1 at 5% (only exact for small df; else warn)
    verdict = "CONSISTENTE" if chi2 < (k - 1) * 2 else "DIVERGENTE (investigar, pode ser ruído)"
    if n < 5 * k:
        verdict += " — AMOSTRA PEQUENA (Chebyshev: não concluir)"
    return {"chi2": round(chi2, 2), "df": k - 1, "n": n, "verdict": verdict}


def ev_per_entry(p_win: float, payout_net: float, p_push: float = 0.0,
                 push_return: float = 0.0, stake: float = 1.0) -> dict:
    """Huygens expectation. EV = sum(p*retorno). House edge explicit."""
    p_loss = max(0.0, 1 - p_win - p_push)
    ev = p_win * payout_net * stake + p_push * push_return * stake - p_loss * stake
    return {"ev": round(ev, 4), "p_win": p_win, "p_push": p_push,
            "p_loss": round(p_loss, 4), "stake": stake}


def prob_k_losses_in_n(p_loss: float, n: int, k: int) -> float:
    """P(at least one run of k consecutive losses in n). De Moivre sequence risk."""
    if k <= 0:
        return 1.0
    if n < k or p_loss <= 0:
        return 0.0 if n < k else (0.0 if p_loss == 0 else None) or 0.0
    p_win = 1 - p_loss
    # recursion: q[i] = P(no k-run in first i)
    q = [1.0] * (n + 1)
    for i in range(1, n + 1):
        if i < k:
            q[i] = 1.0
        elif i == k:
            q[i] = 1 - p_loss ** k
        else:
            q[i] = q[i - 1] - p_win * (p_loss ** k) * (q[i - k - 1] if i - k - 1 >= 0 else 1.0)
    return max(0.0, min(1.0, 1 - q[n]))


def max_drawdown(pnls: list[float]) -> dict:
    peak, maxdd, cur = 0.0, 0.0, 0.0
    eq = 0.0
    for p in pnls:
        eq += p
        peak = max(peak, eq)
        maxdd = max(maxdd, peak - eq)
    return {"max_drawdown": round(maxdd, 2), "final": round(eq, 2)}


def ruin_probability(bankroll_units: float, p_win: float, payout_net: float = 1.0) -> dict:
    """Gambler's ruin (Bernoulli/Laplace). p = P(win), q = P(loss+push-as-loss approx)."""
    q = 1 - p_win
    if p_win <= 0.5:
        return {"ruin": 1.0, "note": "EV<=0: ruína certa no horizonte infinito (preservar capital)"}
    r = q / p_win
    # with even-money approximation
    try:
        ruin = (r ** bankroll_units - 1) / (r ** (bankroll_units * 10) - 1)
    except OverflowError:
        ruin = 1.0
    return {"ruin": round(min(1.0, max(0.0, ruin)), 4),
            "note": "aproximação even-money; com edge da casa, ruína → 1"}


def kelly_fraction(p_win: float, payout_net: float) -> dict:
    """Kelly study ONLY. Never turns negative EV positive."""
    b = payout_net
    q = 1 - p_win
    f = (b * p_win - q) / b if b else 0.0
    return {"kelly_f": round(max(0.0, f), 4),
            "note": "Kelly dimensiona, não cria vantagem. EV negativo => f=0 (não apostar)"}


def walk_forward_split(items: list, n_splits: int = 3) -> list[dict]:
    """Train/val/test temporal splits without leakage."""
    n = len(items)
    if n < 10:
        return []
    fold = n // (n_splits + 1)
    out = []
    for i in range(n_splits):
        a, b, c = i * fold, (i + 1) * fold, (i + 2) * fold
        out.append({"train": [a, b], "test": [b, min(c, n)]})
    return out


def summarize_session(outcomes: list[str], pnls: list[float],
                      categories: tuple = ("home", "away", "draw")) -> dict[str, Any]:
    fr = freq_relative(outcomes)
    nums = [1 if p > 0 else (-1 if p < 0 else 0) for p in pnls]
    return {
        "n": len(outcomes),
        "freq": {k: round(v, 4) for k, v in fr.items()},
        "entropy_bits": round(entropy(list(fr.values())), 3),
        "streaks": streaks(outcomes),
        "uniformity": chi_square_uniformity(outcomes, list(categories)),
        "drawdown": max_drawdown(pnls),
        "pnl_mean": round(mean(pnls), 4),
        "pnl_std": round(stdev(pnls), 4),
        "pnl_median": round(median(pnls), 4),
        "autocorr": {str(k): round(v, 3) for k, v in autocorr(
            [hash(o) % 97 / 97.0 for o in outcomes]).items()},
    }
