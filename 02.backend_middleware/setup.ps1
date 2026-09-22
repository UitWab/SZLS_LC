param([string]$DatabaseSource = (Join-Path $PSScriptRoot '..\01.backend_db'))
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath (Join-Path $DatabaseSource 'pyproject.toml'))) { throw 'DatabaseSource 不是 A 的 Python 包目录。' }
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    uv venv --python 3.11 .venv
    if ($LASTEXITCODE -ne 0) { throw '虚拟环境创建失败' }
}
uv pip install --python '.venv\Scripts\python.exe' -e $DatabaseSource -e '.[test]'
if ($LASTEXITCODE -ne 0) { throw '依赖安装失败' }
& '.\.venv\Scripts\python.exe' scripts/configure.py
if ($LASTEXITCODE -ne 0) { throw '本地配置初始化失败' }
& '.\.venv\Scripts\python.exe' scripts/export_contract.py
if ($LASTEXITCODE -ne 0) { throw '契约导出失败' }
