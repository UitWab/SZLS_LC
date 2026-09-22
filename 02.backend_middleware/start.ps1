$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$pythonExe = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonExe)) { throw '请先运行 setup.ps1 创建独立 Python 环境。' }
& $pythonExe -m backend_middleware
exit $LASTEXITCODE
