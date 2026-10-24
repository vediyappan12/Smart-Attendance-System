$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Join-Path $projectRoot "backend"
$venvPython = Join-Path $backendDir ".venv\Scripts\python.exe"

Push-Location $backendDir
try {
    if (-not (Test-Path -LiteralPath $venvPython)) {
        py -3.12 -m venv .venv
        if ($LASTEXITCODE -ne 0) {
            throw "Could not create the Python environment. Install Python 3.12 and retry."
        }
    }

    $uvCommand = Get-Command uv -ErrorAction SilentlyContinue
    if ($uvCommand) {
        & $uvCommand.Source pip install --python $venvPython -r requirements.txt
        if ($LASTEXITCODE -ne 0) {
            throw "Could not install backend requirements."
        }
    }
    else {
        & $venvPython -m ensurepip --upgrade
        if ($LASTEXITCODE -ne 0) {
            throw "Could not initialize pip in the Python environment."
        }
        & $venvPython -m pip install -r requirements.txt
        if ($LASTEXITCODE -ne 0) {
            throw "Could not install backend requirements."
        }
    }

    $envFile = Join-Path $backendDir ".env"
    if (-not (Test-Path -LiteralPath $envFile)) {
        $adminKey = (py -3.12 -c "import secrets; print(secrets.token_urlsafe(48))").Trim()
        if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($adminKey)) {
            throw "Could not generate an admin API key."
        }
        @(
            "DATABASE_URL=sqlite:///./attendance.db"
            "ADMIN_API_KEY=$adminKey"
            "ADMIN_USERNAME=admin"
            "ADMIN_PASSWORD="
            "BIOMETRIC_ENCRYPTION_KEY="
            "WORK_START_TIME=09:30:00"
            "GRACE_PERIOD_MINUTES=15"
            "CORS_ORIGINS=http://localhost:8000,http://127.0.0.1:8000"
        ) | Set-Content -LiteralPath $envFile -Encoding ascii
        Write-Host "Created backend/.env with a generated admin key and local SQLite database."
        Write-Host "Read the generated admin password from backend/.env when signing in at /admin."
    }

    $envText = Get-Content -LiteralPath $envFile -Raw
    $generatedCredentials = $false
    if ($envText -notmatch "(?m)^ADMIN_API_KEY=.+$") {
        $signingKey = (& $venvPython -c "import secrets; print(secrets.token_urlsafe(48))").Trim()
        $envText += "`nADMIN_API_KEY=$signingKey`n"
        $generatedCredentials = $true
    }
    if ($envText -notmatch "(?m)^ADMIN_USERNAME=.+$") {
        $envText += "ADMIN_USERNAME=admin`n"
        $generatedCredentials = $true
    }
    if ($envText -notmatch "(?m)^ADMIN_PASSWORD=.+$") {
        $adminPassword = (& $venvPython -c "import secrets; print(secrets.token_urlsafe(24))").Trim()
        $envText += "ADMIN_PASSWORD=$adminPassword`n"
        $generatedCredentials = $true
    }
    if ($envText -notmatch "(?m)^BIOMETRIC_ENCRYPTION_KEY=.+$" -or $envText -match "(?m)^BIOMETRIC_ENCRYPTION_KEY=\s*$") {
        $biometricKey = (& $venvPython -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())").Trim()
        if ($envText -match "(?m)^BIOMETRIC_ENCRYPTION_KEY=.*$") {
            $envText = [regex]::Replace($envText, "(?m)^BIOMETRIC_ENCRYPTION_KEY=.*$", "BIOMETRIC_ENCRYPTION_KEY=$biometricKey")
        }
        else {
            $envText += "BIOMETRIC_ENCRYPTION_KEY=$biometricKey`n"
        }
    }
    Set-Content -LiteralPath $envFile -Value $envText -Encoding ascii
    if ($generatedCredentials) {
        Write-Host "Generated admin credentials. Username: admin. Read the password from backend/.env."
    }
    else {
        Write-Host "Keeping the existing admin credentials in backend/.env."
    }
}
finally {
    Pop-Location
}

Write-Host "Setup complete. Start the application with .\start.ps1"
