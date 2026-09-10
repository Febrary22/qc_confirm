"""한글(HWP/HWPX) 파일의 글자 내용을 PDF 문서로 만드는 도구."""
from __future__ import annotations

import io
from pathlib import Path

import pymupdf
import streamlit as st

from common import download_result, friendly_errors, step_caption, tool_header
from tools.hwp_text_extract import _extract_hwp_preview_text, _extract_hwpx_text

TOOL_META = {
    "name": "한글 파일을 PDF로 변환",
    "category": "한글",
    "description": "한글(.hwp, .hwpx) 파일의 글자 내용을 읽어서 PDF 문서로 만들어드려요.",
    "icon": "📄",
}

FONT_PATH = Path(__file__).resolve().parent.parent / "assets" / "NanumGothic.ttf"
PAGE_WIDTH, PAGE_HEIGHT = 595, 842  # A4
MARGIN = 50
TEXT_RECT = pymupdf.Rect(MARGIN, MARGIN, PAGE_WIDTH - MARGIN, PAGE_HEIGHT - MARGIN)


def _fits_one_page(text: str, fontsize: int) -> bool:
    """이 글자가 A4 한 페이지 안에 다 들어가는지 확인합니다. (실제로 그리지 않고 확인만 해요)"""
    scratch = pymupdf.open()
    try:
        page = scratch.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
        remaining = page.insert_textbox(
            TEXT_RECT, text, fontsize=fontsize, fontfile=str(FONT_PATH), fontname="nanum"
        )
        return remaining >= 0
    finally:
        scratch.close()


def _split_long_paragraph(paragraph: str, fontsize: int) -> list[str]:
    """한 페이지보다도 긴 문단 하나를 여러 조각으로 잘라줍니다."""
    words = paragraph.split(" ")
    chunks: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if _fits_one_page(candidate, fontsize):
            current = candidate
        else:
            if current:
                chunks.append(current)
            current = word
    if current:
        chunks.append(current)
    return chunks or [paragraph]


def _paginate(paragraphs: list[str], fontsize: int) -> list[str]:
    """문단 목록을 여러 페이지 분량의 글자 묶음으로 나눕니다."""
    pages: list[str] = []
    buffer = ""

    def flush() -> None:
        nonlocal buffer
        if buffer:
            pages.append(buffer)
            buffer = ""

    for para in paragraphs:
        if not para.strip():
            continue
        if not buffer and not _fits_one_page(para, fontsize):
            for chunk in _split_long_paragraph(para, fontsize):
                candidate = f"{buffer}\n{chunk}".strip("\n") if buffer else chunk
                if _fits_one_page(candidate, fontsize):
                    buffer = candidate
                else:
                    flush()
                    buffer = chunk
            continue

        candidate = f"{buffer}\n{para}" if buffer else para
        if _fits_one_page(candidate, fontsize):
            buffer = candidate
        else:
            flush()
            buffer = para

    flush()
    return pages


def _build_pdf(text: str, fontsize: int) -> bytes:
    paragraphs = [p for p in text.split("\n")]
    pages_text = _paginate(paragraphs, fontsize)
    if not pages_text:
        raise ValueError("PDF로 만들 글자 내용이 없어요.")

    doc = pymupdf.open()
    for page_text in pages_text:
        page = doc.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
        page.insert_textbox(
            TEXT_RECT, page_text, fontsize=fontsize, fontfile=str(FONT_PATH), fontname="nanum"
        )

    doc.subset_fonts()  # 실제 쓰인 글자만 남겨서 파일 용량을 크게 줄여요
    buffer = io.BytesIO()
    doc.save(buffer, garbage=4, deflate=True)
    doc.close()
    return buffer.getvalue()


def render() -> None:
    tool_header(TOOL_META["name"], TOOL_META["description"])

    st.info(
        "💡 이 도구는 문서 안의 **글자 내용만** 읽어서 새 PDF로 다시 만들어드려요. "
        "표·이미지·원본 그대로의 디자인은 옮겨지지 않으니, 그런 요소가 중요한 문서라면 "
        "원본 파일을 그대로 쓰시는 걸 추천해요.\n\n"
        "**hwpx**(한글 2014 이후 파일)는 본문 전체가, **hwp**(예전 방식 파일)는 문서에 저장된 "
        "미리보기 글자만 변환돼요."
    )

    step_caption(1, "PDF로 만들 한글 파일을 올려주세요")
    file = st.file_uploader("한글 파일 선택 (.hwp 또는 .hwpx)", type=["hwp", "hwpx"])
    if not file:
        st.info("hwp 또는 hwpx 파일을 1개 올려주세요.")
        return

    step_caption(2, "글자 크기를 선택해주세요")
    fontsize = st.select_slider("글자 크기(pt)", options=[9, 10, 11, 12, 14, 16], value=11)

    step_caption(3, "실행 버튼을 눌러주세요")
    if st.button("PDF로 변환하기 실행", type="primary"):
        with friendly_errors("한글 파일을 PDF로 변환"):
            content = file.getvalue()
            is_hwpx = file.name.lower().endswith(".hwpx") or content[:2] == b"PK"

            text = _extract_hwpx_text(content) if is_hwpx else _extract_hwp_preview_text(content)
            text = text.strip()
            if not text:
                st.warning("이 파일에서 글자를 찾지 못했어요. 표나 그림만 있는 문서일 수 있어요.")
                return

            pdf_bytes = _build_pdf(text, fontsize)

            step_caption(4, "결과 파일을 받아주세요")
            download_result(
                "변환된 PDF 내려받기",
                pdf_bytes,
                f"{file.name.rsplit('.', 1)[0]}_변환.pdf",
                "application/pdf",
            )
