"""개별 QC 체크 항목 구현.

모든 체크 함수는 (LoadedDataset, config: dict) -> dict 형태의 시그니처를 가지며,
{"status": "pass" | "warning" | "fail" | "skipped", ...세부정보} 를 반환한다.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from .loader import LoadedDataset

STATUS_ORDER = {"pass": 0, "skipped": 0, "warning": 1, "fail": 2}


# ---------------------------------------------------------------------------
# 공통 헬퍼
# ---------------------------------------------------------------------------

def _iter_numeric_vars(loaded: LoadedDataset):
    if loaded.kind == "netcdf":
        for name, da in loaded.ds.data_vars.items():
            lname = str(name).lower()
            if lname.endswith("_bnds") or "bounds" in lname:
                continue
            if not np.issubdtype(da.dtype, np.number):
                continue
            yield name, da
    else:
        for col in loaded.df.columns:
            if col == loaded.time_col:
                continue
            if pd.api.types.is_numeric_dtype(loaded.df[col]):
                yield col, loaded.df[col]


def _values_of(arr) -> np.ndarray:
    raw = arr.values if hasattr(arr, "values") else np.asarray(arr)
    return np.asarray(raw, dtype="float64").ravel()


def _status_from_ratio(ratio: float, warn: float, fail: float) -> str:
    if ratio >= fail:
        return "fail"
    if ratio >= warn:
        return "warning"
    return "pass"


def _worst_status(statuses: List[str]) -> str:
    real = [s for s in statuses if s != "skipped"]
    if not real:
        return "skipped" if statuses else "skipped"
    return max(real, key=lambda s: STATUS_ORDER.get(s, 0))


def _match_rule_kv(name, rules: Dict) -> Tuple[Optional[str], Optional[dict]]:
    if not rules:
        return None, None
    lname = str(name).lower()
    if lname in rules:
        return lname, rules[lname]
    candidates = [(k, v) for k, v in rules.items() if k in lname or lname in k]
    if not candidates:
        return None, None
    candidates.sort(key=lambda kv: -len(kv[0]))
    return candidates[0]


def _match_rule(name, rules: Dict) -> Optional[dict]:
    return _match_rule_kv(name, rules)[1]


def _match_rule_key(name, rules: Dict) -> Optional[str]:
    return _match_rule_kv(name, rules)[0]


def _human_duration(seconds: float) -> str:
    seconds = float(seconds)
    if seconds < 60:
        return f"{seconds:.0f}초"
    minutes = seconds / 60
    if minutes < 60:
        return f"{minutes:.0f}분"
    hours = minutes / 60
    if hours < 24:
        return f"{hours:.1f}시간"
    days = hours / 24
    return f"{days:.1f}일"


def _time_axis(loaded: LoadedDataset) -> Optional[np.ndarray]:
    if loaded.kind == "netcdf" and loaded.time_dim and loaded.time_dim in loaded.ds.coords:
        return pd.to_datetime(loaded.ds[loaded.time_dim].values, errors="coerce").to_numpy()
    if loaded.kind == "csv" and loaded.time_col:
        return pd.to_datetime(loaded.df[loaded.time_col], errors="coerce").to_numpy()
    return None


def _time_missing_series(loaded: LoadedDataset, arr) -> Optional[np.ndarray]:
    if loaded.kind == "netcdf":
        if loaded.time_dim and loaded.time_dim in getattr(arr, "dims", ()):
            other_dims = [d for d in arr.dims if d != loaded.time_dim]
            try:
                series = arr.isnull().mean(dim=other_dims) if other_dims else arr.isnull().astype(float)
                return np.asarray(series.values, dtype="float64")
            except Exception:  # noqa: BLE001
                return None
        return None
    if loaded.time_col:
        return arr.isna().astype(float).to_numpy()
    return None


def _build_missing_heatmap(loaded: LoadedDataset, candidates, max_vars=12, max_buckets=40) -> Optional[dict]:
    if not candidates:
        return None
    time_axis = _time_axis(loaded)
    if time_axis is None or len(time_axis) == 0:
        return None
    n = len(time_axis)
    candidates = [c for c in candidates if len(c[2]) == n]
    if not candidates:
        return None
    candidates = sorted(candidates, key=lambda c: -c[1])[:max_vars]

    n_buckets = max(1, min(max_buckets, n))
    edges = np.linspace(0, n, n_buckets + 1).astype(int)
    valid_time = pd.Series(time_axis)
    labels = []
    for i in range(n_buckets):
        s, e = edges[i], max(edges[i + 1], edges[i] + 1)
        mid = min(s + (e - s) // 2, n - 1)
        t = valid_time.iloc[mid]
        labels.append(t.strftime("%Y-%m-%d %H:%M") if pd.notna(t) else f"idx{mid}")

    variables, matrix = [], []
    for name, _ratio, series in candidates:
        row = []
        for i in range(n_buckets):
            s, e = edges[i], max(edges[i + 1], edges[i] + 1)
            seg = series[s:e]
            row.append(float(np.nanmean(seg)) if len(seg) else 0.0)
        matrix.append(row)
        variables.append(str(name))

    return {"time_labels": labels, "variables": variables, "matrix": matrix}


def _summarize_counts(items: List[dict]) -> dict:
    total = len(items)
    counts = {"pass": 0, "warning": 0, "fail": 0}
    for it in items:
        counts[it["status"]] = counts.get(it["status"], 0) + 1
    avg_ratio = float(np.mean([it["ratio"] for it in items])) if items else 0.0
    return {"total_variables": total, **counts, "avg_ratio": avg_ratio}


# ---------------------------------------------------------------------------
# 1. 결측치 검사
# ---------------------------------------------------------------------------

def check_missing_values(loaded: LoadedDataset, cfg: dict) -> dict:
    thr = cfg["thresholds"]["missing"]
    warn, fail = thr["warning"], thr["fail"]

    items, heatmap_candidates = [], []
    for name, arr in _iter_numeric_vars(loaded):
        values = _values_of(arr)
        total = values.size
        if total == 0:
            continue
        missing = int(np.isnan(values).sum())
        ratio = missing / total
        status = _status_from_ratio(ratio, warn, fail)
        items.append({"variable": str(name), "total": total, "missing": missing, "ratio": ratio, "status": status})

        ts = _time_missing_series(loaded, arr)
        if ts is not None:
            heatmap_candidates.append((str(name), ratio, ts))

    items.sort(key=lambda x: -x["ratio"])
    overall_status = _worst_status([i["status"] for i in items]) if items else "skipped"

    return {
        "status": overall_status,
        "summary": _summarize_counts(items),
        "variables": items,
        "heatmap": _build_missing_heatmap(loaded, heatmap_candidates),
    }


# ---------------------------------------------------------------------------
# 2. 시간 연속성 검사
# ---------------------------------------------------------------------------

def check_time_continuity(loaded: LoadedDataset, cfg: dict) -> dict:
    tcfg = cfg["thresholds"]["time_gap"]
    time_axis = _time_axis(loaded)
    if time_axis is None:
        return {"status": "skipped", "message": "시간 좌표/컬럼을 찾을 수 없어 연속성 검사를 건너뜁니다.", "gaps": []}

    t = pd.Series(time_axis).dropna()
    t = pd.Series(sorted(t.unique()))
    if len(t) < 2:
        return {"status": "skipped", "message": "시간 값이 2개 미만이라 연속성 검사를 수행할 수 없습니다.", "gaps": []}

    diffs = t.diff().dropna().dt.total_seconds()
    diffs = diffs[diffs > 0]
    if diffs.empty:
        return {"status": "skipped", "message": "시간 간격을 계산할 수 없습니다(중복 타임스탬프?).", "gaps": []}

    expected = float(diffs.median())
    tolerance = expected * tcfg["tolerance_factor"]

    gaps = []
    missing_points_total = 0
    for i in range(1, len(t)):
        gap_sec = (t.iloc[i] - t.iloc[i - 1]).total_seconds()
        if gap_sec > tolerance:
            missing_n = max(int(round(gap_sec / expected)) - 1, 1)
            missing_points_total += missing_n
            gaps.append({
                "start": str(t.iloc[i - 1]),
                "end": str(t.iloc[i]),
                "actual_gap_sec": gap_sec,
                "actual_gap_human": _human_duration(gap_sec),
                "missing_points": missing_n,
            })

    total_span_sec = (t.iloc[-1] - t.iloc[0]).total_seconds()
    expected_points = int(round(total_span_sec / expected)) + 1 if expected > 0 else len(t)
    ratio = missing_points_total / expected_points if expected_points else 0.0

    n_gaps = len(gaps)
    if n_gaps == 0:
        status = "pass"
    elif n_gaps >= tcfg["fail_gaps"] or ratio >= tcfg["fail_ratio"]:
        status = "fail"
    elif n_gaps >= tcfg["warning_gaps"]:
        status = "warning"
    else:
        status = "pass"

    return {
        "status": status,
        "expected_interval_sec": expected,
        "expected_interval_human": _human_duration(expected),
        "n_timestamps": int(len(t)),
        "expected_points": expected_points,
        "missing_points": missing_points_total,
        "ratio": ratio,
        "n_gaps_total": n_gaps,
        "gaps": gaps[:200],
    }


# ---------------------------------------------------------------------------
# 3. 값의 범위 검사
# ---------------------------------------------------------------------------

def check_range(loaded: LoadedDataset, cfg: dict) -> dict:
    thr = cfg["thresholds"]["range"]
    warn, fail = thr["warning"], thr["fail"]
    rules = cfg.get("variable_ranges", {})

    items, unmatched = [], []
    for name, arr in _iter_numeric_vars(loaded):
        rule = _match_rule(name, rules)
        if rule is None:
            unmatched.append(str(name))
            continue
        values = _values_of(arr)
        valid = values[~np.isnan(values)]
        if valid.size == 0:
            continue
        vmin, vmax = rule["min"], rule["max"]
        out_of_range = int(np.sum((valid < vmin) | (valid > vmax)))
        ratio = out_of_range / valid.size
        status = _status_from_ratio(ratio, warn, fail)
        items.append({
            "variable": str(name), "min": vmin, "max": vmax, "unit": rule.get("unit"),
            "total": int(valid.size), "out_of_range": out_of_range, "ratio": ratio, "status": status,
            "observed_min": float(np.min(valid)), "observed_max": float(np.max(valid)),
        })

    if not items:
        return {
            "status": "skipped",
            "message": "설정된 범위 규칙과 일치하는 변수가 없습니다. 설정 패널에서 변수별 범위를 추가해보세요.",
            "variables": [], "unmatched_variables": unmatched,
        }

    overall = _worst_status([i["status"] for i in items])
    return {"status": overall, "variables": items, "unmatched_variables": unmatched}


# ---------------------------------------------------------------------------
# 4. 이상치 검사
# ---------------------------------------------------------------------------

def check_outliers(loaded: LoadedDataset, cfg: dict) -> dict:
    ocfg = cfg["thresholds"]["outlier"]
    warn, fail = ocfg["warning"], ocfg["fail"]
    method = ocfg.get("method", "zscore")

    items = []
    for name, arr in _iter_numeric_vars(loaded):
        values = _values_of(arr)
        valid = values[~np.isnan(values)]
        if valid.size < 5:
            continue
        if method == "iqr":
            q1, q3 = np.percentile(valid, [25, 75])
            iqr = q3 - q1
            mult = ocfg.get("iqr_multiplier", 1.5)
            lo, hi = q1 - mult * iqr, q3 + mult * iqr
            n_out = int(np.sum((valid < lo) | (valid > hi)))
        else:
            std = float(np.std(valid))
            if std == 0:
                n_out = 0
            else:
                z = np.abs((valid - np.mean(valid)) / std)
                n_out = int(np.sum(z > ocfg.get("zscore_threshold", 3.0)))
        ratio = n_out / valid.size
        status = _status_from_ratio(ratio, warn, fail)
        items.append({
            "variable": str(name), "method": method, "total": int(valid.size),
            "outliers": n_out, "ratio": ratio, "status": status,
        })

    if not items:
        return {"status": "skipped", "message": "이상치를 계산할 수 있는 수치형 변수가 없습니다.", "variables": [], "method": method}

    overall = _worst_status([i["status"] for i in items])
    return {"status": overall, "method": method, "variables": items}


# ---------------------------------------------------------------------------
# 5. 메타데이터 검증
# ---------------------------------------------------------------------------

def check_metadata(loaded: LoadedDataset, cfg: dict) -> dict:
    mrules = cfg.get("metadata_rules", {})
    wcfg = cfg["thresholds"]["metadata"]
    checks: List[dict] = []
    note = None

    if loaded.kind == "netcdf":
        ds = loaded.ds
        for attr in mrules.get("required_global_attrs", []):
            checks.append({"item": f"전역 속성 '{attr}' 존재 여부", "passed": attr in ds.attrs})

        prefix = mrules.get("cf_convention_prefix", "CF-")
        conv = str(ds.attrs.get("Conventions", ""))
        checks.append({"item": f"CF Convention 준수 (Conventions 속성에 '{prefix}' 포함)", "passed": prefix in conv})

        expected_units = mrules.get("expected_units", {})
        for name, da in ds.data_vars.items():
            for attr in mrules.get("required_var_attrs", []):
                checks.append({"item": f"변수 '{name}'.{attr} 속성 존재", "passed": attr in da.attrs})
            rule_key = _match_rule_key(name, expected_units)
            if rule_key:
                unit_val = str(da.attrs.get("units", "")).lower().strip()
                allowed = [u.lower() for u in expected_units[rule_key]]
                checks.append({
                    "item": f"변수 '{name}' 단위 확인 (기대: {expected_units[rule_key]}, 실제: '{da.attrs.get('units', '(없음)')}')",
                    "passed": unit_val in allowed,
                })
    else:
        for col in loaded.df.columns:
            if col == loaded.time_col:
                continue
            checks.append({"item": f"컬럼 '{col}' 존재", "passed": True})
        note = "CSV 파일은 단위·좌표계 등 메타데이터가 없어 검증 범위가 제한적입니다 (컬럼 존재 여부만 확인)."

    total = len(checks)
    passed = sum(1 for c in checks if c["passed"])
    ratio = passed / total if total else 1.0

    if total == 0:
        status = "skipped"
    elif ratio < wcfg["fail"]:
        status = "fail"
    elif ratio < wcfg["warning"]:
        status = "warning"
    else:
        status = "pass"

    return {
        "status": status, "compliance_ratio": ratio, "total_checks": total,
        "passed_checks": passed, "checks": checks[:300], "note": note,
    }


# ---------------------------------------------------------------------------
# 6. 중복 검사
# ---------------------------------------------------------------------------

def check_duplicates(loaded: LoadedDataset, cfg: dict) -> dict:
    dcfg = cfg["thresholds"]["duplicates"]
    warn, fail = dcfg["warning"], dcfg["fail"]

    if loaded.kind == "netcdf":
        if loaded.time_dim and loaded.time_dim in loaded.ds.coords:
            tvals = pd.to_datetime(loaded.ds[loaded.time_dim].values, errors="coerce")
            total = len(tvals)
            if total == 0:
                return {"status": "skipped", "message": "시간 좌표가 비어 있습니다."}
            dup = int(total - pd.Index(tvals).nunique())
            ratio = dup / total
            status = _status_from_ratio(ratio, warn, fail)
            return {"status": status, "type": "timestamp", "total": total, "duplicates": dup, "ratio": ratio}
        return {"status": "skipped", "message": "시간 좌표가 없어 중복 검사를 건너뜁니다."}

    df = loaded.df
    total_rows = len(df)
    if total_rows == 0:
        return {"status": "skipped", "message": "데이터가 비어 있습니다."}
    dup_rows = int(df.duplicated().sum())
    ratio_rows = dup_rows / total_rows
    out = {"total": total_rows, "duplicate_rows": dup_rows, "row_ratio": ratio_rows}
    worst_ratio = ratio_rows

    if loaded.time_col:
        dup_time = int(df[loaded.time_col].duplicated().sum())
        ratio_time = dup_time / total_rows
        out["duplicate_timestamps"] = dup_time
        out["timestamp_ratio"] = ratio_time
        worst_ratio = max(worst_ratio, ratio_time)

    out["status"] = _status_from_ratio(worst_ratio, warn, fail)
    out["type"] = "row"
    return out
