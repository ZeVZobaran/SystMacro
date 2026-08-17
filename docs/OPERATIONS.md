# Operations

## Refresh sequence

1. Download or conditionally validate the three BIS bulk archives.
2. Validate each archive before atomically replacing its cached copy.
3. Stream the compressed CSVs in chunks and retain only the 29 configured currency series.
4. Validate currency coverage, uniqueness, and positive spot/REER levels.
5. Rebuild returns, signals, factors, exposures, forecasts, performance, and QA outputs.
6. Write stable CSVs and a SHA-256 manifest.
7. Run tests before any scheduled workflow commits results.
8. Rebuild `bis_coverage_audit.csv` so source-coverage changes are visible.

## Failure behavior

- A failed or corrupt download never replaces the prior archive.
- Missing currencies, duplicate keys, invalid levels, or an insufficient ARMA history stop the run with a non-zero exit.
- A publication delay does not stop the run if history remains usable; it is surfaced as `STALE` in the dashboard after the configured 75-day threshold.
- The GitHub workflow commits only after the pipeline and tests pass.
- The local scheduled task exits on the first error. Windows Task Scheduler retains its last-run result for diagnosis.

## Common commands

```powershell
# Cached/conditional update
& .\.venv\Scripts\python.exe -m systmacro.pipeline

# Forced full download
& .\.venv\Scripts\python.exe -m systmacro.pipeline --refresh

# Tests
& .\.venv\Scripts\python.exe -m pytest

# Dashboard
& .\.venv\Scripts\python.exe -m streamlit run app.py
```

## Configuration changes

All operational and methodological parameters are centralized in `config/settings.toml`. A universe change is not merely cosmetic: verify spot, REER, and policy-rate coverage; reconsider tercile leg sizes; rerun tests; and document the research reason in `docs/METHODOLOGY.md`.

## Publishing

For an always-on dashboard, push the project to GitHub and connect `app.py` to Streamlit Community Cloud or another Python web host. The weekly workflow commits new `data/processed` outputs; a deployment that watches the default branch will update after that commit. Keep the workflow's `contents: write` permission enabled.
