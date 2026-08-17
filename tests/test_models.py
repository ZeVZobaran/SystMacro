from __future__ import annotations

import numpy as np
import pandas as pd

from systmacro.models import forecast_factors


def test_forecast_shape_and_nested_intervals() -> None:
    rng = np.random.default_rng(17)
    dates = pd.date_range("2012-01-31", periods=144, freq="ME")
    frame = pd.DataFrame({"date": dates})
    for factor in ("dollar", "carry", "value", "momentum"):
        innovations = rng.normal(0, 0.02, len(dates))
        values = np.zeros(len(dates))
        for index in range(1, len(dates)):
            values[index] = 0.3 * values[index - 1] + innovations[index]
        frame[factor] = values
    config = {
        "forecast": {
            "horizon_months": 12,
            "max_ar_order": 2,
            "max_ma_order": 2,
            "minimum_observations": 60,
        }
    }
    result = forecast_factors(frame, config)
    assert len(result) == 48
    assert set(result["factor"]) == {"dollar", "carry", "value", "momentum"}
    assert (result["lower_95"] <= result["lower_80"]).all()
    assert (result["lower_80"] <= result["forecast"]).all()
    assert (result["forecast"] <= result["upper_80"]).all()
    assert (result["upper_80"] <= result["upper_95"]).all()
