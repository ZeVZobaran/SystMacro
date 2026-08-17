from __future__ import annotations

import json
import os
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
import requests


DATASETS = {
    "xru": ("xru_url", "WS_XRU_csv_flat.zip"),
    "eer": ("eer_url", "WS_EER_csv_flat.zip"),
    "policy": ("policy_url", "WS_CBPOL_csv_flat.zip"),
}


def _code(value: object) -> str:
    return str(value).split(":", 1)[0].strip()


def _month_end(values: pd.Series) -> pd.Series:
    return pd.PeriodIndex(values.astype(str), freq="M").to_timestamp("M")


def download_bis_archives(config: dict[str, Any], force: bool = False) -> dict[str, Path]:
    """Download BIS bulk archives with conditional HTTP requests and atomic writes."""
    raw_dir: Path = config["_raw_dir"]
    raw_dir.mkdir(parents=True, exist_ok=True)
    metadata_path = raw_dir / "download_metadata.json"
    metadata = json.loads(metadata_path.read_text("utf-8")) if metadata_path.exists() else {}
    output: dict[str, Path] = {}

    for dataset, (url_key, filename) in DATASETS.items():
        target = raw_dir / filename
        output[dataset] = target
        headers: dict[str, str] = {}
        prior = metadata.get(dataset, {})
        if target.exists() and not force:
            if prior.get("etag"):
                headers["If-None-Match"] = prior["etag"]
            if prior.get("last_modified"):
                headers["If-Modified-Since"] = prior["last_modified"]
            if not headers:
                continue

        url = config["data"][url_key]
        try:
            response_context = requests.get(
                url, headers=headers, stream=True, timeout=(20, 180)
            )
        except requests.RequestException as error:
            if target.exists() and not force:
                prior["checked_at_utc"] = datetime.now(timezone.utc).isoformat()
                prior["last_check_error"] = str(error)
                metadata[dataset] = prior
                continue
            raise
        with response_context as response:
            if response.status_code == 304:
                prior["checked_at_utc"] = datetime.now(timezone.utc).isoformat()
                prior.pop("last_check_error", None)
                metadata[dataset] = prior
                continue
            response.raise_for_status()
            file_descriptor, temp_name = tempfile.mkstemp(
                prefix=f".{filename}.", suffix=".part", dir=raw_dir
            )
            try:
                with os.fdopen(file_descriptor, "wb") as handle:
                    for block in response.iter_content(chunk_size=1024 * 1024):
                        if block:
                            handle.write(block)
                with zipfile.ZipFile(temp_name) as archive:
                    if not archive.namelist():
                        raise ValueError(f"Downloaded archive {dataset} is empty")
                    if archive.testzip() is not None:
                        raise ValueError(f"Downloaded archive {dataset} failed CRC validation")
                os.replace(temp_name, target)
            finally:
                if os.path.exists(temp_name):
                    os.unlink(temp_name)
            metadata[dataset] = {
                "url": url,
                "etag": response.headers.get("ETag"),
                "last_modified": response.headers.get("Last-Modified"),
                "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
                "checked_at_utc": datetime.now(timezone.utc).isoformat(),
                "bytes": target.stat().st_size,
            }

    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return output


def _csv_member(archive: zipfile.ZipFile) -> str:
    members = [name for name in archive.namelist() if name.lower().endswith(".csv")]
    if len(members) != 1:
        raise ValueError(f"Expected one CSV in BIS archive, found {len(members)}")
    return members[0]


def _read_filtered_chunks(
    path: Path,
    usecols: list[str],
    filter_fn,
    chunksize: int = 250_000,
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    with zipfile.ZipFile(path) as archive:
        with archive.open(_csv_member(archive)) as handle:
            for chunk in pd.read_csv(
                handle,
                usecols=usecols,
                dtype=str,
                chunksize=chunksize,
                low_memory=False,
            ):
                selected = filter_fn(chunk)
                if not selected.empty:
                    frames.append(selected.copy())
    if not frames:
        raise ValueError(f"No matching observations found in {path.name}")
    return pd.concat(frames, ignore_index=True)


def read_spot(path: Path, areas: Iterable[str], start_date: str) -> pd.DataFrame:
    cols = [
        "FREQ:Frequency",
        "REF_AREA:Reference area",
        "CURRENCY:Currency",
        "COLLECTION:Collection",
        "TIME_PERIOD:Time period or range",
        "OBS_VALUE:Observation Value",
    ]
    area_set = set(areas)

    def select(chunk: pd.DataFrame) -> pd.DataFrame:
        freq = chunk[cols[0]].map(_code)
        area = chunk[cols[1]].map(_code)
        collection = chunk[cols[3]].map(_code)
        return chunk[(freq == "M") & area.isin(area_set) & (collection == "E")]

    frame = _read_filtered_chunks(path, cols, select)
    frame = frame.rename(
        columns={cols[1]: "area", cols[2]: "currency", cols[4]: "date", cols[5]: "spot"}
    )
    frame["area"] = frame["area"].map(_code)
    frame["currency"] = frame["currency"].map(_code)
    frame["date"] = _month_end(frame["date"])
    frame["spot"] = pd.to_numeric(frame["spot"], errors="coerce")
    cutoff = pd.Period(start_date, freq="M").to_timestamp("M")
    return frame.loc[(frame["date"] >= cutoff) & (frame["spot"] > 0), ["date", "area", "currency", "spot"]]


def read_reer(path: Path, areas: Iterable[str], start_date: str) -> pd.DataFrame:
    cols = [
        "FREQ:Frequency",
        "EER_TYPE:Type",
        "EER_BASKET:Basket",
        "REF_AREA:Reference area",
        "TIME_PERIOD:Time period or range",
        "OBS_VALUE:Observation Value",
    ]
    area_set = set(areas)

    def select(chunk: pd.DataFrame) -> pd.DataFrame:
        freq = chunk[cols[0]].map(_code)
        kind = chunk[cols[1]].map(_code)
        basket = chunk[cols[2]].map(_code)
        area = chunk[cols[3]].map(_code)
        return chunk[(freq == "M") & (kind == "R") & (basket == "B") & area.isin(area_set)]

    frame = _read_filtered_chunks(path, cols, select)
    frame = frame.rename(columns={cols[3]: "area", cols[4]: "date", cols[5]: "reer"})
    frame["area"] = frame["area"].map(_code)
    frame["date"] = _month_end(frame["date"])
    frame["reer"] = pd.to_numeric(frame["reer"], errors="coerce")
    cutoff = pd.Period(start_date, freq="M").to_timestamp("M")
    return frame.loc[(frame["date"] >= cutoff) & (frame["reer"] > 0), ["date", "area", "reer"]]


def read_policy(path: Path, areas: Iterable[str], start_date: str) -> pd.DataFrame:
    cols = [
        "FREQ:Frequency",
        "REF_AREA:Reference area",
        "TIME_PERIOD:Time period or range",
        "OBS_VALUE:Observation Value",
    ]
    area_set = set(areas)

    def select(chunk: pd.DataFrame) -> pd.DataFrame:
        freq = chunk[cols[0]].map(_code)
        area = chunk[cols[1]].map(_code)
        return chunk[(freq == "M") & area.isin(area_set)]

    frame = _read_filtered_chunks(path, cols, select)
    frame = frame.rename(columns={cols[1]: "area", cols[2]: "date", cols[3]: "policy_rate"})
    frame["area"] = frame["area"].map(_code)
    frame["date"] = _month_end(frame["date"])
    frame["policy_rate"] = pd.to_numeric(frame["policy_rate"], errors="coerce")
    cutoff = pd.Period(start_date, freq="M").to_timestamp("M")
    return frame.loc[frame["date"] >= cutoff, ["date", "area", "policy_rate"]]


def build_market_panel(config: dict[str, Any], archives: dict[str, Path]) -> pd.DataFrame:
    universe = config["universe"]
    area_to_currency = {item["area"]: currency for currency, item in universe.items()}
    all_areas = set(area_to_currency)
    start = config["project"]["start_date"]

    spot = read_spot(archives["xru"], all_areas, start)
    reer = read_reer(archives["eer"], all_areas, start)
    rates = read_policy(archives["policy"], all_areas, start)
    spot["currency"] = spot["area"].map(area_to_currency)
    reer["currency"] = reer["area"].map(area_to_currency)
    rates["currency"] = rates["area"].map(area_to_currency)

    panel = spot[["date", "currency", "spot"]].merge(
        reer[["date", "currency", "reer"]], on=["date", "currency"], how="outer"
    )
    base_rates = rates[rates["currency"] == config["base_rate"]["currency"]][
        ["date", "policy_rate"]
    ].rename(columns={"policy_rate": "usd_policy_rate"})
    panel = panel.merge(
        rates[["date", "currency", "policy_rate"]],
        on=["date", "currency"],
        how="left",
    ).merge(base_rates, on="date", how="left")
    panel = panel.sort_values(["currency", "date"]).reset_index(drop=True)
    panel[["policy_rate", "usd_policy_rate"]] = panel.groupby("currency")[[
        "policy_rate", "usd_policy_rate"
    ]].ffill(limit=2)
    panel["market"] = panel["currency"].map(
        {currency: item["market"] for currency, item in universe.items()}
    )
    panel["factor_eligible"] = panel["currency"].map(
        {currency: bool(item.get("factor_eligible", True)) for currency, item in universe.items()}
    )
    return panel


def data_quality(panel: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    now = pd.Timestamp.now(tz="UTC").tz_localize(None)
    rows: list[dict[str, Any]] = []
    for currency, group in panel.groupby("currency"):
        row: dict[str, Any] = {"currency": currency, "observations": len(group)}
        for column in ("spot", "reer", "policy_rate"):
            valid = group.dropna(subset=[column])
            latest = valid["date"].max() if not valid.empty else pd.NaT
            row[f"latest_{column}"] = latest
            row[f"missing_{column}_pct"] = float(group[column].isna().mean())
            row[f"staleness_{column}_days"] = (
                int((now - latest).days) if pd.notna(latest) else np.nan
            )
        rows.append(row)
    quality = pd.DataFrame(rows).sort_values("currency")
    max_stale = config["data"]["max_monthly_staleness_days"]
    quality["status"] = np.where(
        quality[["staleness_spot_days", "staleness_reer_days", "staleness_policy_rate_days"]]
        .max(axis=1)
        .le(max_stale),
        "OK",
        "STALE",
    )
    return quality


def validate_panel(panel: pd.DataFrame, config: dict[str, Any]) -> None:
    expected = set(config["universe"])
    actual = set(panel["currency"].dropna().unique())
    if missing := expected - actual:
        raise ValueError(f"Currencies missing from market panel: {sorted(missing)}")
    duplicates = panel.duplicated(["date", "currency"]).sum()
    if duplicates:
        raise ValueError(f"Market panel contains {duplicates} duplicate date/currency rows")
    if (panel["spot"].dropna() <= 0).any() or (panel["reer"].dropna() <= 0).any():
        raise ValueError("Spot and REER levels must be strictly positive")
