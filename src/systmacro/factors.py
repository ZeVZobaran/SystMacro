from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import statsmodels.api as sm


STYLE_FACTOR_NAMES = ("carry", "value", "momentum")
FACTOR_NAMES = ("dollar", *STYLE_FACTOR_NAMES)


def compute_currency_panel(panel: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    """Compute investable currency returns and strictly lagged factor signals."""
    factor_cfg = config["factors"]
    currencies = list(config["universe"])

    def pivot(column: str) -> pd.DataFrame:
        return (
            panel.pivot(index="date", columns="currency", values=column)
            .sort_index()
            .reindex(columns=currencies)
        )

    spot = pivot("spot")
    reer = pivot("reer")
    policy = pivot("policy_rate")
    usd_policy = panel.groupby("date")["usd_policy_rate"].first().sort_index()

    spot_return_usd = -np.log(spot).diff()
    rate_differential = policy.sub(usd_policy, axis=0)
    carry_component_usd = rate_differential.shift(1) / 1200.0
    excess_return_usd = spot_return_usd + carry_component_usd

    basket_members = [
        currency
        for currency, item in config["universe"].items()
        if bool(item.get("factor_eligible", True))
    ]
    availability = excess_return_usd[basket_members].notna()
    basket_mean_excess = excess_return_usd[basket_members].mean(axis=1)
    basket_mean_spot = spot_return_usd[basket_members].where(availability).mean(axis=1)
    basket_mean_carry = carry_component_usd[basket_members].where(availability).mean(axis=1)
    excess_return = excess_return_usd.sub(basket_mean_excess, axis=0)
    spot_return = spot_return_usd.sub(basket_mean_spot, axis=0)
    carry_component = carry_component_usd.sub(basket_mean_carry, axis=0)

    # Absolute policy rates are the numeraire-free cross-sectional carry ranking.
    carry_signal = policy.shift(1)
    momentum_signal = (
        excess_return.rolling(
            int(factor_cfg["momentum_months"]),
            min_periods=int(factor_cfg["momentum_months"]),
        ).sum().shift(1)
    )
    lag = int(factor_cfg["value_lookback_months"])
    smooth = int(factor_cfg["value_smoothing_months"])
    historical_reer = reer.shift(lag - smooth).rolling(2 * smooth + 1).mean()
    value_signal = (np.log(historical_reer) - np.log(reer)).shift(1)

    variables = {
        "spot_lcu_per_usd": spot,
        "reer_2020_100": reer,
        "policy_rate_pct": policy,
        "spot_return_usd": spot_return_usd,
        "carry_component_usd": carry_component_usd,
        "excess_return_usd": excess_return_usd,
        "spot_return": spot_return,
        "carry_component": carry_component,
        "excess_return": excess_return,
        "carry_signal": carry_signal,
        "value_signal": value_signal,
        "momentum_signal": momentum_signal,
    }
    frames = []
    for name, wide in variables.items():
        frames.append(wide.stack(future_stack=True).rename(name))
    result = pd.concat(frames, axis=1).reset_index()
    result = result.rename(columns={"level_0": "date", "level_1": "currency"})
    result["market"] = result["currency"].map(
        {
            currency: item.get("market", "Unclassified")
            for currency, item in config["universe"].items()
        }
    )
    result["factor_eligible"] = result["currency"].map(
        {
            currency: bool(item.get("factor_eligible", True))
            for currency, item in config["universe"].items()
        }
    )
    return result.sort_values(["date", "currency"]).reset_index(drop=True)


def construct_factors(
    currency_panel: pd.DataFrame, config: dict[str, Any]
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build equal-weighted top-minus-bottom cross-sectional factor returns."""
    fraction = float(config["factors"]["leg_fraction"])
    minimum = int(config["factors"]["minimum_currencies"])
    reference_currency = config.get("project", {}).get("base_currency", "USD")
    factor_rows: list[dict[str, Any]] = []
    weight_rows: list[dict[str, Any]] = []

    for date, dated in currency_panel.groupby("date", sort=True):
        factor_row: dict[str, Any] = {"date": date}
        eligible_base = (
            dated[dated["factor_eligible"].fillna(False)]
            if "factor_eligible" in dated
            else dated
        )

        dollar_sample = eligible_base.dropna(subset=["excess_return"])
        usd = dollar_sample[dollar_sample["currency"] == reference_currency]
        foreign = dollar_sample[dollar_sample["currency"] != reference_currency]
        factor_row["n_dollar"] = len(foreign)
        if len(foreign) >= minimum - 1 and len(usd) == 1:
            usd_return = float(usd.iloc[0]["excess_return"])
            factor_row["dollar"] = float(foreign["excess_return"].mean() - usd_return)
            weight_rows.append(
                {
                    "date": date,
                    "factor": "dollar",
                    "currency": reference_currency,
                    "side": "short",
                    "rank_within_leg": 1,
                    "signal": np.nan,
                    "weight": -1.0,
                    "currency_return": usd_return,
                }
            )
            for rank, (_, observation) in enumerate(
                foreign.sort_values("currency").iterrows(), start=1
            ):
                weight_rows.append(
                    {
                        "date": date,
                        "factor": "dollar",
                        "currency": observation["currency"],
                        "side": "long",
                        "rank_within_leg": rank,
                        "signal": np.nan,
                        "weight": 1.0 / len(foreign),
                        "currency_return": observation["excess_return"],
                    }
                )
        else:
            factor_row["dollar"] = np.nan

        for factor in STYLE_FACTOR_NAMES:
            signal_column = f"{factor}_signal"
            eligible = eligible_base.dropna(
                subset=[signal_column, "excess_return"]
            ).sort_values([signal_column, "currency"], kind="mergesort")
            n_available = len(eligible)
            factor_row[f"n_{factor}"] = n_available
            if n_available < minimum:
                factor_row[factor] = np.nan
                continue
            leg_size = max(1, int(np.floor(n_available * fraction)))
            leg_size = min(leg_size, n_available // 2)
            short = eligible.head(leg_size)
            long = eligible.tail(leg_size)
            factor_row[factor] = float(long["excess_return"].mean() - short["excess_return"].mean())
            for side, subset, sign in (("short", short, -1.0), ("long", long, 1.0)):
                for rank, (_, observation) in enumerate(subset.iterrows(), start=1):
                    weight_rows.append(
                        {
                            "date": date,
                            "factor": factor,
                            "currency": observation["currency"],
                            "side": side,
                            "rank_within_leg": rank,
                            "signal": observation[signal_column],
                            "weight": sign / leg_size,
                            "currency_return": observation["excess_return"],
                        }
                    )
        factor_rows.append(factor_row)

    returns = pd.DataFrame(factor_rows).sort_values("date").reset_index(drop=True)
    weights = pd.DataFrame(weight_rows).sort_values(["date", "factor", "side", "rank_within_leg"])
    return returns, weights.reset_index(drop=True)


def _regression_metrics(
    joined: pd.DataFrame, hac_lags: int
) -> tuple[dict[str, float], np.ndarray]:
    y = joined["excess_return"].astype(float)
    x = sm.add_constant(joined[list(FACTOR_NAMES)].astype(float), has_constant="add")
    result = sm.OLS(y, x).fit(cov_type="HAC", cov_kwds={"maxlags": hac_lags})
    residuals = np.asarray(result.resid)
    metrics: dict[str, float] = {
        "alpha_annualized": float(result.params["const"] * 12),
        "alpha_tstat_hac": float(result.tvalues["const"]),
        "r_squared": float(result.rsquared),
        "idio_vol_annualized": float(np.std(residuals, ddof=len(result.params)) * np.sqrt(12)),
        "idio_variance_share": float(max(0.0, min(1.0, 1.0 - result.rsquared))),
        "observations": int(result.nobs),
    }
    for factor in FACTOR_NAMES:
        metrics[f"beta_{factor}"] = float(result.params[factor])
        metrics[f"tstat_{factor}_hac"] = float(result.tvalues[factor])
    return metrics, residuals


def estimate_loadings(
    currency_panel: pd.DataFrame,
    factor_returns: pd.DataFrame,
    config: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Estimate full-sample and rolling factor loadings with HAC inference."""
    settings = config["loadings"]
    window = int(settings["rolling_window_months"])
    minimum = int(settings["minimum_observations"])
    hac_lags = int(settings["hac_lags"])
    factors = factor_returns[["date", *FACTOR_NAMES]].dropna()
    full_rows: list[dict[str, Any]] = []
    rolling_rows: list[dict[str, Any]] = []

    for currency, observations in currency_panel.groupby("currency"):
        joined = observations[["date", "excess_return"]].merge(factors, on="date").dropna()
        if len(joined) >= minimum:
            metrics, _ = _regression_metrics(joined, hac_lags)
            metrics["currency"] = currency
            metrics["start_date"] = joined["date"].min()
            metrics["end_date"] = joined["date"].max()
            full_rows.append(metrics)
        for end in range(window - 1, len(joined)):
            sample = joined.iloc[end - window + 1 : end + 1]
            if len(sample) < minimum:
                continue
            metrics, _ = _regression_metrics(sample, hac_lags)
            metrics["currency"] = currency
            metrics["date"] = sample["date"].iloc[-1]
            rolling_rows.append(metrics)

    full = pd.DataFrame(full_rows).sort_values("currency").reset_index(drop=True)
    rolling = pd.DataFrame(rolling_rows).sort_values(["date", "currency"]).reset_index(drop=True)
    return full, rolling


def factor_performance(factor_returns: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for factor in FACTOR_NAMES:
        series = factor_returns.set_index("date")[factor].dropna()
        wealth = np.exp(series.cumsum())
        drawdown = wealth / wealth.cummax() - 1.0
        annual_return = float(series.mean() * 12)
        annual_vol = float(series.std(ddof=1) * np.sqrt(12))
        rows.append(
            {
                "factor": factor,
                "start_date": series.index.min(),
                "end_date": series.index.max(),
                "observations": len(series),
                "annualized_return": annual_return,
                "annualized_volatility": annual_vol,
                "sharpe_ratio": annual_return / annual_vol if annual_vol else np.nan,
                "maximum_drawdown": float(drawdown.min()),
                "latest_month_return": float(series.iloc[-1]),
            }
        )
    return pd.DataFrame(rows)
