# F-AUTO-PAPER — Entrada automática em PAPER (anti-streak 4x + escada)
Status: draft
Outcome: validar fluxo 24h em PAPER sem saldo real
Dono: humano (Victor)
Escopo agente: pode tocar server.py, progression.py, collect_200.py, web/app.js (somente lógica de sinal). Não pode tocar migrations destrutivas, .env com segredos, infra de produção.

## Por que
Permitir observar se o sistema sustenta operação contínua (dedup, fila, limites) antes de pensar em 24h.

## O que
- Regra 4x MANDANTE->VISITANTE e vice-versa; empate quebra.
- Escada [0.50, 1, 2, 4, 6, 12]; avanço em loss, reset em win/push.
- AUTO-PAPER default OFF; 1 paper por streak fresco (last_anchor).
- Travas: sem aposta aberta, 200/dia, loss-streak 8, sessão expirada rotaciona.

## Constraints
Nunca aposta real, nunca navegador de cassino, nunca Telegram com ordem financeira.

## Critérios de aceite
| ID | Critério | Verificação |
|----|----------|-------------|
| AC1 | 4x gera sinal com stake da escada | test_signal_uses_ladder |
| AC2 | AUTO-PAPER cria 1 paper por streak | test_auto_paper_flow (10 giros sim) |
| AC3 | Dedup 409 não quebra streak | test_dedup_temporal_order |
| AC4 | Ledger chain íntegra após 10 | test_replay_restart_ledger |
