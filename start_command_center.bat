@echo off
cd /d "%~dp0"
echo [Football Blitz] starting backend on http://127.0.0.1:8766 ...
echo (boot takes ~20s: RAG rebuild + Telegram)
start "FB-Backend" /min cmd /c "python -m uvicorn server:app --port 8766 >> data\uvicorn_boot.log 2>&1" > nul 2>&1 < nul
ping -n 26 127.0.0.1 > nul
start "" http://127.0.0.1:8766
echo Backend started in window "FB-Backend". Dashboard opened.
