"""큰 엑셀 파일을 여러 개의 파일로 쪼개는 도구."""
from __future__ import annotations

import io
import re
import zipfile

import pandas as pd
import streamlit as st

from common import download_result, friendly_errors, step_caption, tool_header

TOOL_META = {
    "name": "엑셀 파일 쪼개기",
    "category": "Excel",
    "description": "하나의 큰 엑셀 표를 정해진 행 개수씩, 또는 특정 열의 값 기준으로 여러 파일로 나눠드려요.",
    "icon": "✂️",
}

BY_ROWS = "정해진 행 개수씩 나누기 (예: 1000행씩)"
BY_COLUMN = "특정 열의 값 기준으로 나누기 (예: 부서별로)"


def _safe_filename(value: str) -> str:
    text = str(value).strip() or "빈값"
    return re.sub(r'[\\/*?:"<>|]', "_", text)[:80]


def render() -> None:
    tool_header(TOOL_META["name"], TOOL_META["description"])

    step_caption(1, "쪼갤 엑셀 파일을 올려주세요")
    file = st.file_uploader("엑셀 파일 선택", type=["xlsx", "xls"])
    if not file:
        st.info("엑셀 파일을 1개 올려주세요.")
        return

    with friendly_errors("엑셀 시트 목록 확인"):
        excel_file = pd.ExcelFile(file)
        sheet_names = excel_file.sheet_names

    sheet_name = sheet_names[0]
    if len(sheet_names) > 1:
        sheet_name = st.selectbox("쪼갤 시트 선택", sheet_names)

    with friendly_errors("엑셀 내용 읽기"):
        df = excel_file.parse(sheet_name)
    st.caption(f"'{sheet_name}' 시트: {len(df):,}행 × {len(df.columns):,}열")

    step_caption(2, "나누는 방식을 선택해주세요")
    mode = st.radio("나누는 방식", [BY_ROWS, BY_COLUMN], label_visibility="collapsed")

    rows_per_file = 1000
    split_column = None
    if mode == BY_ROWS:
        rows_per_file = st.number_input(
            "파일 하나당 행 개수", min_value=1, value=min(1000, max(len(df), 1))
        )
    else:
        split_column = st.selectbox("기준으로 삼을 열", list(df.columns))

    step_caption(3, "실행 버튼을 눌러주세요")
    if st.button("엑셀 쪼개기 실행", type="primary"):
        with friendly_errors("엑셀 쪼개기"):
            if df.empty:
                raise ValueError("이 시트에는 데이터가 없어요.")

            chunks: list[tuple[str, pd.DataFrame]] = []
            if mode == BY_ROWS:
                total = len(df)
                for i, start in enumerate(range(0, total, rows_per_file), start=1):
                    part = df.iloc[start : start + rows_per_file]
                    chunks.append((f"{i:03d}", part))
            else:
                for value, group in df.groupby(split_column, dropna=False):
                    chunks.append((_safe_filename(value), group))

            if not chunks:
                raise ValueError("나눌 데이터가 없어요.")

            step_caption(4, "결과를 확인하고 받아주세요")
            st.caption(f"{len(chunks)}개 파일로 나뉘었어요.")
            preview_df = pd.DataFrame(
                {"파일명": [f"{sheet_name}_{name}.xlsx" for name, _ in chunks], "행 개수": [len(g) for _, g in chunks]}
            )
            st.dataframe(preview_df, hide_index=True, use_container_width=True)

            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                for name, part_df in chunks:
                    part_buffer = io.BytesIO()
                    part_df.to_excel(part_buffer, index=False, sheet_name=sheet_name)
                    zf.writestr(f"{sheet_name}_{name}.xlsx", part_buffer.getvalue())

            download_result(
                "쪼개진 엑셀 모음(zip) 내려받기",
                zip_buffer.getvalue(),
                f"{file.name.rsplit('.', 1)[0]}_쪼갠결과.zip",
                "application/zip",
            )
