# MEMÓRIA DA SESSÃO — Football Blitz Command Center
Data: 2026-09-12 · Backend v2.1.0-real-system · 63 testes verdes · Modo PAPER

## Estado atual (fato)
- Backend: `http://127.0.0.1:8766` (uvicorn, processo solto — SEM serviço ainda).
- Frontend: app 6 abas (SINAL/MESA/PAPEL/RISCO/BRAIN/MAIS), PWA, sons, holograma scan.
- Ledger hash-chain íntegra (events/audit/decisions True). Banca paper ~R$ 235.
- Regra ativa: 4x MANDANTE→VISITANTE R$ 0,50 e vice-versa; empate quebra.
- Escada PAPER: [0.50, 1, 2, 4, 6, 12] — NOTA: 4→6 não é dobra pura (decisão do operador, pendente confirmação).
- AUTO-PAPER existe, default OFF. OBSERVER_TOKEN ativo (WS exige token; 403 sem token = correto).
- ARENA_TOMBSTONE travada em SIMULACAO (era REAL). OpenClaw fallback corrigido p/ laguna. OpenCode 1.18.30 reparado.
- Backups: `server.py.bak-20260912`, `.env.bak-20260912`, `openclaw.json.bak-*`, `ARENA .env.bak-20260912`.

## Decisões tomadas
1. Football Blitz (Zona de Jogo), NÃO roleta. Arquivado tudo de roleta.
2. Sem WebSocket externo: Pragmatic só tem API B2B p/ operadoras. Caminho = observer DOM na sessão do usuário → backend local.
3. Sem aposta real em nenhuma camada. Martingale = educacional.
4. i-have-adhd (42k): só estilo de resposta; NÃO aprende mercado. Não instalado.
5. JSESSIONID/cookies: auditoria limpa, nada no projeto.

## Erros vistos e causa real
- Timeouts PowerShell no restart: boot do uvicorn leva 15-25s (RAG rebuild + Telegram). Não é bug — aguardar.
- `GET /ws 403`: correto, token obrigatório após hardening.
- `node --check` quebrou 1x: faltava `)` em `L.push` (corrigido, JS_OK).
- pytest collection error na raiz: rodar sempre com workdir=command-center.
- `meta-llama:free` AUSENTE no OpenRouter → trocado por laguna.

## Pendências (amanhã) — ver TASKS_AMANHA.md
1. Rodada supervisionada 4-6h com AUTO-PAPER + sons.
2. Limite 200 eventos/dia estoura em ~3h → elevar p/ observação (backup .env antes).
3. Rotação de sessão já existe no auto-paper; validar na prática.
4. Serviço Windows (NSSM/Task Scheduler) + watchdog.
5. Telegram de alerta crítico.
6. Coletar 200 giros reais → chi-square + hit-rate PAPER.
7. Confirmar escada: 6 ou 8 no nível 5?
8. `collect_200.py` pronto para a coleta.
