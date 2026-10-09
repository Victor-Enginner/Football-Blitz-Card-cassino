// harness/observer-playwright.js — somente leitura, sem hack.
// Injetado via Playwright page.evaluate em sessão logada do usuário.
// Observa o DOM do Football Blitz e envia para ws local; nunca toca em cookie externo.
export function installObserver() {
  if (window.__fbHarness) return window.__fbHarness;
  const RESULT_SELECTORS = [
    "[data-automation-locator*='history'] [class*='item']",
    ".history-item .history-item-value__text",
    "[class*='result'][class*='value']",
  ];
  let last = null, ws = null;
  function findDoc() {
    try {
      const f = document.querySelector("iframe[src*='pragmatic'], iframe[id*='game']");
      if (f && f.contentDocument) return f.contentDocument;
    } catch {}
    return document;
  }
  function extract(text) {
    const t = text.trim().toLowerCase();
    if (["home","away","draw","mandante","visitante","empate"].includes(t)) {
      if (t==="mandante"||t==="home") return "home";
      if (t==="visitante"||t==="away") return "away";
      return "draw";
    }
    return null;
  }
  window.__fbHarness = { last, send: (o)=> ws && ws.readyState===1 && ws.send(JSON.stringify({kind:"outcome", outcome:o, observed_at: new Date().toISOString(), raw:o, parser_version:"harness-mo-1.0"})) };
  const doc = findDoc();
  const target = doc.body || doc.documentElement;
  if (!target) return window.__fbHarness;
  new MutationObserver(()=>{
    for (const sel of RESULT_SELECTORS) {
      const nodes = doc.querySelectorAll(sel);
      if (!nodes.length) continue;
      const text = (nodes[0].textContent||"").trim();
      if (!text || text===last) return;
      const out = extract(text);
      if (out) { last=text; window.__fbHarness.last=text; window.__fbHarness.send(out); }
      return;
    }
  }).observe(target, {childList:true, subtree:true, characterData:true});
  return window.__fbHarness;
}
