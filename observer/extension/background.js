/* The scoped capture credential lives only in the extension worker. */
importScripts('local-config.js');
chrome.runtime.onMessage.addListener((message, sender, reply) => {
  let source;
  try { source = new URL(sender.url); } catch { return false; }
  if (sender.id !== chrome.runtime.id || source.protocol !== 'https:' ||
      !['client.pragmaticplaylive.net', 'games.pragmaticplaylive.net'].includes(source.hostname)) return false;
  if (!['heartbeat', 'observation'].includes(message?.kind)) return false;
  const isOutcome = message.kind === 'observation';
  const body = message.observation;
  if (isOutcome && (!body || !/^\d{8,24}$/.test(body.round_id) ||
      !['home', 'away', 'draw'].includes(body.outcome))) return false;
  (async () => {
    try {
      const response = await fetch(BLITZ_CAPTURE.base + '/api/observer/' + (isOutcome ? 'outcomes' : 'heartbeat'), {
        method: isOutcome ? 'PUT' : 'POST',
        headers: {'Authorization': 'Bearer ' + BLITZ_CAPTURE.token, 'Content-Type': 'application/json'},
        ...(isOutcome ? {body: JSON.stringify({round_id: body.round_id, outcome: body.outcome,
          observed_at: body.observed_at, parser_version: 'fb-banner-1.0'})} : {}),
        signal: AbortSignal.timeout(5000), redirect: 'error', credentials: 'omit', cache: 'no-store'
      });
      if (!response.ok) return reply({ok: false, status: response.status});
      reply({ok: true, ...await response.json()});
    } catch { reply({ok: false, status: 'offline'}); }
  })();
  return true;
});
