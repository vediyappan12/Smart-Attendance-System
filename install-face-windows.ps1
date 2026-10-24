$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Join-Path $projectRoot "backend"
$venvPython = Join-Path $backendDir ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $venvPython)) {
    throw "Backend environment is missing. Run .\setup.ps1 first."
}

$uvCommand = Get-Command uv -ErrorAction SilentlyContinue
Push-Location $backendDir
try {
    if ($uvCommand) {
        & $uvCommand.Source pip install --python $venvPython "dlib-bin==20.0.1.post1" pillow "setuptools<81" face-recognition-models
        if ($LASTEXITCODE -ne 0) {
            throw "Could not install prebuilt dlib and face recognition models."
        }
        & $uvCommand.Source pip install --python $venvPython --no-deps face-recognition
    }
    else {
        & $venvPython -m pip install "dlib-bin==20.0.1.post1" pillow "setuptools<81" face-recognition-models
        if ($LASTEXITCODE -ne 0) {
            throw "Could not install prebuilt dlib and face recognition models."
        }
        & $venvPython -m pip install --no-deps face-recognition
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Could not install face-recognition."
    }

    & $venvPython -c "import cv2, dlib, face_recognition; print('Face recognition ready:', face_recognition.__version__, dlib.__version__)"
    if ($LASTEXITCODE -ne 0) {
        throw "Face recognition packages were installed but could not be imported."
    }
}
finally {
    Pop-Location
}

Write-Host "Face recognition installed. Restart the server with .\start.ps1."
