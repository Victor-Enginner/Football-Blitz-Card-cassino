# Serviço Windows — Football Blitz Command Center (T13/T15)

Backend em `http://127.0.0.1:8766` (PAPER). Duas opções — escolha UMA.

## Opção A — Task Scheduler (sem instalar nada)

O `watchdog.bat` já contém o loop: verifica `/ready` a cada 60s, mata processo
travado e reinicia o uvicorn. Log rotativo em `data/watchdog.log`.

Registrar para rodar no logon (ajuste o caminho se mover a pasta):

```bat
schtasks /Create /TN "FootballBlitz\Watchdog" ^
  /TR "'C:\caminho\para\football RAG SYSTEM AGENTS\command-center\watchdog.bat'" ^
  /SC ONLOGON /RL HIGHEST /F

schtasks /Run /TN "FootballBlitz\Watchdog"
```

> A pasta tem espaços — mantenha as aspas simples dentro de `TR` exatamente assim.

Verificar: `schtasks /Query /TN "FootballBlitz\Watchdog" /V`

Remover: `schtasks /Delete /TN "FootballBlitz\Watchdog" /F`

## Opção B — NSSM (serviço de verdade, sobrevive a logoff)

```bat
nssm install FootballBlitzBackend "C:\caminho\para\python.exe" "-m uvicorn server:app --port 8766"
nssm set FootballBlitzBackend AppDirectory "C:\caminho\para\command-center"
nssm set FootballBlitzBackend AppStdout "C:\caminho\para\command-center\data\service.log"
nssm set FootballBlitzBackend AppStderr "C:\caminho\para\command-center\data\service.err.log"
nssm set FootballBlitzBackend AppExit Default Restart
nssm start FootballBlitzBackend
```

Com NSSM, o serviço já reinicia sozinho — nesse caso NÃO rode o watchdog
também (evita dois supervisores brigando pela porta).

## T15 — teste de queda (obrigatório antes da rodada 6h)

1. Com watchdog ativo, mate o backend no meio de uma sessão:
   `taskkill /F /PID <pid do python na porta 8766>`
2. Aguarde ~90s (checagem 60s + boot 25s).
3. Verifique: `curl http://127.0.0.1:8766/ready` → `"ready":true`.
4. Checar integridade: `"chain":{"events":true,...}` no `/ready`.
5. Evidência no log: `type data\watchdog.log` deve mostrar linha `DOWN - restarting`.

Teste rápido manual (sem scheduler): `watchdog.bat --once` roda UMA checagem.

## Critério de aceite

- Backend cai → volta sozinho em < 2 min com hash chain íntegra.
- Nenhum estado `AUTO_EXECUTION` em nenhum momento (sempre PAPER).
