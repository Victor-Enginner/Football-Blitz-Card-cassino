/* Football Blitz Command Center — dashboard logic (vanilla JS, no build step). */
"use strict";

const $ = (id) => document.getElementById(id);
let lastEventId = 0;

/* ── sound engine: GREEN signal + alerts (WebAudio, no assets) ───────────── */
let audioCtx = null;
function ensureAudio() {
  if (!audioCtx) {
    try { audioCtx = new (window.AudioContext || window.webkitAudioContext)(); }
    catch (e) { audioCtx = null; }
  }
  return audioCtx;
}
function beep(freq, dur, type = "sine", when = 0, vol = 0.18) {
  if (muted) return; /* mudo global respeitado */
  const ctx = ensureAudio();
  if (!ctx) return;
  const osc = ctx.createOscillator();
  const gain = ctx.createGain();
  osc.type = type; osc.frequency.value = freq;
  gain.gain.setValueAtTime(vol, ctx.currentTime + when);
  gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + when + dur);
  osc.connect(gain); gain.connect(ctx.destination);
  osc.start(ctx.currentTime + when);
  osc.stop(ctx.currentTime + when + dur);
}
function soundGreen() {           /* rising two-tone chime */
  beep(660, 0.12, "sine", 0);
  beep(990, 0.22, "sine", 0.12);
}
function soundBlock() {           /* low double-buzz for blocked action */
  beep(180, 0.15, "square", 0, 0.12);
  beep(140, 0.25, "square", 0.18, 0.12);
}
function soundHotStreak() {       /* urgent triple-beep */
  beep(880, 0.1, "triangle", 0);
  beep(880, 0.1, "triangle", 0.15);
  beep(880, 0.1, "triangle", 0.3);
}
function soundEntryAlert() {      /* sirene fixa de entrada: 2 tons ×3 */
  for (let i = 0; i < 3; i++) {
    beep(660, 0.12, "square", i * 0.3, 0.1);
    beep(520, 0.12, "square", i * 0.3 + 0.14, 0.1);
  }
}
function soundConfirmed() {       /* entrada confirmada: arpejo subida */
  beep(523, 0.1, "sine", 0, 0.16);
  beep(659, 0.1, "sine", 0.1, 0.16);
  beep(784, 0.18, "sine", 0.2, 0.16);
}
function soundCoin() {            /* moeda pingando: ping agudo c/ decay */
  beep(1568, 0.35, "sine", 0, 0.12);
  beep(2093, 0.3, "sine", 0.02, 0.07);
}
function soundWin() {             /* GREEN coerente: fanfarra + moeda */
  soundCoin();
  beep(523, 0.1, "sine", 0.12, 0.15);
  beep(659, 0.1, "sine", 0.22, 0.15);
  beep(784, 0.12, "sine", 0.32, 0.15);
  beep(1047, 0.25, "sine", 0.44, 0.15);
}
document.addEventListener("click", ensureAudio, { once: true });
document.addEventListener("keydown", ensureAudio, { once: true });

/* ── toast ────────────────────────────────────────────────────────────────── */
let toastTimer = null;
function toast(msg, kind = "green") {
  const t = $("toast");
  if (!t) { console.log(`[${kind}] ${msg}`); return; }
  t.textContent = msg;
  t.className = "show" + (kind === "red" ? " red" : "");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.className = ""; }, 3500);
}

/* ── api helpers ──────────────────────────────────────────────────────────── */
async function api(path, opts) {
  const res = await fetch(path, opts);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = data.detail;
    const reasons = Array.isArray(detail) ? detail.map(d => d.msg || String(d))
      : (detail && detail.reasons) ? detail.reasons : [typeof detail === "string" ? detail : res.statusText];
    const err = new Error(reasons.join(" · "));
    err.reasons = reasons;
    err.status = res.status;
    throw err;
  }
  return data;
}

/* ── state + limits ───────────────────────────────────────────────────────── */
let lastHotKey = "";
async function refreshState() {
  try {
    const s = await api("/api/state");
    const u = s.check.usage;
    if ($("state-pill")) $("state-pill").textContent = s.state;
    updateAutoBtn(!!s.auto_paper);
    if ($("hero-session")) $("hero-session").textContent = s.session ? `${s.session.session_id.slice(0, 12)}…` : "—";
    if ($("hero-event-budget")) $("hero-event-budget").textContent = `${u.events_today} / ${u.daily_limit}`;
    if ($("hero-ai-status")) $("hero-ai-status").textContent = s.state === "OFFLINE" ? "STANDBY" : "CONECTADO";
    document.body.dataset.state = s.state;
    document.body.dataset.neuralActive = String(s.state === "PAPER" && s.check.allowed === true);
    $("lim-events").textContent = `${u.events_today} / ${u.daily_limit}`;
    const pct = Math.min(100, (u.events_today / Math.max(1, u.daily_limit)) * 100);
    const bar = $("lim-bar");
    bar.style.width = pct + "%";
    bar.classList.toggle("warn", pct >= 80);
    const pnl = u.paper_pnl_today;
    $("lim-pnl").textContent = `R$ ${pnl.toFixed(2).replace(".", ",")}`;
    $("lim-pnl").style.color = pnl < 0 ? "var(--red)" : pnl > 0 ? "var(--green)" : "inherit";
    $("lim-time").textContent = `${u.session_minutes} / ${u.max_session_minutes} min`;
    const hot = u.hot_streak;
    $("lim-hot").textContent = hot ? `${hot.outcome} ×${hot.run}` : "—";
    $("lim-hot").style.color = hot ? "var(--red)" : "inherit";
    const reasons = s.check.reasons.filter(r => !r.startsWith("HOT STREAK"));
    const br = $("block-reasons");
    if (reasons.length) {
      br.hidden = false;
      br.innerHTML = reasons.map(r => `⛔ ${escapeHtml(r)}`).join("<br>");
      notify("block", "Bloqueio: " + reasons[0], "block:" + reasons[0]);
    } else { br.hidden = true; }
    document.querySelectorAll(".status-pill.state").forEach(p =>
      p.dataset.hot = String(!!hot));

    /* hot-streak sound fires once per new streak */
    if (hot) {
      const key = `${hot.outcome}:${hot.run}`;
      if (key !== lastHotKey) { soundHotStreak(); const ptH = ptOutcome(hot.outcome); toast(`🔥 Mesa quente: ${ptH.emoji} ${ptH.name} repetiu ${hot.run}x — considere pausar`, "red"); }
      lastHotKey = key;
    } else { lastHotKey = ""; }
  } catch (e) { document.body.dataset.neuralActive = "false"; console.warn("state:", e.message); }
}

/* ── timeline ─────────────────────────────────────────────────────────────── */
function renderTimeline(events) {
  const tl = $("timeline");
  tl.innerHTML = "";
  for (const ev of events.slice().reverse()) {
    const div = document.createElement("div");
    div.className = "ev" + (ev.id > lastEventId ? " flash" : "");
    const meta = safeParse(ev.metadata);
    const pnl = meta && typeof meta.pnl !== "undefined" ? ` · R$ ${Number(meta.pnl).toFixed(2)}` : "";
    const pt = ptOutcome(ev.outcome);
    div.innerHTML = `<span class="outcome ${pt.cls}">${pt.emoji} ${pt.name}</span>
      <span class="origin">${escapeHtml(ev.data_origin)}${pnl}</span>
      <span class="time">${escapeHtml((ev.observed_at || "").slice(11, 19))}</span>`;
    tl.appendChild(div);
  }
  /* GREEN signal: sound + toast for genuinely new events */
  const newest = events.length ? events[events.length - 1].id : 0;
  if (lastEventId && newest > lastEventId) {
    const ev = events[events.length - 1];
    soundGreen();
    toast(`🟢 GREEN registrado: ${ev.outcome}`);
  }
  lastEventId = Math.max(lastEventId, newest);
}
function safeParse(s) { try { return JSON.parse(s); } catch { return null; } }
function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
/* ── linguagem do jogo: MANDANTE 🟡 / VISITANTE 🔵 / EMPATE 🟢 ─────────── */
function ptOutcome(o) {
  const t = String(o || "").trim().toLowerCase();
  if (t === "home" || t === "mandante" || t === "casa") return { name: "MANDANTE", cls: "out-home", emoji: "🟡" };
  if (t === "away" || t === "visitante" || t === "fora") return { name: "VISITANTE", cls: "out-away", emoji: "🔵" };
  if (t === "draw" || t === "empate") return { name: "EMPATE", cls: "out-draw", emoji: "🟢" };
  return { name: String(o), cls: "out-unknown", emoji: "" };
}

async function refreshEvents() {
  try {
    const data = await api("/api/events?n=40");
    renderTimeline(data.events);
    if ($("timeline-counter")) $("timeline-counter").textContent = `${data.events.length} EVENTS`;
  } catch (e) { console.warn("events:", e.message); }
}

/* ── stats ────────────────────────────────────────────────────────────────── */
async function refreshStats() {
  try {
    const s = await api("/api/stats");
    const el = $("stats-freq");
    const max = Math.max(1, ...s.outcome_frequency.map(f => f.count));
    el.innerHTML = s.outcome_frequency.map(f => {
      const pt = ptOutcome(f.outcome);
      return `
      <div class="freq-row">
        <span class="label ${pt.cls}">${pt.emoji} ${pt.name}</span>
        <div class="bar2"><div style="width:${(f.count / max) * 100}%"></div></div>
        <span class="count">${f.count}</span>
      </div>`;}).join("") || "<p class='hint'>sem eventos ainda</p>";
  } catch (e) { console.warn("stats:", e.message); }
}

/* ── omniroute pill ───────────────────────────────────────────────────────── */
async function refreshOmniroute() {
  try {
    const h = await api("/api/health");
    const p = $("omniroute-pill");
    const ok = h.omniroute && h.omniroute.enabled;
    p.textContent = ok ? "◎ OmniRoute OK" : "◎ OmniRoute —";
    p.style.color = ok ? "var(--green)" : "var(--muted)";
  } catch { const p = $("omniroute-pill"); if (p) { p.textContent = "◎ OmniRoute —"; p.style.color = "var(--muted)"; } }
}

/* ── session buttons ──────────────────────────────────────────────────────── */
$("btn-start").addEventListener("click", async () => {
  try {
    await api("/api/session/start", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ note: "dashboard" }) });
    soundGreen(); toast("▶ Sessão PAPER iniciada"); refreshAll();
  } catch (e) { soundBlock(); toast("⛔ " + e.message, "red"); }
});
$("btn-pause").addEventListener("click", async () => {
  try { await api("/api/session/cooldown", { method: "POST" }); toast("⏸ Cooldown ativado"); refreshAll(); }
  catch (e) { soundBlock(); toast("⛔ " + e.message, "red"); }
});
$("btn-stop").addEventListener("click", async () => {
  try { await api("/api/session/stop", { method: "POST" }); soundBlock(); toast("⏹ Tudo parado (STOPPED)", "red"); refreshAll(); }
  catch (e) { soundBlock(); toast("⛔ " + e.message, "red"); }
});

/* ── event form ───────────────────────────────────────────────────────────── */
$("event-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const payload = {
    session_id: activeSessionId(),
    observed_at: new Date().toISOString(),
    outcome: $("ev-outcome").value.trim(),
    data_origin: $("ev-origin").value,
    metadata: {},
  };
  const pnl = parseFloat($("ev-pnl").value);
  if (!Number.isNaN(pnl) && $("ev-pnl").value !== "") payload.metadata.pnl = pnl;
  try {
    const r = await api("/api/events", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    soundGreen();
    toast(`🟢 Evento registrado: ${payload.outcome}`);
    $("ev-outcome").value = ""; $("ev-pnl").value = "";
    refreshAll();
  } catch (err) {
    soundBlock();
    toast("⛔ " + err.message, "red");
  }
});
function activeSessionId() {
  /* read from state each submit; fallback keeps a local one */
  return window.__sessionId || localStorage.getItem("fb_session") || "local-" + (localStorage.getItem("fb_local_seed") || (localStorage.setItem("fb_local_seed", Math.random().toString(36).slice(2, 10)), localStorage.getItem("fb_local_seed")));
}

/* keep session id in sync */
async function syncSession() {
  try {
    const s = await api("/api/state");
    if (s.session) {
      window.__sessionId = s.session.session_id;
      localStorage.setItem("fb_session", s.session.session_id);
    }
  } catch { /* offline */ }
}

/* ── copilot ──────────────────────────────────────────────────────────────── */
$("copilot-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const q = $("copilot-q").value.trim();
  const box = $("copilot-answer");
  box.innerHTML = "<p class='hint'>analisando…</p>";
  try {
    const a = await api("/api/copilot", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question: q }) });
    box.innerHTML = `
      <p>${escapeHtml(a.summary)}</p>
      ${a.observations.map(o => `<div class="obs">▸ ${escapeHtml(o)}</div>`).join("")}
      ${a.caveats.map(c => `<div class="caveat">⚠ ${escapeHtml(c)}</div>`).join("")}
      <div class="src">fontes: ${a.sources.map(s => `${escapeHtml(s.source)}${s.line ? ":" + s.line : ""}`).join(" · ")}</div>
      <div class="meta">ai=${a.meta && a.meta.ai ? a.meta.provider || "on" : "off"} · compressão=${a.meta && a.meta.compression ? a.meta.compression.ratio : "n/a"}</div>`;
  } catch (err) {
    box.innerHTML = `<p class="caveat">⛔ ${escapeHtml(err.message)}</p>`;
  }
});

/* ── Game Center (PAPER) ─────────────────────────────────────────────────── */
async function refreshGame() {
  try {
    const g = await api("/api/game/state");
    window.__game = g;
    const tb = $("top-balance");
    if (tb) tb.textContent = `R$ ${g.balance.toFixed(2).replace(".", ",")}`;
    $("g-balance").textContent = `R$ ${g.balance.toFixed(2).replace(".", ",")}`;
    const pnlEl = $("g-pnl");
    pnlEl.textContent = `R$ ${g.stats.pnl_total.toFixed(2).replace(".", ",")}`;
    pnlEl.style.color = g.stats.pnl_total < 0 ? "var(--red)" : g.stats.pnl_total > 0 ? "var(--green)" : "inherit";
    $("g-roi").textContent = `${g.stats.roi_pct}%`;
    $("g-open").textContent = g.open_bets.length;
    $("g-open-list").innerHTML = g.open_bets.map(b => {
      const pt = ptOutcome(b.bet_type);
      return `<div class="bet open">${pt.emoji} ${pt.name} <span class="mono">R$ ${b.stake.toFixed(2)}</span></div>`;
    }).join("") || "<p class='hint'>nenhuma</p>";
    $("g-settled-list").innerHTML = g.recent.filter(b => b.status !== "open").slice(0, 12).map(b => {
      const cls = b.status === "won" ? "won" : b.status === "push" ? "push" : "lost";
      const pt = ptOutcome(b.bet_type);
      return `<div class="bet ${cls}">${pt.emoji} ${pt.name} R$ ${b.stake.toFixed(2)}
        <span class="mono pnl">${b.pnl >= 0 ? "+" : ""}${b.pnl.toFixed(2)}</span></div>`;
    }).join("") || "<p class='hint'>nenhuma</p>";
  } catch (e) { console.warn("game:", e.message); }
}

$("bet-form").addEventListener("submit", async (e) => {  e.preventDefault();
  try {
    const r = await api("/api/game/bet", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ bet_type: $("bet-type").value, stake: parseFloat($("bet-stake").value) }) });
    beep(520, 0.08, "sine", 0, 0.1);
    soundConfirmed();
    toast(`📝 Aposta papel: ${r.bet.bet_type} R$ ${r.bet.stake.toFixed(2)}`);
    refreshGame();
  } catch (err) { soundBlock(); toast("⛔ " + err.message, "red"); }
});

document.querySelectorAll("#chip-row .chip").forEach((btn) => {
  btn.addEventListener("click", () => {
    $("bet-stake").value = btn.dataset.stake;
    document.querySelectorAll("#chip-row .chip").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
  });
});

$("sim-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  $("sim-out").textContent = "simulando…";
  try {
    const s = await api(`/api/game/simulate?shoes=${$("sim-shoes").value}`);
    $("sim-out").textContent =
      `sapatos: ${s.shoes} | apostas: ${s.bets}\nPnL simulado: R$ ${s.pnl} | por aposta: R$ ${s.pnl_per_bet}\n${s.note}`;
  } catch (err) { $("sim-out").textContent = "erro: " + err.message; }
});

/* ── WebSocket live channel ───────────────────────────────────────────────── */
let ws = null, wsBackoff = 1000;
function wsConnect() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  ws = new WebSocket(`${proto}://${location.host}/ws`);
  ws.onopen = () => {
    wsBackoff = 1000;
    $("ws-status").textContent = "ws: ao vivo";
    $("ws-status").classList.add("on");
    if ($("ws-status-inline")) $("ws-status-inline").textContent = "LIVE";
  };
  ws.onclose = () => {
    $("ws-status").textContent = "ws: reconectando…"; $("ws-status").classList.remove("on");
    if ($("ws-status-inline")) $("ws-status-inline").textContent = "RECONNECTING";
    setTimeout(wsConnect, wsBackoff); wsBackoff = Math.min(wsBackoff * 2, 15000);
  };
  ws.onmessage = (m) => {
    try {
      const msg = JSON.parse(m.data);
      if (msg.kind === "event") {
        const ev = msg.event;
        renderTimelineAppend(ev);
        updateHologram(ev);
        soundGreen();
        toast(`🟢 NOVO: ${ev.outcome}`);
        pulsePipeline();
        refreshGame();           // settlement may have happened
      } else if (msg.kind === "bet_settled") {
        const b = msg.bet;
        const ptB = ptOutcome(b.bet_type);
        if (b.pnl >= 0) { soundWin(); toast(`🟢 GREEN ${ptB.emoji} ${ptB.name}: R$ +${b.pnl.toFixed(2)}`); }
        else { soundBlock(); toast(`🔴 RED ${ptB.emoji} ${ptB.name}: R$ ${b.pnl.toFixed(2)}`, "red"); }
        refreshGame();
      }
    } catch { /* ignore malformed */ }
  };
}

/* append single event to timeline without full refetch */
function renderTimelineAppend(ev) {
  const tl = $("timeline");
  const div = document.createElement("div");
  div.className = "ev flash";
  const meta = safeParse(ev.metadata || "{}");
  const pnl = meta && typeof meta.pnl !== "undefined" ? ` · R$ ${Number(meta.pnl).toFixed(2)}` : "";
  const ptA = ptOutcome(ev.outcome);
  div.innerHTML = `<span class="outcome ${ptA.cls}">${ptA.emoji} ${ptA.name}</span>
    <span class="origin">${escapeHtml(ev.data_origin)}${pnl}</span>
    <span class="time">${escapeHtml((ev.observed_at || "").slice(11, 19))}</span>`;
  tl.insertBefore(div, tl.firstChild);
  const newest = Number(ev.id || 0);
  if (newest > lastEventId) lastEventId = newest;
}

/* ── risk panel (PAPER, educational) ──────────────────────────────────── */
async function refreshRisk() {
  try {
    const r = await api("/api/risk/summary?n=200");
    $("r-n").textContent = `${r.n} eventos`;
    $("r-ev").textContent = `R$ ${r.ev_home ? r.ev_home.ev : "—"}`;
    $("r-dd").textContent = `R$ ${r.drawdown ? r.drawdown.max_drawdown : "—"}`;
    const st = r.streaks && r.streaks.current;
    $("r-streak").textContent = st ? `${st.outcome} ×${st.run}` : "—";
    $("r-freq").textContent = Object.entries(r.freq || {}).map(([k, v]) => `${k} ${(v * 100).toFixed(1)}%`).join(" · ") || "—";
    $("r-chi").textContent = r.uniformity ? `χ²=${r.uniformity.chi2} ${r.uniformity.verdict}` : "—";
    $("r-ent").textContent = r.entropy_bits != null ? `${r.entropy_bits} bits` : "—";
    $("r-p4").textContent = r.p_4loss_in_200 != null ? `${(r.p_4loss_in_200 * 100).toFixed(1)}%` : "—";
    $("risk-warning").textContent = `${r.warning} · modo PAPER · origem ledger local · ${new Date().toLocaleTimeString("pt-BR", { hour12: false })}`;
    try {
      const mg = await api("/api/risk/progression?base=2.5&levels=3");
      $("r-mg").textContent = `exposição R$ ${mg.plan.total_exposure} · recuperar ${mg.plan.wins_to_recover_at_base} wins`;
    } catch { $("r-mg").textContent = "—"; }
    // sound cue on hot streak only (no auto action)
    if (st && st.run >= 10) { soundHotStreak(); toast(`⚠️ Sequência ${st.outcome} ×${st.run} — mesa quente, considere pausar`, "red"); }
  } catch (e) { const w = $("risk-warning"); if (w) w.textContent = "Risco indisponível: " + e.message; }
}
const _btnRisk = $("btn-risk-refresh");
if (_btnRisk) _btnRisk.addEventListener("click", refreshRisk);

/* ── sinal ao vivo · 1 clique PAPER ───────────────────────────────────── */
let lastSignalId = "";
let pendingSignal = null;
function renderOrbs(orbs) {
  const el = $("orbs");
  if (!el) return;
  el.innerHTML = (orbs || []).map((o) => {
    const cls = o === "home" ? "o-home" : o === "away" ? "o-away" : o === "draw" ? "o-draw" : "o-other";
    return `<i class="${cls}" title="${o}"></i>`;
  }).join("");
}
async function confirmSignal() {
  if (!pendingSignal) return;
  try {
    const r = await api("/api/game/bet", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ bet_type: pendingSignal.side, stake: pendingSignal.stake }) });
    const pt = ptOutcome(r.bet.bet_type);
    soundConfirmed();
    toast(`${pt.emoji} Entrada confirmada: ${pt.name} R$ ${r.bet.stake.toFixed(2)}`);
    hideSignalPopup();
    refreshGame();
  } catch (err) { soundBlock(); toast("⛔ " + err.message, "red"); }
}
function hideSignalPopup() {
  const p = $("signal-popup");
  if (p) p.hidden = true;
}
async function refreshSignal() {
  try {
    const s = await api("/api/signals/current");
    renderOrbs(s.orbs);
    const card = $("signal-card"), orb = $("signal-orb");
    if (s.signal) {
      const pt = ptOutcome(s.side);
      const stakeTxt = `R$ ${s.stake.toFixed(2)}`;
      const lad = s.ladder ? ` · nível ${s.ladder.level}/5` : "";
      card.dataset.active = "true";
      orb.textContent = pt.emoji || "●";
      orb.className = "signal-orb side-" + s.side;
      $("signal-title").textContent = `${pt.name} ${stakeTxt}`;
      $("signal-sub").textContent = `${s.run}× ${ptOutcome(s.base_outcome).name} seguidos · ${s.n_decisive} decisivos${lad} · PAPER`;
      const cb = $("btn-signal-confirm");
      cb.hidden = false;
      cb.textContent = `✓ ${stakeTxt}`;
      $("btn-signal-dismiss").hidden = false;
      pendingSignal = s;
      if (s.signal_id !== lastSignalId) {
        lastSignalId = s.signal_id;
        const pt = ptOutcome(s.side);
        notify("warn", `Sinal ${s.rule}: ${s.run}× ${ptOutcome(s.base_outcome).name} → ${pt.name} R$ ${s.stake.toFixed(2)}`, s.signal_id);
        const po = $("popup-orb");
        po.textContent = pt.emoji || "●";
        po.className = "signal-orb big side-" + s.side;
        $("popup-text").textContent = `${s.run}× ${ptOutcome(s.base_outcome).name} → ${pt.name} R$ ${s.stake.toFixed(2)}?`;
        $("btn-popup-confirm").textContent = `✓ R$ ${s.stake.toFixed(2)}`;
        $("signal-popup").hidden = false;
        soundEntryAlert();
        if (navigator.vibrate) { try { navigator.vibrate([120, 60, 120]); } catch { /* sem vibração */ } }
      }
    } else {
      card.dataset.active = "false";
      orb.textContent = "–";
      orb.className = "signal-orb";
      $("signal-title").textContent = "Sem sinal";
      const base = s.base_outcome ? ptOutcome(s.base_outcome) : null;
      $("signal-sub").textContent = base ? `Sequência atual: ${base.name} ×${s.run} (precisa 4×)…` : "Aguardando 4× seguidos…";
      $("btn-signal-confirm").hidden = true;
      $("btn-signal-dismiss").hidden = true;
      pendingSignal = null;
      hideSignalPopup();
    }
  } catch (e) { /* sem sinal se offline */ }
}
const _btnSigC = $("btn-signal-confirm"), _btnSigD = $("btn-signal-dismiss");
if (_btnSigC) _btnSigC.addEventListener("click", confirmSignal);
if (_btnSigD) _btnSigD.addEventListener("click", () => { lastSignalId = pendingSignal ? pendingSignal.signal_id : lastSignalId; pendingSignal = null; hideSignalPopup(); const c = $("signal-card"); if (c) c.dataset.active = "false"; });
const _btnPopC = $("btn-popup-confirm"), _btnPopD = $("btn-popup-dismiss");
if (_btnPopC) _btnPopC.addEventListener("click", confirmSignal);
if (_btnPopD) _btnPopD.addEventListener("click", () => { lastSignalId = pendingSignal ? pendingSignal.signal_id : lastSignalId; pendingSignal = null; hideSignalPopup(); });

/* ── holograma scan + contagem de cartas ──────────────────────────────── */
function updateHologram(ev) {
  if (!ev) return;
  let meta = {};
  try { meta = JSON.parse(ev.metadata || "{}"); } catch { meta = {}; }
  const h = (meta.home_card || "–").toUpperCase(), a = (meta.away_card || "–").toUpperCase();
  $("holo-home").textContent = h;
  $("holo-away").textContent = a;
  const pt = ptOutcome(ev.outcome);
  const out = $("holo-out");
  out.textContent = `${pt.emoji} ${pt.name}`;
  out.className = "holo-out o-" + (["home", "away", "draw"].includes(ev.outcome) ? ev.outcome : "");
  const hg = $("hologram");
  hg.classList.remove("pulse");
  void hg.offsetWidth;
  hg.classList.add("pulse");
}
async function refreshCards() {
  try {
    const c = await api("/api/cards/summary?n=200");
    $("cards-count").textContent = `${c.rounds_with_cards}/${c.rounds} giros com carta`;
    const order = Object.entries(c.counts).sort((x, y) => y[1] - x[1]);
    const mx = Math.max(1, ...order.map((x) => x[1]));
    $("cards-dist").innerHTML = order.map(([k, v]) =>
      `<div class="hot-row"><span>🂡 ${escapeHtml(k)}</span><div class="hbar"><i style="width:${(v / mx) * 100}%;background:#7dd3fc"></i></div><b>${v}</b></div>`
    ).join("") || "<span class='dim'>Sem cartas capturadas ainda —</span>";
    if (c.note) $("cards-note").textContent = c.note;
  } catch { /* sem cartas se offline */ }
}

/* ── app shell · abas + painéis visuais ───────────────────────────────── */
document.querySelectorAll("[data-tab]").forEach((b) =>
  b.addEventListener("click", () => {
    const v = b.dataset.tab;
    document.querySelectorAll(".view").forEach((s) => s.classList.toggle("active", s.dataset.view === v));
    document.querySelectorAll("[data-tab]").forEach((x) => x.classList.toggle("active", x.dataset.tab === v));
  })
);
/* registro rápido 1 toque */
document.querySelectorAll("[data-quick]").forEach((b) =>
  b.addEventListener("click", async () => {
    try {
      const sid = window.__sessionId || localStorage.getItem("fb_session");
      if (!sid) { toast("▶ Inicie a sessão primeiro", "red"); return; }
      await api("/api/events", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sid, observed_at: new Date().toISOString(), outcome: b.dataset.quick, data_origin: "manual", metadata: {} }) });
      const pt = ptOutcome(b.dataset.quick);
      soundGreen(); toast(`${pt.emoji} ${pt.name} registrado`);
      refreshAll();
    } catch (e) { soundBlock(); toast("⛔ " + e.message, "red"); }
  })
);
/* board visual: grade + gauges + histórico + quentes */
function dialPct(id, val, color) {
  const el = $(id);
  if (!el) return;
  el.style.setProperty("--p", (val * 100).toFixed(1) + "%");
  el.style.setProperty("--gc", color);
}
async function refreshBoard() {
  try {
    const data = await api("/api/events?n=100");
    const evs = data.events || [];
    const outs = evs.map((e) => e.outcome).filter((o) => ["home", "away", "draw"].includes(o));
    const n = outs.length;
    $("res-count").textContent = n;
    /* grade */
    const grid = $("results-grid");
    grid.innerHTML = outs.slice(-100).map((o) => `<i class="g-${o}" title="${o}"></i>`).join("");
    /* % */
    const c = { home: 0, away: 0, draw: 0 };
    outs.forEach((o) => c[o]++);
    const pc = (k) => (n ? c[k] / n : 0);
    $("pct-home").textContent = (pc("home") * 100).toFixed(1) + "%";
    $("pct-away").textContent = (pc("away") * 100).toFixed(1) + "%";
    $("pct-draw").textContent = (pc("draw") * 100).toFixed(1) + "%";
    $("pb-home").style.width = pc("home") * 100 + "%";
    $("pb-away").style.width = pc("away") * 100 + "%";
    $("pb-draw").style.width = pc("draw") * 100 + "%";
    dialPct("gg-home", pc("home"), "#f5c518"); $("gg-home-v").textContent = (pc("home") * 100).toFixed(0) + "%";
    dialPct("gg-away", pc("away"), "#4da3ff"); $("gg-away-v").textContent = (pc("away") * 100).toFixed(0) + "%";
    dialPct("gg-draw", pc("draw"), "#35d07f"); $("gg-draw-v").textContent = (pc("draw") * 100).toFixed(0) + "%";
    /* último */
    if (evs.length) {
      const last = evs[evs.length - 1], pt = ptOutcome(last.outcome);
      updateHologram(last);
      const lo = $("last-orb");
      lo.textContent = pt.emoji || "●";
      lo.className = "signal-orb side-" + (["home", "away", "draw"].includes(last.outcome) ? last.outcome : "");
      $("last-name").textContent = `${pt.emoji} ${pt.name}`;
      $("last-time").textContent = (last.observed_at || "").slice(11, 19) + " · " + last.data_origin;
    }
    /* sequência + tendência */
    let run = 0, cur = outs.length ? outs[outs.length - 1] : null;
    for (let i = outs.length - 1; i >= 0 && outs[i] === cur; i--) run++;
    const ptc = cur ? ptOutcome(cur) : null;
    $("st-streak").textContent = cur ? `${ptc.name} ×${run}` : "—";
    const tend = $("tend-panel");
    if (cur && run >= 4 && cur !== "draw") {
      const opp = ptOutcome(cur === "home" ? "away" : "home");
      $("tend-state").textContent = "CONFIRMADA";
      $("tend-title").textContent = `${ptc.emoji} ${run}× ${ptc.name} → ${opp.emoji} ${opp.name} R$ 0,50`;
      $("tend-sub").textContent = "Toque ✓ no sinal para registrar paper.";
      tend.dataset.hot = "true";
    } else {
      $("tend-state").textContent = cur ? "OBSERVANDO" : "—";
      $("tend-title").textContent = cur ? `${ptc.emoji} ${ptc.name} ×${run}` : "Aguardando mesa…";
      $("tend-sub").textContent = "4× seguidos disparam sinal.";
    }
    /* análise histórica mini (últimos 8, gatilho + alvo) */
    const hm = $("history-mini");
    hm.innerHTML = evs.slice(-8).reverse().map((e) => {
      const pt = ptOutcome(e.outcome);
      const alvo = e.outcome === "home" ? "🔵" : e.outcome === "away" ? "🟡" : "–";
      return `<div class="hist-row"><span class="dot d-${e.outcome}">${pt.emoji}</span><span>${pt.name}</span><span class="dim">→ alvo ${alvo}</span></div>`;
    }).join("") || "<span class='dim'>—</span>";
    $("hist-count").textContent = Math.min(8, evs.length);
    /* quentes */
    const order = ["home", "away", "draw"].sort((a, b) => c[b] - c[a]);
    const mx = Math.max(1, ...order.map((k) => c[k]));
    $("hot-sides").innerHTML = order.map((k) => {
      const pt = ptOutcome(k), col = k === "home" ? "#f5c518" : k === "away" ? "#4da3ff" : "#35d07f";
      return `<div class="hot-row"><span>${pt.emoji} ${pt.name}</span><div class="hbar"><i style="width:${(c[k] / mx) * 100}%;background:${col}"></i></div><b>${c[k]}</b></div>`;
    }).join("");
    /* jogar chips (espelha sinal) */
    const pc2 = $("play-chips");
    if (pendingSignal) {
      const pt = ptOutcome(pendingSignal.side);
      pc2.innerHTML = `<button class="play-chip" id="play-chip-btn" style="border-color:${pendingSignal.side === "home" ? "#f5c518" : pendingSignal.side === "away" ? "#4da3ff" : "#35d07f"}">${pt.emoji} ${pt.name} R$ ${pendingSignal.stake.toFixed(2)}</button>`;
      $("play-chip-btn").addEventListener("click", confirmSignal);
    } else pc2.innerHTML = "<span class='dim'>Sem sinal —</span>";
    /* sinais mini (paper recentes) */
    const g = window.__game;
    if (g && g.recent) {
      $("signals-mini").innerHTML = g.recent.slice(0, 6).map((b) => {
        const pt = ptOutcome(b.bet_type);
        const tag = b.status === "open" ? "open" : b.status === "won" ? "win" : "loss";
        const lbl = b.status === "open" ? "ABERTA" : b.status === "won" ? "GREEN" : b.status === "push" ? "PUSH" : "LOSS";
        return `<div class="sig-row"><span class="tag ${tag}">${lbl}</span><span>${pt.emoji} ${pt.name} R$ ${b.stake.toFixed(2)}</span></div>`;
      }).join("") || "<span class='dim'>—</span>";
    }
  } catch (e) { /* board espera backend */ }
}

/* ── BRAIN · agentes reais + notificações + paleta ─────────────────────── */
const AG_META = {
  observador: "👁", analista: "🔍", matematico: "∑", executor: "🤖",
  memoria: "🧠", seguranca: "🛡", coordenador: "🎼",
};
const AG_POS = { observador: [60, 60], analista: [170, 40], matematico: [280, 60], memoria: [60, 180], seguranca: [170, 200], executor: [280, 180], coordenador: [170, 120] };
const AG_LINKS = [["observador", "coordenador"], ["analista", "coordenador"], ["matematico", "analista"], ["memoria", "analista"], ["executor", "coordenador"], ["seguranca", "executor"], ["seguranca", "coordenador"]];
let AGENTS = [], muted = localStorage.getItem("blitz.muted") === "1";
const NOTIFS = [];
function fmtConf(c) {
  if (c == null) return "n/d";
  if (typeof c === "object" && "low" in c) return `${(c.low * 100).toFixed(0)}–${(c.high * 100).toFixed(0)}% (n=${c.n})`;
  if (typeof c === "object" && "n" in c) return `n=${c.n} · ${c.nota || ""}`;
  return String(c);
}
function notify(kind, text, key) {
  const k = key || kind + ":" + text;
  if (NOTIFS.some((n) => n.key === k)) return; // dedup
  NOTIFS.unshift({ kind, text, key: k, at: new Date() });
  if (NOTIFS.length > 20) NOTIFS.pop();
  renderNotifs();
  if (!muted && (kind === "err" || kind === "block" || kind === "warn")) soundBlock();
}
function renderNotifs() {
  const el = $("notif-center");
  if (!el) return;
  $("notif-count").textContent = NOTIFS.length;
  el.innerHTML = NOTIFS.map((n) =>
    `<div class="notif ${n.kind}">${escapeHtml(n.text)}<time>${n.at.toLocaleTimeString("pt-BR", { hour12: false })}</time></div>`
  ).join("") || "<span class='dim'>Nenhuma notificação —</span>";
}
function setRadar(id, cls) {
  const el = $(id);
  if (el) el.className = "rdot " + cls;
}
async function refreshAgents() {
  const loading = $("agents-loading"), errBox = $("agents-error");
  try {
    const r = await api("/api/agents/status");
    if (loading) loading.hidden = true;
    if (errBox) errBox.hidden = true;
    AGENTS = r.agents;
    $("agents-count").textContent = AGENTS.length + " agentes · " + r.coleta_ms + "ms";
    $("brain-mode").textContent = r.mode;
    $("brain-ms").textContent = "coleta " + r.coleta_ms + "ms";
    /* radar */
    const st = await api("/api/state").catch(() => null);
    setRadar("hr-api", "ok");
    const wsOn = ($("ws-status") || {}).textContent || "";
    setRadar("hr-ws", wsOn.includes("vivo") ? "ok" : "warn");
    try {
      const h = await api("/api/health");
      setRadar("hr-ledger", h.status === "ok" ? "ok" : "bad");
    } catch { setRadar("hr-ledger", "bad"); }
    try {
      const rk = await api("/api/risk/summary?n=50");
      setRadar("hr-risk", rk.n >= 60 ? "ok" : "warn");
    } catch { setRadar("hr-risk", "bad"); }
    /* grafo */
    const svg = $("agent-graph");
    const byId = Object.fromEntries(AGENTS.map((a) => [a.id, a]));
    svg.innerHTML =
      AG_LINKS.map(([a, b]) => {
        const A = AG_POS[a], B = AG_POS[b];
        if (!A || !B) return "";
        const hot = byId[a] && (byId[a].estado === "bloqueado" || byId[a].estado === "alerta");
        return `<line class="edge${hot ? " hot" : ""}" x1="${A[0]}" y1="${A[1]}" x2="${B[0]}" y2="${B[1]}"/>`;
      }).join("") +
      AGENTS.map((a) => {
        const P = AG_POS[a.id] || [170, 120];
        return `<g class="node st-${a.estado}" data-agent="${a.id}" tabindex="0" role="button" aria-label="${a.nome}, ${a.estado}"><circle cx="${P[0]}" cy="${P[1]}" r="20"/><text x="${P[0]}" y="${P[1] + 3}">${AG_META[a.id] || "●"}</text><text x="${P[0]}" y="${P[1] + 32}">${a.nome}</text></g>`;
      }).join("");
    svg.querySelectorAll(".node").forEach((n) => {
      const open = () => openAgent(n.dataset.agent);
      n.addEventListener("click", open);
      n.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); open(); } });
    });
    /* cards */
    $("agents-grid").innerHTML = AGENTS.map((a) =>
      `<button class="agent-card" data-agent="${a.id}" aria-label="${a.nome}, ${a.funcao}, ${a.estado}">
        <span class="av">${AG_META[a.id] || "●"}</span><b>${escapeHtml(a.nome)}</b>
        <small>${escapeHtml(a.funcao)} · ${escapeHtml((a.tarefa || "").slice(0, 42))}</small>
        <span class="st st-${a.estado}">${a.estado.toUpperCase()}</span>
      </button>`
    ).join("") || "<span class='dim'>Nenhum agente —</span>";
    document.querySelectorAll(".agent-card").forEach((c) =>
      c.addEventListener("click", () => openAgent(c.dataset.agent)));
  } catch (e) {
    if (loading) loading.hidden = true;
    if (errBox) { errBox.hidden = false; errBox.textContent = "Falha ao carregar agentes: " + e.message; }
    notify("err", "Brain: " + e.message, "brain-err");
  }
}
function openAgent(id) {
  const a = AGENTS.find((x) => x.id === id);
  if (!a) return;
  $("agent-detail").hidden = false;
  $("ad-name").textContent = `${AG_META[a.id] || ""} ${a.nome} · ${a.funcao}`;
  $("ad-role").textContent = a.personalidade;
  $("ad-state").textContent = a.estado.toUpperCase();
  $("ad-task").textContent = a.tarefa || "—";
  $("ad-conf").textContent = fmtConf(a.confianca);
  $("ad-queue").textContent = a.fila != null ? a.fila : "n/d";
  const la = a.ultima_acao ? JSON.stringify(a.ultima_acao).slice(0, 140) : "sem ação registrada";
  $("ad-detail").textContent = `${a.detalhe} · última: ${la} · tokens: n/d · latência modelo: n/d`;
  $("agent-detail").scrollIntoView({ behavior: "smooth", block: "nearest" });
}
/* por quê? / evidência / matemática */
async function explainWhy() {
  const box = $("why-box");
  box.innerHTML = "<span class='dim'>Analisando…</span>";
  try {
    const [sig, rk, st] = await Promise.all([
      api("/api/signals/current").catch(() => null),
      api("/api/risk/summary?n=200").catch(() => null),
      api("/api/state").catch(() => null),
    ]);
    const L = [];
    L.push(`<div><span class="fact">FATO</span> · modo ${(st && st.mode) || "PAPER"}, sessão ${(st && st.state) || "?"}, eventos ${(st && st.check.usage.events_today) ?? "?"}.</div>`);
    if (sig && sig.signal) {
      L.push(`<div><span class="inf">INFERÊNCIA</span> · regra ${sig.rule}: ${sig.run}× ${ptOutcome(sig.base_outcome).name} → ${ptOutcome(sig.side).name} R$ ${sig.stake} (n=${sig.n_decisive}).</div>`);
      L.push(`<div><span class="hyp">HIPÓTESE</span> · contra-tendência de curto prazo; sem edge comprovado.</div>`);
    } else {
      L.push(`<div><span class="fact">FATO</span> · sem sequência de 4× (atual: ${sig && sig.base_outcome ? ptOutcome(sig.base_outcome).name + " ×" + sig.run : "—"}).</div>`);
      L.push(`<div><span class="unk">DESCONHECIDO</span> · próximo resultado; roleta de cartas é independente por giro.</div>`);
    }
    if (rk) L.push(`<div><span class="inf">INFERÊNCIA</span> · EV home ${rk.ev_home.ev}, χ² ${rk.uniformity.chi2} (${rk.uniformity.verdict}), n=${rk.n}.</div>`);
    if (st && !st.check.allowed) L.push(`<div><span class="block">BLOQUEIO</span> · ${st.check.reasons.join(" · ")}</div>`);
    box.innerHTML = L.join("");
    notify("info", "Explicação gerada a partir de dados reais.", "why-ok");
  } catch (e) { box.innerHTML = `<span class="alert">Falha: ${escapeHtml(e.message)}</span>`; }
}
/* paleta de comandos */
const COMMANDS = [
  { n: "Ir: Sinal", run: () => goTab("sinal") }, { n: "Ir: Mesa", run: () => goTab("mesa") },
  { n: "Ir: Papel", run: () => goTab("papel") }, { n: "Ir: Risco", run: () => goTab("risco") },
  { n: "Ir: Brain", run: () => goTab("brain") }, { n: "Ir: Mais", run: () => goTab("mais") },
  { n: "Sessão: iniciar", run: () => $("btn-start").click() }, { n: "Sessão: pausar", run: () => $("btn-pause").click() },
  { n: "Registrar: mandante", run: () => quickOutcome("home") }, { n: "Registrar: visitante", run: () => quickOutcome("away") },
  { n: "Registrar: empate", run: () => quickOutcome("draw") },
  { n: "Sinal: confirmar R$ 0,50", run: () => confirmSignal() },
  { n: "Risco: atualizar", run: () => refreshRisk() }, { n: "Tour guiado", run: () => startTour() },
];
function goTab(v) {
  document.querySelector(`[data-tab="${v}"]`)?.click();
}
function quickOutcome(o) {
  document.querySelector(`[data-quick="${o}"]`)?.click();
}
function openPalette() {
  $("palette").hidden = false;
  $("palette-input").value = "";
  renderPalette("");
  setTimeout(() => $("palette-input").focus(), 30);
}
function renderPalette(q) {
  const list = COMMANDS.filter((c) => c.n.toLowerCase().includes(q.toLowerCase()));
  $("palette-list").innerHTML = list.map((c, i) => `<button data-cmd="${c.n}" class="${i === 0 ? "sel" : ""}">${escapeHtml(c.n)}</button>`).join("") || "<span class='dim'>Nada —</span>";
  $("palette-list").querySelectorAll("button").forEach((b) =>
    b.addEventListener("click", () => { $("palette").hidden = true; COMMANDS.find((c) => c.n === b.dataset.cmd)?.run(); }));
}
let palSel = 0;
/* tour */
const TOUR = [
  ["Sinal", "Aqui nasce o sinal 4× → oposto R$ 0,50. Um clique confirma paper. Nada é automático."],
  ["Mesa", "O jogo ao vivo e a grade dos últimos 100 resultados, com % e lados quentes."],
  ["Brain", "Os 7 agentes com estado real, grafo, porquê e notificações. Tokens: n/d até haver LLM."],
];
let tourI = 0;
function startTour() {
  tourI = 0;
  $("tour").hidden = false;
  showTour();
}
function showTour() {
  const tabs = ["sinal", "mesa", "brain"];
  goTab(tabs[tourI]);
  $("tour-title").textContent = `Tour ${tourI + 1}/3 · ${TOUR[tourI][0]}`;
  $("tour-text").textContent = TOUR[tourI][1];
}
/* modo simples/especialista */
function applyMode() {
  const m = localStorage.getItem("blitz.mode") || "expert";
  document.body.dataset.mode = m;
  $("btn-mode").textContent = m === "simple" ? "◐ SIMPLES" : "◑ ESPECIALISTA";
}
/* atalhos */
document.addEventListener("keydown", (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); openPalette(); return; }
  if (!$("palette").hidden) {
    if (e.key === "Escape") $("palette").hidden = true;
    if (e.key === "Enter") { $("palette-list").querySelector("button.sel")?.click(); }
    return;
  }
  if (!$("tour").hidden) {
    if (e.key === "Escape") $("tour").hidden = true;
    if (e.key === "ArrowRight") { tourI = Math.min(2, tourI + 1); showTour(); }
    if (e.key === "ArrowLeft") { tourI = Math.max(0, tourI - 1); showTour(); }
    return;
  }
  if (e.target.matches("input, select, textarea")) return;
  const tabs = ["sinal", "mesa", "papel", "risco", "brain", "mais"];
  if (e.key >= "1" && e.key <= "6") goTab(tabs[+e.key - 1]);
});

/* ── boot + polling ───────────────────────────────────────────────────────── */
function refreshAll() { refreshState(); refreshEvents(); refreshStats(); syncSession(); refreshGame(); refreshRisk(); refreshSignal(); refreshBoard(); refreshCards(); }
function updateClock() {
  const now = new Date();
  if ($("hero-sync")) $("hero-sync").textContent = now.toLocaleTimeString("pt-BR", { hour12: false });
}

function initNeuralField() {
  const canvas = $("neural-canvas");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const nodes = [];
  let width = 0;
  let height = 0;
  let frame = 0;
  let resizeObserver;

  function resize() {
    const rect = canvas.getBoundingClientRect();
    const ratio = window.devicePixelRatio || 1;
    width = rect.width;
    height = rect.height;
    canvas.width = width * ratio;
    canvas.height = height * ratio;
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    nodes.length = 0;
    for (let i = 0; i < 26; i++) {
      nodes.push({
        x: width * (0.08 + Math.random() * 0.84),
        y: height * (0.08 + Math.random() * 0.84),
        vx: (Math.random() - 0.5) * 0.12,
        vy: (Math.random() - 0.5) * 0.12,
        r: Math.random() > 0.82 ? 2.4 : 1.3,
      });
    }
  }

  function draw() {
    ctx.clearRect(0, 0, width, height);
    const cx = width / 2;
    const cy = height / 2;
    nodes.forEach((node) => {
      node.x += node.vx;
      node.y += node.vy;
      if (node.x < 0 || node.x > width) node.vx *= -1;
      if (node.y < 0 || node.y > height) node.vy *= -1;
      const distance = Math.hypot(node.x - cx, node.y - cy);
      ctx.fillStyle = distance < 150 ? "rgba(96,211,255,.65)" : "rgba(140,114,255,.45)";
      ctx.beginPath();
      ctx.arc(node.x, node.y, node.r, 0, Math.PI * 2);
      ctx.fill();
    });
    nodes.forEach((a, index) => {
      nodes.slice(index + 1).forEach((b) => {
        const distance = Math.hypot(a.x - b.x, a.y - b.y);
        if (distance > 105) return;
        ctx.strokeStyle = `rgba(96,211,255,${Math.max(0, 0.16 - distance / 900)})`;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
        ctx.stroke();
      });
    });
    frame = requestAnimationFrame(draw);
  }

  resizeObserver = new ResizeObserver(resize);
  resizeObserver.observe(canvas);
  resize();
  draw();
  window.addEventListener("beforeunload", () => {
    cancelAnimationFrame(frame);
    resizeObserver.disconnect();
  }, { once: true });
}

function initStrategyLab() {
  const run = $("strategy-run");
  const color = $("strategy-color");
  const save = $("save-strategy");
  if (!run || !color || !save) return;
  const observation = $("strategy-window");
  const status = $("strategy-status");
  const valid = (v) => ['home', 'away', 'draw'].includes(v.outcome) && Number.isInteger(v.run) && v.run >= 1 && v.run <= 20 && Number.isInteger(v.window) && v.window >= 1 && v.window <= 10;
  try {
    const stored = JSON.parse(localStorage.getItem("blitz.hypothesis.v1") || "null");
    if (stored && valid(stored)) {
      color.value = stored.outcome; run.value = stored.run; observation.value = stored.window;
      status.textContent = "Hipótese recuperada deste navegador. Sem execução automática.";
    }
  } catch { status.textContent = "Armazenamento local indisponível ou rascunho inválido."; }
  save.addEventListener("click", () => {
    const value = { outcome: color.value, run: Number(run.value), window: Number(observation.value) };
    if (!valid(value)) { status.textContent = "Informe 1–20 repetições e 1–10 rodadas inteiras."; return; }
    try {
      localStorage.setItem("blitz.hypothesis.v1", JSON.stringify(value));
      const ptS = ptOutcome(value.outcome);
      status.textContent = `Salva neste navegador: ${ptS.name} ×${value.run}, observar ${value.window} rodadas. Sem execução automática.`;
      toast("Hipótese salva neste navegador");
    } catch { status.textContent = "Não foi possível salvar no navegador. Verifique as permissões de armazenamento."; }
  });
  document.querySelectorAll(".nav-item").forEach((item) => {
    item.addEventListener("click", () => {
      document.querySelectorAll(".nav-item").forEach((nav) => nav.classList.remove("active"));
      item.classList.add("active");
    });
  });
  document.querySelectorAll("[data-scroll]").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelector(button.dataset.scroll)?.scrollIntoView({ behavior: "smooth" });
    });
  });
}

/* ── pipeline pulse (flowchart lights up on new events) ─────────────────── */
function pulsePipeline() {
  document.querySelectorAll(".flow-step").forEach((el, i) => {
    setTimeout(() => {
      el.classList.add("active");
      setTimeout(() => el.classList.remove("active"), 900);
    }, i * 140);
  });
}

/* ── agent mesh · semantic graph of the real system ─────────────────────── */
function initAgentMesh() {
  const canvas = $("agent-canvas");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const COLORS = {
    violet: "128,82,255", amber: "255,184,41", teal: "21,132,110", dim: "90,90,90",
  };
  const LAYOUT = [
    { id: "observer", label: "OBSERVER", color: "violet", fx: .06, fy: .50 },
    { id: "ledger",   label: "LEDGER",   color: "violet", fx: .22, fy: .30 },
    { id: "policy",   label: "POLICY",   color: "violet", fx: .22, fy: .74 },
    { id: "rag",      label: "RAG · COMPRESSÃO", color: "violet", fx: .42, fy: .50 },
    { id: "router",   label: "ROUTER",  color: "violet", fx: .62, fy: .50 },
    { id: "omni",     label: "OMNIROUTE", color: "violet", fx: .82, fy: .14 },
    { id: "tr",       label: "TOKENROUTER", color: "amber", fx: .84, fy: .34 },
    { id: "nv",       label: "NVIDIA NIM", color: "amber", fx: .86, fy: .54 },
    { id: "aisa",     label: "AISA", color: "teal", fx: .82, fy: .74 },
    { id: "9r",       label: "9ROUTE (slot)", color: "dim", fx: .78, fy: .92 },
  ];
  const LINKS = [
    ["observer", "ledger"], ["observer", "policy"], ["ledger", "rag"],
    ["policy", "rag"], ["rag", "router"], ["router", "omni"],
    ["router", "tr"], ["router", "nv"], ["router", "aisa"], ["router", "9r"],
  ];
  let nodes = [];
  let sparks = [];
  let width = 0, height = 0, frame = 0, t0 = performance.now();
  let resizeObserver;

  function layout() {
    nodes = LAYOUT.map(n => ({ ...n, x: n.fx * width, y: n.fy * height, phase: Math.random() * Math.PI * 2 }));
    sparks = LINKS.map((_, i) => ({ link: i, t: Math.random(), speed: .0025 + Math.random() * .003 }));
  }
  function byId(id) { return nodes.find(n => n.id === id); }

  function resize() {
    const rect = canvas.getBoundingClientRect();
    const ratio = window.devicePixelRatio || 1;
    width = rect.width; height = rect.height;
    canvas.width = width * ratio; canvas.height = height * ratio;
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    layout();
  }

  function draw(now) {
    const time = (now - t0) / 1000;
    const speed = (window.__uiTuning && window.__uiTuning.meshSpeed) || 1;
    const glow = !window.__uiTuning || window.__uiTuning.glow !== false;
    ctx.clearRect(0, 0, width, height);

    /* links */
    for (const [a, b] of LINKS) {
      const na = byId(a), nb = byId(b);
      if (!na || !nb) continue;
      ctx.strokeStyle = `rgba(${COLORS[na.color]},.16)`;
      ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(na.x, na.y); ctx.lineTo(nb.x, nb.y); ctx.stroke();
    }
    /* traveling sparks */
    for (const s of sparks) {
      s.t += s.speed * speed;
      if (s.t > 1) s.t = 0;
      const [a, b] = LINKS[s.link];
      const na = byId(a), nb = byId(b);
      if (!na || !nb) continue;
      const x = na.x + (nb.x - na.x) * s.t;
      const y = na.y + (nb.y - na.y) * s.t;
      ctx.fillStyle = `rgba(${COLORS[na.color]},.8)`;
      ctx.beginPath(); ctx.arc(x, y, 1.6, 0, Math.PI * 2); ctx.fill();
    }
    /* nodes */
    for (const n of nodes) {
      const pulse = 1 + Math.sin(time * 1.4 * speed + n.phase) * .18;
      const rgb = COLORS[n.color];
      if (glow) {
        const grad = ctx.createRadialGradient(n.x, n.y, 0, n.x, n.y, 22 * pulse);
        grad.addColorStop(0, `rgba(${rgb},.30)`);
        grad.addColorStop(1, `rgba(${rgb},0)`);
        ctx.fillStyle = grad;
        ctx.beginPath(); ctx.arc(n.x, n.y, 22 * pulse, 0, Math.PI * 2); ctx.fill();
      }
      ctx.fillStyle = `rgba(${rgb},${n.color === "dim" ? .5 : .95})`;
      ctx.beginPath(); ctx.arc(n.x, n.y, 4.5, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = `rgba(255,255,255,.82)`;
      ctx.font = "500 9px 'JetBrains Mono', monospace";
      ctx.textAlign = n.fx > .7 ? "right" : "left";
      const dx = n.fx > .7 ? -10 : 10;
      ctx.fillText(n.label, n.x + dx, n.y + 3);
    }
    frame = requestAnimationFrame(draw);
  }

  resizeObserver = new ResizeObserver(resize);
  resizeObserver.observe(canvas);
  resize();
  frame = requestAnimationFrame(draw);
  window.addEventListener("beforeunload", () => {
    cancelAnimationFrame(frame);
    resizeObserver.disconnect();
  }, { once: true });
}

/* ── DialKit · live tuning panel (vanilla adapter) ───────────────────────── */
function initDialKit() {
  if (!window.DialKit) return;
  try {
    const root = DialKit.createDialRoot();
    const kit = DialKit.createDialKit("Blitz UI", {
      accent: "#8052ff",
      meshSpeed: [1, 0.2, 3, 0.1],
      glow: true,
    }, { persist: true, defaultCollapsed: true });
    kit.subscribe((v) => {
      document.documentElement.style.setProperty("--iris", v.accent);
      window.__uiTuning = v;
    });
  } catch (e) { console.warn("dialkit:", e); }
}

function initBlitzViewer() {
  const frame = $("blitz-frame");
  const placeholder = $("viewer-placeholder");
  const status = $("viewer-status");
  const close = $("viewer-close");
  if (!frame) return;
  $("viewer-load").addEventListener("click", () => {
    frame.src = "https://www.zonadejogo.bet.br/play/pragmatic/football-blitz";
    frame.hidden = false;
    placeholder.hidden = true;
    close.hidden = false;
    status.textContent = "Página externa solicitada. Se não aparecer, abra na Zona de Jogo.";
  });
  close.addEventListener("click", () => {
    frame.removeAttribute("src");
    frame.hidden = true;
    placeholder.hidden = false;
    close.hidden = true;
    status.textContent = "Visualização externa pausada.";
  });
  $("viewer-expand").addEventListener("click", (event) => {
    const expanded = document.body.classList.toggle("viewer-wide");
    event.currentTarget.setAttribute("aria-pressed", String(expanded));
    event.currentTarget.textContent = expanded ? "Reduzir mesa" : "Ampliar mesa";
  });
}

function initSemanticBackground() {
  const canvas = $("semantic-background");
  const ctx = canvas?.getContext("2d");
  if (!ctx) return;
  const reduced = matchMedia("(prefers-reduced-motion: reduce)");
  let width = 0, height = 0, timer = null, previous = 0, time = 0, activity = 0;
  let nodes = [];
  const palette = ["255,90,31", "255,65,110", "62,220,255", "108,255,157", "163,112,255"];
  function resize() {
    width = innerWidth; height = innerHeight;
    const ratio = Math.min(devicePixelRatio || 1, 1.5);
    canvas.width = Math.round(width * ratio); canvas.height = Math.round(height * ratio);
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    const count = Math.min(66, Math.max(22, Math.floor(width * height / 23000)));
    nodes = Array.from({ length: count }, (_, i) => ({
      x: Math.random() * width, y: Math.random() * height,
      vx: (Math.random() - .5) * 8, vy: (Math.random() - .5) * 8,
      phase: Math.random() * Math.PI * 2, color: i % palette.length,
      birth: i < count * .55 ? 0 : .1 + Math.random() * .8,
    }));
    render();
  }
  function render() {
    ctx.clearRect(0, 0, width, height);
    const range = Math.min(210, width * .38);
    const rgb = (node) => activity > .15 ? palette[node.color] : palette[0];
    const alpha = (node) => node.birth === 0 ? 1 : Math.max(0, Math.min(1, (activity - node.birth) * 4));
    for (let i = 0; i < nodes.length; i++) {
      const a = nodes[i], opacity = alpha(a);
      if (!opacity) continue;
      for (let j = i + 1; j < nodes.length; j++) {
        const b = nodes[j], distance = Math.hypot(a.x - b.x, a.y - b.y);
        const visible = Math.min(opacity, alpha(b));
        if (distance > range || !visible) continue;
        const strength = (1 - distance / range) * visible;
        ctx.strokeStyle = `rgba(${rgb(a)},${strength * (.10 + activity * .13)})`;
        ctx.lineWidth = .65;
        ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
        const progress = (time * (.07 + activity * .20) + i * .19 + j * .13) % 1;
        const x = a.x + (b.x - a.x) * progress, y = a.y + (b.y - a.y) * progress;
        ctx.fillStyle = `rgba(${rgb(a)},${strength * (.25 + activity * .35)})`;
        ctx.beginPath(); ctx.arc(x, y, 1 + activity * .6, 0, Math.PI * 2); ctx.fill();
      }
      const pulse = .5 + .5 * Math.sin(time * (1 + activity * 2) + a.phase);
      const glow = ctx.createRadialGradient(a.x, a.y, 0, a.x, a.y, 10 + pulse * 7);
      glow.addColorStop(0, `rgba(${rgb(a)},${opacity * (.07 + pulse * .1 + activity * .08)})`);
      glow.addColorStop(1, `rgba(${rgb(a)},0)`);
      ctx.fillStyle = glow; ctx.beginPath(); ctx.arc(a.x, a.y, 17, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = `rgba(${rgb(a)},${opacity * (.25 + pulse * .35)})`;
      ctx.beginPath(); ctx.arc(a.x, a.y, 1 + pulse * .9, 0, Math.PI * 2); ctx.fill();
    }
    canvas.dataset.mode = reduced.matches ? "static" : activity > .15 ? "active" : "calm";
  }
  function tick() {
    timer = null;
    if (document.hidden || reduced.matches) return;
    const now = performance.now();
    const dt = Math.min((now - previous) / 1000, .1); previous = now; time += dt;
    const target = document.body.dataset.neuralActive === "true" ? 1 : 0;
    activity += (target - activity) * Math.min(1, dt * 1.3);
    for (const node of nodes) {
      node.x += node.vx * dt * (1 + activity * 2.5);
      node.y += node.vy * dt * (1 + activity * 2.5);
      if (node.x < 0) node.x = width;
      if (node.x > width) node.x = 0;
      if (node.y < 0) node.y = height;
      if (node.y > height) node.y = 0;
    }
    render();
    timer = setTimeout(tick, activity > .15 ? 1000 / 24 : 1000 / 12);
  }
  function resume() {
    clearTimeout(timer); timer = null; previous = performance.now();
    if (reduced.matches) { activity = 0; render(); }
    else if (!document.hidden) tick();
  }
  resize(); resume();
  window.addEventListener("resize", resize);
  document.addEventListener("visibilitychange", resume);
  reduced.addEventListener("change", resume);
  window.addEventListener("pagehide", () => clearTimeout(timer));
  window.addEventListener("pageshow", resume);
}

refreshAll(); refreshOmniroute(); wsConnect(); initStrategyLab(); initBlitzViewer(); initSemanticBackground(); updateClock();
applyMode();
/* brain wiring */
$("palette-input").addEventListener("input", (e) => renderPalette(e.target.value));
$("btn-tour").addEventListener("click", startTour);
$("btn-tour-next").addEventListener("click", () => { tourI = Math.min(2, tourI + 1); showTour(); });
$("btn-tour-back").addEventListener("click", () => { tourI = Math.max(0, tourI - 1); showTour(); });
$("btn-tour-done").addEventListener("click", () => { $("tour").hidden = true; localStorage.setItem("blitz.tour", "1"); });
$("btn-mode").addEventListener("click", () => {  const m = (localStorage.getItem("blitz.mode") || "expert") === "simple" ? "expert" : "simple";
  localStorage.setItem("blitz.mode", m); applyMode();
  toast(m === "simple" ? "Modo simples" : "Modo especialista");
});
$("btn-mute").addEventListener("click", () => {
  muted = !muted;
  localStorage.setItem("blitz.muted", muted ? "1" : "0");
  $("btn-mute").textContent = muted ? "🔇" : "🔊";
});
if (muted) $("btn-mute").textContent = "🔇";
$("btn-clear-n").addEventListener("click", () => { NOTIFS.length = 0; renderNotifs(); });
$("btn-auto-paper").addEventListener("click", async () => {
  try {
    const cur = $("btn-auto-paper").textContent.includes("ON");
    const r = await api("/api/session/auto", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ enabled: !cur }) });
    updateAutoBtn(r.auto_paper);
    toast(r.auto_paper ? "🤖 AUTO-PAPER ligado (simulação)" : "AUTO-PAPER desligado");
    if (r.auto_paper) soundConfirmed();
  } catch (e) { soundBlock(); toast("⛔ " + e.message, "red"); }
});
function updateAutoBtn(on) {
  const b = $("btn-auto-paper");
  if (b) { b.textContent = on ? "AUTO: ON" : "AUTO: OFF"; b.classList.toggle("danger", on); }
}
$("btn-why").addEventListener("click", explainWhy);
$("btn-evidence").addEventListener("click", () => { goTab("mesa"); toast("Evidência: timeline e grade"); });
$("btn-math").addEventListener("click", () => { goTab("risco"); refreshRisk(); });
$("btn-ad-close").addEventListener("click", () => { $("agent-detail").hidden = true; });
$("btn-ad-evidence").addEventListener("click", () => { goTab("mesa"); });
$("btn-risk-refresh").addEventListener("click", refreshRisk);
if (!localStorage.getItem("blitz.tour")) startTour();
notify("info", "Conectado ao Command Center (PAPER).", "boot");
setInterval(refreshAgents, 8000);
refreshAgents();
setInterval(refreshState, 4000);
setInterval(refreshSignal, 4000);
setInterval(refreshBoard, 5000);
setInterval(refreshGame, 10000);
setInterval(refreshStats, 15000);
setInterval(refreshOmniroute, 30000);
setInterval(updateClock, 1000);
