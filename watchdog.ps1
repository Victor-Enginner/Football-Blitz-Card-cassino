Set-Location $PSScriptRoot
# Caminho absoluto primeiro: tarefas agendadas nem sempre herdam o PATH do usuário.
$python = Join-Path (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent) '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { $python = 'python' }
& $python openclaw_supervisor.py --once
