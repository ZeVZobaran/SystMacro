# Data dictionary

## Raw archives

Raw ZIP files are cached in `data/raw/` and ignored by Git. `download_metadata.json` records URL, ETag, Last-Modified header, size, timestamps, and any non-fatal cached-mode connection error.

| Archive | BIS dataflow | Filter used |
|---|---|---|
| `WS_XRU_csv_flat.zip` | `WS_XRU` bilateral USD rates | Monthly, end of period, configured 29 areas |
| `WS_EER_csv_flat.zip` | `WS_EER` effective exchange rates | Monthly, real, broad basket, configured 29 areas |
| `WS_CBPOL_csv_flat.zip` | `WS_CBPOL` policy rates | Monthly, configured 29 areas |

## Processed files

| File | Grain | Main fields |
|---|---|---|
| `bis_coverage_audit.csv` | BIS area/currency | start, end, count, and common coverage for all areas in the three-dataflow intersection |
| `market_panel.csv` | month x currency | spot, broad REER, policy rates, DM/EM label, eligibility |
| `currency_panel.csv` | month x currency | raw USD and basket-relative spot/carry/excess returns plus lagged signals |
| `factor_returns.csv` | month | dollar/carry/value/momentum returns and available-currency counts |
| `factor_weights.csv` | month x factor x selected currency | signal, side, rank, signed weight, realized basket-relative return |
| `factor_loadings.csv` | currency | alpha, HAC t-statistics, four betas, R-squared, idiosyncratic volatility/share |
| `rolling_loadings.csv` | month x currency | same metrics over rolling 60-month windows |
| `factor_forecasts.csv` | forecast month x factor | point forecast, 80%/95% bounds, AR/MA orders, AIC |
| `factor_performance.csv` | factor | annualized return/volatility, Sharpe ratio, maximum drawdown |
| `data_quality.csv` | currency | latest dates, missing shares, staleness, status |
| `run_metadata.json` | run | timestamps, numeraire, universe/group counts, disclosure, checksums |

Key return fields in `currency_panel.csv`:

| Field | Meaning |
|---|---|
| `spot_return_usd` | FX spot return versus USD; USD equals zero after the first observation |
| `carry_component_usd` | lagged policy-rate differential versus USD divided by 1200 |
| `excess_return_usd` | sum of the preceding two raw USD-investor components |
| `spot_return` | spot return after subtracting the available-universe cross-sectional mean |
| `carry_component` | carry component after subtracting the same-universe mean |
| `excess_return` | basket-relative analytical return; sums to zero across available currencies |

Returns, signals, betas, and shares are decimals. Policy rates are percentage points per year. Spot is local-currency units per USD. REER is an index with 2020 equal to 100.

