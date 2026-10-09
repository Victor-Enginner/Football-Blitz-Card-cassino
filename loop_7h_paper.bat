@echo off
REM Loop 7h-8h PAPER: 60 iteracoes de 1 min, cada agente em seu papel
for /L %%i in (1,1,60) do (
  echo [%TIME%] Iter %%i - Hermes healthcheck
  powershell -NoProfile -NonInteractive -WindowStyle Hidden -Command "try{Invoke-RestMethod http://127.0.0.1:8766/ready -TimeoutSec 10 | Out-Null; Write-Host 'ready ok'}catch{Write-Host 'ready pendente'}"
  timeout /t 60 /nobreak >nul
)
