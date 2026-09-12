"""Council tests — deterministic, no LLM required (router mocked via monkeypatch)."""
import pytest

import council


@pytest.fixture
def no_llm(monkeypatch):
    """Force _chat to return None: roles must degrade to fail-closed 'unknown'."""
    monkeypatch.setattr(council, "_chat", lambda system, user: None)


def test_roles_present():
    names = [r.__name__ for r in council.ROLES]
    assert names == ["hermes_analyst", "orca_verifier", "swe_validator", "kode_builder"]
    assert council.BLOCKED_ROLES == [council.freecode_blocked]


def test_roles_fail_closed_without_llm(no_llm):
    task = {"kind": "review", "summary": "review dashboard schema validation"}
    report = council.run_council(task, use_deepagents=False)
    assert report["engine"] == "sequential"
    for v in report["verdicts"]:
        assert v["verdict"] in ("pass", "unknown")
    assert not report["blocked"]


def test_orca_blocks_on_secrets(no_llm):
    task = {"kind": "review", "summary": "artifact contains API_KEY=sk-123 hardcoded"}
    report = council.run_council(task, use_deepagents=False)
    orca = next(v for v in report["verdicts"] if v["agent"] == "orca-agent")
    assert orca["verdict"] == "block"
    assert report["blocked"] is True


def test_free_code_always_refused(no_llm):
    v = council.freecode_blocked({"kind": "x", "summary": "y"})
    assert v["verdict"] == "refused"


def test_council_health_shape(no_llm):
    h = council.council_health()
    assert h["deepagents"] is True
    assert set(h["roles"]) == {"hermes_analyst", "orca_verifier", "swe_validator", "kode_builder"}
    assert h["llm_chain"] in (True, False, None)


def test_council_writes_decision_to_ledger(no_llm, tmp_path):
    """A full run with a session writes a hashed decision row."""
    import tempfile
    from ledger import Ledger

    db = tmp_path / "council_test.db"
    led = Ledger(db)
    led.start_session("sess-council-1", state="PAPER", note="council test")
    report = council.run_council(
        {"kind": "review", "summary": "schema validation of quiz components"},
        session_id="sess-council-1",
        use_deepagents=False,
        ledger=led,
    )
    assert report["engine"] == "sequential"
    # ledger must contain the hashed decision
    row = led._conn.execute(
        "SELECT action, blocked_by FROM manual_decisions ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert row["action"] == "council_review"
