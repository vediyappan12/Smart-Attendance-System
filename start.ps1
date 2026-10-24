$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Join-Path $projectRoot "backend"
$venvPython = Join-Path $backendDir ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $venvPython)) {
    throw "Backend is not set up yet. Run .\setup.ps1 first."
}
if (-not (Test-Path -LiteralPath (Join-Path $backendDir ".env"))) {
    throw "backend/.env is missing. Run .\setup.ps1 first."
}

Push-Location $backendDir
try {
    Write-Host "Starting Smart Attendance at http://127.0.0.1:8000"
    Write-Host "Keep this terminal open; press Ctrl+C to stop the server."
    & $venvPython -m uvicorn app.main:app --host 127.0.0.1 --port 8000
}
finally {
    Pop-Location
}
