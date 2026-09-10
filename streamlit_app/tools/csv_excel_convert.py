"""CSV 파일과 엑셀 파일을 서로 변환하는 도구."""
from __future__ import annotations

import io

import pandas as pd
import streamlit as st

from common import download_result, friendly_errors, step_caption, tool_header

TOOL_META = {
    "name": "CSV ↔ 엑셀 변환",
    "category": "Excel",
    "description": "CSV 파일을 엑셀로, 엑셀 파일을 CSV로 서로 바꿔드려요.",
    "icon": "🔁",
}

AUTO_ENCODING = "자동 감지 (추천)"
ENCODING_OPTIONS = {
    AUTO_ENCODING: None,
    "UTF-8": "utf-8-sig",
    "CP949 / EUC-KR (오래된 한글 윈도우 엑셀 파일)": "cp949",
}

SEP_OPTIONS = {
    "쉼표 ( , )": ",",
    "탭": "\t",
    "세미콜론 ( ; )": ";",
}

OUTPUT_ENCODING_OPTIONS = {
    "UTF-8 (요즘 프로그램 대부분 · 추천)": "utf-8-sig",
    "CP949 / EUC-KR (오래된 엑셀에서 열 때)": "cp949",
}


def _read_csv_auto(file, encoding_choice: str, sep: str) -> pd.DataFrame:
    encoding = ENCODING_OPTIONS[encoding_choice]
    if encoding is not None:
        file.seek(0)
        return pd.read_csv(file, encoding=encoding, sep=sep)

    # 자동 감지: UTF-8을 먼저 시도하고, 안 되면 한글 윈도우에서 흔한 CP949로 시도해요
    for candidate in ["utf-8-sig", "cp949"]:
        try:
            file.seek(0)
            return pd.read_csv(file, encoding=candidate, sep=sep)
        except (UnicodeDecodeError, UnicodeError):
            continue
    raise ValueError(
        "글자가 깨져서 자동으로 읽지 못했어요. 옵션에서 인코딩을 'UTF-8' 또는 'CP949'로 "
        "직접 선택해서 다시 시도해 주세요."
    )


def render() -> None:
    tool_header(TOOL_META["name"], TOOL_META["description"])

    step_caption(1, "변환할 파일을 올려주세요 (CSV 또는 엑셀)")
    file = st.file_uploader("파일 선택", type=["csv", "xlsx", "xls"])
    if not file:
        st.info("CSV 또는 엑셀 파일을 1개 올려주세요.")
        return

    is_csv = file.name.lower().endswith(".csv")

    if is_csv:
        step_caption(2, "옵션을 선택해주세요")
        encoding_choice = st.radio(
            "원본 CSV의 인코딩", list(ENCODING_OPTIONS.keys()), horizontal=True
        )
        sep_label = st.radio("구분 기호", list(SEP_OPTIONS.keys()), horizontal=True)

        step_caption(3, "실행 버튼을 눌러주세요")
        if st.button("엑셀로 변환하기 실행", type="primary"):
            with friendly_errors("CSV를 엑셀로 변환"):
                df = _read_csv_auto(file, encoding_choice, SEP_OPTIONS[sep_label])
                if df.empty:
                    raise ValueError("이 CSV 파일에서 데이터를 찾지 못했어요.")

                step_caption(4, "결과를 확인하고 받아주세요")
                st.caption(f"{len(df):,}행 × {len(df.columns):,}열")
                st.dataframe(df.head(50), use_container_width=True)

                buffer = io.BytesIO()
                df.to_excel(buffer, index=False)
                download_result(
                    "변환된 엑셀 내려받기",
                    buffer.getvalue(),
                    f"{file.name.rsplit('.', 1)[0]}.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
    else:
        with friendly_errors("엑셀 시트 목록 확인"):
            excel_file = pd.ExcelFile(file)
            sheet_names = excel_file.sheet_names

        step_caption(2, "옵션을 선택해주세요")
        sheet_name = st.selectbox("CSV로 만들 시트 선택", sheet_names)
        output_encoding_label = st.radio(
            "CSV 인코딩", list(OUTPUT_ENCODING_OPTIONS.keys())
        )

        step_caption(3, "실행 버튼을 눌러주세요")
        if st.button("CSV로 변환하기 실행", type="primary"):
            with friendly_errors("엑셀을 CSV로 변환"):
                df = excel_file.parse(sheet_name)
                if df.empty:
                    raise ValueError(f"'{sheet_name}' 시트에서 데이터를 찾지 못했어요.")

                step_caption(4, "결과를 확인하고 받아주세요")
                st.caption(f"{len(df):,}행 × {len(df.columns):,}열")
                st.dataframe(df.head(50), use_container_width=True)

                csv_bytes = df.to_csv(index=False).encode(
                    OUTPUT_ENCODING_OPTIONS[output_encoding_label]
                )
                download_result(
                    "변환된 CSV 내려받기",
                    csv_bytes,
                    f"{file.name.rsplit('.', 1)[0]}_{sheet_name}.csv",
                    "text/csv",
                )
