@echo off
REM Operacao PAPER em 1 clique: confere backend, liga auto-paper, abre dashboard.
REM Nada aqui aposta de verdade — tudo é simulação local (127.0.0.1).
cd /d "%~dp0"
echo [1/3] Conferindo backend :8766 ...
curl -sf -m 8 http://127.0.0.1:8766/ready -o nul
if errorlevel 1 (
  echo BACKEND DOWN — subindo via supervisor...
  start "" /min cmd /c ""..\..\.venv\Scripts\python.exe" openclaw_supervisor.py --once"
  timeout /t 25 /nobreak >nul
  curl -sf -m 8 http://127.0.0.1:8766/ready -o nul
  if errorlevel 1 (
    echo FALHOU. Rode manualmente: ..\..\.venv\Scripts\python.exe openclaw_supervisor.py --once
    pause
    exit /b 1
  )
)
echo [2/3] Ligando AUTO-PAPER ...
curl -s -m 8 -X POST http://127.0.0.1:8766/api/session/auto -H "Content-Type: application/json" -d "{\"enabled\": true}"
echo.
echo [3/3] Abrindo dashboard ...
start "" http://127.0.0.1:8766/
echo.
echo PRONTO: loop PAPER automatico (sinais + apostas simuladas + rotacao + desligamento sozinho).
echo Deixe a mesa aberta no navegador para o observer capturar. Bom trade (simulado)!
