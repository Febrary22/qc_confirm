"""PDF 페이지 순서를 바꾸는 도구."""
from __future__ import annotations

import io

import pandas as pd
import streamlit as st
from pypdf import PdfReader, PdfWriter

from common import download_result, friendly_errors, step_caption, tool_header

TOOL_META = {
    "name": "PDF 페이지 순서 바꾸기",
    "category": "PDF",
    "description": "PDF 안의 페이지들을 원하는 순서로 다시 배치해드려요.",
    "icon": "🔀",
}


def render() -> None:
    tool_header(TOOL_META["name"], TOOL_META["description"])

    step_caption(1, "순서를 바꿀 PDF 파일을 올려주세요")
    file = st.file_uploader("PDF 파일 선택", type=["pdf"])
    if not file:
        st.info("PDF 파일을 1개 올려주세요.")
        return

    with friendly_errors("PDF 페이지 확인"):
        file.seek(0)
        total_pages = len(PdfReader(file).pages)

    step_caption(2, "새로운 순서 번호를 입력해주세요 (원하는 순서대로 1, 2, 3...)")
    st.caption("예) 3쪽을 가장 앞으로 보내고 싶으면 '원래 페이지 3'의 새 순서를 1로 입력하세요.")
    order_df = pd.DataFrame(
        {
            "원래 페이지": list(range(1, total_pages + 1)),
            "새 순서": list(range(1, total_pages + 1)),
        }
    )
    edited = st.data_editor(
        order_df,
        hide_index=True,
        use_container_width=True,
        disabled=["원래 페이지"],
        key="pdf_reorder_editor",
    )

    step_caption(3, "실행 버튼을 눌러주세요")
    if st.button("순서 바꾸기 실행", type="primary"):
        with friendly_errors("PDF 페이지 순서 바꾸기"):
            new_order = edited["새 순서"].tolist()
            if sorted(new_order) != list(range(1, total_pages + 1)):
                raise ValueError(
                    f"새 순서 번호는 1부터 {total_pages}까지 한 번씩만 사용해야 해요. "
                    "중복되거나 빠진 번호가 없는지 확인해 주세요."
                )

            # 새 순서(1,2,3...) 기준으로 어떤 원래 페이지를 가져올지 정렬
            order_map = list(zip(edited["원래 페이지"].tolist(), new_order))
            order_map.sort(key=lambda pair: pair[1])

            file.seek(0)
            reader = PdfReader(file)
            writer = PdfWriter()
            for original_page, _ in order_map:
                writer.add_page(reader.pages[original_page - 1])

            buffer = io.BytesIO()
            writer.write(buffer)

            step_caption(4, "결과 파일을 받아주세요")
            download_result(
                "순서가 바뀐 PDF 내려받기",
                buffer.getvalue(),
                "순서변경_결과.pdf",
                "application/pdf",
            )
