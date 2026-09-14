# Football Card Blitz — validação de ENTRADAS REAIS (1/2)
OUTCOMES = ("home", "away", "draw")
CARD_VALUES = {"A": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7,
               "8": 8, "9": 9, "10": 10, "J": 11, "Q": 12, "K": 13}


def validate_outcome(outcome) -> str:
    """Normaliza e valida outcome real. Levanta ValueError se inválido."""
    if not isinstance(outcome, str):
        raise ValueError(f"outcome deve ser str, veio {type(outcome).__name__}")
    o = outcome.strip().lower()
    aliases = {"empate": "draw", "casa": "home", "fora": "away",
               "mandante": "home", "visitante": "away",
               "h": "home", "a": "away", "d": "draw",
               "home win": "home", "away win": "away"}
    o = aliases.get(o, o)
    if o not in OUTCOMES:
        raise ValueError(f"outcome inválido: {outcome!r} (use home/away/draw)")
    return o


def validate_cards(home_card, away_card) -> str:
    """Valida cartas Home/Away e DERIVA o outcome. Prova contra erro de leitura."""
    h = str(home_card).strip().upper()
    a = str(away_card).strip().upper()
    if h not in CARD_VALUES:
        raise ValueError(f"carta home inválida: {home_card!r}")
    if a not in CARD_VALUES:
        raise ValueError(f"carta away inválida: {away_card!r}")
    hv, av = CARD_VALUES[h], CARD_VALUES[a]
    if hv > av:
        return "home"
    if av > hv:
        return "away"
    return "draw"


def validate_bet_entry(bet_type, stake, balance, policy_allowed: bool,
                       reasons=None, max_stake: float = 100.0) -> dict:
    """Portão único de entrada real. Retorna {ok, reasons}."""
    reasons = list(reasons or [])
    if bet_type not in ("home", "away", "draw", "spread_h", "spread_a"):
        reasons.append(f"bet_type inválido: {bet_type!r}")
    try:
        stake = float(stake)
    except (TypeError, ValueError):
        return {"ok": False, "reasons": reasons + ["stake não-numérico"]}
    if stake <= 0:
        reasons.append("stake deve ser > 0")
    if stake > max_stake:
        reasons.append(f"stake {stake} acima do teto {max_stake}")
    if stake > balance:
        reasons.append(f"stake R$ {stake:.2f} > banca R$ {balance:.2f}")
    if not policy_allowed:
        reasons.append("policy bloqueou (stop/cooldown/kill-switch)")
    return {"ok": not reasons, "reasons": reasons, "stake": stake}
