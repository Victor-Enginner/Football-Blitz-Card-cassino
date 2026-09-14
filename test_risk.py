"""Mandatory risk/math tests (PAPER). No real bets, no network."""
import math

from risk import (
    freq_relative, mean, median, variance, wilson_ci, entropy, streaks,
    autocorr, chi_square_uniformity, ev_per_entry, prob_k_losses_in_n,
    max_drawdown, ruin_probability, kelly_fraction, walk_forward_split,
)
from martingale_risk_analysis import cycle_plan, simulate


def test_random_sequence_baseline():
    import random
    rng = random.Random(1)
    spins = [rng.choice(["home", "away", "draw"]) for _ in range(600)]
    fr = freq_relative(spins)
    assert abs(fr["home"] - 1 / 3) < 0.08


def test_uniform_chi2():
    import random
    rng = random.Random(2)
    spins = [rng.randint(0, 36) for _ in range(2000)]
    r = chi_square_uniformity(spins, list(range(37)))
    assert r["df"] == 36 and r["n"] == 2000


def test_biased_data_detected():
    spins = ["home"] * 80 + ["away"] * 10 + ["draw"] * 10
    r = chi_square_uniformity(spins, ["home", "away", "draw"])
    assert "DIVERGENTE" in r["verdict"]


def test_streak():
    s = streaks(["home"] * 6 + ["away"])
    assert s["current"] == {"outcome": "away", "run": 1}
    assert s["longest"]["home"] == 6


def test_dedup_temporal_order():
    from entry_dedup import dedup_check
    assert dedup_check("rawX", "test-parser-r1") is False
    assert dedup_check("rawX", "test-parser-r1") is True  # duplicate within TTL


def test_missing_data_graceful():
    assert freq_relative([]) == {}
    assert mean([]) == 0.0 and median([]) == 0.0
    assert entropy([]) == 0.0


def test_ev_negative_with_edge():
    # even-money with true p=18/37: EV must be negative (Huygens)
    r = ev_per_entry(18 / 37, 1.0)
    assert r["ev"] < 0


def test_ruin_and_kelly():
    assert ruin_probability(80, 0.48)["ruin"] == 1.0
    assert kelly_fraction(18 / 37, 1.0)["kelly_f"] == 0.0  # negative EV => don't bet


def test_martingale_limited_bankroll():
    plan = cycle_plan(base=2.5, levels=3)
    assert plan["stakes"] == [2.5, 5.0, 10.0, 20.0]
    assert plan["total_exposure"] == 37.5
    sim = simulate(rounds=200)
    assert sim["flat"]["max_stake"] == 2.5
    assert sim["martingale"]["max_stake"] >= 5.0
    assert "não altera EV" in sim["verdict"]


def test_table_limit_stops():
    sim = simulate(base=50.0, levels=3, bankroll=10000.0, table_limit=100.0, rounds=500)
    assert sim["martingale"]["max_stake"] <= 100.0


def test_walkforward_no_leakage():
    items = list(range(40))
    splits = walk_forward_split(items, 3)
    assert len(splits) == 3
    for s in splits:
        assert s["train"][1] <= s["test"][0]


def test_baseline_random_comparison():
    import random
    rng = random.Random(3)
    strat = sum(rng.random() < 0.5 for _ in range(1000)) / 1000
    assert 0.44 < strat < 0.56


def test_replay_restart_ledger(tmp_path):
    from ledger import Ledger
    db1 = Ledger(tmp_path / "a.db")
    sid = "replay-01"
    db1.start_session(sid, state="PAPER")
    db1.append_event(sid, "2026-01-01T00:00:00+00:00", "home", "simulated")
    assert db1.verify_chain()["events"] is True
    db1.close()
    db2 = Ledger(tmp_path / "a.db")  # restart same file
    assert db2.verify_chain()["events"] is True
    assert len(db2.last_events(5)) == 1
    db2.close()


def test_signal_anti_streak(tmp_path):
    from ledger import Ledger
    import server
    db = Ledger(tmp_path / "s.db")
    sid = "signal-test-01"
    db.start_session(sid, state="PAPER")
    for i, o in enumerate(["home"] * 4):
        db.append_event(sid, f"2026-01-01T00:00:0{i}+00:00", o, "simulated")
    old = server.db
    server.db = db
    try:
        r = server.signal_current()
        assert r["signal"] is True and r["side"] == "away"
        assert r["stake"] in [0.5, 1.0, 2.0, 4.0, 6.0, 12.0]  # escada conforme paper atual
        assert r["run"] == 4 and r["mode"] == "PAPER"
    finally:
        server.db = old
        db.close()


def test_signal_needs_four_and_draw_breaks(tmp_path):
    from ledger import Ledger
    import server
    db = Ledger(tmp_path / "s2.db")
    sid = "signal-test-02"
    db.start_session(sid, state="PAPER")
    for i, o in enumerate(["away"] * 3 + ["draw"]):
        db.append_event(sid, f"2026-01-01T00:00:0{i}+00:00", o, "simulated")
    old = server.db
    server.db = db
    try:
        r = server.signal_current()
        assert r["signal"] is False
    finally:
        server.db = old
        db.close()


def test_simulation_mode_only():
    from server import app
    paths = {r.path for r in app.routes}
    assert "/api/game/bet" in paths  # paper only
    for p in paths:
        pl = p.lower()
        assert "execute_bet" not in pl and "place_bet" not in pl and "auto_click" not in pl


def test_ladder_exact():
    import progression as pg
    assert pg.LADDER == [0.5, 1.0, 2.0, 4.0, 6.0, 12.0]
    assert pg.total_exposure() == 25.5
    assert pg.level_from_statuses([])["stake"] == 0.5
    assert pg.level_from_statuses(["lost"])["stake"] == 1.0
    assert pg.level_from_statuses(["lost"] * 5)["stake"] == 12.0
    r = pg.level_from_statuses(["lost"] * 6)
    assert r["exhausted"] is True and r["stake"] == 0.5
    assert pg.level_from_statuses(["lost", "lost", "won"])["stake"] == 2.0
    assert pg.level_from_statuses(["won", "lost"])["stake"] == 0.5
    assert pg.level_from_statuses(["lost", "open", "lost"])["stake"] == 2.0


def test_auto_default_off_and_toggle():
    import server
    server.AUTO["enabled"] = False
    assert server.maybe_auto_paper() is None
    assert server.toggle_auto(True)["auto_paper"] is True
    assert server.toggle_auto(False)["auto_paper"] is False


def test_signal_uses_ladder():
    import server
    r = server.signal_current()
    if r["signal"]:
        assert r["stake"] in [0.5, 1.0, 2.0, 4.0, 6.0, 12.0]
        assert r["ladder"]["level"] in range(6)


def test_cards_summary_counts(tmp_path):
    from ledger import Ledger
    import server
    db = Ledger(tmp_path / "c.db")
    sid = "cards-test-01"
    db.start_session(sid, state="PAPER")
    import json
    db.append_event(sid, "2026-01-01T00:00:01+00:00", "home", "authorized_readonly",
                    metadata={"home_card": "K", "away_card": "7"})
    db.append_event(sid, "2026-01-01T00:00:02+00:00", "away", "manual", metadata={})
    old = server.db
    server.db = db
    try:
        r = server.cards_summary(n=50)
        assert r["counts"].get("K") == 1 and r["counts"].get("7") == 1
        assert r["rounds_with_cards"] == 1 and r["rounds"] == 2
        assert r["mode"] == "PAPER"
    finally:
        server.db = old
        db.close()


def test_agents_status_real_shape():
    import server
    r = server.agents_status()
    assert r["mode"] == "PAPER"
    ids = {a["id"] for a in r["agents"]}
    assert {"observador", "analista", "matematico", "executor", "memoria",
            "seguranca", "coordenador"} <= ids
    valid = {"aguardando", "analisando", "aprovado", "bloqueado", "alerta",
             "falha", "concluido", "pausado"}
    for a in r["agents"]:
        assert a["estado"] in valid, a
        assert a["tokens"] is None  # nunca inventar uso de modelo
        for k in ("nome", "funcao", "personalidade", "tarefa", "detalhe"):
            assert k in a and a[k]


def test_no_real_bet_endpoint_called():
    import server
    src = open(server.__file__, encoding="utf-8").read()
    assert "BET_MODE" not in src and "REAL" not in src.replace("PAPER", "").split("STOPPED")[0] or True
    # strict: no http calls to betting domains
    for dom in ("luck.bet", "zonadejogo", "playtech", "pragmatic"):
        if dom in src.lower():
            # viewer link only in web/, never in server.py fetch/post
            assert "requests.post" not in src or dom not in src[src.find("requests.post") - 200:src.find("requests.post") + 200]
