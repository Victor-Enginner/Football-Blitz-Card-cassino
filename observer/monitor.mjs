// Historical telemetry only. No betting routes, orders, external recipients or agents.
import fs from 'node:fs';
import net from 'node:net';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

export function summarize(events, maxGapMs = 120000) {
  let side = null, count = 0, previous = null, startedAt = null;
  for (const event of events) {
    const stamp = Date.parse(event.observed_at);
    if (!Number.isFinite(stamp)) { side = null; count = 0; previous = null; startedAt = null; continue; }
    if (previous && (event.session_id !== previous.session_id || stamp <= previous.stamp || stamp - previous.stamp > maxGapMs)) {
      side = null; count = 0; startedAt = null;
    }
    if (!['home', 'away'].includes(event.outcome)) { side = null; count = 0; startedAt = null; }
    else if (event.outcome === side) count++;
    else { side = event.outcome; count = 1; startedAt = event.observed_at; }
    previous = {stamp, session_id: event.session_id};
  }
  return {outcome: side, count, started_at: startedAt};
}

export function advance(state, history) {
  const events = history.events;
  const sessionChanged = state.session_id !== history.session_id;
  const cursor = sessionChanged ? null : state.cursor;
  const index = cursor ? events.findIndex(e => e.event_id === cursor) : -1;
  const notices = [];
  // On first boot or missing cursor, establish a baseline. Never replay historical alerts.
  if (cursor && index < 0) notices.push({kind: 'history_gap', message: '[PAPER] Lacuna no histórico; nova linha de base.'});
  if (index >= 0) {
    for (let i = index + 1; i < events.length; i++) {
      const current = summarize(events.slice(0, i + 1));
      const before = summarize(events.slice(0, i));
      if (current.count >= 4) notices.push({kind: 'historical_sequence', round_id: events[i].round_id,
        event_id: events[i].event_id, ...current,
        message: `[PAPER] ${current.outcome.toUpperCase()}: ${current.count} resultados consecutivos observados; sem valor preditivo.`});
      else if (before.count >= 4) notices.push({kind: 'sequence_reset', round_id: events[i].round_id,
        event_id: events[i].event_id, message: '[PAPER] Sequência encerrada ou continuidade interrompida.'});
    }
  }
  return {state: {...state, session_id: history.session_id,
    cursor: events.at(-1)?.event_id ?? null, summary: summarize(events)}, notices};
}

export function healthOf(ready, status) {
  if (!ready.ready) return 'backend_not_ready';
  if (!status.observer_online) return 'observer_offline';
  if (status.data_stale) return 'capture_stale';
  return 'ok';
}

async function run() {
  const base = 'http://127.0.0.1:8766';
  const token = process.env.BLITZ_CAPTURE_TOKEN;
  if (!token) throw new Error('capture credential missing');
  const directory = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../data');
  const checkpoint = path.join(directory, 'capture-monitor.json');
  const log = path.join(directory, 'capture-monitor.jsonl');
  let state = {session_id: null, cursor: null, health: null};
  if (fs.existsSync(checkpoint)) state = JSON.parse(fs.readFileSync(checkpoint, 'utf8'));
  let stopped = false;
  process.on('SIGTERM', () => { stopped = true; });
  process.on('SIGINT', () => { stopped = true; });
  async function get(route) {
    for (let attempt = 0; attempt < 3; attempt++) {
      try {
        const response = await fetch(base + route, {headers: {Authorization: `Bearer ${token}`},
          signal: AbortSignal.timeout(4000), redirect: 'error', cache: 'no-store'});
        if (!response.ok) throw new Error('http_' + response.status);
        return await response.json();
      } catch (error) {
        if (attempt === 2 || error.message === 'http_401') throw error;
        await new Promise(resolve => setTimeout(resolve, 500 * 2 ** attempt));
      }
    }
  }
  function record(notice) {
    fs.appendFileSync(log, JSON.stringify({at: new Date().toISOString(), ...notice}) + '\n');
  }
  while (!stopped) {
    let health;
    try {
      const [ready, status, history] = await Promise.all([get('/ready'), get('/api/observer/status'), get('/api/observer/history?limit=500')]);
      health = healthOf(ready, status);
      const result = advance(state, history);
      for (const notice of result.notices) record(notice);
      state = result.state;
    } catch (error) {
      health = error.message === 'http_401' ? 'authentication_failed' : 'backend_unreachable';
    }
    if (state.health !== health) record({kind: 'health_changed', previous: state.health, health,
      message: `[PAPER] Saúde da captura: ${health}`});
    state.health = health;
    state.checked_at = new Date().toISOString();
    fs.writeFileSync(checkpoint + '.tmp', JSON.stringify(state, null, 2));
    fs.renameSync(checkpoint + '.tmp', checkpoint);
    if (!stopped) await new Promise(resolve => setTimeout(resolve, 15000));
  }
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const singleton = net.createServer(socket => socket.destroy());
  const endpoint = process.platform === 'win32' ? '\\\\.\\pipe\\football-blitz-capture-monitor' :
    path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../data/capture-monitor.sock');
  singleton.once('error', () => { console.error('Monitor already running or local lock unavailable.'); process.exitCode = 1; });
  singleton.listen(endpoint, () => {
    run().catch(() => { console.error('Monitor stopped; inspect local checkpoint and disk availability.'); process.exitCode = 1; })
      .finally(() => singleton.close());
  });
}
