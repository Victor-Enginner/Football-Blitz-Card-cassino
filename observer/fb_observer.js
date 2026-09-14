// Football Blitz observer bridge — runs in the game tab (DevTools console or
// Tampermonkey). Reads the result via MutationObserver on the game DOM and
// pushes each outcome to the Command Center over WebSocket.
//
// GOVERNANCE: read-only. This script NEVER clicks, never bets, never touches
// anti-bot systems. It only watches the visible result and reports it.
//
// Usage (in the game tab console, after login):
//   const s = fbObserverCreate({ server: "ws://SEU-VPS:8765/ws", token: "SEU_OBSERVER_TOKEN" });
//   // para parar: s.disconnect()
//
// Como funciona:
// 1. Procura o container de resultados do Football Blitz (Top Card) no DOM.
//    O jogo é Pragmatic Play num iframe — o script tenta o iframe primeiro.
// 2. MutationObserver reage a novos nós (novo resultado na timeline).
// 3. Extrai o texto (home/away/draw ou valores das cartas) e envia via WS.
// 4. Reconexão automática com backoff. Ping keepalive a cada 20s.

(function () {
  if (window.__fbObserverLoaded) return;
  window.__fbObserverLoaded = true;

  window.fbObserverCreate = function fbObserverCreate(opts) {
    const server = opts.server || "ws://localhost:8765/ws";
    const token = opts.token || "";
    let ws = null;
    let backoff = 1000;
    let lastOutcome = null;
    let stopped = false;
    let observer = null;

    function connect() {
      if (stopped) return;
      const url = token ? `${server}?token=${encodeURIComponent(token)}` : server;
      ws = new WebSocket(url);
      ws.onopen = () => {
        console.info("[fb-observer] conectado ao Command Center");
        backoff = 1000;
        start();
      };
      ws.onclose = () => {
        if (stopped) return;
        console.warn(`[fb-observer] ws caiu, reconectando em ${backoff}ms`);
        setTimeout(connect, backoff);
        backoff = Math.min(backoff * 2, 30000);
      };
      ws.onerror = (e) => console.warn("[fb-observer] ws erro", e);
    }

    function send(payload) {
      if (ws && ws.readyState === 1) {
        ws.send(JSON.stringify(payload));
        return true;
      }
      return false;
    }

    // keepalive ping every 20s
    setInterval(() => send({ kind: "ping", at: Date.now() }), 20000);

    // ── DOM reading ──────────────────────────────────────────────────────
    // Seletores candidatos (Pragmatic muda nomes entre versões; cobrimos os
    // comuns e você pode adicionar o seu após inspecionar com F12).
    const RESULT_SELECTORS = [
      "[data-automation-locator*='history'] [class*='item']",
      ".history-item .history-item-value__text",
      "[class*='result'][class*='value']",
      ".game-history__item",
    ];

    function findIframeDocument() {
      // Pragmatic games usually live inside an iframe
      try {
        const frame = document.querySelector("iframe[src*='pragmatic'], iframe[id*='game']");
        if (frame && frame.contentDocument) return frame.contentDocument;
      } catch (e) { /* cross-origin: stay in top document */ }
      return document;
    }

    function extractOutcome(text) {
      if (!text) return null;
      const t = text.trim().toLowerCase();
      if (["home", "away", "draw", "empate", "casa", "fora", "mandante", "visitante"].includes(t)) {
        if (t === "empate" || t === "draw") return "draw";
        if (t === "casa" || t === "mandante" || t === "home") return "home";
        return "away";
      }
      // card values: "H 7", "A K", "7 x 9", "Kx7"… (A=1 low, J=11 Q=12 K=13)
      const cardVal = (c) => {
        c = c.toLowerCase();
        if (c === "j") return 11; if (c === "q") return 12;
        if (c === "k") return 13; if (c === "a") return 1;
        const n = parseInt(c, 10);
        return (n >= 2 && n <= 10) ? n : NaN;
      };
      // "H 7 / A 9" ou "H:K A:7"
      let m = t.match(/h\s*[:\s]\s*([2-9jqka]|10).*?a\s*[:\s]\s*([2-9jqka]|10)/i);
      // "7 x 9" / "K×7"
      if (!m) m = t.match(/([2-9jqka]|10)\s*[x×]\s*([2-9jqka]|10)/i);
      if (m) {
        const hv = cardVal(m[1]), av = cardVal(m[2]);
        if (isNaN(hv) || isNaN(av)) return null;
        return { outcome: hv > av ? "home" : av > hv ? "away" : "draw",
                 homeCard: m[1].toUpperCase(), awayCard: m[2].toUpperCase() };
      }
      return null; // texto não mapeado: log raw p/ triagem
    }

    function readNewResults(mutations) {
      const doc = findIframeDocument();
      for (const sel of RESULT_SELECTORS) {
        const nodes = doc.querySelectorAll(sel);
        if (!nodes.length) continue;
        const node = nodes[0]; // most recent result
        const text = (node.textContent || "").trim();
        if (!text || text === lastOutcome) return;
        const parsed = extractOutcome(text);
        console.info("[fb-observer] novo resultado bruto:", text, "→", parsed ? parsed.outcome : "(não mapeado)");
        lastOutcome = text;
        if (parsed) {
          const outcome = typeof parsed === "string" ? parsed : parsed.outcome;
          const ok = send({
            kind: "outcome",
            outcome,
            home_card: parsed.homeCard, away_card: parsed.awayCard,
            observed_at: new Date().toISOString(),
            raw: text.slice(0, 40),
            parser_version: "fb-mutation-2.0",
          });
          console.info(`[fb-observer] enviado: ${outcome} (${ok ? "ok" : "ws fechado"})`);
        }
        return;
      }
    }

    function start() {
      const doc = findIframeDocument();
      const target = doc.body || doc.documentElement;
      if (!target) { console.warn("[fb-observer] sem body para observar"); return; }
      observer = new MutationObserver(() => readNewResults());
      observer.observe(target, { childList: true, subtree: true, characterData: true });
      console.info("[fb-observer] MutationObserver ativo. Aguardando resultados…");
      readNewResults([]); // read current state once
    }

    connect();
    return {
      disconnect() {
        stopped = true;
        if (observer) observer.disconnect();
        if (ws) ws.close();
        console.info("[fb-observer] parado");
      },
      status() {
        return { connected: ws && ws.readyState === 1, lastOutcome, server };
      },
    };
  };
  console.info("[fb-observer] pronto: fbObserverCreate({server, token})");
})();
