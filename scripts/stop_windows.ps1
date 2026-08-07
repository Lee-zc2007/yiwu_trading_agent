$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$PidFile = Join-Path $ProjectRoot '.tradeguard-pids.json'
if (-not (Test-Path -LiteralPath $PidFile)) {
    Write-Host 'No running process record was found.'
    exit 0
}
$Processes = Get-Content -LiteralPath $PidFile -Raw | ConvertFrom-Json
function Stop-ProcessTree([int]$RootId) {
    $Children = Get-CimInstance Win32_Process -Filter "ParentProcessId=$RootId" -ErrorAction SilentlyContinue
    foreach ($Child in $Children) {
        Stop-ProcessTree -RootId $Child.ProcessId
    }
    if (Get-Process -Id $RootId -ErrorAction SilentlyContinue) {
        Stop-Process -Id $RootId -Force
    }
}
foreach ($ProcessId in @($Processes.backend, $Processes.frontend)) {
    if ($ProcessId) {
        Stop-ProcessTree -RootId $ProcessId
    }
}
Remove-Item -LiteralPath $PidFile -Force
Write-Host 'TradeGuard AI stopped.'
