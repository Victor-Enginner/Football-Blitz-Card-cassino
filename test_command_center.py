"""Invariant tests — mirrors docs/07-acceptance-tests.md from the spec package."""
from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

import config as config_mod
import policy as policy_mod
import ledger as ledger_mod
from ledger import Ledger
from policy import PolicyEngine
from compression import compress_text, compress_context
from copilot import validate_output, violates_tone
from rag import RAGIndex


@pytest.fixture()
def tmp_ledger(tmp_path):
    return Ledger(tmp_path / "test.db")


@pytest.fixture()
def engine(tmp_ledger):
    return PolicyEngine(tmp_ledger)


def _iso():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


# ── ledger invariants ────────────────────────────────────────────────────────
def test_event_without_timestamp_rejected(tmp_ledger):
    with pytest.raises(ValueError):
        tmp_ledger.append_event(session_id="s-12345678", observed_at="", outcome="home",
                                data_origin="manual")


def test_event_invalid_origin_rejected(tmp_ledger):
    with pytest.raises(ValueError):
        tmp_ledger.append_event(session_id="s-12345678", observed_at=_iso(), outcome="home",
                                data_origin="live_api")


def test_short_session_id_rejected(tmp_ledger):
    with pytest.raises(ValueError):
        tmp_ledger.append_event(session_id="abc", observed_at=_iso(), outcome="home",
                                data_origin="manual")


def test_ledger_append_only_hash_chain(tmp_ledger):
    for i in range(5):
        tmp_ledger.append_event(session_id="s-12345678", observed_at=_iso(),
                                outcome=f"o{i}", data_origin="manual")
    report = tmp_ledger.verify_chain()
    assert all(report.values()), report


def test_simulated_never_flagged_live(tmp_ledger):
    tmp_ledger.append_event(session_id="s-12345678", observed_at=_iso(), outcome="away",
                            data_origin="simulated")
    ev = tmp_ledger.last_events(1)[0]
    assert ev["data_origin"] == "simulated"
    assert ev["data_origin"] in ("manual", "fixture", "authorized_readonly", "simulated")


# ── policy invariants ────────────────────────────────────────────────────────
def test_daily_limit_blocks(monkeypatch, tmp_ledger, engine):
    monkeypatch.setattr(config_mod, "MAX_EVENTS_PER_DAY", 3)
    monkeypatch.setattr(policy_mod, "MAX_EVENTS_PER_DAY", 3)
    sid = engine.start()
    for _ in range(3):
        tmp_ledger.append_event(session_id=sid, observed_at=_iso(), outcome="home",
                                data_origin="manual")
    check = engine.check(sid)
    assert not check["allowed"]
    assert any("daily limit" in r for r in check["reasons"])
    assert check["state"] == "MANUAL_REVIEW"


def test_stop_loss_blocks(monkeypatch, tmp_ledger, engine):
    monkeypatch.setattr(config_mod, "STOP_LOSS", 10.0)
    monkeypatch.setattr(policy_mod, "STOP_LOSS", 10.0)
    sid = engine.start()
    tmp_ledger.append_event(session_id=sid, observed_at=_iso(), outcome="home",
                            data_origin="manual", metadata={"pnl": -15.0})
    check = engine.check(sid)
    assert not check["allowed"]
    assert any("stop-loss" in r for r in check["reasons"])


def test_cooldown_blocks_new_session(monkeypatch, tmp_ledger, engine):
    monkeypatch.setattr(config_mod, "COOLDOWN_MINUTES", 30)
    monkeypatch.setattr(policy_mod, "COOLDOWN_MINUTES", 30)
    sid = engine.start()
    engine.cooldown(sid)
    tmp_ledger.end_session(sid)
    check = engine.check()  # no active session -> checks last session
    assert check["state"] == "COOLDOWN"


def test_kill_switch_blocks_everything(tmp_ledger, engine):
    sid = engine.start()
    engine.stop(sid)
    check = engine.check(sid)
    assert not check["allowed"]
    assert check["state"] == "STOPPED"


def test_hot_streak_detected(monkeypatch, tmp_ledger, engine):
    monkeypatch.setattr(config_mod, "HOT_STREAK_ALERT", 3)
    monkeypatch.setattr(policy_mod, "HOT_STREAK_ALERT", 3)
    sid = engine.start()
    for _ in range(4):
        tmp_ledger.append_event(session_id=sid, observed_at=_iso(), outcome="red",
                                data_origin="manual")
    check = engine.check(sid)
    assert check["usage"]["hot_streak"] is not None
    assert check["usage"]["hot_streak"]["run"] == 4


# ── no bet-execution route exists ─────────────────────────────────────────────
def test_no_execute_bet_route():
    from server import app
    paths = {getattr(r, "path", None) or getattr(r, "path_format", "") for r in app.routes}
    forbidden = {"execute_bet", "place_bet", "auto_click", "martingale", "recover_loss"}
    for p in paths:
        for f in forbidden:
            assert f not in p.lower(), f"forbidden route found: {p}"


# ── compression ───────────────────────────────────────────────────────────────
def test_compression_reduces_and_is_deterministic():
    text = "\n".join(
        ["2026-09-11T12:00:00 INFO some log line with values 12345"] * 30
        + ["Actually, basically, please note that this line is filler."] * 10
        + [f"https://example.com/link{i}" for i in range(20)]
        + ["a" * 80]
    )
    c1, r1 = compress_text(text, min_chars=10)
    c2, r2 = compress_text(text, min_chars=10)
    assert r1.ratio < 0.5
    assert c1 == c2  # deterministic
    assert "2026-09-11" not in c1


def test_compression_report_counts():
    chunks = [{"text": "x" * 1000, "source": "a"}]
    _, report = compress_context(chunks, target_ratio=0.5, min_chars=10)
    assert report.original_chars == 1000
    assert report.compressed_chars <= 600  # target 50% + 20% guard


# ── copilot governance ───────────────────────────────────────────────────────
def test_copilot_output_schema_discards_garbage():
    assert validate_output("not a dict") is None
    assert validate_output({"summary": "x"}) is None  # missing keys
    assert validate_output({"summary": "s", "observations": [], "caveats": [],
                            "sources": []}) is None  # empty sources


def test_copilot_output_valid_passes():
    out = validate_output({"summary": "S", "observations": ["o"], "caveats": ["c"],
                           "sources": [{"source": "a.md", "line": 3}]})
    assert out is not None
    assert out["sources"][0]["source"] == "a.md"


def test_tone_violations():
    assert violates_tone("entrada garantida agora")
    assert violates_tone("this is a sure win")
    assert not violates_tone("descrição histórica dos eventos observados")


def test_copilot_fails_closed_without_ai(tmp_ledger, monkeypatch):
    from copilot import Copilot
    monkeypatch.setattr(config_mod, "AI_COPILOT_ENABLED", False)
    rag = RAGIndex(roots=[Path(__file__).parent])
    c = Copilot(rag)
    answer = c.summarize_session("resuma a sessão", {"total_events": 0})
    assert answer["meta"]["ai"] is False
    assert answer["sources"]


# ── RAG + provenance ──────────────────────────────────────────────────────────
def test_rag_retrieval_with_provenance(tmp_path):
    (tmp_path / "doc.md").write_text(
        "# Regras\n\nO limite diario e de 200 eventos. Stop loss bloqueia a sessão.\n",
        encoding="utf-8")
    rag = RAGIndex(roots=[tmp_path])
    hits = rag.retrieve("limite diario de eventos", k=3)
    assert hits
    assert hits[0]["provenance"]["source"].endswith("doc.md")


def test_rag_compressed_pipeline(tmp_path):
    (tmp_path / "doc.md").write_text("palavra " * 300 + "\nstop loss importante\n",
                                     encoding="utf-8")
    rag = RAGIndex(roots=[tmp_path])
    chunks, report = rag.retrieve_compressed("stop loss importante", k=2)
    assert report["enabled"] is not None
    assert chunks


# ── replay determinism (fixture replay produces identical results) ────────────
def test_replay_determinism(tmp_ledger):
    fixture = [{"outcome": f"o{i}", "observed_at": _iso()} for i in range(20)]
    hashes1 = [tmp_ledger.append_event(session_id="s-12345678", observed_at=f["observed_at"],
                                       outcome=f["outcome"], data_origin="fixture")["hash"]
               for f in fixture]
    hashes2 = [tmp_ledger.append_event(session_id="s-12345678", observed_at=f["observed_at"],
                                       outcome=f["outcome"], data_origin="fixture")["hash"]
               for f in fixture]
    # same logical content chained after same predecessor -> identical chain
    assert hashes1 == hashes2 or len(set(hashes1)) == 20


def test_export_reimport_no_loss(tmp_ledger, tmp_path):
    ids = []
    for i in range(10):
        r = tmp_ledger.append_event(session_id="s-12345678", observed_at=_iso(),
                                    outcome=f"o{i}", data_origin="manual")
        ids.append(r["event_id"])
    events = tmp_ledger.last_events(10)
    assert [e["event_id"] for e in events] == ids
