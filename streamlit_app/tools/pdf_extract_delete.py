"""PDF에서 특정 페이지만 남기거나(추출) 지우는(삭제) 도구."""
from __future__ import annotations

import io

import streamlit as st
from pypdf import PdfReader, PdfWriter

from common import download_result, friendly_errors, parse_page_ranges, step_caption, tool_header

TOOL_META = {
    "name": "PDF 페이지 삭제·추출",
    "category": "PDF",
    "description": "PDF에서 원하는 페이지만 뽑아내거나, 필요 없는 페이지만 지워드려요.",
    "icon": "🗑️",
}


def render() -> None:
    tool_header(TOOL_META["name"], TOOL_META["description"])

    step_caption(1, "작업할 PDF 파일을 올려주세요")
    file = st.file_uploader("PDF 파일 선택", type=["pdf"])
    if not file:
        st.info("PDF 파일을 1개 올려주세요.")
        return

    with friendly_errors("PDF 페이지 수 확인"):
        file.seek(0)
        total_pages = len(PdfReader(file).pages)
    st.caption(f"이 파일은 총 {total_pages}쪽이에요.")

    step_caption(2, "어떻게 할지 정해주세요")
    mode = st.radio(
        "작업 방식",
        ["이 페이지들만 남기기 (추출)", "이 페이지들만 지우기 (삭제)"],
        label_visibility="collapsed",
    )
    pages_text = st.text_input("페이지 번호 (예: 1-3, 5, 7-9)", placeholder="예: 1-3, 5, 7-9")

    step_caption(3, "실행 버튼을 눌러주세요")
    if st.button("실행하기", type="primary"):
        with friendly_errors("PDF 페이지 처리"):
            target_indices = set(parse_page_ranges(pages_text, total_pages))

            file.seek(0)
            reader = PdfReader(file)
            writer = PdfWriter()

            is_extract = mode.startswith("이 페이지들만 남기기")
            for idx in range(total_pages):
                keep = (idx in target_indices) if is_extract else (idx not in target_indices)
                if keep:
                    writer.add_page(reader.pages[idx])

            if len(writer.pages) == 0:
                raise ValueError("결과에 남는 페이지가 없어요. 페이지 번호와 작업 방식을 다시 확인해 주세요.")

            buffer = io.BytesIO()
            writer.write(buffer)

            step_caption(4, "결과 파일을 받아주세요")
            result_name = "추출_결과.pdf" if is_extract else "삭제_결과.pdf"
            download_result("결과 PDF 내려받기", buffer.getvalue(), result_name, "application/pdf")
