# Plataforma operacional — primeira entrega

## Referências e direção

Referências inspecionadas no navegador em 14/09/2026:
- Straplay, https://app.straplay.pro/: lobby e uma mesa autenticada. Referência dominante para imagens, cards, agrupamento e entrada na operação. A mesa observada incorpora um jogo externo com uma faixa de sinal. Backend e cálculo de indicadores não foram auditados.
- Catalogador Pro, https://app.marcodosanjos.pro/home: home, agrupamentos e retomada de mesa. Scanner bloqueado por saldo.
- IA Roleta, https://iaroleta.com/: painel em três colunas e estado de espera.

## Decisões de implementação

| Decisão | Origem | Aplicação |
|---|---|---|
| Lobby com destaque visual e acessos operacionais | Straplay | Banner com imagens existentes e quatro cartões funcionais |
| Preservar paleta | Instrução do usuário / CSS efetivo | Carvão #09090b, laranja #ff5a1f, âmbar #ffae55 |
| Dados junto aos acessos | Catalogador / IA Roleta | Sessão, conexão, eventos e PnL paper |
| Manter funções existentes | Projeto | IDs e endpoints preservados; sem migração de stack |
| Indicadores sem duplicação de requisições | Implementação local | Espelhamento textual das saídas existentes com MutationObserver |
| URL por área e retorno do navegador | Continuidade operacional | Hash validado contra as views existentes |

Imagens: assets próprios já presentes, blitz-capa.png e blitz-rodada.png. Sem copiar marcas, código ou mídia das referências. Não criar mesas fictícias, métricas de audiência ou resultados promocionais.

## Escopo e validação

Entrada padrão em lobby; tour mantido disponível nas ferramentas, sem desviar a abertura. Operação preservada e com cabeçalho contextual. Cards abrem mesa, operação, paper, risco, Brain e ferramentas. Layout responsivo.

Verificação: sintaxe JavaScript, imagens carregadas, espelhos iguais às fontes, navegação lobby/operação e voltar, inspeção desktop e viewport móvel. Nenhuma sessão, evento, aposta ou configuração de negócio criada durante QA.

Limitação observada na primeira entrega: o WebSocket aparecia como `RECONNECTING`; a correção está documentada abaixo. A implementação não replica o backend do Straplay.

## Evolução da operação ao vivo

- WebSocket do dashboard local corrigido: o navegador recebe broadcasts sem conhecer o segredo do observer; mensagens `outcome` continuam restritas ao observer autenticado. Origens remotas sem token são rejeitadas.
- A operação usa até 50 eventos. Quando existe qualquer evento `authorized_readonly`, a análise passa a usar exclusivamente as rodadas reais mais recentes e exclui registros manuais/simulados.
- Frequência por mandante, visitante e empate; contagem absoluta; liderança observada; diferença para o segundo; alternâncias; maior sequência; cadência e quantidade de eventos reais.
- Relógio local e idade do último evento atualizados a cada segundo. `OBSERVER ATIVO` exige evento real nos últimos 120 segundos; depois disso o estado muda para `OBSERVER SEM EVENTO`.
- Timeline compacta e leituras em observação exibidas dentro do centro operacional. Frequência histórica é apresentada como descrição da amostra, não como previsão.
- Dock `RODADA ATUAL` no canto superior direito: cartas, resultado, origem, horário e estado `AGUARDANDO CARTAS`, `RESULTADO SEM CARTAS` ou `RESULTADO CONFIRMADO`. O dock também reserva o estado `SINAL PAPER` quando a regra gerar uma entrada.

Validação: 21 testes do backend, `py_compile`, `node --check`, WebSocket `LIVE` no navegador e painel renderizado sem overflow. A amostra observada durante o QA continha somente dados simulados; por isso o produto mostrou `SEM CAPTURA REAL`, como esperado.

## Governança do sinal (evolução de 14/09/2026)

A auditoria encontrou um problema crítico: `/api/signals/current` calculava a regra anti-sequência sobre qualquer origem — quatro registros manuais geravam "sinal confirmado" com popup e dock armado. Correções aplicadas:

| Decisão | Motivo | Implementação |
|---|---|---|
| Sinal exige rodadas reais frescas | Manual/simulado é prévia rotulada, nunca leitura da mesa | `_fresh_real_window()` em server.py: janela `authorized_readonly` dos últimos 50 eventos; sem rodada real há mais de `SIGNAL_MAX_STALENESS_S` (600 s) a estratégia falha fechada |
| Sinal com metadados operacionais | O operador precisa auditar de onde veio a recomendação | Resposta carrega `sample` (n, origem, janela completa), `computed_at`, `valid_until` (`SIGNAL_VALIDITY_S` = 90 s), `confidence` e `cancellation.reason` |
| Frontend respeita a validade | Sinal vencido não pode registrar entrada | `confirmSignal()` recusa `pendingSignal` com `valid_until` no passado e pede recálculo |
| Estados do sinal visíveis | "Sem entrada confirmada" precisa explicar o motivo | Painel `signal-meta` (estratégia, amostra real, confiança, calculado, válido até, status) + aviso de cancelamento em âmbar |
| Testes de governança | Regressão nunca mais deve abrir sinal sem dado real | `test_signal_never_from_manual_or_stale_real` e `test_signal_carries_operational_metadata` em test_risk.py |

## Estados vivos do sistema (evolução de 14/09/2026)

- **Ribbon de sistema** no topo de todas as áreas: `AO VIVO` (observer real < 120 s), `captura atrasada`, `reconectando` (WS caiu), `conectado sem captura real` e `conectando`. Corrigida a condição que impedia o estado `reconnecting` de aparecer (o handler sobrescrevia a variável).
- **Lobby operacional**: badge `AO VIVO / AGUARDANDO PARTIDA / SEM CAPTURA` dentro do hero e faixa de 5 células (captura, último resultado com idade e origem, última rodada real, amostra na janela, sinal). Nada inventado: células espelham o ledger.
- **Dock da rodada com 7 estados**: `AGUARDANDO PARTIDA`, `RESULTADO CONFIRMADO` (cartas reais), `RESULTADO SEM CARTAS` (real sem cartas), `PRÉVIA MANUAL`, `PRÉVIA SIMULADA`, `CAPTURA ATRASADA` (> 120 s sem leitura real) e `SINAL PAPER`. Origem e rótulo de confiança exibidos em tags próprias; manual/simulado nunca recebem "RESULTADO CONFIRMADO". Em mobile o dock vira cartão acima da tabbar, sem cobrir navegação.
- **Mesa**: ganhou a análise completa da janela de 50 (amostra, sequência, maior sequência, trocas, cadência, reais/total) espelhada da operação, nota de contexto de dados e timeline com badge de origem colorido (real/manual/simulado) e estado vazio desenhado com instrução de ação.
- **Acessibilidade**: `role=tablist/tab` com `aria-selected` nas abas, `aria-live=polite` na timeline e dock, `aria-label` na tabbar mobile.

## Correção de robustez no ledger (evolução de 14/09/2026)

O QA de carga revelou `sqlite3.InterfaceError` e `IndexError` intermitentes: `Ledger` compartilha uma conexão SQLite entre threads e as leituras (`last_events`, `stats`, `hot_streak`, `paper_pnl_today`, `verify_chain`, `get_session`, `active_session`, `count_events_on`, `list_hypotheses`, `_last_hash`) executavam fora do lock global usado pelos writers. Todas as leituras agora compartilham o mesmo `_LOCK` (convertido para `RLock` porque `append_event` segura o lock e chama `_last_hash` internamente). `agents_status` também recebeu guarda para evento sem `event_id`.

## Validação final

- `node --check web/app.js` — ok.
- `python -m py_compile server.py realtime.py ledger.py` — ok.
- 65 testes backend (incluindo os 2 novos de governança de sinal) — passando.
- `git diff --check` — sem conflitos de whitespace.
- QA em navegador headless (desktop 1440px e mobile 390px): zero erros de console, zero requisições falhando, sem overflow horizontal, estados verificados: lobby com e sem captura, operação com sinal suspenso (cancelamento visível), mesa com estado vazio e com eventos, dock em prévia manual, ribbon `reconnecting` confirmado derrubando o servidor de QA com a página aberta.
- Amostra durante o QA: apenas manual/simulado — o produto exibiu `SEM CAPTURA REAL` e `SEM ENTRADA CONFIRMADA` em todo o percurso, como deve.
- Limitação conhecida: a instância de produção do usuário na porta 8766 continua executando o código anterior até ser reiniciada; o QA completo rodou na 8767.
