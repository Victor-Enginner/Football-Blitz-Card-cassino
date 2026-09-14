@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
set PORT=8766
set LOG=data\watchdog.log
set ONCE=%1

:loop
set ALIVE=0
curl -s -o nul -m 5 http://127.0.0.1:!PORT!/ready && set ALIVE=1
if !ALIVE!==1 (
  echo %date% %time% ok >> !LOG!
) else (
  echo %date% %time% DOWN - restarting backend >> !LOG!
  for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":!PORT! .*LISTENING"') do taskkill /F /PID %%p > nul 2>&1
  start "FB-Backend" /min cmd /c "python -m uvicorn server:app --port !PORT! >> data\uvicorn_boot.log 2>&1" > nul 2>&1 < nul
  echo %date% %time% restart issued, waiting 25s boot >> !LOG!
  ping -n 26 127.0.0.1 > nul
)
if /i "!ONCE!"=="--once" goto end
for %%F in (!LOG!) do if %%~zF GTR 1000000 del !LOG!
ping -n 61 127.0.0.1 > nul
goto loop

:end
echo watchdog --once done
endlocal
