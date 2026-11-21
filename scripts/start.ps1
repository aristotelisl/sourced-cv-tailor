# Starts CV Tailor: backend (uvicorn on :8000) and frontend (Vite on :5173),
# each in its own window, then opens the app in your browser.
# Close the two server windows (or press Ctrl+C in them) to stop.

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root '.venv\Scripts\python.exe'
$frontend = Join-Path $root 'frontend'

function Test-Port([int]$port) {
    # Vite listens on ::1 (IPv6) and uvicorn on 127.0.0.1, so check both.
    foreach ($addr in '127.0.0.1', '::1') {
        $client = New-Object System.Net.Sockets.TcpClient([System.Net.Sockets.AddressFamily]([System.Net.IPAddress]::Parse($addr).AddressFamily))
        try { $client.Connect($addr, $port); return $true } catch {} finally { $client.Close() }
    }
    return $false
}

# Basic setup checks
if (-not (Test-Path $python)) {
    Write-Host 'No .venv found. Create it first:' -ForegroundColor Red
    Write-Host '  python -m venv .venv; .venv\Scripts\pip install -r requirements.txt'
    exit 1
}
if (-not (Test-Path (Join-Path $root '.env'))) {
    Write-Host 'No .env found. Copy .env.example to .env and add your ANTHROPIC_API_KEY.' -ForegroundColor Red
    exit 1
}
$profileYaml = Join-Path $root 'data\profile.yaml'
if (-not (Test-Path $profileYaml)) {
    Copy-Item (Join-Path $root 'examples\profile.example.yaml') $profileYaml
    Write-Host 'Created data\profile.yaml from the fictional example. Replace it with your own facts.' -ForegroundColor Yellow
}
if (-not (Test-Path (Join-Path $frontend 'node_modules'))) {
    Write-Host 'Installing frontend packages (first run)...' -ForegroundColor Yellow
    Push-Location $frontend; npm install; Pop-Location
}

# Backend
if (Test-Port 8000) {
    Write-Host 'Port 8000 already in use - assuming the backend is already running.' -ForegroundColor Yellow
} else {
    Start-Process powershell -WorkingDirectory $root -ArgumentList @(
        '-NoExit', '-Command',
        "`$Host.UI.RawUI.WindowTitle = 'CV Tailor backend'; & '$python' -m uvicorn backend.main:app --reload --port 8000"
    )
}

# Frontend
if (Test-Port 5173) {
    Write-Host 'Port 5173 already in use - assuming the frontend is already running.' -ForegroundColor Yellow
} else {
    Start-Process powershell -WorkingDirectory $frontend -ArgumentList @(
        '-NoExit', '-Command',
        "`$Host.UI.RawUI.WindowTitle = 'CV Tailor frontend'; npm run dev"
    )
}

# Wait for both, then open the browser
Write-Host 'Waiting for servers...'
for ($i = 0; $i -lt 60; $i++) {
    if ((Test-Port 8000) -and (Test-Port 5173)) { break }
    Start-Sleep -Seconds 1
}
if ((Test-Port 8000) -and (Test-Port 5173)) {
    Write-Host 'CV Tailor is running at http://localhost:5173' -ForegroundColor Green
    Start-Process 'http://localhost:5173'
} else {
    Write-Host 'Servers did not come up within 60s - check the two server windows for errors.' -ForegroundColor Red
    exit 1
}
