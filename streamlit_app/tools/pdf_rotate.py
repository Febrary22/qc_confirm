"""PDF 페이지를 회전시키는 도구."""
from __future__ import annotations

import io

import streamlit as st
from pypdf import PdfReader, PdfWriter

from common import download_result, friendly_errors, parse_page_ranges, step_caption, tool_header

TOOL_META = {
    "name": "PDF 페이지 회전",
    "category": "PDF",
    "description": "스캔하다가 옆으로 눕거나 거꾸로 찍힌 PDF 페이지를 바로 세워드려요.",
    "icon": "🔃",
}

ALL_PAGES = "전체 페이지"
SOME_PAGES = "일부 페이지만 (번호 지정)"


def render() -> None:
    tool_header(TOOL_META["name"], TOOL_META["description"])

    step_caption(1, "회전시킬 PDF 파일을 올려주세요")
    file = st.file_uploader("PDF 파일 선택", type=["pdf"])
    if not file:
        st.info("PDF 파일을 1개 올려주세요.")
        return

    with friendly_errors("PDF 페이지 수 확인"):
        total_pages = len(PdfReader(io.BytesIO(file.getvalue())).pages)
    st.caption(f"이 파일은 총 {total_pages}쪽이에요.")

    step_caption(2, "회전 방향과 대상 페이지를 정해주세요")
    angle_label = st.radio(
        "회전 방향",
        ["시계 방향으로 90도", "180도 (거꾸로 뒤집기)", "반시계 방향으로 90도"],
        horizontal=True,
    )
    angle = {"시계 방향으로 90도": 90, "180도 (거꾸로 뒤집기)": 180, "반시계 방향으로 90도": -90}[angle_label]

    target = st.radio("대상 페이지", [ALL_PAGES, SOME_PAGES])
    pages_text = ""
    if target == SOME_PAGES:
        pages_text = st.text_input("회전시킬 페이지 번호 (예: 1-3, 5)", placeholder="예: 1-3, 5")

    step_caption(3, "실행 버튼을 눌러주세요")
    if st.button("페이지 회전 실행", type="primary"):
        with friendly_errors("PDF 페이지 회전"):
            file.seek(0)
            reader = PdfReader(file)
            writer = PdfWriter()

            if target == ALL_PAGES:
                target_indices = set(range(total_pages))
            else:
                target_indices = set(parse_page_ranges(pages_text, total_pages))

            for idx, page in enumerate(reader.pages):
                if idx in target_indices:
                    page.rotate(angle)
                writer.add_page(page)

            buffer = io.BytesIO()
            writer.write(buffer)

            step_caption(4, "결과 파일을 받아주세요")
            download_result(
                "회전된 PDF 내려받기",
                buffer.getvalue(),
                f"{file.name.rsplit('.', 1)[0]}_회전.pdf",
                "application/pdf",
            )
