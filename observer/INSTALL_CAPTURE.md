# Captura local somente leitura

O coletor desta pasta usa uma extensão Chrome Manifest V3 em contexto isolado.
Ele não injeta o token na página, não clica e não abre nem liquida apostas.
Substitui o caminho antigo de `fb_observer.js` para este deploy; não rode os dois.

## Instalação neste computador

1. Execute `python build_capture_extension.py` na pasta command-center.
2. No Chrome, abra `chrome://extensions`, habilite o modo do desenvolvedor e escolha
   **Carregar sem compactação**.
3. Selecione `command-center/data/observer-extension`.
4. Recarregue a aba do dashboard e abra a mesa. Se a sessão do jogo pedir login,
   reconecte normalmente. Nenhuma leitura é feita de cookies ou senhas.

A pasta gerada contém uma credencial derivada do OBSERVER_TOKEN, limitada às
rotas `/api/observer/*`. Ela é ignorada pelo Git. Não compartilhe essa pasta.
O token principal permanece no servidor. A extensão só solicita acesso aos frames
`client.pragmaticplaylive.net` e `games.pragmaticplaylive.net`, e ao serviço local
127.0.0.1 (o destino do worker é fixo em 8766).

## Contrato e confirmação

O banner final `div.F_M` e `[data-testid="game-header-game-id"]` foram observados
no DOM em 14/09/2026. Classes do provedor podem mudar: se o banner não corresponder,
a coleta não deve produzir eventos. `.ee_en` é rótulo de aposta, não resultado.

A extensão aguarda uma fase sem banner e duas amostras estáveis. O servidor exige
duas requisições iguais separadas por pelo menos 500 ms, dentro de 8 segundos.
Identidade persistente: SHA-256 de `football-blitz:round:<round_id>` no ledger.
Precisa existir uma sessão PAPER ativa. Não cria sessão e não altera políticas.

Exemplo ilustrativo de corpo de `PUT /api/observer/outcomes` (não transmitir como real):

```json
{"round_id":"17755021116","outcome":"home","observed_at":"2026-09-14T16:30:00Z","parser_version":"fb-banner-1.0"}
```

Somente após confirmação o evento recebe `data_origin=authorized_readonly` e é
publicado no WebSocket existente como `{"kind":"event","event":{...}}`.
`collect_200.py` lê o mesmo ledger e restringe a coleta à sessão selecionada.
O heartbeat ocorre a cada 15 s; `/api/observer/status` considera offline após 120 s.
Heartbeat comprova presença do coletor, não novos resultados ou login válido.

## Monitor local de saúde e histórico

Execute `python start_capture_monitor.py` para iniciar o processo Node oculto.
O processo roda enquanto o computador estiver ligado; não há inicialização automática
após reboot. Uma trava local impede duas instâncias simultâneas.
Ele consulta `/ready`, `/api/observer/status` e `/api/observer/history` em intervalos
de 15 s após cada ciclo. Em falhas de rede tenta até três vezes com backoff.

Estado: `data/capture-monitor.json`. Avisos: `data/capture-monitor.jsonl`.
O cursor é salvo entre reinícios. Avisos ocorrem em mudanças de saúde ou novos
eventos históricos, sem repetir o histórico na primeira inicialização.
Os avisos de sequência são apenas descritivos: 4, 5 etc. resultados observados;
empate, troca de lado, sessão diferente ou lacuna superior a 120 s reiniciam a
contagem. Rodadas não capturadas em intervalos menores podem passar despercebidas;
esses avisos não provam continuidade integral da mesa e não têm valor preditivo.

## Limites deste entregável

Não há alertas externos, gatilhos de aposta, integração com agentes ou agenda
automática. Não há garantia de recuperação de rodadas perdidas:
se a API ficar offline enquanto o banner desaparece, a rodada pode não entrar.
O coletor tenta novamente durante o banner, com backoff de até 15 s. Ele não
fabrica eventos para preencher lacunas e não importa um banner já aberto no início.

Validação: `python -m pytest test_observer_capture.py -q` e
`node --test observer/extension/capture.test.cjs` usam dados isolados/sintéticos.
O aceite do deploy exige ver um novo evento real no ledger e no WebSocket.

Referências: https://developer.chrome.com/docs/extensions/reference/manifest/content-scripts
e https://developer.chrome.com/docs/extensions/develop/concepts/network-requests.
