# TASKS AMANHÃ — validação 100% do Football Blitz Command Center

## P0 — antes de qualquer rodada longa
- [x] T1. Backup `data/*.db` + `.env` (copiar p/ pasta `backup_YYYYMMDD/`).
  - Evidência: `backup_20260914/` com .env, .env.pre-t2, command_center.db, paper_bets.db
- [x] T2. Elevar `FB_MAX_EVENTS_PER_DAY` 200 → 3000 no `.env` (mesa cheia ~1500/dia).
  - Evidência: `/api/events/today-count` → `{"limit": 3000}`
- [ ] T3. Confirmar escada nível 5: 6 ou 8? (atual: [..., 4, 6, 12]). — PENDENTE OPERADOR
- [x] T4. Ligar backend via `start_command_center.bat` ajustado p/ porta 8766 + checar `/ready`.
  - Evidência: `/ready` → `{"ready":true, chain all True, mode PAPER}`; `.bat` criado (boot com `ping`, não `timeout`)

## P1 — rodada supervisionada 4-6h (PAPER)
- [ ] T5. INICIAR sessão no dashboard → login Zona de Jogo → `fbObserverCreate` no console.
- [ ] T6. Ligar AUTO-PAPER no sinal + som ligado. Observar: sirene 4x, confirmação, coin no GREEN.
- [ ] T7. Rodar `python collect_200.py --target 200` em paralelo.
- [ ] T8. Anotar: sinais gerados, GREEN/LOSS, drawdown máx, escada máx atingida, erros WS.

## P2 — validação estatística (com os 200 giros)
- [ ] T9. Chi-square uniformidade (home/away/draw) + p-valor.
- [ ] T10. Hit-rate da regra 4x em PAPER vs baseline aleatório.
- [ ] T11. Walk-forward: treino giros 1-100 → teste 101-200.
- [ ] T12. Veredito escrito: "vantagem confiável" OU "sem evidência" (sem meio-termo).

## P3 — robustez 24h
- [x] T13. Serviço Windows + restart automático + log rotativo.
  - Evidência: `watchdog.bat` (60s check, revive, log rotativo 1MB) + `start_command_center.bat` + receita `deploy/WINDOWS_SERVICE.md`. Registro no Task Scheduler pendente (Opção A ou B).
- [ ] T14. Telegram: token dedicado, alerta em bloqueio/erro/loss-streak. — PENDENTE OPERADOR
- [x] T15. Teste de queda: matar backend no meio da sessão → restart → chain True?
  - Evidência: `data/watchdog.log` 14/09/2026 01:42:50 + 01:48:30 "DOWN - restarting backend" → `/ready` 200 com chain True nas duas vezes.
- [ ] T16. Documentar sessão 24h simulada (2 dias observer sem clique já valem como T6 estendido).

## Critério 100%
Backend íntegro + 200 giros reais validados + rodada 6h sem erro + serviço com restart + Telegram alertando + PDF atualizado. Sem aposta real em nenhuma etapa.
