from __future__ import annotations

import numpy as np
import pandas as pd

from systmacro.factors import compute_currency_panel, construct_factors, estimate_loadings


def factor_config() -> dict:
    return {
        "project": {"base_currency": "USD"},
        "factors": {"leg_fraction": 1 / 3, "minimum_currencies": 6},
        "loadings": {"rolling_window_months": 60, "minimum_observations": 48, "hac_lags": 3},
    }


def test_currency_returns_and_signals_are_lagged() -> None:
    dates = pd.date_range("2018-01-31", periods=72, freq="ME")
    aud = pd.DataFrame(
        {
            "date": dates,
            "currency": "AUD",
            "spot": np.exp(np.arange(len(dates)) * 0.01),
            "reer": 100 + np.arange(len(dates), dtype=float),
            "policy_rate": np.arange(len(dates), dtype=float),
            "usd_policy_rate": 1.0,
        }
    )
    usd = pd.DataFrame(
        {
            "date": dates,
            "currency": "USD",
            "spot": 1.0,
            "reer": 100 + np.arange(len(dates), dtype=float) / 2,
            "policy_rate": 1.0,
            "usd_policy_rate": 1.0,
        }
    )
    market = pd.concat([aud, usd], ignore_index=True)
    config = {
        "universe": {
            "USD": {"area": "US", "name": "US dollar", "market": "DM"},
            "AUD": {"area": "AU", "name": "Australian dollar", "market": "DM"},
        },
        "factors": {"momentum_months": 3, "value_lookback_months": 60, "value_smoothing_months": 6},
    }
    result = compute_currency_panel(market, config).set_index(["date", "currency"])
    current = dates[10]
    assert np.isclose(result.loc[(current, "AUD"), "spot_return_usd"], -0.01)
    assert np.isclose(result.loc[(current, "AUD"), "spot_return"], -0.005)
    assert np.isclose(result.loc[(current, "AUD"), "carry_signal"], 9.0)
    expected_momentum = sum(
        result.loc[(date, "AUD"), "excess_return"] for date in dates[7:10]
    )
    assert np.isclose(result.loc[(current, "AUD"), "momentum_signal"], expected_momentum)
    for date in dates[1:]:
        assert np.isclose(result.loc[date, "excess_return"].sum(), 0.0)

    baseline = result.loc[(dates[-1], "AUD"), ["carry_signal", "value_signal", "momentum_signal"]].copy()
    market.loc[
        (market["date"] == dates[-1]) & (market["currency"] == "AUD"),
        ["spot", "reer", "policy_rate"],
    ] *= 10
    changed = compute_currency_panel(market, config).set_index("date")
    pd.testing.assert_series_equal(
        baseline,
        changed[changed["currency"] == "AUD"].loc[
            dates[-1], ["carry_signal", "value_signal", "momentum_signal"]
        ].astype(float),
        check_names=False,
    )


def test_factor_legs_are_neutral_and_follow_signal_order() -> None:
    date = pd.Timestamp("2025-01-31")
    currencies = list("ABCDEFGHI")
    panel = pd.DataFrame(
        {
            "date": date,
            "currency": currencies,
            "excess_return": np.arange(9) / 100,
            "carry_signal": np.arange(9),
            "value_signal": np.arange(9),
            "momentum_signal": np.arange(9),
        }
    )
    returns, weights = construct_factors(panel, factor_config())
    assert np.isclose(returns.loc[0, "carry"], 0.06)
    for factor in ("carry", "value", "momentum"):
        selected = weights[weights["factor"] == factor]
        assert np.isclose(selected["weight"].sum(), 0.0)
        assert np.isclose(selected[selected["weight"] > 0]["weight"].sum(), 1.0)
        assert np.isclose(selected[selected["weight"] < 0]["weight"].sum(), -1.0)
        assert set(selected[selected["side"] == "long"]["currency"]) == {"G", "H", "I"}


def test_dollar_is_explicit_and_style_returns_are_numeraire_invariant() -> None:
    date = pd.Timestamp("2025-01-31")
    currencies = ["USD", "AUD", "BRL", "CAD", "EUR", "JPY", "MXN", "NOK", "ZAR"]
    usd_returns = np.array([0.0, 0.01, 0.04, -0.01, 0.02, -0.02, 0.03, 0.005, 0.05])
    basket_returns = usd_returns - usd_returns.mean()
    panel = pd.DataFrame(
        {
            "date": date,
            "currency": currencies,
            "factor_eligible": True,
            "excess_return_usd": usd_returns,
            "excess_return": basket_returns,
            "carry_signal": np.arange(9),
            "value_signal": np.arange(9),
            "momentum_signal": np.arange(9),
        }
    )
    basket_factors, weights = construct_factors(panel, factor_config())
    raw_panel = panel.copy()
    raw_panel["excess_return"] = raw_panel["excess_return_usd"]
    raw_factors, _ = construct_factors(raw_panel, factor_config())

    assert np.isclose(basket_factors.loc[0, "dollar"], usd_returns[1:].mean())
    for factor in ("carry", "value", "momentum"):
        assert np.isclose(basket_factors.loc[0, factor], raw_factors.loc[0, factor])
    dollar_weights = weights[weights["factor"] == "dollar"]
    assert np.isclose(dollar_weights["weight"].sum(), 0.0)
    assert float(dollar_weights[dollar_weights["currency"] == "USD"]["weight"].iloc[0]) == -1.0


def test_loadings_recover_known_exposures() -> None:
    rng = np.random.default_rng(7)
    dates = pd.date_range("2010-01-31", periods=132, freq="ME")
    factor_returns = pd.DataFrame(
        {
            "date": dates,
            "dollar": rng.normal(0, 0.02, len(dates)),
            "carry": rng.normal(0, 0.02, len(dates)),
            "value": rng.normal(0, 0.02, len(dates)),
            "momentum": rng.normal(0, 0.02, len(dates)),
        }
    )
    y = (
        0.2 * factor_returns["dollar"]
        + 0.8 * factor_returns["carry"]
        - 0.4 * factor_returns["value"]
        + 0.25 * factor_returns["momentum"]
        + rng.normal(0, 0.001, len(dates))
    )
    panel = pd.DataFrame({"date": dates, "currency": "TST", "excess_return": y})
    full, rolling = estimate_loadings(panel, factor_returns, factor_config())
    assert abs(full.loc[0, "beta_carry"] - 0.8) < 0.03
    assert abs(full.loc[0, "beta_dollar"] - 0.2) < 0.03
    assert abs(full.loc[0, "beta_value"] + 0.4) < 0.03
    assert abs(full.loc[0, "beta_momentum"] - 0.25) < 0.03
    assert full.loc[0, "idio_variance_share"] < 0.02
    assert not rolling.empty
