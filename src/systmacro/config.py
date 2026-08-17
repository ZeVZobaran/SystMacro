from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "config" / "settings.toml"


def load_config(path: Path | str = DEFAULT_CONFIG) -> dict[str, Any]:
    """Load the project TOML configuration and attach resolved project paths."""
    path = Path(path).resolve()
    with path.open("rb") as handle:
        config = tomllib.load(handle)
    config["_root"] = ROOT
    config["_config_path"] = path
    config["_raw_dir"] = ROOT / config["data"]["raw_dir"]
    config["_processed_dir"] = ROOT / config["data"]["processed_dir"]
    return config

