"""PDF 여러 개를 하나로 합치는 도구."""
from __future__ import annotations

import io

import pandas as pd
import streamlit as st
from pypdf import PdfReader, PdfWriter

from common import download_result, friendly_errors, step_caption, tool_header

TOOL_META = {
    "name": "PDF 합치기",
    "category": "PDF",
    "description": "여러 개의 PDF 파일을 원하는 순서로 하나의 파일로 합쳐드려요.",
    "icon": "📎",
}


def render() -> None:
    tool_header(TOOL_META["name"], TOOL_META["description"])

    step_caption(1, "합칠 PDF 파일들을 올려주세요")
    files = st.file_uploader(
        "PDF 파일 선택 (여러 개 선택 가능)", type=["pdf"], accept_multiple_files=True
    )
    if not files:
        st.info("PDF 파일을 2개 이상 올려주세요.")
        return
    if len(files) == 1:
        st.warning("파일이 1개뿐이에요. 2개 이상 올리면 순서를 정해서 합칠 수 있어요.")

    step_caption(2, "합칠 순서를 정해주세요 (숫자가 작을수록 앞에 놓여요)")
    order_df = pd.DataFrame(
        {
            "파일명": [f.name for f in files],
            "순서": list(range(1, len(files) + 1)),
        }
    )
    edited = st.data_editor(
        order_df,
        hide_index=True,
        use_container_width=True,
        disabled=["파일명"],
        key="pdf_merge_order_editor",
    )

    step_caption(3, "실행 버튼을 눌러주세요")
    if st.button("PDF 합치기 실행", type="primary"):
        with friendly_errors("PDF 합치기"):
            files_by_name: dict[str, list] = {}
            for f in files:
                files_by_name.setdefault(f.name, []).append(f)

            ordered_rows = edited.sort_values("순서")
            writer = PdfWriter()
            used_index: dict[str, int] = {}
            for _, row in ordered_rows.iterrows():
                name = row["파일명"]
                idx = used_index.get(name, 0)
                used_index[name] = idx + 1
                target_file = files_by_name[name][idx]
                target_file.seek(0)
                reader = PdfReader(target_file)
                for page in reader.pages:
                    writer.add_page(page)

            buffer = io.BytesIO()
            writer.write(buffer)

            step_caption(4, "결과 파일을 받아주세요")
            download_result(
                "합쳐진 PDF 내려받기",
                buffer.getvalue(),
                "합쳐진_결과.pdf",
                "application/pdf",
            )
