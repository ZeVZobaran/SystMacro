"""Audit the live intersection of BIS FX, broad REER, and policy-rate data."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"


def code(series: pd.Series) -> pd.Series:
    return series.astype(str).str.split(":", n=1).str[0].str.strip()


def member(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        return next(name for name in archive.namelist() if name.lower().endswith(".csv"))


def filtered(path: Path, columns: list[str], predicate) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    with zipfile.ZipFile(path) as archive, archive.open(member(path)) as handle:
        for chunk in pd.read_csv(handle, usecols=columns, dtype=str, chunksize=250_000):
            selected = predicate(chunk)
            if not selected.empty:
                frames.append(selected)
    return pd.concat(frames, ignore_index=True)


def main() -> None:
    xru_columns = [
        "FREQ:Frequency",
        "REF_AREA:Reference area",
        "CURRENCY:Currency",
        "COLLECTION:Collection",
        "TIME_PERIOD:Time period or range",
        "OBS_VALUE:Observation Value",
    ]
    xru = filtered(
        RAW / "WS_XRU_csv_flat.zip",
        xru_columns,
        lambda frame: frame[
            (code(frame[xru_columns[0]]) == "M")
            & (code(frame[xru_columns[3]]) == "E")
            & frame[xru_columns[5]].notna()
        ],
    )
    xru["area"] = code(xru[xru_columns[1]])
    xru["area_name"] = xru[xru_columns[1]].str.split(":", n=1).str[-1].str.strip()
    xru["currency"] = code(xru[xru_columns[2]])
    xru["currency_name"] = xru[xru_columns[2]].str.split(":", n=1).str[-1].str.strip()
    xru["date"] = pd.to_datetime(xru[xru_columns[4]], format="%Y-%m")
    spot = (
        xru.groupby(["area", "area_name", "currency", "currency_name"], as_index=False)
        .agg(spot_start=("date", "min"), spot_end=("date", "max"), spot_n=("date", "size"))
        .sort_values(["area", "spot_end"], ascending=[True, False])
        .drop_duplicates("area")
    )

    eer_columns = [
        "FREQ:Frequency",
        "EER_TYPE:Type",
        "EER_BASKET:Basket",
        "REF_AREA:Reference area",
        "TIME_PERIOD:Time period or range",
        "OBS_VALUE:Observation Value",
    ]
    eer = filtered(
        RAW / "WS_EER_csv_flat.zip",
        eer_columns,
        lambda frame: frame[
            (code(frame[eer_columns[0]]) == "M")
            & (code(frame[eer_columns[1]]) == "R")
            & (code(frame[eer_columns[2]]) == "B")
            & frame[eer_columns[5]].notna()
        ],
    )
    eer["area"] = code(eer[eer_columns[3]])
    eer["date"] = pd.to_datetime(eer[eer_columns[4]], format="%Y-%m")
    reer = eer.groupby("area", as_index=False).agg(
        reer_start=("date", "min"), reer_end=("date", "max"), reer_n=("date", "size")
    )

    rate_columns = [
        "FREQ:Frequency",
        "REF_AREA:Reference area",
        "TIME_PERIOD:Time period or range",
        "OBS_VALUE:Observation Value",
    ]
    rate = filtered(
        RAW / "WS_CBPOL_csv_flat.zip",
        rate_columns,
        lambda frame: frame[
            (code(frame[rate_columns[0]]) == "M") & frame[rate_columns[3]].notna()
        ],
    )
    rate["area"] = code(rate[rate_columns[1]])
    rate["date"] = pd.to_datetime(rate[rate_columns[2]], format="%Y-%m")
    policy = rate.groupby("area", as_index=False).agg(
        policy_start=("date", "min"), policy_end=("date", "max"), policy_n=("date", "size")
    )

    coverage = spot.merge(reer, on="area").merge(policy, on="area")
    coverage["common_start"] = coverage[["spot_start", "reer_start", "policy_start"]].max(axis=1)
    coverage["common_end"] = coverage[["spot_end", "reer_end", "policy_end"]].min(axis=1)
    coverage["common_months"] = (
        (coverage["common_end"].dt.year - coverage["common_start"].dt.year) * 12
        + coverage["common_end"].dt.month
        - coverage["common_start"].dt.month
        + 1
    )
    coverage = coverage.sort_values(["common_end", "common_months"], ascending=[False, False])
    output = ROOT / "data" / "processed" / "bis_coverage_audit.csv"
    coverage.to_csv(output, index=False, date_format="%Y-%m-%d")
    print(coverage.to_string(index=False))
    print(f"\nWrote {output}")


if __name__ == "__main__":
    main()

