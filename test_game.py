"""Game engine tests — payouts, bankroll, settlement, guardrails."""
from __future__ import annotations

import pytest

from game import GameEngine, PAYOUTS


@pytest.fixture()
def engine(tmp_path):
    return GameEngine(tmp_path / "bets.db", bankroll_start=100.0)


def test_open_bet_debits_bankroll(engine):
    engine.open_bet("s-12345678", "home", 10.0)
    assert engine.balance() == 90.0


def test_stake_above_bankroll_rejected(engine):
    with pytest.raises(ValueError, match="bankroll"):
        engine.open_bet("s-12345678", "home", 150.0)


def test_invalid_bet_type_rejected(engine):
    with pytest.raises(ValueError):
        engine.open_bet("s-12345678", "lucky7", 5.0)


def test_home_wins_full(engine):
    engine.open_bet("s-12345678", "home", 10.0)
    engine.settle("home")
    assert engine.balance() == 110.0  # 100 - 10 + 20 (stake + 1:1)


def test_home_draw_push_half(engine):
    engine.open_bet("s-12345678", "home", 10.0)
    engine.settle("draw")
    assert engine.balance() == 95.0  # half returned (10-10+5)


def test_draw_wins_11_to_1(engine):
    engine.open_bet("s-12345678", "draw", 2.0)
    engine.settle("draw")
    assert engine.balance() == 122.0  # 100 - 2 + 24


def test_away_home_lost(engine):
    engine.open_bet("s-12345678", "away", 10.0)
    engine.settle("home")
    assert engine.balance() == 90.0


def test_multiple_open_bets_settle_together(engine):
    engine.open_bet("s-12345678", "home", 10.0)
    engine.open_bet("s-12345678", "draw", 2.0)
    assert engine.balance() == 88.0
    settled = engine.settle("draw")
    assert len(settled) == 2
    # home push_half: +5 ; draw win: +24 → 88 + 5 + 24 = 117
    assert engine.balance() == 117.0


def test_settle_ignores_unknown_outcome(engine):
    engine.open_bet("s-12345678", "home", 10.0)
    assert engine.settle("banana") == []
    assert len(engine.open_bets()) == 1


def test_stats_shape(engine):
    engine.open_bet("s-12345678", "home", 10.0)
    engine.settle("home")
    s = engine.stats()
    assert s["total"] == 1 and s["wins"] == 1
    assert s["pnl_total"] == 10.0
    assert s["bankroll"] == 110.0


def test_spread_settles_1_to_1_base(engine):
    engine.open_bet("s-12345678", "spread_h", 10.0)
    engine.settle("home")
    assert engine.balance() == 110.0
    engine.open_bet("s-12345678", "spread_h", 10.0)
    engine.settle("away")
    assert engine.balance() == 100.0


def test_payouts_table_matches_spec():
    """RTP-validated payouts from PLANO_FOOTBALL_BLITZ.md."""
    assert PAYOUTS["home"]["mult"] == 1.0 and PAYOUTS["home"]["draw"] == "push_half"
    assert PAYOUTS["away"]["mult"] == 1.0 and PAYOUTS["away"]["draw"] == "push_half"
    assert PAYOUTS["draw"]["mult"] == 11.0
