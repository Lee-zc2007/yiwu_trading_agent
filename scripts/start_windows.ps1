param(
    [switch]$SkipInstall
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$PythonPath = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
$PidFile = Join-Path $ProjectRoot '.tradeguard-pids.json'

if (-not (Test-Path -LiteralPath $PythonPath)) {
    python -m venv (Join-Path $ProjectRoot '.venv')
}
if (-not $SkipInstall) {
    & $PythonPath -m pip install -r (Join-Path $ProjectRoot 'backend\requirements.txt')
    if (-not (Test-Path -LiteralPath (Join-Path $ProjectRoot 'frontend\node_modules'))) {
        npm --prefix (Join-Path $ProjectRoot 'frontend') install
    }
}

& $PythonPath (Join-Path $ProjectRoot 'scripts\init_data.py')
$Backend = Start-Process -FilePath $PythonPath -ArgumentList '-m','uvicorn','backend.app.main:app','--host','0.0.0.0','--port','8000' -WorkingDirectory $ProjectRoot -WindowStyle Hidden -PassThru
$NodePath = (Get-Command node.exe).Source
$NextCli = Join-Path $ProjectRoot 'frontend\node_modules\next\dist\bin\next'
$Frontend = Start-Process -FilePath $NodePath -ArgumentList $NextCli,'dev','-p','3000' -WorkingDirectory (Join-Path $ProjectRoot 'frontend') -WindowStyle Hidden -PassThru
@{ backend = $Backend.Id; frontend = $Frontend.Id } | ConvertTo-Json | Set-Content -LiteralPath $PidFile -Encoding UTF8

Write-Host "TradeGuard AI started"
Write-Host "Web: http://localhost:3000"
Write-Host "Swagger: http://localhost:8000/docs"
Write-Host "Stop: powershell -ExecutionPolicy Bypass -File scripts/stop_windows.ps1"
