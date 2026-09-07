import os
import sys

import numpy as np
import pandas as pd
import pytest
import xarray as xr

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), "..")))

from qc.loader import LoadedDataset  # noqa: E402
from qc.report import load_default_config, run_qc  # noqa: E402


@pytest.fixture
def config():
    return load_default_config()


@pytest.fixture
def netcdf_dataset():
    times = pd.date_range("2024-01-01", periods=24, freq="h")
    lat = np.linspace(30, 35, 3)
    lon = np.linspace(120, 125, 3)
    rng = np.random.default_rng(0)
    temp = 20 + rng.standard_normal((len(times), len(lat), len(lon)))
    temp[0, 0, 0] = np.nan
    temp[5, 1, 1] = 999.0  # 이상치 & 범위 초과

    ds = xr.Dataset(
        {"temperature": (("time", "lat", "lon"), temp, {"units": "degC", "long_name": "Air Temp"})},
        coords={"time": times, "lat": lat, "lon": lon},
        attrs={"Conventions": "CF-1.8", "title": "t", "institution": "i"},
    )
    return LoadedDataset(kind="netcdf", filename="test.nc", ds=ds, time_dim="time", lat_dim="lat", lon_dim="lon")


@pytest.fixture
def csv_dataset():
    n = 50
    t = pd.date_range("2024-01-01", periods=n, freq="h")
    df = pd.DataFrame({"time": t, "temperature": 20 + np.random.default_rng(1).standard_normal(n)})
    df.loc[3, "temperature"] = np.nan
    df = pd.concat([df, df.iloc[[0]]], ignore_index=True)  # 중복 행 추가
    return LoadedDataset(kind="csv", filename="test.csv", df=df, time_col="time")


def test_run_qc_netcdf_smoke(netcdf_dataset, config):
    report = run_qc(netcdf_dataset, None)
    assert report["file_type"] == "netcdf"
    assert 0 <= report["score"]["total"] <= 100
    for key in ["missing_values", "time_continuity", "range_check", "outliers", "metadata", "duplicates"]:
        assert key in report["checks"]
        assert report["checks"][key]["status"] in ("pass", "warning", "fail", "skipped")


def test_run_qc_csv_smoke(csv_dataset, config):
    report = run_qc(csv_dataset, None)
    assert report["file_type"] == "csv"
    assert 0 <= report["score"]["total"] <= 100


def test_missing_values_detects_nan(netcdf_dataset, config):
    from qc.checks import check_missing_values

    result = check_missing_values(netcdf_dataset, config)
    temp_var = next(v for v in result["variables"] if v["variable"] == "temperature")
    assert temp_var["missing"] == 1


def test_duplicates_detects_dup_rows(csv_dataset, config):
    from qc.checks import check_duplicates

    result = check_duplicates(csv_dataset, config)
    assert result["duplicate_rows"] == 1


def test_range_check_flags_out_of_range(netcdf_dataset, config):
    from qc.checks import check_range

    result = check_range(netcdf_dataset, config)
    temp_var = next(v for v in result["variables"] if v["variable"] == "temperature")
    assert temp_var["out_of_range"] >= 1


def test_time_continuity_no_gap_when_regular(config):
    from qc.checks import check_time_continuity

    times = pd.date_range("2024-01-01", periods=10, freq="h")
    ds = xr.Dataset({"x": (("time",), np.arange(10, dtype="float64"))}, coords={"time": times})
    loaded = LoadedDataset(kind="netcdf", filename="t.nc", ds=ds, time_dim="time")
    result = check_time_continuity(loaded, config)
    assert result["status"] == "pass"
    assert result["n_gaps_total"] == 0


def test_time_continuity_detects_gap(config):
    from qc.checks import check_time_continuity

    times = pd.date_range("2024-01-01", periods=10, freq="h").delete([4, 5, 6])
    ds = xr.Dataset({"x": (("time",), np.arange(len(times), dtype="float64"))}, coords={"time": times})
    loaded = LoadedDataset(kind="netcdf", filename="t.nc", ds=ds, time_dim="time")
    result = check_time_continuity(loaded, config)
    assert result["n_gaps_total"] == 1
    assert result["missing_points"] == 3


def test_metadata_check_flags_missing_attrs(config):
    from qc.checks import check_metadata

    ds = xr.Dataset({"temperature": (("x",), np.array([1.0, 2.0]))})  # 속성/전역속성 없음
    loaded = LoadedDataset(kind="netcdf", filename="t.nc", ds=ds)
    result = check_metadata(loaded, config)
    assert result["status"] == "fail"
    assert result["compliance_ratio"] < 0.5
