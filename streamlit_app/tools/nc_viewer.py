"""NetCDF(.nc) 파일을 열어서 구조와 데이터를 확인하는 도구."""
from __future__ import annotations

import os
import tempfile

import pandas as pd
import streamlit as st
import xarray as xr

from common import download_result, friendly_errors, step_caption, tool_header

TOOL_META = {
    "name": "NC 파일 열어보기",
    "category": "NC데이터",
    "description": "NetCDF(.nc) 파일 안에 어떤 변수·차원이 있는지, 실제 값은 어떤지 표와 그래프로 바로 확인해요.",
    "icon": "🌊",
}

MAX_UPLOAD_BYTES = 300 * 1024 * 1024  # 300MB 안전 한도


@st.cache_resource(show_spinner="NC 파일을 읽는 중이에요...")
def _open_dataset(content: bytes) -> xr.Dataset:
    """업로드된 바이트를 임시 파일로 저장했다가 xarray로 엽니다."""
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".nc", delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        try:
            ds = xr.open_dataset(tmp_path, decode_times=True)
        except Exception:
            # 일부 nc 파일은 h5netcdf 엔진으로만 열려요.
            ds = xr.open_dataset(tmp_path, decode_times=True, engine="h5netcdf")
        ds.load()
        ds.close()
        return ds
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


def _describe_dataset(ds: xr.Dataset) -> None:
    st.markdown("**차원(Dimension) 크기**")
    dim_df = pd.DataFrame(
        {"차원 이름": list(ds.sizes.keys()), "크기": list(ds.sizes.values())}
    )
    st.dataframe(dim_df, hide_index=True, use_container_width=True)

    st.markdown("**변수(Variable) 목록**")
    var_rows = [
        {
            "변수 이름": name,
            "차원": ", ".join(var.dims) if var.dims else "-",
            "단위(units)": var.attrs.get("units", "-"),
            "설명": var.attrs.get("long_name", var.attrs.get("standard_name", "-")),
        }
        for name, var in ds.variables.items()
    ]
    st.dataframe(pd.DataFrame(var_rows), hide_index=True, use_container_width=True)

    if ds.attrs:
        st.markdown("**전역 속성(Global Attributes)**")
        st.json({str(k): str(v) for k, v in ds.attrs.items()})
    else:
        st.caption("전역 속성은 없어요.")


def render() -> None:
    tool_header(TOOL_META["name"], TOOL_META["description"])

    step_caption(1, "열어볼 NC(NetCDF) 파일을 올려주세요")
    file = st.file_uploader("NC 파일 선택", type=["nc", "nc4", "netcdf", "cdf"])
    if not file:
        st.info("NC 파일을 1개 올려주세요.")
        return

    content = file.getvalue()
    if len(content) > MAX_UPLOAD_BYTES:
        st.error(
            f"파일이 너무 커요 ({len(content) / 1e6:.1f}MB). "
            f"이 도구는 한 번에 {MAX_UPLOAD_BYTES / 1e6:.0f}MB까지만 열 수 있어요."
        )
        return

    with friendly_errors("NC 파일 열기"):
        ds = _open_dataset(content)
    st.success(f"'{file.name}' 파일을 열었어요.")

    with st.expander("📋 파일 전체 구조 보기 (차원 · 변수 · 전역 정보)", expanded=True):
        with friendly_errors("파일 구조 확인"):
            _describe_dataset(ds)

    data_vars = list(ds.data_vars)
    if not data_vars:
        st.warning("이 파일에는 실제 데이터 변수가 없어요. (좌표 변수만 있는 파일일 수 있어요)")
        return

    step_caption(2, "자세히 살펴볼 변수와 범위를 선택해주세요")
    var_name = st.selectbox("변수 선택", data_vars)
    da = ds[var_name]
    st.caption(f"'{var_name}'의 차원: {', '.join(da.dims) or '없음'} / 크기: {tuple(da.shape)}")

    indexers: dict[str, int] = {}
    if da.ndim > 2:
        st.caption(
            "차원이 3개 이상이에요. 표와 그래프로 보려면 앞쪽 차원들의 값을 하나씩 골라 "
            "2차원(또는 1차원)으로 줄여야 해요."
        )
        for dim in da.dims[:-2]:
            size = da.sizes[dim]
            if size <= 1:
                # 크기가 1(또는 0)인 차원은 고를 값이 없으니 슬라이더 없이 그냥 0번째로 고정해요.
                indexers[dim] = 0
                st.caption(f"'{dim}' 차원은 크기가 {size}라서 자동으로 선택했어요.")
            else:
                indexers[dim] = st.slider(f"'{dim}' 값 선택 (0 ~ {size - 1})", 0, size - 1, 0)

    step_caption(3, "미리보기 만들기 버튼을 눌러주세요")
    if st.button("미리보기 만들기", type="primary"):
        with friendly_errors("데이터 미리보기 만들기"):
            sliced = da.isel(**indexers) if indexers else da

            if sliced.ndim == 0:
                st.metric(var_name, float(sliced.values))
                preview_df = sliced.to_dataframe(name=var_name).reset_index()
            elif sliced.ndim == 1:
                preview_df = sliced.to_dataframe(name=var_name).reset_index()
                st.line_chart(preview_df, x=preview_df.columns[0], y=var_name)
                st.caption("표는 앞부분 200줄만 보여드려요. 전체 내용은 아래에서 CSV로 받을 수 있어요.")
                st.dataframe(preview_df.head(200), use_container_width=True)
            elif sliced.ndim == 2:
                st.caption("2차원 데이터라서 표로 보여드려요. (값이 클수록 진한 색이에요)")
                df2d = sliced.to_pandas()
                try:
                    st.dataframe(df2d.style.background_gradient(cmap="Blues"), use_container_width=True)
                except Exception:
                    st.dataframe(df2d, use_container_width=True)
                preview_df = df2d.reset_index()
            else:
                st.warning("아직 3차원 이상은 그대로 보여드리지 못해요. 위에서 차원 값을 더 골라 주세요.")
                return

            step_caption(4, "필요하면 표를 CSV로 내려받으세요")
            csv_bytes = preview_df.to_csv(index=False).encode("utf-8-sig")
            download_result(
                f"'{var_name}' 미리보기 CSV로 내려받기",
                csv_bytes,
                f"{var_name}_미리보기.csv",
                "text/csv",
            )
