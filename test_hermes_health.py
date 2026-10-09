import json

from hermes_health import HermesHealth, health_of


def fake_fetch_factory(ready, status):
    def fake(route, headers, timeout):
        return ready if route.endswith("/ready") else status
    return fake


def test_health_states_fail_closed():
    assert health_of({"ready": False, "chain": {"events": True}}, {}) == "backend_not_ready"
    assert health_of({"ready": True, "chain": {"events": True}}, {"observer_online": False}) == "observer_offline"
    assert health_of({"ready": True, "chain": {"events": True}}, {"observer_online": True, "data_stale": True}) == "capture_stale"
    assert health_of({"ready": True, "chain": {"events": True}}, {"observer_online": True, "data_stale": False}) == "ok"
    assert health_of({"ready": True, "chain": {"events": False}}, {"observer_online": True, "data_stale": False}) == "backend_not_ready"


def test_alert_only_on_state_change(tmp_path):
    ready = {"ready": True, "chain": {"events": True, "audit_log": True}}
    status = {"observer_online": True, "data_stale": False, "heartbeat_age_s": 2}
    hermes = HermesHealth("http://test", "token", tmp_path, fetch=fake_fetch_factory(ready, status))
    assert hermes.check_once()["health"] == "ok"
    assert hermes.check_once()["health"] == "ok"
    lines = tmp_path.joinpath("hermes-health.jsonl").read_text().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["previous"] is None
    status["observer_online"] = False
    assert hermes.check_once()["health"] == "observer_offline"
    assert len(tmp_path.joinpath("hermes-health.jsonl").read_text().splitlines()) == 2


def test_checkpoint_is_reloaded_without_repeating_alert(tmp_path):
    ready = {"ready": True, "chain": {"events": True}}
    status = {"observer_online": True, "data_stale": False}
    fetch = fake_fetch_factory(ready, status)
    HermesHealth("http://test", "token", tmp_path, fetch=fetch).check_once()
    second = HermesHealth("http://test", "token", tmp_path, fetch=fetch)
    second.check_once()
    assert len(tmp_path.joinpath("hermes-health.jsonl").read_text().splitlines()) == 1
