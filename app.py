from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "processed"
FACTORS = ["dollar", "carry", "value", "momentum"]
STYLE_FACTORS = ["carry", "value", "momentum"]
COLORS = {
    "dollar": "#22c55e",
    "carry": "#0ea5e9",
    "value": "#f59e0b",
    "momentum": "#a78bfa",
}


st.set_page_config(page_title="SystMacro FX Factors", page_icon="◈", layout="wide")
st.markdown(
    """
    <style>
    .block-container {padding-top: 1.4rem; max-width: 1500px;}
    [data-testid="stMetric"] {background: #101827; border: 1px solid #243247;
      padding: 14px; border-radius: 10px;}
    .small-note {color: #94a3b8; font-size: .86rem;}
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(show_spinner=False)
def load_outputs(metadata_mtime_ns: int) -> dict[str, object]:
    del metadata_mtime_ns  # Cache key: invalidates data when the weekly run completes.
    required = {
        "returns": "factor_returns.csv",
        "performance": "factor_performance.csv",
        "forecasts": "factor_forecasts.csv",
        "loadings": "factor_loadings.csv",
        "rolling": "rolling_loadings.csv",
        "weights": "factor_weights.csv",
        "currency": "currency_panel.csv",
        "quality": "data_quality.csv",
    }
    loaded: dict[str, object] = {}
    for key, filename in required.items():
        frame = pd.read_csv(DATA / filename)
        for column in frame.columns:
            if column == "date" or column.endswith("_date") or column == "training_end":
                frame[column] = pd.to_datetime(frame[column], errors="coerce")
        loaded[key] = frame
    loaded["metadata"] = json.loads((DATA / "run_metadata.json").read_text("utf-8"))
    return loaded


def percent(value: float) -> str:
    return "—" if pd.isna(value) else f"{value:.1%}"


def cumulative_figure(returns: pd.DataFrame) -> go.Figure:
    long = returns.melt("date", FACTORS, var_name="factor", value_name="return").dropna()
    long["index"] = long.groupby("factor")["return"].transform(lambda x: 100 * np.exp(x.cumsum()))
    figure = px.line(
        long,
        x="date",
        y="index",
        color="factor",
        color_discrete_map=COLORS,
        labels={"index": "Growth of 100", "date": "", "factor": ""},
    )
    figure.update_layout(hovermode="x unified", legend_orientation="h", height=440)
    return figure


def recent_style_returns_figure(returns: pd.DataFrame) -> go.Figure:
    """Show the latest 12 monthly, non-cumulative style-factor returns."""
    recent = returns.dropna(subset=STYLE_FACTORS, how="all").tail(12)
    long = recent.melt(
        "date", STYLE_FACTORS, var_name="factor", value_name="return"
    ).dropna()
    long["month"] = long["date"].dt.strftime("%b")
    long["month_year"] = long["date"].dt.strftime("%b %Y")
    month_order = recent["date"].dt.strftime("%b").tolist()
    long["return_pct"] = 100.0 * long["return"]
    long["factor"] = long["factor"].str.title()
    figure = px.bar(
        long,
        x="month",
        y="return_pct",
        color="factor",
        barmode="group",
        color_discrete_map={factor.title(): COLORS[factor] for factor in STYLE_FACTORS},
        category_orders={"month": month_order},
        custom_data=["month_year"],
        labels={"return_pct": "Monthly return (%)", "month": "", "factor": ""},
    )
    figure.add_hline(y=0, line_width=1, line_color="#64748b")
    figure.update_traces(
        hovertemplate="%{customdata[0]}<br>%{fullData.name}: %{y:.2f}%<extra></extra>"
    )
    figure.update_layout(
        height=390,
        hovermode="x unified",
        legend_orientation="h",
        bargap=0.18,
        bargroupgap=0.06,
    )
    return figure


def forecast_figure(returns: pd.DataFrame, forecasts: pd.DataFrame, factor: str) -> go.Figure:
    history = returns[["date", factor]].dropna().tail(72)
    projected = forecasts[forecasts["factor"] == factor].sort_values("date")
    figure = go.Figure()
    figure.add_trace(
        go.Scatter(x=history["date"], y=history[factor], name="Realized", line=dict(color=COLORS[factor]))
    )
    figure.add_trace(
        go.Scatter(
            x=pd.concat([projected["date"], projected["date"].iloc[::-1]]),
            y=pd.concat([projected["upper_95"], projected["lower_95"].iloc[::-1]]),
            fill="toself",
            fillcolor="rgba(148,163,184,.12)",
            line=dict(color="rgba(0,0,0,0)"),
            hoverinfo="skip",
            name="95% interval",
        )
    )
    figure.add_trace(
        go.Scatter(
            x=pd.concat([projected["date"], projected["date"].iloc[::-1]]),
            y=pd.concat([projected["upper_80"], projected["lower_80"].iloc[::-1]]),
            fill="toself",
            fillcolor="rgba(14,165,233,.18)",
            line=dict(color="rgba(0,0,0,0)"),
            hoverinfo="skip",
            name="80% interval",
        )
    )
    figure.add_trace(
        go.Scatter(
            x=projected["date"], y=projected["forecast"], name="ARMA forecast",
            line=dict(color="#f8fafc", dash="dash")
        )
    )
    figure.add_hline(y=0, line_width=1, line_color="#64748b")
    figure.update_layout(
        height=420,
        hovermode="x unified",
        legend_orientation="h",
        yaxis_tickformat=".1%",
        xaxis_title="",
        yaxis_title="Monthly log excess return",
    )
    return figure


st.title("SystMacro · FX factor monitor")
st.caption("29 currencies · explicit USD · equal-weight basket numeraire · monthly factors · weekly refresh")

try:
    data = load_outputs((DATA / "run_metadata.json").stat().st_mtime_ns)
except FileNotFoundError:
    st.error("Processed data are missing. Run `python -m systmacro.pipeline --refresh` first.")
    st.stop()

returns: pd.DataFrame = data["returns"]  # type: ignore[assignment]
performance: pd.DataFrame = data["performance"]  # type: ignore[assignment]
forecasts: pd.DataFrame = data["forecasts"]  # type: ignore[assignment]
loadings: pd.DataFrame = data["loadings"]  # type: ignore[assignment]
rolling: pd.DataFrame = data["rolling"]  # type: ignore[assignment]
weights: pd.DataFrame = data["weights"]  # type: ignore[assignment]
currency_panel: pd.DataFrame = data["currency"]  # type: ignore[assignment]
quality: pd.DataFrame = data["quality"]  # type: ignore[assignment]
metadata: dict = data["metadata"]  # type: ignore[assignment]
market_map = (
    currency_panel[["currency", "market"]].drop_duplicates().set_index("currency")["market"]
)
loadings["market"] = loadings["currency"].map(market_map)
rolling["market"] = rolling["currency"].map(market_map)

with st.sidebar:
    st.subheader("Run status")
    st.success(f"Latest factor month: {metadata['latest_complete_factor_date']}")
    st.caption(f"Built {pd.Timestamp(metadata['generated_at_utc']).strftime('%Y-%m-%d %H:%M UTC')}")
    st.markdown("**Universe**")
    st.write(
        f"{metadata['universe_size']} currencies · "
        f"{metadata['market_counts'].get('DM', 0)} DM · {metadata['market_counts'].get('EM', 0)} EM"
    )
    with st.expander("Currency list"):
        st.write(" · ".join(metadata["universe"]))
    st.markdown("**Analysis numeraire**")
    st.caption("Equal-weight basket of available eligible currencies; USD is an explicit member.")
    st.markdown("**Carry input**")
    st.caption(metadata["carry_proxy"])
    st.info("Research output only. It is not an investment recommendation.")

overview_tab, forecast_tab, exposure_tab, usd_tab, signals_tab, method_tab = st.tabs(
    ["Overview", "Forecasts", "Currency exposures", "USD & numeraire", "Signals & data", "Methodology"]
)

with overview_tab:
    latest = performance.set_index("factor")
    columns = st.columns(4)
    for column, factor in zip(columns, FACTORS):
        with column:
            st.metric(
                factor.title(),
                percent(latest.loc[factor, "annualized_return"]),
            )
            st.caption(
                f"Sharpe {latest.loc[factor, 'sharpe_ratio']:.2f} · "
                f"Vol {percent(latest.loc[factor, 'annualized_volatility'])} · "
                f"Max DD {percent(latest.loc[factor, 'maximum_drawdown'])}"
            )
    st.info(
        "**How to read this chart:** each line is an idealized standalone factor sleeve, "
        "compounded from monthly log excess returns and indexed to 100. Carry, value and "
        "momentum are +100% the top signal tercile and -100% the bottom signal tercile; "
        "dollar is +100% the foreign-currency basket and -100% USD. The sleeves are not "
        "hedged against one another, so incidental cross-factor exposure remains. Gross "
        "exposure is about 200%, and trading costs and implementation constraints are excluded."
    )
    st.plotly_chart(cumulative_figure(returns), width="stretch")

    st.subheader("Recent standalone style-factor returns")
    st.caption(
        f"Latest 12 monthly observations through {returns['date'].max():%B %Y} "
        "(weekly inputs are not available). Each bar is that "
        "month's non-cumulative return for an equal-weight top-tercile minus bottom-tercile "
        "portfolio. The dollar factor is excluded because it is foreign basket minus USD, "
        "not a ranked top-minus-bottom portfolio."
    )
    st.plotly_chart(recent_style_returns_figure(returns), width="stretch")
    display_performance = performance[
        ["factor", "start_date", "end_date", "observations", "annualized_return", "annualized_volatility", "sharpe_ratio", "maximum_drawdown"]
    ].copy()
    st.dataframe(
        display_performance.style.format(
            {"annualized_return": "{:.2%}", "annualized_volatility": "{:.2%}", "sharpe_ratio": "{:.2f}", "maximum_drawdown": "{:.2%}"}
        ),
        width="stretch",
        hide_index=True,
    )

with forecast_tab:
    factor = st.segmented_control("Factor", FACTORS, default="carry") or "carry"
    selected = forecasts[forecasts["factor"] == factor].iloc[0]
    st.caption(
        f"AIC-selected ARMA({int(selected['ar_order'])},{int(selected['ma_order'])}); "
        f"12-month point forecasts and 80%/95% model-based prediction intervals."
    )
    st.plotly_chart(forecast_figure(returns, forecasts, factor), width="stretch")
    table = forecasts[forecasts["factor"] == factor][
        ["date", "forecast", "lower_80", "upper_80", "lower_95", "upper_95"]
    ]
    st.dataframe(
        table.style.format({column: "{:.2%}" for column in table.columns if column != "date"}),
        hide_index=True,
        width="stretch",
    )

with exposure_tab:
    st.subheader("Full-sample factor loadings")
    st.caption(
        "USD's near-unit negative dollar beta and near-zero residual share are mechanical because USD is the short leg of the dollar factor."
    )
    market_filter = st.segmented_control(
        "Market group", ["All", "DM", "EM"], default="All"
    ) or "All"
    filtered_loadings = (
        loadings if market_filter == "All" else loadings[loadings["market"] == market_filter]
    )
    beta_columns = [f"beta_{factor}" for factor in FACTORS]
    heat = filtered_loadings.set_index("currency")[beta_columns].rename(
        columns=lambda x: x.replace("beta_", "")
    )
    figure = px.imshow(
        heat,
        text_auto=".2f",
        aspect="auto",
        color_continuous_scale="RdBu",
        color_continuous_midpoint=0,
        labels={"color": "Beta"},
    )
    figure.update_layout(height=430, xaxis_title="", yaxis_title="")
    st.plotly_chart(figure, width="stretch")
    display = filtered_loadings[[
        "currency", "market", *beta_columns, "alpha_annualized", "r_squared", "idio_vol_annualized", "idio_variance_share", "observations"
    ]]
    st.dataframe(
        display.style.format(
            {**{column: "{:.2f}" for column in beta_columns}, "alpha_annualized": "{:.2%}", "r_squared": "{:.1%}", "idio_vol_annualized": "{:.2%}", "idio_variance_share": "{:.1%}"}
        ),
        hide_index=True,
        width="stretch",
    )
    rolling_choices = sorted(filtered_loadings["currency"].unique())
    currency = st.selectbox("Rolling 60-month detail", rolling_choices)
    selected = rolling[rolling["currency"] == currency]
    load_long = selected.melt("date", beta_columns, var_name="factor", value_name="beta")
    load_long["factor"] = load_long["factor"].str.replace("beta_", "")
    beta_chart = px.line(load_long, x="date", y="beta", color="factor", color_discrete_map=COLORS)
    beta_chart.update_layout(height=360, hovermode="x unified", legend_orientation="h", xaxis_title="", yaxis_title="Rolling beta")
    st.plotly_chart(beta_chart, width="stretch")
    idio_chart = px.area(selected, x="date", y="idio_variance_share")
    idio_chart.update_layout(height=280, yaxis_tickformat=".0%", xaxis_title="", yaxis_title="Idiosyncratic variance share")
    st.plotly_chart(idio_chart, width="stretch")

with usd_tab:
    st.subheader("USD as an explicit currency")
    st.caption(
        "The green dollar factor is long an equal-weight foreign basket and short USD; a positive return means broad USD weakness. "
        "The blue series is USD's own return against the symmetric basket, so a positive return means USD strength."
    )
    usd_returns = currency_panel[currency_panel["currency"] == "USD"][["date", "excess_return"]].dropna()
    dollar_returns = returns[["date", "dollar"]].dropna()
    usd_compare = dollar_returns.merge(usd_returns, on="date", how="inner")
    usd_compare["Foreign basket vs USD"] = 100 * np.exp(usd_compare["dollar"].cumsum())
    usd_compare["USD vs equal-weight basket"] = 100 * np.exp(usd_compare["excess_return"].cumsum())
    usd_long = usd_compare.melt(
        "date",
        ["Foreign basket vs USD", "USD vs equal-weight basket"],
        var_name="series",
        value_name="index",
    )
    usd_figure = px.line(
        usd_long,
        x="date",
        y="index",
        color="series",
        color_discrete_map={
            "Foreign basket vs USD": COLORS["dollar"],
            "USD vs equal-weight basket": COLORS["carry"],
        },
    )
    usd_figure.update_layout(
        height=430,
        hovermode="x unified",
        legend_orientation="h",
        xaxis_title="",
        yaxis_title="Growth of 100",
    )
    st.plotly_chart(usd_figure, width="stretch")
    latest_usd = currency_panel[currency_panel["currency"] == "USD"].dropna(
        subset=["excess_return"]
    ).tail(1)
    latest_dollar = returns.dropna(subset=["dollar"]).tail(1)
    metric_columns = st.columns(3)
    metric_columns[0].metric(
        "Latest USD basket return", percent(float(latest_usd.iloc[0]["excess_return"]))
    )
    metric_columns[1].metric(
        "Latest dollar-factor return", percent(float(latest_dollar.iloc[0]["dollar"]))
    )
    metric_columns[2].metric(
        "USD policy rate", f"{float(latest_usd.iloc[0]['policy_rate_pct']):.2f}%"
    )
    st.subheader("Numeraire choices")
    st.dataframe(
        pd.DataFrame(
            [
                ["USD bilateral", "Investor-facing and tradable", "USD is implicit in every series"],
                ["Equal-weight basket", "Symmetric; USD becomes observable", "Basket composition changes with coverage"],
                ["Trade-weighted / SDR", "Economically weighted", "External weights and periodic rebalancing"],
                ["Pairwise / network", "Fully numeraire-free", "High dimensional and less transparent"],
            ],
            columns=["Method", "Strength", "Cost"],
        ),
        hide_index=True,
        width="stretch",
    )

with signals_tab:
    latest_weight_date = weights["date"].max()
    st.subheader(f"Latest portfolio membership · {latest_weight_date:%B %Y}")
    latest_weights = weights[weights["date"] == latest_weight_date][
        ["factor", "currency", "side", "signal", "weight", "currency_return"]
    ]
    st.dataframe(
        latest_weights.style.format({"signal": "{:.3f}", "weight": "{:.1%}", "currency_return": "{:.2%}"}),
        hide_index=True,
        width="stretch",
    )
    st.subheader("Latest raw signals")
    latest_currency_date = currency_panel["date"].max()
    latest_signals = currency_panel[currency_panel["date"] == latest_currency_date][
        [
            "currency", "market", "spot_lcu_per_usd", "reer_2020_100", "policy_rate_pct",
            "excess_return_usd", "excess_return", "carry_signal", "value_signal", "momentum_signal"
        ]
    ]
    st.dataframe(latest_signals, hide_index=True, width="stretch")
    st.subheader("Data quality")
    stale = int((quality["status"] != "OK").sum())
    if stale:
        st.warning(f"{stale} currency series have a stale input according to the configured threshold.")
    else:
        st.success("All currencies pass the configured recency checks.")
    st.dataframe(quality, hide_index=True, width="stretch")

with method_tab:
    methodology = (ROOT / "docs" / "METHODOLOGY.md").read_text("utf-8")
    st.markdown(methodology)
