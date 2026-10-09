$ErrorActionPreference = 'Stop'
$record = Join-Path $PSScriptRoot '.cache/local-processes.json'
if (-not (Test-Path -LiteralPath $record)) { Write-Output 'No launcher-owned process record found.'; exit }
foreach ($entry in (Get-Content -LiteralPath $record -Raw | ConvertFrom-Json)) {
    $process = Get-Process -Id $entry.id -ErrorAction SilentlyContinue
    if ($process -and $process.StartTime.ToUniversalTime().ToString('o') -eq $entry.started) {
        Stop-Process -Id $entry.id
    }
}
Write-Output 'Stopped matching launcher-owned processes. Training history is preserved.'
