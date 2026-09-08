"""여러 엑셀 파일을 하나로 합치는 도구."""
from __future__ import annotations

import io

import pandas as pd
import streamlit as st

from common import download_result, friendly_errors, step_caption, tool_header

TOOL_META = {
    "name": "엑셀 합치기",
    "category": "Excel",
    "description": "여러 개의 엑셀 파일을 하나의 파일로 합쳐드려요.",
    "icon": "📎",
}

KEEP_SHEETS = "시트별로 유지하기 (각 시트를 그대로 모아요)"
STACK_ROWS = "표 하나로 합치기 (위아래로 이어붙여요)"


def _unique_sheet_name(base: str, used: set[str]) -> str:
    name = base[:31] if base else "Sheet"
    original = name
    n = 1
    while name in used:
        suffix = f"_{n}"
        name = original[: 31 - len(suffix)] + suffix
        n += 1
    used.add(name)
    return name


def render() -> None:
    tool_header(TOOL_META["name"], TOOL_META["description"])

    step_caption(1, "합칠 엑셀 파일들을 올려주세요")
    files = st.file_uploader(
        "엑셀 파일 선택 (여러 개 선택 가능)", type=["xlsx", "xls"], accept_multiple_files=True
    )
    if not files:
        st.info("엑셀 파일을 2개 이상 올려주세요.")
        return

    step_caption(2, "합치는 방식을 선택해주세요")
    mode = st.radio(
        "합치는 방식",
        [KEEP_SHEETS, STACK_ROWS],
        label_visibility="collapsed",
        help=(
            f"'{KEEP_SHEETS}'는 파일마다 있던 시트를 그대로 새 파일에 모아줘요.\n\n"
            f"'{STACK_ROWS}'는 각 파일의 첫 번째 시트에 있는 표를 위아래로 이어붙여서 표 1개로 만들어요."
        ),
    )

    step_caption(3, "실행 버튼을 눌러주세요")
    if st.button("엑셀 합치기 실행", type="primary"):
        with friendly_errors("엑셀 합치기"):
            buffer = io.BytesIO()

            if mode == KEEP_SHEETS:
                used_names: set[str] = set()
                with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                    for f in files:
                        f.seek(0)
                        excel_file = pd.ExcelFile(f)
                        base_name = f.name.rsplit(".", 1)[0]
                        for sheet_name in excel_file.sheet_names:
                            df = excel_file.parse(sheet_name)
                            new_name = _unique_sheet_name(f"{base_name}_{sheet_name}", used_names)
                            df.to_excel(writer, sheet_name=new_name, index=False)
            else:
                all_dfs = []
                for f in files:
                    f.seek(0)
                    df = pd.read_excel(f, sheet_name=0)
                    df.insert(0, "출처파일", f.name)
                    all_dfs.append(df)
                merged = pd.concat(all_dfs, ignore_index=True, sort=False)
                merged.to_excel(buffer, index=False)

            step_caption(4, "결과 파일을 받아주세요")
            download_result(
                "합쳐진 엑셀 내려받기",
                buffer.getvalue(),
                "합쳐진_결과.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
