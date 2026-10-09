param([switch]$Install)
$ErrorActionPreference = 'Stop'
$forgeRoot = $PSScriptRoot
$backend = Join-Path $forgeRoot 'backend'
$frontend = Join-Path $forgeRoot 'frontend'
$python = Join-Path $backend '.venv/Scripts/python.exe'
if ($Install -or -not (Test-Path -LiteralPath $python)) {
    Push-Location $backend
    try { uv sync --python 3.12 --extra vector; if ($LASTEXITCODE) { throw 'Dependency setup failed.' } } finally { Pop-Location }
    Push-Location $frontend
    try { npm ci; if ($LASTEXITCODE) { throw 'Frontend setup failed.' } } finally { Pop-Location }
}
& $python (Join-Path $forgeRoot 'tools/setup_local.py')
Push-Location $backend
try {
    & $python -m alembic upgrade head
    if ($LASTEXITCODE) { throw 'Database migration failed.' }
    & $python -m app.seed demo
    if ($LASTEXITCODE) { throw 'Demo bootstrap failed.' }
} finally { Pop-Location }
$logDir = Join-Path $forgeRoot '.cache'
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
$api = Start-Process -FilePath $python -ArgumentList '-m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log' -WorkingDirectory $backend -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logDir 'api.log') -RedirectStandardError (Join-Path $logDir 'api-error.log')
$worker = Start-Process -FilePath $python -ArgumentList '-m app.worker' -WorkingDirectory $backend -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logDir 'worker.log') -RedirectStandardError (Join-Path $logDir 'worker-error.log')
$node = (Get-Command node).Source
$viteScript = Join-Path $frontend 'node_modules/vite/bin/vite.js'
$web = Start-Process -FilePath $node -ArgumentList ('"' + $viteScript + '" --host 127.0.0.1 --port 5173 --strictPort') -WorkingDirectory $frontend -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logDir 'web.log') -RedirectStandardError (Join-Path $logDir 'web-error.log')
@($api, $worker, $web) | ForEach-Object { @{id=$_.Id; started=$_.StartTime.ToUniversalTime().ToString('o')} } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $logDir 'local-processes.json')
Write-Output 'Fault Forge is starting at http://localhost:5173. Open local-access.txt for your generated credentials.'
