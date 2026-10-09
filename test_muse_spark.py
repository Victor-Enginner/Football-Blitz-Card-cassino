import json
from pathlib import Path

from muse_spark import MuseSpark, analyze_events, monitor_danger_windows


def event(number, outcome):
    return {"event_id": f"e{number}", "outcome": outcome,
            "observed_at": f"2026-09-14T10:00:{number:02d}+00:00"}


def test_metrics_and_home_streak_are_descriptive():
    report = analyze_events([event(i, "home") for i in range(1, 5)] + [event(5, "draw")])
    assert report["current_outcome"] == "draw"
    assert report["current_streak"] == 0
    assert report["risk_danger_window"] is False
    assert report["frequency"] == {"home": 4, "away": 0, "draw": 1}
    assert report["orders_allowed"] is False


def test_streak_danger_survives_window_and_draw_resets():
    report = analyze_events([event(i, "away") for i in range(1, 5)])
    assert report["current_streak"] == 4
    assert report["risk_danger_window"] is True
    assert report["danger_reason"] == "same_outcome_streak"


def test_run_once_writes_report_and_marker(tmp_path: Path):
    runner = MuseSpark(tmp_path, tmp_path / "unused.db", risk_threshold=0.5)
    report = runner.run_once([event(i, "home") for i in range(1, 5)])
    assert report["risk_danger_window"]
    saved = json.loads((tmp_path / "muse-spark.jsonl").read_text().splitlines()[0])
    marker = json.loads((tmp_path / "muse-risk-danger.json").read_text())
    assert saved["risk_score"] == marker["risk_score"]
    assert marker["event_id"] == "e4"


def test_monitor_notice_filter(tmp_path: Path):
    path = tmp_path / "monitor.jsonl"
    path.write_text(json.dumps({"kind": "historical_sequence", "count": 4}) + "\n" +
                    json.dumps({"kind": "health_changed"}) + "\n")
    assert len(monitor_danger_windows(path)) == 1
