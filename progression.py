"""Progression ladder — PAPER only, educational.

Exact ladder from operations: 0.50 → 1 → 2 → 4 → 6 → 12 (6 levels).
NOTE: 4 → 6 is NOT a pure double (ops choice, softer than 8).
Loss advances one level; win/push resets to start; after the last
level a loss resets + flags cooldown. Never executes anything.
"""
from __future__ import annotations

LADDER = [0.50, 1.0, 2.0, 4.0, 6.0, 12.0]
MAX_LEVEL = len(LADDER) - 1  # 5


def level_from_statuses(statuses_newest_first: list[str]) -> dict:
    """Derive ladder level from consecutive settled paper results.

    statuses: 'won' | 'lost' | 'push' (or 'open' = ignored/skipped).
    Returns {level, stake, next_stake, exhausted}.
    """
    consec = 0
    for s in statuses_newest_first:
        if s == "lost":
            consec += 1
        elif s in ("won", "push"):
            break
        # 'open' ignored
    if consec > MAX_LEVEL:
        return {"level": 0, "stake": LADDER[0], "next_stake": LADDER[1],
                "exhausted": True, "consec_losses": consec,
                "note": "escada esgotada: volta ao início + pausa"}
    lvl = min(consec, MAX_LEVEL)
    return {"level": lvl, "stake": LADDER[lvl],
            "next_stake": LADDER[min(lvl + 1, MAX_LEVEL)],
            "exhausted": False, "consec_losses": consec,
            "exposure_so_far": round(sum(LADDER[:lvl]), 2)}


def total_exposure() -> float:
    return round(sum(LADDER), 2)  # 25.50 worst case full ladder
