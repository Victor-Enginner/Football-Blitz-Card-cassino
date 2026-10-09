from datetime import datetime, timezone, timedelta
from unittest.mock import Mock
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from ledger import Ledger
from observer_capture import create_capture_router, capture_token


@pytest.fixture
def setup(tmp_path, monkeypatch):
    db = Ledger(tmp_path / 'test.db')
    db.start_session('test-paper-session')
    broadcaster = Mock()
    app = FastAPI()
    app.include_router(create_capture_router(db, broadcaster, 'test-secret'))
    tick = [100.0]
    monkeypatch.setattr('observer_capture.time.monotonic', lambda: tick[0])
    yield db, broadcaster, TestClient(app), tick
    db.close()


HEADERS = {'Authorization': 'Bearer ' + capture_token('test-secret')}


def body(round_id='17755021116', outcome='home'):
    return dict(round_id=round_id, outcome=outcome,
                observed_at=datetime.now(timezone.utc).isoformat(), parser_version='fb-banner-1.0')


def test_auth_and_validation(setup):
    db, bus, client, tick = setup
    assert client.put('/api/observer/outcomes', json=body()).status_code == 401
    assert client.put('/api/observer/outcomes', json=body(outcome='invalid'), headers=HEADERS).status_code == 422
    assert client.put('/api/observer/outcomes', json=body(round_id='bad'), headers=HEADERS).status_code == 422
    old = body()
    old['observed_at'] = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    assert client.put('/api/observer/outcomes', json=old, headers=HEADERS).status_code == 422
    assert db.last_events(10) == []


def test_double_confirmation_and_persistent_dedup(setup):
    db, bus, client, tick = setup
    payload = body()
    assert not client.put('/api/observer/outcomes', json=payload, headers=HEADERS).json()['accepted']
    assert not client.put('/api/observer/outcomes', json=payload, headers=HEADERS).json()['accepted']
    tick[0] += 1
    assert client.put('/api/observer/outcomes', json=payload, headers=HEADERS).json()['accepted']
    # Fresh router has no in-memory dedup state.
    restarted = FastAPI()
    restarted.include_router(create_capture_router(db, bus, 'test-secret'))
    result = TestClient(restarted).put('/api/observer/outcomes', json=payload, headers=HEADERS)
    assert result.json()['duplicate']
    assert len(db.last_events(10)) == 1
    assert db.last_events(1)[0]['session_id'] == 'test-paper-session'
    assert bus.broadcast.call_count == 1
    assert all(db.verify_chain().values())


def test_equal_results_different_rounds_and_draw(setup):
    db, bus, client, tick = setup
    for i, outcome in enumerate(['home', 'home', 'home', 'home', 'draw', 'away']):
        payload = body(str(17755021116+i), outcome)
        client.put('/api/observer/outcomes', json=payload, headers=HEADERS)
        tick[0] += 1
        assert client.put('/api/observer/outcomes', json=payload, headers=HEADERS).json()['accepted']
    assert [e['outcome'] for e in db.last_events(10)] == ['home']*4 + ['draw', 'away']
    assert bus.broadcast.call_count == 6


def test_conflict_and_session_gate(setup):
    db, bus, client, tick = setup
    payload = body()
    client.put('/api/observer/outcomes', json=payload, headers=HEADERS)
    tick[0] += 1
    client.put('/api/observer/outcomes', json=payload, headers=HEADERS)
    assert client.put('/api/observer/outcomes', json=body(outcome='away'), headers=HEADERS).status_code == 409
    db.end_session('test-paper-session')
    other = body('17755021117')
    client.put('/api/observer/outcomes', json=other, headers=HEADERS)
    tick[0] += 1
    assert client.put('/api/observer/outcomes', json=other, headers=HEADERS).status_code == 423
    assert len(db.last_events(10)) == 1


def test_health(setup):
    db, bus, client, tick = setup
    assert not client.get('/api/observer/status', headers=HEADERS).json()['observer_online']
    assert client.post('/api/observer/heartbeat', headers=HEADERS).status_code == 200
    assert client.get('/api/observer/status', headers=HEADERS).json()['observer_online']
    assert client.get('/api/observer/status', headers=HEADERS).json()['data_stale']


def test_history_is_session_scoped_and_authenticated(setup):
    db, bus, client, tick = setup
    assert client.get('/api/observer/history').status_code == 401
    assert client.get('/api/observer/history?limit=501', headers=HEADERS).status_code == 422
    db.append_event(session_id='other-session', outcome='away',
        observed_at=datetime.now(timezone.utc).isoformat(), data_origin='authorized_readonly',
        parser_version='fb-banner-1.0')
    payload = body()
    client.put('/api/observer/outcomes', json=payload, headers=HEADERS)
    tick[0] += 1
    client.put('/api/observer/outcomes', json=payload, headers=HEADERS)
    history = client.get('/api/observer/history', headers=HEADERS).json()
    assert len(history['events']) == 1
    assert history['events'][0]['session_id'] == 'test-paper-session'
    status = client.get('/api/observer/status', headers=HEADERS).json()
    assert status['last_outcome'] == payload['observed_at']
    assert not status['data_stale']
