"""nc/csv 파일을 공통 표현(LoadedDataset)으로 읽어들이는 로더."""
from __future__ import annotations

import io
import os
import tempfile
from dataclasses import dataclass
from typing import List, Optional

import pandas as pd
import xarray as xr

TIME_NAME_CANDIDATES = [
    "time", "Time", "TIME", "date", "Date", "DATE",
    "datetime", "Datetime", "DateTime", "timestamp", "Timestamp",
]
LAT_NAME_CANDIDATES = ["lat", "latitude", "Lat", "Latitude", "LAT", "y", "nav_lat"]
LON_NAME_CANDIDATES = ["lon", "longitude", "Lon", "Longitude", "LON", "x", "nav_lon"]

MAX_UPLOAD_BYTES = 300 * 1024 * 1024  # 300MB 안전 한도


class UnsupportedFileError(ValueError):
    pass


@dataclass
class LoadedDataset:
    kind: str  # "netcdf" | "csv"
    filename: str
    ds: Optional[xr.Dataset] = None
    df: Optional[pd.DataFrame] = None
    time_col: Optional[str] = None
    time_dim: Optional[str] = None
    lat_dim: Optional[str] = None
    lon_dim: Optional[str] = None


def _find_first(names, candidates) -> Optional[str]:
    names = list(names)
    for c in candidates:
        if c in names:
            return c
    lower_map = {str(n).lower(): n for n in names}
    for c in candidates:
        if c.lower() in lower_map:
            return lower_map[c.lower()]
    return None


def load_file(filename: str, content: bytes) -> LoadedDataset:
    if len(content) > MAX_UPLOAD_BYTES:
        raise UnsupportedFileError(
            f"파일이 너무 큽니다 ({len(content) / 1e6:.1f}MB). 현재 한 번에 처리 가능한 최대 크기는 "
            f"{MAX_UPLOAD_BYTES / 1e6:.0f}MB 입니다."
        )
    ext = os.path.splitext(filename)[1].lower()
    if ext in (".nc", ".nc4", ".netcdf", ".cdf"):
        return _load_netcdf(filename, content)
    if ext in (".csv", ".tsv", ".txt"):
        return _load_csv(filename, content, sep="\t" if ext == ".tsv" else ",")
    raise UnsupportedFileError(f"지원하지 않는 파일 형식입니다: '{ext or filename}'. nc / csv 파일만 지원합니다.")


def _load_netcdf(filename: str, content: bytes) -> LoadedDataset:
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".nc", delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        try:
            ds = xr.open_dataset(tmp_path, decode_times=True)
        except Exception:
            ds = xr.open_dataset(tmp_path, decode_times=True, engine="h5netcdf")
        ds.load()
        ds.close()
    except Exception as exc:  # noqa: BLE001
        raise UnsupportedFileError(f"NetCDF 파일을 읽는 중 오류가 발생했습니다: {exc}") from exc
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    all_names: List[str] = list(ds.dims) + list(ds.coords)
    time_dim = _find_first(all_names, TIME_NAME_CANDIDATES)
    lat_dim = _find_first(all_names, LAT_NAME_CANDIDATES)
    lon_dim = _find_first(all_names, LON_NAME_CANDIDATES)

    return LoadedDataset(kind="netcdf", filename=filename, ds=ds, time_dim=time_dim, lat_dim=lat_dim, lon_dim=lon_dim)


def _load_csv(filename: str, content: bytes, sep: str = ",") -> LoadedDataset:
    try:
        df = pd.read_csv(io.BytesIO(content), sep=sep)
    except Exception as exc:  # noqa: BLE001
        raise UnsupportedFileError(f"CSV 파일을 읽는 중 오류가 발생했습니다: {exc}") from exc

    if df.shape[1] == 1 and sep == ",":
        # 구분자가 실제로는 세미콜론/탭인 경우 재시도
        for alt_sep in (";", "\t"):
            try:
                alt_df = pd.read_csv(io.BytesIO(content), sep=alt_sep)
                if alt_df.shape[1] > 1:
                    df = alt_df
                    break
            except Exception:  # noqa: BLE001
                continue

    time_col = _find_first(df.columns, TIME_NAME_CANDIDATES)
    if time_col:
        parsed = pd.to_datetime(df[time_col], errors="coerce")
        if parsed.notna().sum() > 0:
            df[time_col] = parsed
        else:
            time_col = None

    return LoadedDataset(kind="csv", filename=filename, df=df, time_col=time_col)
