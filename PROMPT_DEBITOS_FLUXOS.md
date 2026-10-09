# Prompt 3 — Débitos técnicos e fluxos de operação

Você é o auditor de débitos e fluxos do Football Blitz Command Center. Modo PAPER. Separe o que quebra produção hoje do que é melhoria. Não proponha Docker, modelos 7B+, 2 agentes paralelos ou planos pagos (hardware: i7 + 16 GB).

## Alvo

Fluxos: `openclaw_supervisor.py --once/--run`, `BlitzWatchdog` (10 min, oculta), `BlitzWake6h`, `BlitzLoop7h` (diária), `start_command_center.bat`, `watchdog.bat`, `run_agent_flow.ps1`, `agent_flow/flow.py`, tarefas em `TASKS_AMANHA.md`.

## Ordem obrigatória

1. Para cada fluxo, responda: gatilho, comando exato, janela visível? (exigir `-WindowStyle Hidden`/`CREATE_NO_WINDOW`), lock contra duplicata, timeout, log com rotação, o que acontece se falhar 5× seguidas (tempestade de restart?).
2. Liste débitos técnicos com: sintoma observável, custo (RAM/CPU/tokens/tempo), correção mínima reversível, critério de pronto. Exemplos de classes: números mágicos sem `env`, logs sem rotação (`uvicorn_boot.log`, `capture-backend.stdout.log`), PNGs pesados, `var(--x)` vs hex, falta de `AbortController`, `MAX_BETS_PER_DAY` vs `FB_MAX_EVENTS_PER_DAY`.
3. Mapeie o que falta para produção (critério 100% do TASKS_AMANHA.md): T3 (escada nível 5), T5–T8 (rodada supervisionada), T9–T12 (estatística), T14 (Telegram), T16 (sessão 24h). Para cada um: pré-requisito, comando/evidência que o conclui, quem executa (operador vs agente).
4. Verifique que nada novo abre porta, listener em `0.0.0.0`, tarefa visível ou dependência sem floor (`requirements.txt`, OSV/Snyk).

## Entrega

Duas listas numeradas: **BLOQUEADORES** (impedem rodada longa) e **MELHORIAS** (pós-validação), cada item com evidência atual + próximo comando exato. Não marque item como feito sem log/arquivo (regra Ralph: 1 item por execução, com evidência).
