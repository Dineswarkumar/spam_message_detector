$ErrorActionPreference = 'Stop'

$projectRoot = $PSScriptRoot
$backendPath = Join-Path $projectRoot 'backend'
$siteUrl = 'http://127.0.0.1:8000/'
$healthUrl = 'http://127.0.0.1:8000/health'

if (-not (Test-Path -LiteralPath (Join-Path $backendPath 'main.py'))) {
    throw "Backend entry point not found under $backendPath"
}

# Reuse an already-running current server. Detect an older server version that
# still shows the API banner at / so the user gets a clear restart instruction.
try {
    $health = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 2
    if ($health.model_loaded) {
        $home = Invoke-WebRequest -Uri $siteUrl -TimeoutSec 2
        if ($home.Content -match '<html') {
            Start-Process $siteUrl
            Write-Host "Spam Shield is open at $siteUrl"
            return
        }
        Write-Host 'The backend is running an older version. In its terminal press Ctrl+C, then run this launcher again.' -ForegroundColor Yellow
        return
    }
} catch {
    # No responding model server; start one below.
}

$python = Get-Command python -ErrorAction Stop
$server = Start-Process -FilePath $python.Source `
    -ArgumentList @('-m', 'uvicorn', 'main:app', '--host', '127.0.0.1', '--port', '8000') `
    -WorkingDirectory $backendPath -PassThru -NoNewWindow

try {
    $ready = $false
    for ($attempt = 0; $attempt -lt 90; $attempt++) {
        if ($server.HasExited) {
            throw 'The backend stopped before it became ready. Check the error above.'
        }
        try {
            $health = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 2
            if ($health.model_loaded) {
                $ready = $true
                break
            }
        } catch {
            # Model loading can take a few seconds on startup.
        }
        Start-Sleep -Seconds 1
    }
    if (-not $ready) {
        throw 'The backend did not become ready within 90 seconds.'
    }

    Start-Process $siteUrl
    Write-Host "Spam Shield is open at $siteUrl. Keep this window open; press Ctrl+C to stop the backend."
    while (-not $server.HasExited) { Start-Sleep -Seconds 1 }
} finally {
    if ($server -and -not $server.HasExited) {
        Stop-Process -Id $server.Id -Force
    }
}
