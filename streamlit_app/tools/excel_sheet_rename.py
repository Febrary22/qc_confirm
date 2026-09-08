"""엑셀 시트 이름을 한꺼번에 바꾸는 도구."""
from __future__ import annotations

import io

import pandas as pd
import streamlit as st
from openpyxl import load_workbook

from common import download_result, friendly_errors, step_caption, tool_header

TOOL_META = {
    "name": "엑셀 시트 이름 일괄 변경",
    "category": "Excel",
    "description": "엑셀 파일 안에 있는 여러 시트의 이름을 한 번에 바꿔드려요.",
    "icon": "✏️",
}

INVALID_CHARS = set(r"[]:*?/\\")


def _validate_names(names: list[str]) -> None:
    if any(not n.strip() for n in names):
        raise ValueError("빈 시트 이름은 사용할 수 없어요.")
    for n in names:
        if len(n) > 31:
            raise ValueError(f"'{n}'는 31자를 넘어요. 엑셀 시트 이름은 31자 이내여야 해요.")
        if any(ch in INVALID_CHARS for ch in n):
            raise ValueError(f"'{n}'에 사용할 수 없는 글자가 있어요. ( [ ] : * ? / \\ 는 사용할 수 없어요)")
    if len(set(names)) != len(names):
        raise ValueError("시트 이름이 서로 겹치지 않게 해주세요.")


def render() -> None:
    tool_header(TOOL_META["name"], TOOL_META["description"])

    step_caption(1, "이름을 바꿀 엑셀 파일을 올려주세요")
    file = st.file_uploader("엑셀 파일 선택", type=["xlsx"])
    if not file:
        st.info("엑셀 파일을 1개 올려주세요. (.xlsx 형식만 가능해요)")
        return

    with friendly_errors("엑셀 시트 목록 확인"):
        file.seek(0)
        wb = load_workbook(file)
        sheet_names = wb.sheetnames

    step_caption(2, "새 이름을 입력해주세요")
    st.caption("바꾸고 싶은 시트만 새 이름을 입력하고, 그대로 둘 시트는 비워두거나 원래 이름을 유지하세요.")

    prefix = st.text_input(
        "(선택) 모든 시트 이름 앞에 공통으로 붙일 글자",
        placeholder="예: 2024년_ 를 입력하면 모든 시트 앞에 '2024년_'가 붙어요",
    )

    rename_df = pd.DataFrame(
        {
            "원래 이름": sheet_names,
            "새 이름": sheet_names,
        }
    )
    edited = st.data_editor(
        rename_df,
        hide_index=True,
        use_container_width=True,
        disabled=["원래 이름"],
        key="excel_rename_editor",
    )

    step_caption(3, "실행 버튼을 눌러주세요")
    if st.button("시트 이름 바꾸기 실행", type="primary"):
        with friendly_errors("엑셀 시트 이름 바꾸기"):
            new_names = [f"{prefix}{n}".strip() for n in edited["새 이름"].tolist()]
            _validate_names(new_names)

            file.seek(0)
            wb = load_workbook(file)
            for original, new_name in zip(sheet_names, new_names):
                wb[original].title = new_name

            buffer = io.BytesIO()
            wb.save(buffer)

            step_caption(4, "결과 파일을 받아주세요")
            download_result(
                "이름이 바뀐 엑셀 내려받기",
                buffer.getvalue(),
                "시트이름변경_결과.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
