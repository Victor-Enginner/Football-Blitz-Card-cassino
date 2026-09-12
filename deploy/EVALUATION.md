# Avaliação honesta — pedidos do usuário (2026-09-11)

## apache/cloudberry — ❌ não usar (por enquanto)

O Cloudberry Database é um warehouse OLAP baseado em Greenplum/Postgres,
desenhado para **analytics distribuído em escala de TB** (múltiplos segments,
master + seg nodes). Nossa realidade:

- Dados: centenas/milhares de eventos/dia → **SQLite aguenta anos** disso
- VPS: 4GB RAM → Cloudberry quer 4GB+ só pra subir o cluster mínimo
- Caso de uso: append-only + agregações simples → índices SQL bastam

**Quando rever:** se um dia tivermos >100M eventos ou necessidade de OLAP
multi-dimensional (frota de observers, múltiplos usuários). Nesse cenário,
Postgres + materialized views é o próximo degrau (não Cloudberry).

## coder/websocket (Go) — ❌ não aplicar diretamente / ✅ equivalente já usado

É uma excelente lib **Go**. Nosso backend é Python (FastAPI) e o cliente é
browser JS. O papel dela já está coberto por:
- Python: `websockets` 16.0 (via uvicorn/FastAPI, nativo)
- Browser: `WebSocket` nativo

Mesma função (canal duplex, reconexão, keepalive), zero dependência nova.
Se no futuro algum componente em **Go** entrar (ex: microserviço de alta
frequência), aí sim usamos `coder/websocket`.

## Framer / Framer Motion — ❌ desnecessário

Framer é design tool/web builder; Framer Motion é React. Nossa UI é
**vanilla CSS/JS sem build step** (decisão ADR — stack leve, mobile-first).
O "efeito framer" desejado (transições suaves, toasts animados, timeline
com slide-in) já está implementado em CSS puro (`animation: slidein`,
transições de bar/toast). Adicionar React+Motion quebraria a premissa
"sem build step" e dobraria o peso da página por zero ganho funcional.

## hermes-agent — ✅ adotado (combo de IA)

MIT, aceita qualquer endpoint OpenAI-compatible → apontado pro OmniRoute
(combo `auto` + fallback AIsa). Config governada em `agent/hermes.json`
(sem browser/code-exec/computer-use toolsets; system prompt com política
de linguagem neutra). Ver `agent/README.md`.

## Telegram — ✅ integrado

Bot do @BotFather conectado via `telegram_notify.py`: alertas GREEN/RED,
blocks, mesa quente, relatório diário + comandos `/status /saldo /apostas
/parar /voltar /relatorio`. Credenciais só no `.env` (nunca commit).
