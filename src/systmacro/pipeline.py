from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from .config import DEFAULT_CONFIG, load_config
from .data import build_market_panel, data_quality, download_bis_archives, validate_panel
from .factors import (
    FACTOR_NAMES,
    compute_currency_panel,
    construct_factors,
    estimate_loadings,
    factor_performance,
)
from .models import forecast_factors


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    copy = frame.copy()
    for column in copy.columns:
        if pd.api.types.is_datetime64_any_dtype(copy[column]):
            copy[column] = copy[column].dt.strftime("%Y-%m-%d")
    copy.to_csv(path, index=False, float_format="%.10g")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run_pipeline(
    config_path: Path | str = DEFAULT_CONFIG,
    refresh: bool = False,
) -> dict[str, Any]:
    config = load_config(config_path)
    processed_dir: Path = config["_processed_dir"]
    processed_dir.mkdir(parents=True, exist_ok=True)
    archives = download_bis_archives(config, force=refresh)
    market_panel = build_market_panel(config, archives)
    validate_panel(market_panel, config)
    quality = data_quality(market_panel, config)
    currency_panel = compute_currency_panel(market_panel, config)
    factor_returns, weights = construct_factors(currency_panel, config)
    loadings, rolling_loadings = estimate_loadings(currency_panel, factor_returns, config)
    forecasts = forecast_factors(factor_returns, config)
    performance = factor_performance(factor_returns)

    outputs = {
        "market_panel.csv": market_panel,
        "currency_panel.csv": currency_panel,
        "factor_returns.csv": factor_returns,
        "factor_weights.csv": weights,
        "factor_loadings.csv": loadings,
        "rolling_loadings.csv": rolling_loadings,
        "factor_forecasts.csv": forecasts,
        "factor_performance.csv": performance,
        "data_quality.csv": quality,
    }
    manifest: dict[str, Any] = {}
    for filename, frame in outputs.items():
        path = processed_dir / filename
        _write_csv(frame, path)
        manifest[filename] = {"rows": len(frame), "sha256": _sha256(path)}

    factor_dates = factor_returns.dropna(subset=list(FACTOR_NAMES))["date"]
    market_counts = pd.Series(
        {currency: item["market"] for currency, item in config["universe"].items()}
    ).value_counts()
    metadata = {
        "pipeline_version": "0.1.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "latest_market_date": market_panel["date"].max().strftime("%Y-%m-%d"),
        "latest_complete_factor_date": factor_dates.max().strftime("%Y-%m-%d"),
        "universe": list(config["universe"]),
        "universe_size": len(config["universe"]),
        "market_counts": {str(key): int(value) for key, value in market_counts.items()},
        "data_quote_currency": config["project"]["base_currency"],
        "analysis_numeraire": config["project"]["analysis_numeraire"],
        "data_provider": "Bank for International Settlements",
        "carry_proxy": "lagged central-bank policy rate; returns use basket-relative rate carry",
        "factor_names": list(FACTOR_NAMES),
        "files": manifest,
    }
    (processed_dir / "run_metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description="Update the SystMacro FX factor dataset")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--refresh", action="store_true", help="Force re-download of BIS archives")
    args = parser.parse_args()
    metadata = run_pipeline(args.config, refresh=args.refresh)
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
