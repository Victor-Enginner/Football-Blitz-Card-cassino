import json
from pathlib import Path
from openclaw_supervisor import OpenClawSupervisor, SingleInstance, SupervisorConfig


def test_single_instance_exclusive(tmp_path):
    first = SingleInstance(tmp_path / "lock")
    second = SingleInstance(tmp_path / "lock")
    assert first.acquire()
    assert not second.acquire()
    first.close()
    assert second.acquire()
    second.close()


def test_backend_ready_and_stale_checkpoint(tmp_path, monkeypatch):
    clock = [1000.0]
    sup = OpenClawSupervisor(SupervisorConfig(data_dir=tmp_path, monitor_stale_s=120), now=lambda: clock[0])
    monkeypatch.setattr(sup, "_get_json", lambda route: {"ready": True})
    assert sup.backend_ready()
    assert sup.monitor_stale()
    (tmp_path / "capture-monitor.json").write_text(json.dumps({"checked_at": "1970-01-01T00:14:50Z"}))
    assert not sup.monitor_stale()
    clock[0] += 121
    assert sup.monitor_stale()


def test_maintenance_is_due_only_after_30_minutes(tmp_path, monkeypatch):
    clock = [1000.0]
    sup = OpenClawSupervisor(SupervisorConfig(data_dir=tmp_path, maintenance_s=1800), now=lambda: clock[0])
    calls = []
    monkeypatch.setattr(sup, "ensure_monitor", lambda **kw: calls.append(kw) or True)
    assert not sup.maintenance()
    clock[0] += 1800
    assert sup.maintenance()
    assert calls == [{"force": True}]
