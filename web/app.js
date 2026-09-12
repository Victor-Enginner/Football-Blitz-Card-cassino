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
    if ($("hero-session")) $("hero-session").textContent = s.session ? `${s.session.session_id.slice(0, 12)}…` : "—";
    if ($("hero-event-budget")) $("hero-event-budget").textContent = `${u.events_today} / ${u.daily_limit}`;
    if ($("hero-ai-status")) $("hero-ai-status").textContent = s.state === "OFFLINE" ? "STANDBY" : "ROUTED";
    document.body.dataset.state = s.state;
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
      br.innerHTML = reasons.map(r => `⛔ ${r}`).join("<br>");
    } else { br.hidden = true; }
    document.querySelectorAll(".status-pill.state").forEach(p =>
      p.dataset.hot = String(!!hot));

    /* hot-streak sound fires once per new streak */
    if (hot) {
      const key = `${hot.outcome}:${hot.run}`;
      if (key !== lastHotKey) { soundHotStreak(); toast(`🔥 Mesa quente: ${hot.outcome} repetiu ${hot.run}x — considere pausar`, "red"); }
      lastHotKey = key;
    } else { lastHotKey = ""; }
  } catch (e) { console.warn("state:", e.message); }
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
    div.innerHTML = `<span class="outcome">${escapeHtml(ev.outcome)}</span>
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
    el.innerHTML = s.outcome_frequency.map(f => `
      <div class="freq-row">
        <span class="label">${escapeHtml(f.outcome)}</span>
        <div class="bar2"><div style="width:${(f.count / max) * 100}%"></div></div>
        <span class="count">${f.count}</span>
      </div>`).join("") || "<p class='hint'>sem eventos ainda</p>";
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
    $("g-balance").textContent = `R$ ${g.balance.toFixed(2).replace(".", ",")}`;
    const pnlEl = $("g-pnl");
    pnlEl.textContent = `R$ ${g.stats.pnl_total.toFixed(2).replace(".", ",")}`;
    pnlEl.style.color = g.stats.pnl_total < 0 ? "var(--red)" : g.stats.pnl_total > 0 ? "var(--green)" : "inherit";
    $("g-roi").textContent = `${g.stats.roi_pct}%`;
    $("g-open").textContent = g.open_bets.length;
    $("g-open-list").innerHTML = g.open_bets.map(b =>
      `<div class="bet open">${escapeHtml(b.bet_type)} <span class="mono">R$ ${b.stake.toFixed(2)}</span></div>`
    ).join("") || "<p class='hint'>nenhuma</p>";
    $("g-settled-list").innerHTML = g.recent.filter(b => b.status !== "open").slice(0, 12).map(b => {
      const cls = b.status === "won" ? "won" : b.status === "push" ? "push" : "lost";
      return `<div class="bet ${cls}">${escapeHtml(b.bet_type)} R$ ${b.stake.toFixed(2)}
        <span class="mono pnl">${b.pnl >= 0 ? "+" : ""}${b.pnl.toFixed(2)}</span></div>`;
    }).join("") || "<p class='hint'>nenhuma</p>";
  } catch (e) { console.warn("game:", e.message); }
}

$("bet-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    const r = await api("/api/game/bet", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ bet_type: $("bet-type").value, stake: parseFloat($("bet-stake").value) }) });
    beep(520, 0.08, "sine", 0, 0.1);
    toast(`📝 Aposta papel: ${r.bet.bet_type} R$ ${r.bet.stake.toFixed(2)}`);
    refreshGame();
  } catch (err) { soundBlock(); toast("⛔ " + err.message, "red"); }
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
        soundGreen();
        toast(`🟢 NOVO: ${ev.outcome}`);
        pulsePipeline();
        refreshGame();           // settlement may have happened
      } else if (msg.kind === "bet_settled") {
        const b = msg.bet;
        if (b.pnl >= 0) { soundGreen(); toast(`🟢 GREEN ${b.bet_type}: R$ +${b.pnl.toFixed(2)}`); }
        else { soundBlock(); toast(`🔴 RED ${b.bet_type}: R$ ${b.pnl.toFixed(2)}`, "red"); }
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
  div.innerHTML = `<span class="outcome">${escapeHtml(ev.outcome)}</span>
    <span class="origin">${escapeHtml(ev.data_origin)}${pnl}</span>
    <span class="time">${escapeHtml((ev.observed_at || "").slice(11, 19))}</span>`;
  tl.insertBefore(div, tl.firstChild);
  const newest = Number(ev.id || 0);
  if (newest > lastEventId) lastEventId = newest;
}

/* ── boot + polling ───────────────────────────────────────────────────────── */
function refreshAll() { refreshState(); refreshEvents(); refreshStats(); syncSession(); refreshGame(); }
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
  save.addEventListener("click", () => {
    const summary = `Hipótese salva: ${color.value} ×${run.value} → revisão manual`;
    toast(summary);
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

refreshAll(); refreshOmniroute(); wsConnect(); initNeuralField(); initAgentMesh(); initDialKit(); initStrategyLab(); updateClock();
setInterval(refreshState, 4000);
setInterval(refreshGame, 10000);
setInterval(refreshStats, 15000);
setInterval(refreshOmniroute, 30000);
setInterval(updateClock, 1000);
