# SystMacro

SystMacro is a reproducible FX factor-research pipeline and Streamlit dashboard. It downloads public BIS data, constructs monthly dollar, carry, value, and momentum factors across 29 DM and EM currencies, estimates currency exposures and idiosyncratic risk, fits low-order ARMA models, and publishes 12-month forecasts with uncertainty bands.

## What is implemented

- One-source ingestion from the BIS bulk-download service: USD bilateral exchange rates, broad REER indices, and central-bank policy rates.
- Atomic downloads, conditional HTTP refreshes, archive integrity checks, raw caching, schema filtering, and data-quality diagnostics.
- Raw USD-investor returns plus symmetric equal-weight-basket returns that make USD an explicit currency.
- A literature-standard broad-dollar factor, long the foreign basket and short USD.
- Cross-sectional high-minus-low carry, value, and momentum factors with one-month signal lags and equal-weighted tercile legs.
- Full-sample and rolling 60-month loadings for all 29 currencies, including USD, with HAC inference and idiosyncratic variance shares.
- AIC selection over ARMA(p,q), with p and q from 0 to 2, plus 12-month 80% and 95% prediction intervals.
- A six-tab Streamlit dashboard and both GitHub Actions and Windows Task Scheduler weekly automation.
- Unit tests for signal timing, portfolio construction, loading recovery, and forecasts.

## Quick start on this machine

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\bootstrap.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\update_weekly.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_dashboard.ps1
```

The dashboard opens at `http://localhost:8501`. To install the local Monday 08:00 update task, run PowerShell as a user allowed to create scheduled tasks and execute:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\install_weekly_task.ps1
```

That command changes Windows Task Scheduler state; it is intentionally not run by the pipeline itself.

## Direct commands

```powershell
& .\.venv\Scripts\python.exe -m systmacro.pipeline --refresh
& .\.venv\Scripts\python.exe -m pytest
& .\.venv\Scripts\python.exe -m streamlit run app.py
```

Without `--refresh`, the downloader uses cached archives and conditional requests when server metadata are available. Processed outputs and a checksum manifest are written to `data/processed/`.

## Automation

The workflow in `.github/workflows/weekly_fx_dashboard.yml` runs Mondays at 08:17 in `America/Sao_Paulo`, refreshes inputs, rebuilds all outputs, runs tests, and commits changed processed files. A Streamlit deployment connected to the repository will then rebuild from that commit. GitHub scheduled workflows only operate after this directory is placed in a GitHub repository and the workflow is present on its default branch.

## Documentation

- [Methodology and decision register](docs/METHODOLOGY.md)
- [Numeraire design and alternatives](docs/NUMERAIRE_DESIGN.md)
- [Data dictionary](docs/DATA_DICTIONARY.md)
- [Operations and failure handling](docs/OPERATIONS.md)
- [Reference inventory](Papers/README.md)

## Important limitation

The current carry signal uses central-bank policy rates, not one-month forward discounts or matched interbank/deposit rates. This preserves the high-rate-versus-low-rate ordering and permits a fully public pipeline, but it is not a tradable forward-based carry return. EM onshore/offshore access, pegs, capital controls, and NDF implementation are not yet encoded as portfolio constraints. Replacing the carry proxy and adding an investability overlay are the first recommended upgrades.

All outputs are research analytics, not investment advice.
