"""PDF를 원하는 페이지 범위로 나누는 도구."""
from __future__ import annotations

import io
import zipfile

import streamlit as st
from pypdf import PdfReader, PdfWriter

from common import download_result, friendly_errors, parse_page_ranges, step_caption, tool_header

TOOL_META = {
    "name": "PDF 분할하기",
    "category": "PDF",
    "description": "하나의 PDF를 원하는 페이지 범위마다 여러 개의 파일로 나눠드려요.",
    "icon": "✂️",
}


def render() -> None:
    tool_header(TOOL_META["name"], TOOL_META["description"])

    step_caption(1, "나눌 PDF 파일을 올려주세요")
    file = st.file_uploader("PDF 파일 선택", type=["pdf"])
    if not file:
        st.info("PDF 파일을 1개 올려주세요.")
        return

    with friendly_errors("PDF 페이지 수 확인"):
        file.seek(0)
        total_pages = len(PdfReader(file).pages)
    st.caption(f"이 파일은 총 {total_pages}쪽이에요.")

    step_caption(2, "나눌 범위를 그룹별로 콤마( , )로 구분해서 입력해주세요")
    st.caption("예) `1-3, 4-6, 7-10` 을 입력하면 세 개의 파일로 나뉘어요. 예) `1-5` 만 입력하면 파일 1개만 만들어져요.")
    ranges_text = st.text_input("나눌 범위", placeholder="예: 1-3, 4-6, 7-10")

    step_caption(3, "실행 버튼을 눌러주세요")
    if st.button("PDF 분할 실행", type="primary"):
        with friendly_errors("PDF 분할"):
            if not ranges_text.strip():
                raise ValueError("나눌 범위를 입력해 주세요. 예: 1-3, 4-6")

            groups = [g.strip() for g in ranges_text.split(",") if g.strip()]
            file.seek(0)
            reader = PdfReader(file)

            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                for i, group in enumerate(groups, start=1):
                    page_indices = parse_page_ranges(group, total_pages)
                    writer = PdfWriter()
                    for idx in page_indices:
                        writer.add_page(reader.pages[idx])
                    part_buffer = io.BytesIO()
                    writer.write(part_buffer)
                    zf.writestr(f"분할_{i}_{group.replace(' ', '')}.pdf", part_buffer.getvalue())

            step_caption(4, "결과 파일을 받아주세요")
            download_result(
                "나눠진 PDF 모음(zip) 내려받기",
                zip_buffer.getvalue(),
                "분할_결과.zip",
                "application/zip",
            )
