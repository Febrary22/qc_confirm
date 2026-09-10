"""여러 파일의 이름을 한 번에 규칙대로 바꾸는 도구."""
from __future__ import annotations

import io
import zipfile

import pandas as pd
import streamlit as st

from common import download_result, friendly_errors, step_caption, tool_header

TOOL_META = {
    "name": "파일 이름 일괄 변경",
    "category": "기타",
    "description": "여러 파일의 이름에 접두사·순번을 붙이거나, 특정 글자를 한 번에 바꿔드려요.",
    "icon": "🏷️",
}


def _split_name(filename: str) -> tuple[str, str]:
    if "." in filename:
        base, ext = filename.rsplit(".", 1)
        return base, f".{ext}"
    return filename, ""


def _build_new_name(
    original: str,
    index: int,
    prefix: str,
    suffix: str,
    find: str,
    replace: str,
    use_number: bool,
    number_start: int,
    number_digits: int,
) -> str:
    base, ext = _split_name(original)

    if find:
        base = base.replace(find, replace)

    if use_number:
        number = str(number_start + index).zfill(number_digits)
        base = f"{base}_{number}"

    return f"{prefix}{base}{suffix}{ext}"


def render() -> None:
    tool_header(TOOL_META["name"], TOOL_META["description"])

    step_caption(1, "이름을 바꿀 파일들을 올려주세요")
    files = st.file_uploader("파일 선택 (여러 개 선택 가능)", accept_multiple_files=True)
    if not files:
        st.info("파일을 1개 이상 올려주세요. (어떤 종류든 상관없어요)")
        return

    step_caption(2, "이름 변경 규칙을 정해주세요")
    col1, col2 = st.columns(2)
    with col1:
        prefix = st.text_input("파일명 맨 앞에 붙일 글자 (접두사)", placeholder="예: 2024_영업팀_")
    with col2:
        suffix = st.text_input("파일명 맨 뒤에 붙일 글자 (접미사)", placeholder="예: _최종")

    st.caption("찾아서 바꾸기 (필요 없으면 비워두세요)")
    col3, col4 = st.columns(2)
    with col3:
        find = st.text_input("이 글자를 찾아서", placeholder="예: 초안")
    with col4:
        replace = st.text_input("이 글자로 바꿔요", placeholder="예: 최종")

    use_number = st.checkbox("일련번호 붙이기 (예: _001, _002...)")
    number_start, number_digits = 1, 3
    if use_number:
        col5, col6 = st.columns(2)
        with col5:
            number_start = st.number_input("시작 번호", min_value=0, value=1)
        with col6:
            number_digits = st.number_input("번호 자릿수", min_value=1, max_value=6, value=3)

    step_caption(3, "바뀔 이름을 미리 확인하세요")
    preview_rows = []
    for i, f in enumerate(files):
        new_name = _build_new_name(
            f.name, i, prefix, suffix, find, replace, use_number, int(number_start), int(number_digits)
        )
        preview_rows.append({"원래 이름": f.name, "→ 새 이름": new_name})
    st.dataframe(pd.DataFrame(preview_rows), hide_index=True, use_container_width=True)

    step_caption(4, "실행 버튼을 눌러주세요")
    if st.button("이름 바꿔서 내려받기 실행", type="primary"):
        with friendly_errors("파일 이름 일괄 변경"):
            new_names = [row["→ 새 이름"] for row in preview_rows]
            if len(set(new_names)) != len(new_names):
                raise ValueError(
                    "바뀐 이름 중에 서로 겹치는 게 있어요. (일련번호 붙이기를 켜면 보통 해결돼요) "
                    "규칙을 다시 확인해 주세요."
                )

            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                for f, new_name in zip(files, new_names):
                    zf.writestr(new_name, f.getvalue())

            download_result(
                "이름이 바뀐 파일 모음(zip) 내려받기",
                zip_buffer.getvalue(),
                "이름변경_결과.zip",
                "application/zip",
            )
