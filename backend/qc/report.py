"""단일 파일에 대한 QC 실행 및 리포트 조립."""
from __future__ import annotations

import copy
import os
from datetime import datetime, timezone
from typing import Optional

import pandas as pd
import yaml

from . import checks as checks_mod
from .loader import LoadedDataset
from .scorer import score_report

CONFIG_PATH = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "config", "default_rules.yaml"))

CHECK_FUNCS = {
    "missing_values": checks_mod.check_missing_values,
    "time_continuity": checks_mod.check_time_continuity,
    "range_check": checks_mod.check_range,
    "outliers": checks_mod.check_outliers,
    "metadata": checks_mod.check_metadata,
    "duplicates": checks_mod.check_duplicates,
}

CHECK_LABELS = {
    "missing_values": "결측치",
    "time_continuity": "시간 연속성",
    "range_check": "값의 범위",
    "outliers": "이상치",
    "metadata": "메타데이터",
    "duplicates": "중복/버전",
}


def load_default_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _deep_merge(base: dict, override: dict) -> dict:
    result = copy.deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(result.get(k), dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def merge_config(override: Optional[dict]) -> dict:
    base = load_default_config()
    if not override:
        return base
    return _deep_merge(base, override)


def _time_range(loaded: LoadedDataset) -> Optional[dict]:
    if loaded.kind == "netcdf" and loaded.time_dim and loaded.time_dim in loaded.ds.coords:
        vals = pd.to_datetime(loaded.ds[loaded.time_dim].values, errors="coerce")
    elif loaded.kind == "csv" and loaded.time_col:
        vals = pd.to_datetime(loaded.df[loaded.time_col], errors="coerce")
    else:
        return None
    vals = pd.Series(vals).dropna()
    if vals.empty:
        return None
    return {"start": str(vals.min()), "end": str(vals.max()), "count": int(len(vals))}


def _dataset_info(loaded: LoadedDataset) -> dict:
    if loaded.kind == "netcdf":
        ds = loaded.ds
        variables = [
            {
                "name": str(name), "dtype": str(da.dtype), "dims": [str(d) for d in da.dims],
                "shape": list(da.shape), "units": da.attrs.get("units"), "long_name": da.attrs.get("long_name"),
            }
            for name, da in ds.data_vars.items()
        ]
        return {
            "dims": {str(k): int(v) for k, v in ds.sizes.items()},
            "n_variables": len(ds.data_vars),
            "variables": variables,
            "global_attrs": {str(k): str(v) for k, v in list(ds.attrs.items())[:50]},
            "time_range": _time_range(loaded),
        }

    df = loaded.df
    return {
        "dims": {"rows": len(df), "columns": len(df.columns)},
        "n_variables": len(df.columns),
        "variables": [{"name": str(c), "dtype": str(df[c].dtype)} for c in df.columns],
        "global_attrs": {},
        "time_range": _time_range(loaded),
    }


def run_qc(loaded: LoadedDataset, config: Optional[dict] = None) -> dict:
    cfg = merge_config(config)

    checks_out = {}
    for key, func in CHECK_FUNCS.items():
        try:
            checks_out[key] = func(loaded, cfg)
        except Exception as exc:  # noqa: BLE001
            checks_out[key] = {"status": "fail", "message": f"검사 중 오류가 발생했습니다: {exc}"}

    score = score_report(checks_out, cfg)

    return {
        "filename": loaded.filename,
        "file_type": loaded.kind,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset_info": _dataset_info(loaded),
        "score": score,
        "checks": {k: {"label": CHECK_LABELS[k], **v} for k, v in checks_out.items()},
    }
