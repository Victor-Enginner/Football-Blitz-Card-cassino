/* DOM only, isolated extension context. No page globals, clicks or credentials. */
(function () {
  const names = {MANDANTE: 'home', VISITANTE: 'away', EMPATE: 'draw'};
  function snapshot(doc) {
    if (!doc.body || !doc.body.textContent.includes('Football Blitz Top Card')) return null;
    const header = doc.querySelector('[data-testid="game-header-game-id"]');
    const round = header?.textContent.match(/ID\s*:\s*(\d{8,24})\b/);
    // .ee_en is a betting label, NEVER a result. .F_M was observed on the final banner.
    const banners = Array.from(doc.querySelectorAll('div.F_M')).filter(e => e.getClientRects().length);
    if (!round) return null;
    if (banners.length !== 1) return {round_id: round[1], outcome: null};
    const outcome = names[banners[0].textContent.trim().toUpperCase()];
    return {round_id: round[1], outcome: outcome || null};
  }
  function createTracker() {
    let armed = false, candidate = null, since = 0;
    return {
      read(value, now) {
        if (!value) { armed = false; candidate = null; return null; }
        if (!value.outcome) { armed = true; candidate = null; return null; }
        // Do not import a result already displayed at installation/reload.
        if (!armed) return null;
        const key = value.round_id + ':' + value.outcome;
        if (candidate && candidate.split(':')[0] !== value.round_id) {
          armed = false; candidate = null; return null;
        }
        if (candidate !== key) { candidate = key; since = now; return null; }
        return now - since >= 750 ? value : null;
      }
    };
  }
  if (typeof module !== 'undefined') { module.exports = {snapshot, createTracker}; return; }
  const tracker = createTracker(), accepted = new Set();
  let stopped = false, busy = false, latest = null, retries = 0, nextAttempt = 0;
  function send(message) { return chrome.runtime.sendMessage(message); }
  async function poll() {
    if (stopped) return;
    const sample = tracker.read(snapshot(document), Date.now());
    if (!sample || accepted.has(sample.round_id) || busy || Date.now() < nextAttempt) return;
    if (!latest || latest.round_id !== sample.round_id || latest.outcome !== sample.outcome) {
      latest = {...sample, observed_at: new Date().toISOString()}; retries = 0;
    }
    busy = true;
    try {
      const result = await send({kind: 'observation', observation: latest});
      if (result?.ok && result.accepted) {
        accepted.add(sample.round_id);
        if (accepted.size > 500) accepted.delete(accepted.values().next().value);
        console.info('[blitz-capture] rodada registrada', sample.round_id, sample.outcome);
        retries = 0;
      } else if (!result?.ok) {
        nextAttempt = Date.now() + Math.min(1000 * 2 ** Math.min(++retries, 4), 15000);
        console.warn('[blitz-capture] coleta pendente', result?.status || 'offline');
      }
    } catch {
      nextAttempt = Date.now() + 15000;
    } finally { busy = false; }
  }
  const timer = setInterval(poll, 1000);
  const heartbeat = setInterval(() => {
    if (document.querySelector('[data-testid="game-header-game-id"]') &&
        document.body?.textContent.includes('Football Blitz Top Card')) {
      send({kind: 'heartbeat'}).catch(() => {});
    }
  }, 15000);
  addEventListener('pagehide', () => { stopped = true; clearInterval(timer); clearInterval(heartbeat); }, {once: true});
})();
