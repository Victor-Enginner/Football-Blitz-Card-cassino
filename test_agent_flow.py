from pathlib import Path
from unittest.mock import Mock

from agent_flow import AgentFlow


def test_flow_fails_closed_without_secret(tmp_path, monkeypatch):
    import agent_flow
    monkeypatch.setattr(agent_flow, "OBSERVER_TOKEN", "")
    flow = AgentFlow(tmp_path)
    result = flow.once()
    assert result == {"flow": "blocked", "reason": "OBSERVER_TOKEN_missing"}
    assert 'OBSERVER_TOKEN_missing' in (tmp_path / 'agent-flow.jsonl').read_text()


def test_flow_order_and_paper_contract(tmp_path, monkeypatch):
    import agent_flow
    monkeypatch.setattr(agent_flow, "OBSERVER_TOKEN", "configured-secret")
    flow = AgentFlow(tmp_path)
    calls = []
    flow.supervisor.check_once = lambda: calls.append('openclaw') or {'backend_ready': True}
    flow.hermes.check_once = lambda: calls.append('hermes') or {'health': 'ok'}
    flow.muse.run_once = lambda: calls.append('muse') or {'window': 4, 'current_streak': 4,
        'risk_score': 1.0, 'risk_danger_window': True}
    result = flow.once()
    assert calls == ['openclaw', 'hermes', 'muse']
    assert result['orders_allowed'] is False
    assert result['sequence_policy'] == 'observe_only'
    assert 'risk_danger_window' in result['muse']
