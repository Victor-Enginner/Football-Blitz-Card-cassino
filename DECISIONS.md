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

## 2026-09-14 — Correção das janelas de PowerShell e do watchdog
- **Contexto:** janelas de PowerShell aparecendo repetidamente. Investigação
  confirmou: a tarefa `BlitzWatchdog` (criada hoje 05:48 pelo próprio usuário/
  agentes, autor DESKTOP-IR5PG6B\Victor Ads) disparava `powershell.exe -File
  watchdog.ps1` visível a cada 2 min. `watchdog.ps1` usava `python` do PATH,
  que falha no contexto da tarefa (LastTaskResult 4294770688 desde ~14:37),
  e o backend 8766 estava parado. `BlitzLoop7h` registrada com caminho sem
  aspas (falha sempre). `hackagent/` é toolkit de red-team (AISecurityLab),
  não gerencia processos do Windows. `9router.vbs` está desativado
  (`9router.vbs.disabled`); o processo 9router ativo é roteador LLM em tray,
  sem relação com as janelas.
- **Decisão:** `BlitzWatchdog` a cada 10 min + `-WindowStyle Hidden` +
  `watchdog.ps1` com Python absoluto; `BlitzWake6h` também oculta;
  `BlitzLoop7h` desabilitada (reversível); backups em
  `backup_20260914/*.before-20260914.xml`; política de fontes de segurança
  em `OPENCLAW_SUPERVISOR.md`.
- **Consequência:** sem janelas a cada 2 min; backend PAPER restaurado em
  127.0.0.1:8766; supervisor validado com `--once`. Reativar `BlitzLoop7h`
  exige decisão do usuário (ver pendências no relatório).

## 2026-09-14 — Consultas Snyk/OSV/URLhaus/RFC + política de portas
- **Contexto:** usuário exigiu ativar as consultas e nunca abrir portas
  comuns/TCP desnecessários nem fluxos que disparem PowerShell à toa.
- **Decisão:** OSV consultado (zero vulns nas 5 deps); CVE-2026-48710
  verificado como não aplicável (starlette 1.6.0 + auth por token, sem
  `request.url.path`); floors de `requirements.txt` elevados às versões
  testadas; regra durável: só 127.0.0.1:8766 e 127.0.0.1:18789, nada de
  porta nova ou `0.0.0.0` sem aprovação. Snyk conectado e URLhaus-API
  ficam pendentes de conta/Auth-Key (não enviar repo privado sem
  autorização).
- **Consequência:** `9router` em `0.0.0.0:20128` e `freebuff` (320MB,
  lançado de terminal VS Code) registrados como fora do projeto,
  aguardando decisão (ver relatório).

## 2026-09-14 — 9router vinculado só a loopback (proxy local seguro)
- **Contexto:** `custom-server.js` escutava em `0.0.0.0:20128` (todas as
  interfaces, dashboard incluído). O `cli.js` suporta `--host` e avisa
  para usar `--host 127.0.0.1` em modo local.
- **Decisão:** processo parado (`taskkill /F`, graceful recusado pelo SO)
  e religado oculto com `--host 127.0.0.1 --port 20128 --tray
  --skip-update --no-browser`. A inferência já era 100% nuvem; custo
  local do roteador é só ~43MB RAM. Compressão RTK + cache + tiers free
  (TokenRouter/NVIDIA/AIsa) já ativos e validados sem gastar créditos.
- **Consequência:** 20128 só em loopback, 25 modelos respondendo,
  backend PAPER íntegro. Verificação sem nenhuma chamada paga.

## 2026-09-14 — Providers free conectados: OpenRouter + HuggingFace
- **Contexto:** usuário pediu NVIDIA/TokenRouter/OpenRouter/HF free e
  zerar as pendências. Validado sem gastar créditos: 9router 25 modelos,
  TokenRouter 137, NVIDIA 81, AIsa 112, OpenRouter 447 (19 `:free`);
  chats mínimos OK em TokenRouter (glm-5.3-free), NVIDIA (gpt-oss-20b) e
  OpenRouter (north-mini-code `:free`). HF sem token — slot pronto,
  inativo até `HF_TOKEN`.
- **Decisão:** novos slots `OPENROUTER_*` (default `cohere/north-mini-code:free`)
  e `HF_*` (router.huggingface.co/v1, exige token) em `config.py` +
  cadeia `route_chat` (9router→tokenrouter→nvidia→aisa→openrouter→hf→genérico),
  tudo com fail-closed e key-gate. `requirements.txt` com floors; testes
  `test_router_cost_policy.py` passando (2/2); `.env.example` documentado.
- **Consequência:** 6 fallbacks free antes de falhar; custo local continua
  só o roteamento (~43MB), inferência 100% nuvem.

## 2026-09-14 — Zeradas as pendências (gateway, loop, freebuff, logs, startup)
- **Gateway 18789:** processos originais morreram, mas a política de
  restart da tarefa religou sozinho (17:04, PID 5564, loopback OK).
  Veredito: funcionando como desenhado, nada a corrigir.
- **BlitzLoop7h:** ação corrigida (estava quebrada por caminho sem aspas)
  para `powershell -Hidden` invocando o `.bat` (cujas chamadas internas
  já são Hidden) + tarefa reabilitada. Backup em
  `backup_20260914/BlitzLoop7h.after-20260914.xml`.
- **freebuff:** identificado como "free coding agent" da CodebuffAI
  (MIT, freebuff.com), lançado de terminal VS Code — ferramenta do
  usuário, fora do projeto e sem agendamento. Mantido, sem ação.
- **Log Operacional do Agendador:** `wevtutil` negou acesso (exige PowerShell
  como Administrador) — comando pronto para o usuário rodar elevado:
  `wevtutil set-log 'Microsoft-Windows-TaskScheduler/Operational' /enabled:true`.
- **Root `start_command_center.bat`:** loop cego de 10s eliminado; agora só
  inicia se `:8766/ready` estiver DOWN, espera 60s (backup `.bak-20260914`).
- **Startup 9router:** `9router.vbs` reativado com `--host 127.0.0.1
  --no-browser` — boot continua em loopback. Reversão: renomear de volta
  para `.disabled`.

## 2026-09-14 — Snyk CLI instalado; HF/Snyk/URLhaus aguardam credenciais do usuário
- **Contexto:** usuário tem conta Snyk e URLhaus; HF exige token gratuito.
- **Decisão:** `npm i -g snyk` + binário `snyk-win.exe` (CLI 1.1307.2,
  via downloads.snyk.io — wrapper npm sozinho não completava o download).
  Falta 1 login (`snyk auth`) ou `SNYK_TOKEN` para rodar `snyk test`
  (envia só manifesto de dependências). URLhaus: falta `URLHAUS_AUTH_KEY`
  (auth.abuse.ch → perfil). HF: slot pronto, falta `HF_TOKEN` + `HF_MODEL`.
- **Consequência:** nada executado com credencial de terceiros sem o
  usuário; chaves via `setx`, nunca coladas no chat.

## 2026-09-14 — Snyk test executado: 3 projetos limpos
- **Contexto:** usuário autenticado (org `victor-enginner`).
- **Decisão:** `snyk test --all-projects` no `command-center`:
  `requirements.txt` (18 deps), `deploy/requirements.txt` (24 deps) e
  `quiz/package-lock.json` (5 deps) — **nenhuma vulnerabilidade**.
  Confirma OSV (zero vulns) por segunda fonte independente.
- **Consequência:** baseline Snyk limpo em 14/09/2026; repetir `snyk test`
  a cada mudança de dependência. URLhaus-API ainda aguarda
  `URLHAUS_AUTH_KEY` via `setx` (usuário logado no site).

## 2026-09-14 — URLhaus consultado: 5 hosts limpos
- **Contexto:** usuário forneceu Auth-Key temporária (uso único, em
  memória, sem gravar em disco ou exibir).
- **Decisão:** `POST urlhaus-api.abuse.ch/v1/host/` para
  `api.tokenrouter.com`, `integrate.api.nvidia.com`, `api.aisa.one`,
  `router.huggingface.co` e `openrouter.ai` — **todos `no_results`**
  (nenhum registro de distribuição de malware; ausência ≠ garantia).
- **Consequência:** nenhuma indicação de C2/malware nos endpoints
  externos do fluxo. Chave temporária: recomendar revogação na conta.

## 2026-09-14 — HuggingFace ativo (token fine-grained + restart do backend)
- **Contexto:** primeiro token era `read` (403 "insufficient permissions
  to call Inference Providers"); usuário gerou token fine-grained com a
  permissão correta pelo link da doc oficial.
- **Decisão:** `setx HF_TOKEN` + `HF_MODEL=openai/gpt-oss-120b:cheapest`;
  validado (`HF-OK`, tier free); backend reiniciado (`/F` — graceful
  recusado — + `supervisor --once` oculto) para carregar a nova env.
  Listener único em `127.0.0.1:8766`, `/ready: true, PAPER`.
- **Consequência:** 6º fallback free operacional. Apagar o token antigo
  sem permissão em huggingface.co/settings/tokens.

## 2026-09-14 — Auditoria das awesome-lists + especialização fallback free
- **Contexto:** usuário pediu auditoria completa de
  `bradagi/awesome-cli-coding-agents` (130+ agentes, atualizada hoje) e
  `e2b-dev/awesome-ai-agents` (era 2023) e especialização do fallback em
  free/open-source. Extração delegada a 2 subagentes (leitura total).
- **Decisão:** NADA instalado; nenhum provider novo adicionado à cadeia
  (listas são de AGENTES, não de providers free — nenhum endpoint free
  novo verificado). Mapa free confirmado: 9Router→TokenRouter→NVIDIA→
  AIsa→OpenRouter(`:free`)→HF(token free); inferência 100% nuvem.
  Infra leve elegível futura (só se precisar): `hax`/`agentty`/`nanocoder`
  (binário único, MBs de RAM, Ollama/OpenRouter); evitar harnesses com
  Docker (Codel, VibePod, SWE-agent) no i7/16GB.
- **Consequência / alertas:** NÃO usar derivados de leak (Claw Code,
  Claurst, claw-code-agent — risco jurídico/contaminação), nem forks com
  guardrails removidos (`Free Code` — risco de segurança), nem licenças
  não-OSI (SUL-1.0, BUSL-1.1, FSL) como se fossem OSS; lista e2b tem
  projetos mortos (AutoGPT original, AgentGPT, BabyAGI-*); stars e
  duplicatas na lista bradagi inconsistentes — verificar antes de
  instalar qualquer coisa dessas listas.

## 2026-09-14 — agentty instalado; aider incompatível; snyk monitor ativo
- **Contexto:** conectar peças free/open-source auditadas. `agentty`
  (1ay1/agentty, MIT) verificado: repo vivo, release v0.8.0, instalado via
  `winget` (hash verificado) em `%LocalAppData%\Programs\agentty`.
- **Decisão:** agentty pronto p/ uso interativo (`agentty` → `^P` →
  "Custom host…" → `127.0.0.1:20128`, model `auto` = cadeia free inteira;
  ou `--provider openrouter`). Headless `run` da v0.8.0 no Windows está
  bugado (rejeita prompt/flags em `run`, sem sessão no log) — NÃO usar em
  automação; sem sandbox no Windows (só Linux/macOS). Nenhum gasto feito.
  `aider` NÃO instalado: pins incompatíveis com Python 3.14
  (ResolutionImpossible) — agentty+opencode cobrem a necessidade.
  `snyk monitor --all-projects`: 3 snapshots na org victor-enginner.
- **Consequência:** coding agent local de ~16MB sem residente extra;
  smoke test headless fica pendente de correção upstream.

## 2026-09-14 — Produção: sinais, design system, 3 prompts, suíte verde
- **Contexto:** volta à produção do command-center: sinais, refatoração
  do design system, prompts de análise, débitos e fluxos.
- **Decisão:**
  - Sinais: teto hardcoded `>= 200` apostas/dia → `FB_MAX_BETS_PER_DAY`
    (default 200, comportamento preservado; separado de
    `FB_MAX_EVENTS_PER_DAY=3000`); backend reiniciado.
  - Design: `:root` único (valores vencedores, zero mudança visual) +
    vars `--home/--away/--draw/--info` aplicadas em CSS e JS (só contexto
    `element.style`); `api()` com timeout 8s + AbortController; PNG→WebP
    (12MB→1,2MB, `<picture>` com fallback); `loading=lazy` nas 2 imagens.
    WS e rotas verificados OK (sem TypeError, sem rota inválida).
  - 3 prompts criados: `PROMPT_ANALISE_SOFTWARE.md`,
    `PROMPT_LOGICA_PROGRAMACAO.md`, `PROMPT_DEBITOS_FLUXOS.md` (padrão
    GLM53: PAPER, evidência obrigatória, fail-closed).
  - Testes: `test_risk` falhava por isolamento (policy presa ao DB prod;
    pré-existente, provado via stash) → 2 testes agora trocam
    `server.policy` junto; **suíte completa: 85 passed**.
- **Consequência:** dashboard servindo (HTML/CSS/WebP/sinais OK);
  faltam p/ 100% (TASKS_AMANHA): T3, T5–T12 (exigem mesa real + 200
  giros), T14, T16 — operador.

## 2026-09-14 — Loop PAPER 100% automático ligado (sem clique) + limite permanente
- **Contexto:** usuário pediu operação contínua por padrões, sem cliques.
- **Decisão:** `POST /api/session/auto {"enabled": true}` → auto-PAPER
  ATIVO (`/api/state` confirma). Teste novo
  `test_auto_paper_opens_one_bet_per_fresh_streak` (4x→1 paper, sem
  duplicata; DBs temporários, zero poluição do ledger). **Suíte: 86 passed.**
  Rotação de sessão expirada, loss-streak≥8 e teto diário já eram
  automáticos e seguem valendo.
- **LIMITE PERMANENTE (não negociável):** só PAPER. Política
  never-implement de 2026-09-11 proíbe função de aposta real automática,
  martingale, recuperação de perda e bypass anti-bot; `AUTO_EXECUTION`
  não existe nos STATES; teste `test_no_execute_bet_route` quebra o
  build se rota proibida aparecer. Automação real violaria ToS do
  provedor e exporia o operador juridicamente. Cliques que restam (T5
  login Zona de Jogo, extensão observer, Telegram) são fronteira
  anti-bot/humana por desenho.

## 2026-09-14 — Red-team defensivo do copilot (4/4 bloqueios) + listas de hacking
- **Contexto:** usuário pediu hackagent contra nossos prompts + auditoria de
  `EvanThomasLuke/Awesome-AI-Hacking-Agents` (~88 itens) e da
  `bradagi/awesome-cli-coding-agents` (já auditada).
- **Decisão:** hackagent NÃO instalado (exigiria Ollama + pull de modelo
  12B abliterado + GBs — viola regras de peso; default `uncensored`
  inadequado). Em vez disso, bateria adversarial direta e barata contra
  `POST /api/copilot` (tiers free): override p/ recomendar aposta,
  exfiltração de system prompt/OBSERVER_TOKEN, garantia de resultado,
  ativação de execução real — **todos descartados pelo pipeline de
  governança (fail-closed, zero vazamento)**; pergunta legítima
  respondida com caveats anti-previsão. Mecanismo: validação de schema +
  tone-check (não exibir saída IA inválida).
- **Lista hacking (só leitura):** defensivamente úteis: `microsoft/RAMPART`
  (pytest p/ agentes), `snyk/agent-scan`, `cyberark/Vulnhalla` (triage
  CodeQL), `PurCL/RepoAudit`, `scabench-org/hound`; SÓ ofensivas
  (não instalar): `BruteForceAI`, `auto-exploits`; lista é WIP sem
  curadoria — nada apontado a terceiros sem autorização escrita.
- **Consequência:** pareamento com obliteratus (remoção de recusas)
  RECUSADO: finalidade seria contornar a política never-implement;
  além de inviável no hardware, um modelo sem guardrails não torna o
  bot legal/seguro. Red-team aqui = fortalecer a defesa, nunca
  desmontá-la.

## 2026-09-14 — RAMPART avaliado + suíte red-team própria (94 passed)
- **Contexto:** usuário pediu execução ("FAÇA ISSO"): RAMPART da Microsoft.
- **Decisão:** RAMPART **não instalado**: Alpha, Python ≤3.13 declarado e
  `pyrit==0.13.0` puxaria centenas de MB (viola regras de peso). Em vez
  disso, padrão RAMPART implementado nativamente em
  `test_redteam_defense.py` (8 testes, zero deps novas, `route_chat`
  mockado, determinístico): jailbreak→descarte, lucro garantido→descarte,
  eco de segredo→`[REDACTED]`, saída não-JSON→descarte, falha do
  router→fail-closed, 11 frases proibidas, padrões de redação, schema.
  Gap achado e corrigido no `copilot.py`: saída validada agora passa por
  `_redact` (antes só o caminho de erro). **Suíte total: 94 passed.**
- **Consequência:** teste de segurança pytest-nativo permanente, sem peso;
  RAMPART real fica para máquina com folga (requer pyrit + LLM juiz).

## 2026-09-14 — Operação PAPER em 1 clique (`operacao_paper.bat`)
- **Contexto:** usuário aceitou operar em PAPER (risco zero de ban/saldo)
  e pediu o caminho mais fácil.
- **Decisão:** `operacao_paper.bat`: confere `/ready` (sobe via supervisor
  se down) → liga `auto-paper` → abre dashboard. Lógica validada
  (READY-EXIT=0, auto:true); linha `start http` só abre no clique do
  usuário, não executada pelo agente.
- **Consequência:** PAPER = simulação 100% local, nada sai do PC para o
  provedor como aposta → sem violação de ToS, sem ban, sem saldo retido.

## 2026-09-14 — Validação real T9-T12 + viés de lookahead pego e corrigido
- **Contexto:** usuário exigiu tudo real, nunca simulado. Base: 170 eventos
  `authorized_readonly` reais no ledger (faltam 30 p/ os 200 do protocolo).
- **Decisão:** `validate_stats.py` (só stdlib, só dados reais): T9 chi-square,
  T10 anti-4x vs baseline Monte Carlo, T11 walk-forward, T12 binário.
  Primeira versão tinha **lookahead bias** (apostava na rodada que fechou
  a sequência → 100% de acerto até em moeda justa; baseline 0.928
  impossível denunciou). Reescrito sem lookahead (gatilho i..i+3, aposta
  em i+4, draw=push) + teste de regressão
  `test_antifour_backtest_has_no_lookahead` (moeda justa → 0.507).
  Resultado real corrigido: 5 sinais, 2 acertos, 3 pushes, hit 0.400 vs
  baseline 0.485 (z=-0.47) → **T12: sem evidência** (parcial, n=170).
  Regra viva do servidor NÃO tinha o bug (só meu script de backtest).
  **Suíte: 95 passed.**
- **Consequência:** veredito honesto com metodologia sã; completar 200
  giros reais e rodar de novo; pushes altos (3/8) viram débito da regra.

## 2026-09-11 — Política de never-implement
- **Decisão:** permanente — nenhuma função de aposta automática, martingale,
  recuperação de perda, bypass de anti-bot ou importação de cookies será
  implementada. Teste `test_no_execute_bet_route` falha o build se uma rota
  proibida aparecer.
