from __future__ import annotations

import warnings
from typing import Any

import numpy as np
import pandas as pd
from statsmodels.tsa.arima.model import ARIMA

from .factors import FACTOR_NAMES


def _bounds(frame: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    return frame.iloc[:, 0], frame.iloc[:, 1]


def forecast_factors(factor_returns: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    """Select a low-order ARMA model by AIC and produce 80%/95% prediction intervals."""
    settings = config["forecast"]
    horizon = int(settings["horizon_months"])
    max_p = int(settings["max_ar_order"])
    max_q = int(settings["max_ma_order"])
    minimum = int(settings["minimum_observations"])
    rows: list[dict[str, Any]] = []

    for factor in FACTOR_NAMES:
        series = factor_returns.set_index("date")[factor].dropna().astype(float)
        if len(series) < minimum:
            raise ValueError(f"Only {len(series)} observations available for {factor} ARMA model")
        best = None
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            for p in range(max_p + 1):
                for q in range(max_q + 1):
                    try:
                        result = ARIMA(
                            series,
                            order=(p, 0, q),
                            trend="c",
                            enforce_stationarity=True,
                            enforce_invertibility=True,
                        ).fit()
                    except (ValueError, np.linalg.LinAlgError):
                        continue
                    if np.isfinite(result.aic) and (best is None or result.aic < best.aic):
                        best = result
        if best is None:
            raise RuntimeError(f"All ARMA candidates failed for {factor}")

        forecast = best.get_forecast(steps=horizon)
        mean = pd.Series(np.asarray(forecast.predicted_mean), dtype=float)
        lower80, upper80 = _bounds(forecast.conf_int(alpha=0.20))
        lower95, upper95 = _bounds(forecast.conf_int(alpha=0.05))
        future_dates = pd.date_range(series.index.max() + pd.offsets.MonthEnd(1), periods=horizon, freq="ME")
        for index, date in enumerate(future_dates):
            rows.append(
                {
                    "date": date,
                    "factor": factor,
                    "forecast": float(mean.iloc[index]),
                    "lower_80": float(np.asarray(lower80)[index]),
                    "upper_80": float(np.asarray(upper80)[index]),
                    "lower_95": float(np.asarray(lower95)[index]),
                    "upper_95": float(np.asarray(upper95)[index]),
                    "ar_order": int(best.model_orders.get("ar", 0)),
                    "ma_order": int(best.model_orders.get("ma", 0)),
                    "aic": float(best.aic),
                    "training_observations": len(series),
                    "training_end": series.index.max(),
                }
            )
    return pd.DataFrame(rows)

