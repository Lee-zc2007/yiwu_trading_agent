$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$BackendDir = Join-Path $ProjectRoot "backend"
$FrontendDir = Join-Path $ProjectRoot "frontend"

Write-Host "[1/4] Checking Python environment..." -ForegroundColor Cyan
if (-not (Test-Path -LiteralPath $VenvPython)) {
    python -m venv (Join-Path $ProjectRoot ".venv")
}
& $VenvPython -m pip install -q -r (Join-Path $BackendDir "requirements.txt")

Write-Host "[2/4] Checking frontend dependencies..." -ForegroundColor Cyan
if (-not (Test-Path -LiteralPath (Join-Path $FrontendDir "node_modules"))) {
    Push-Location $FrontendDir
    npm install
    Pop-Location
}

Write-Host "[3/4] Starting FastAPI at http://localhost:8000" -ForegroundColor Green
$BackendProcess = Start-Process -FilePath $VenvPython -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000") -WorkingDirectory $BackendDir -WindowStyle Hidden -PassThru

try {
    Start-Sleep -Seconds 2
    Write-Host "[4/4] Starting frontend at http://localhost:5173" -ForegroundColor Green
    Write-Host "Swagger: http://localhost:8000/docs | Press Ctrl+C to stop." -ForegroundColor DarkGray
    Push-Location $FrontendDir
    npm run dev
} finally {
    Pop-Location -ErrorAction SilentlyContinue
    if ($BackendProcess -and -not $BackendProcess.HasExited) {
        Stop-Process -Id $BackendProcess.Id -Force
    }
}

