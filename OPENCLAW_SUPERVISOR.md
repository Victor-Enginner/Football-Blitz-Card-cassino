# OpenClaw supervisor

`openclaw_supervisor.py` is the local process owner for the Football Blitz
telemetry pipeline. It checks `/ready`, starts the API when needed, starts the
Node monitor when its PID/checkpoint is missing or stale, and forces a monitor
restart every 30 minutes so the WebSocket is freshly connected.

All actions are PAPER/read-only. It never calls a betting route. Run
`python openclaw_supervisor.py --once` from this directory for a scheduler, or
`python openclaw_supervisor.py` as the long-lived OpenClaw daemon. The lock and
state are in `data/openclaw-supervisor.lock` and
`data/openclaw-supervisor.json`; operational events are in
`data/openclaw-supervisor.jsonl`.

To run the complete deterministic flow in one process, use
`powershell -ExecutionPolicy Bypass -File run_agent_flow.ps1`. Each cycle runs
OpenClaw, then Hermes, then Muse Spark. The flow is PAPER-only and writes
`data/agent-flow.jsonl`.

## Agendamento no Windows (sem janelas visíveis)

- As tarefas `BlitzWatchdog` (a cada 10 min) e `BlitzWake6h` (diária) executam
  `powershell.exe` com `-NoProfile -NonInteractive -WindowStyle Hidden`.
  Não remover `-WindowStyle Hidden`: sem ele, cada disparo abre uma janela
  de console visível.
- `watchdog.ps1` usa caminho absoluto para o Python do projeto
  (`..\..\.venv\Scripts\python.exe`, com fallback para `python` no PATH),
  pois tarefas agendadas nem sempre herdam o PATH do usuário.
- `BlitzLoop7h` está DESABILITADA (ação registrada com caminho sem aspas —
  `C:\Users\Victor` + resto como argumentos — falha sempre; e o `.bat`
  dispararia 60 janelas de PowerShell se corrigido sem `Hidden`).
  Reativar somente após corrigir a ação e validar em modo oculto.
- Backups das definições originais: `backup_20260914/*.before-20260914.xml`
  (restaurar com `Register-ScheduledTask` / `Enable-ScheduledTask`).
- O supervisor já usa `CREATE_NO_WINDOW` ao criar backend/monitor e
  `SingleInstance` (lock em `data/openclaw-supervisor.lock`) no modo `--run`.
  O modo `--once` não tem lock: manter intervalo >= 10 min para evitar
  sobreposição.

## Política de consulta a fontes de segurança (2026-09-14)

Nas próximas mudanças, consultar as fontes oficiais aplicáveis e registrar
link + data + versão afetada + aplicabilidade. Ausência de registro não
significa segurança:

- **URLhaus (abuse.ch):** investigar URLs públicas suspeitas e indicadores
  de distribuição de malware. Não abrir URL suspeita para "testar"; não
  submeter URLs privadas ou com tokens.
- **Snyk:** vulnerabilidades de dependências e orientações de correção.
  Verificar requisitos de conta e o que será transmitido antes de usar
  scanners conectados; não enviar o repositório privado sem autorização.
- **RFC Editor:** especificações dos protocolos realmente utilizados
  (incluindo atualizações e erratas). RFCs não substituem avaliação de
  vulnerabilidades.
- **Red Hat:** avisos/CVEs aplicáveis apenas aos componentes Linux,
  containers ou produtos Red Hat existentes. Não aplicar instruções Linux
  diretamente ao Windows.
- **Microsoft Learn / Microsoft Security / Sysinternals:** prioridade para
  comportamento de processos, tarefas agendadas, diagnóstico e proteção
  no Windows.
- **Avisos dos mantenedores, OSV e CISA KEV:** complementar análise de
  dependências e vulnerabilidades exploradas.

Limites permanentes: não desativar Defender/firewall, não alterar a
política de execução global do PowerShell, não criar exclusões amplas de
antivírus, não revogar credenciais/apagar dados/alterar controles globais
sem autorização específica. `.env` nunca é commitado (ver `.gitignore`) e
segredos são mascarados em relatórios.

## Política de portas e listeners (2026-09-14)

- Listeners autorizados do fluxo: **127.0.0.1:8766** (API PAPER) e
  **127.0.0.1:18789** (OpenClaw Gateway). Ambos SOMENTE em loopback.
- REGRA: nenhum componente do projeto abre porta nova, expõe listener em
  `0.0.0.0`/rede local ou usa porta comum (80/443/22/etc.) sem aprovação
  explícita do usuário. Auditar com
  `netstat -ano -p TCP | Select-String LISTENING` antes/depois de mudanças.
- EXCEÇÃO CONHECIDA FORA DO PROJETO (não alterar sem decisão):
  `0.0.0.0:20128` (node 9router `custom-server.js`) escuta em TODAS as
  interfaces, alcançável pela rede local. Ver pendências no relatório.
  **RESOLVIDO 2026-09-14:** processo religado com
  `cli.js --host 127.0.0.1 --port 20128 --tray --skip-update --no-browser`
  via `Start-Process -WindowStyle Hidden`; listener agora só em
  `127.0.0.1:20128` (25 modelos OK, backend PAPER OK).
  Reversão: `taskkill /F /PID <novo>` e reiniciar sem `--host`
  (volta a `0.0.0.0`). Durabilidade: após reboot, religar com `--host`
  (o item de Inicialização está desativado; quem inicia o tray deve usar
  a mesma flag).

## Consultas de segurança executadas (2026-09-14)

- **OSV (api.osv.dev, 14/09/2026):** `querybatch` para fastapi 0.141.1,
  uvicorn 0.52.4, starlette 1.6.0, pydantic 2.13.5, requests 2.34.2 —
  **zero vulnerabilidades conhecidas**. Transmitido só nome+versão (público).
- **CVE-2026-48710 "BadHost" (Starlette < 1.0.1, via websearch 14/09/2026,
  fontes: OSV PYSEC-2026-161, Wiz, OSTIF, Red Hat RHSA-2026:22993/23346):**
  NÃO APLICÁVEL — instalamos starlette 1.6.0 (>= 1.0.1 corrigida) e
  `server.py` autentica por comparação de token (`token == OBSERVER_TOKEN`,
  linhas ~740/806), sem `request.url.path` em middleware. Floors de
  `requirements.txt` elevados para as versões testadas.
- **Snyk:** scanner conectado exige conta e enviaria o repositório —
  NÃO usado sem autorização. Cobertura obtida via OSV (agrega
  GHSA/PySEC, mesma base que alimenta o Snyk) + base pública.
- **URLhaus:** API de consulta exige Auth-Key (não configurada) — NÃO
  consultado via API. Alternativa aplicada: inventário de hosts externos
  no código (`api.tokenrouter.com`, `api.telegram.org`,
  `integrate.api.nvidia.com`, `api.aisa.one`, localhost) — nenhum
  indicador suspeito; nada submetido (regra: nunca submeter URL com
  token ou privada).
- **RFC Editor (14/09/2026):** RFC 6455 (WebSocket, Proposed Standard;
  atualizações 7936/8307/8441 sem quebra para nosso `/ws` em loopback).
  HTTP segue RFC 9110/9112 (referência do patch BadHost: validação de
  `Host` per RFC 9112 §3.2).
- **Red Hat / CISA KEV:** nenhum componente Linux/container/Red Hat no
  fluxo Windows — NÃO APLICÁVEL; registrado para não aplicar guias
  Linux aqui.
