# MEMÓRIA DA SESSÃO — Football Blitz Command Center
Data: 2026-09-12 · Backend v2.1.0-real-system · 63 testes verdes · Modo PAPER

## Sessão 2026-09-14 (volta do projeto)
- **Commit `20158ad`**: risco/progressão/coletor/docs da sessão 12 finalmente versionados (20 arquivos, 2288 linhas) — risco de stub resolvido.
- T1 ok (`backup_20260914/` com .env + DBs), T2 ok (`limit:3000` ativo em `/api/events/today-count`), T4 ok (`start_command_center.bat` criado; `/ready` chain True).
- T13/T15 ok: `watchdog.bat` (check 60s, revive, log rotativo 1MB) + receita `deploy/WINDOWS_SERVICE.md`; **teste de queda 2/2** (taskkill → "DOWN - restarting" → `/ready` 200 com chain True).
- Aprendido: `timeout` em .bat trava com stdin redirecionado → trocado por `ping -n`; `start ... > nul` evita pipe herdado.
- Sessão antiga de 12/09 parada (`/api/session/stop`); estava MANUAL_REVIEW com 2693min.
- `BUILD_GIT` é hardcoded em `server.py:43` — o `/ready` mostrar hash velho não significa build errado.
- Pendências operador: **T3** escada nível 5 (6 ou 8?), **T14** token Telegram, registrar watchdog no Task Scheduler (Opção A do WINDOWS_SERVICE.md).

## Stack de agentes reativado (2026-09-14)
- OpenClaw Gateway **rodando** como serviço (schtasks, pid variável, porta 18789, `openclaw gateway status`/`call health` = ok).
- OmniRoute já ativo na 20128. OpenCode 1.18.30 validado com chamada real (OpenRouter `north-mini-code:free`).
- Ralph Loop testado de ponta a ponta no TASK.md da raiz: itens 1 e 2 done com evidência. Item 1 revelou que `.autoclaw/orchestrator/metrics.json` não existe (orquestrador nunca logou). py_compile 4/4 em agent_flow/ + orchestrator importa OK (aviso "Football RAG System não disponível" = modo degradado).
- Aprendido: opencode com `cwd` explícito enxerga o workspace mapeado em outro caminho (C:\workspace\...) e falha ao editar arquivos; rodar SEM cwd. Agente pode alucinar checkbox — sempre confirmar o arquivo depois.
- Pendente: importar cron jobs (openclaw-cron-jobs.json.example), Telegram no OpenClaw (token + allowFrom), rodar `run_multi_agent.py` em modo paper p/ gerar metrics.json.

## Queda do gateway + fix (2026-09-14)
- Causa: gateway subiu SEM token configurado → gerou token runtime volátil; mudança de gateway.auth.mode disparou restart → serviço morreu (schtasks não religou) → `ECONNREFUSED 127.0.0.1:18789` no `openclaw tui`.
- Fix: `openclaw config set gateway.auth.mode token` + `openclaw config set gateway.auth.token <random>` (persistido no ~/.openclaw/openclaw.json) + `openclaw gateway restart`. Health ok, CLI autentica (sem token_mismatch).
- Cheat sheet: status = `openclaw gateway status`; subir = `openclaw gateway start`; cair de novo = `openclaw gateway restart`; diagnóstico = `openclaw doctor`; TUI = `openclaw tui`; dashboard browser = `openclaw dashboard` (colar token se pedir — revelar com `openclaw gateway auth-token --show`).
- Chain de modelos validada com `openclaw agent -m` (turn real respondeu): primary `openrouter/cohere/north-mini-code:free` + fallbacks :free + último `ollama/qwen2.5-coder:1.5b` (local). Zero API paga. Ollama hoje OFF — se quiser 100% local, virar primary e subir Ollama.
- Briefing pronto p/ colar no OpenClaw (contexto do projeto + regras: nunca pedir credenciais, nunca aposta real, sem VPS por enquanto) — resposta ao agente que pediu "detalhes de conexão da VPS". NUNCA colar credenciais SSH/tokens em chat de IA.

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
