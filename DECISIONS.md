# DECISIONS — Registro de decisões (ADR leve)

## 2026-09-11 — Stack Python/FastAPI em vez de Next.js
- **Contexto:** o spec sugere "TypeScript + React/Next ou Vite" para projeto novo, mas
  não é prescrição. O projeto-pai já é Python (Playwright, SQLite, Telegram) e a
  máquina roda Python 3.14.
- **Decisão:** backend FastAPI + dashboard HTML/JS puro servido pelo mesmo processo.
- **Consequência:** zero build step, um único processo para rodar, reuso direto do
  ecossistema Python existente. UI sem framework: aceitável para o escopo do cockpit.

## 2026-09-11 — OmniRoute como primário; 9route como slot genérico desativado
- **Contexto:** usuário pediu "9route e omniroute". 9route não tem repositório
  oficial verificável; o próprio pacote de specs (docs/06-reference-registry.md)
  exige verificação antes de instalar projetos "de nome ambíguo". OmniRoute v3.8.50
  é MIT, npm trusted publisher, gateway local com 352 providers e compressão.
- **Decisão:** OmniRoute primário (`auto` combo); slot genérico OpenAI-compatible
  para 9route, `GENERIC_PROVIDER_ENABLED=false` até o usuário verificar a origem.
- **Consequência:** fail-closed garantido; zero dependência de projeto não verificado.

## 2026-09-11 — Compressão própria em vez de LLMLingua
- **Contexto:** OmniRoute oferece 12 engines de compressão no gateway; LLMLingua-2
  exige torch/transformers (pesado para o hardware do usuário).
- **Decisão:** engine local determinística estilo RTK (strip-noise, dedupe,
  stop-sentences, truncate) — 30–60% de economia medida, sem dependências.
- **Consequência:** compressão auditável e reproduzível; upgrade futuro para
  engines do gateway é plug-and-play (mesma interface de relatório).

## 2026-09-11 — Semantica instalada com --no-deps
- **Contexto:** semantica 0.6.8 depende de gensim, que não tem wheel para
  Python 3.14 (falha de build). O core da semantica (grafo, provenance) não
  precisa de gensim no nosso caso de uso.
- **Decisão:** `pip install --no-deps semantica` + módulo local de provenance
  (hash chain) já cobre o MVP; integração profunda fica para o Sprint 2.
- **Consequência:** risco rastreado no CHANGELOG; nenhuma funcionalidade bloqueada.

## 2026-09-11 — Gateway keyless em loopback
- **Contexto:** o daemon global do OmniRoute (v3.8.50) exigiu API key por padrão;
  a instalação pré-existente em D:\OMNIROUTER (v3.8.48, REQUIRE_API_KEY=false)
  roda keyless. Emitir chave exige dashboard interativo.
- **Decisão:** rodar o gateway com `REQUIRE_API_KEY=false` + bind explícito em
  127.0.0.1 (loopback-only, inacessível pela rede). Documentado no README.
- **Consequência:** caso o usuário exponha o gateway além do loopback, DEVE definir
  REQUIRE_API_KEY=true e emitir chave no dashboard (localhost:20128).

## 2026-09-11 — Política de never-implement
- **Decisão:** permanente — nenhuma função de aposta automática, martingale,
  recuperação de perda, bypass de anti-bot ou importação de cookies será
  implementada. Teste `test_no_execute_bet_route` falha o build se uma rota
  proibida aparecer.
