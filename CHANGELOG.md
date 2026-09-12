# CHANGELOG

## 2.0.0 — 2026-09-11 (sessão 2)

### Adicionado
- **WebSocket ao vivo** (`/ws`): eventos, apostas e settle fazem fan-out instantâneo
  para o dashboard (client com reconexão exponencial + keepalive); polling virou fallback
- **Game Center na dashboard**: registro de apostas papel (home/away/draw/spreads),
  banca, PnL/ROI, listas abertas/resolvidas, toasts GREEN/RED com som, alertas de settle
- **Game engine** (`game.py`): paper bets append-only com settle automático sobre o
  evento observado; payouts RTP-validados (home/away 1:1 push-half, draw 11:1);
  banca não deixa apostar acima do saldo; integrado às travas de política
- **Simulador Monte Carlo** (`/api/game/simulate`): 8 baralhos, reshuffle ~50%, seed
  determinística; confirma honestamente o EV negativo (-3,3% flat home)
- **Observer bridge**: `observer/fb_observer.js` (MutationObserver read-only no DOM do
  jogo, envia via WS) + ingest autenticado (`OBSERVER_TOKEN`) no `/ws` e `/api/ingest`
- **Telegram** (`telegram_notify.py`): alertas GREEN/RED, blocks, mesa quente, sessão;
  comandos `/status /saldo /apostas /parar /voltar /relatorio`; linguagem neutra
- **Hermes Agent combo** (`agent/`): config governada apontada pro OmniRoute (fallback
  AIsa), toolsets restritos, system prompt com política anti-previsão
- **Deploy VPS** (`deploy/`): Dockerfile + docker-compose (command-center + Caddy TLS
  + OmniRoute opcional) + guia Hetzner CX22 (~€3.79/mês) passo a passo
- AIsa como provider verificado no router (OmniRoute → AIsa → slot genérico)
- Testes de jogo (12 novos): payouts, banca, settle, spreads, guardrails — **33/33**

### Decisões (ver deploy/EVALUATION.md)
- apache/cloudberry: não adotado (OLAP de TB; SQLite sobra) — reavaliar em >100M eventos
- coder/websocket (Go): papel já coberto por websockets/Python + WS nativo
- Framer/Framer Motion: desnecessário (UI vanilla sem build step)

## 1.0.0 — 2026-09-11

### Adicionado
- Ledger append-only com hash chain SHA-256 (events, manual_decisions, audit_log)
- Policy engine: limite diário (200), stop-loss/win, cooldown, kill switch, mesa quente
- Estados de operação: OFFLINE / PAPER / MANUAL_REVIEW / COOLDOWN / STOPPED (sem AUTO_EXECUTION)
- RAG local TF-IDF com provenance (fonte + linha) e compressão RTK-style integrada
- Router: OmniRoute primário + slot genérico OpenAI-compatible para 9route (fail-closed)
- AI Copilot governado: schema JSON, tom neutro, redaction de segredos, fail-closed
- Dashboard mobile-first tema terminal (toasts GREEN com som WebAudio, alertas de mesa quente)
- Export JSON/CSV; 21 testes de invariantes (espelham docs/07-acceptance-tests.md)

### Segurança
- Nenhuma rota de aposta/auto-execução existe (testado)
- Segredos apenas em .env (não versionado); .env.example sem segredos
- Gateway OmniRoute em loopback (127.0.0.1)

### Notas
- Semantica 0.6.8 instalada (--no-deps; gensim sem wheel para Python 3.14). Integração
  profunda (grafo de contexto/provenance W3C PROV-O) fica para o próximo sprint.
- OmniRoute v3.8.50 global + instalação pré-existente em D:\OMNIROUTER (v3.8.48).
