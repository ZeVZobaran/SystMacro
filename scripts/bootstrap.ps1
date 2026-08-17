$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = "C:\Users\josez\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

if (-not (Test-Path $Python)) {
    $Python = (Get-Command python -ErrorAction Stop).Source
}

& $Python -m venv (Join-Path $ProjectRoot ".venv")
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
& $VenvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed with exit code $LASTEXITCODE" }
& $VenvPython -m pip install "setuptools>=69" wheel
if ($LASTEXITCODE -ne 0) { throw "packaging backend installation failed with exit code $LASTEXITCODE" }
& $VenvPython -m pip install -e "${ProjectRoot}[dev]" --no-build-isolation
if ($LASTEXITCODE -ne 0) { throw "project dependency installation failed with exit code $LASTEXITCODE" }
Write-Output "Environment ready. Run scripts\update_weekly.ps1 next."
