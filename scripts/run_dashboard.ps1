$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    throw "Virtual environment not found. Run scripts\bootstrap.ps1 first."
}

& $Python -m streamlit run (Join-Path $ProjectRoot "app.py")
if ($LASTEXITCODE -ne 0) { throw "dashboard failed with exit code $LASTEXITCODE" }
