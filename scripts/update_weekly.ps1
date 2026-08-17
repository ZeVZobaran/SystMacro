$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    throw "Virtual environment not found. Run scripts\bootstrap.ps1 first."
}

& $Python -m systmacro.pipeline --refresh
if ($LASTEXITCODE -ne 0) { throw "pipeline failed with exit code $LASTEXITCODE" }
& $Python (Join-Path $ProjectRoot "scripts\audit_bis_coverage.py")
if ($LASTEXITCODE -ne 0) { throw "coverage audit failed with exit code $LASTEXITCODE" }
& $Python -m pytest
if ($LASTEXITCODE -ne 0) { throw "tests failed with exit code $LASTEXITCODE" }
