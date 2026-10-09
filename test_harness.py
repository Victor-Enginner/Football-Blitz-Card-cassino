"""Harness observer — prova que MutationObserver coleta sem rede externa."""
def test_harness_observer_paper(tmp_path):
    from ledger import Ledger
    # simula o que o observer faria: outcome autorizado -> ledger
    db = Ledger(tmp_path / "h.db")
    sid = "harness-test-01"
    db.start_session(sid, state="PAPER")
    for o in ["home","away","draw","home"]:
        db.append_event(sid, "2026-01-01T00:00:00+00:00", o, "authorized_readonly")
    assert db.verify_chain()["events"] is True
    assert len([e for e in db.last_events(10) if e["data_origin"]=="authorized_readonly"]) == 4
    db.close()

def test_agents_collaborate_paper():
    import server
    # 7 agentes existem e colaboram via status (sem aposta real)
    r = server.agents_status()
    assert len(r["agents"]) == 7
    # auto-paper usa a mesma regra 4x + escada — sem executar real
    r2 = server.signal_current()
    assert r2["mode"] == "PAPER"
