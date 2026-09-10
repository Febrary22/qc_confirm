"""PDF에 워터마크(대외비 등 반복 글자)를 넣는 도구."""
from __future__ import annotations

import io
from pathlib import Path

import pymupdf
import streamlit as st

from common import download_result, friendly_errors, step_caption, tool_header

TOOL_META = {
    "name": "PDF 워터마크 넣기",
    "category": "PDF",
    "description": "PDF 모든 페이지에 '대외비', '초안' 같은 글자를 옅게 반복해서 넣어드려요.",
    "icon": "💧",
}

FONT_PATH = Path(__file__).resolve().parent.parent / "assets" / "NanumGothic.ttf"

CENTER_ONLY = "가운데에 하나만"
TILE_FULL = "페이지 전체에 반복해서 채우기 (추천)"


def _add_watermark(
    content: bytes, text: str, fontsize: int, opacity: float, placement: str
) -> bytes:
    doc = pymupdf.open(stream=content, filetype="pdf")
    try:
        for page in doc:
            rect = page.rect
            mat = pymupdf.Matrix(45)

            if placement == CENTER_ONLY:
                center = pymupdf.Point(rect.width / 2, rect.height / 2)
                page.insert_text(
                    (center.x - len(text) * fontsize * 0.3, center.y),
                    text,
                    fontsize=fontsize,
                    fontfile=str(FONT_PATH),
                    fontname="nanum",
                    color=(0.55, 0.55, 0.55),
                    fill_opacity=opacity,
                    morph=(center, mat),
                )
            else:
                step_x = fontsize * (len(text) + 4)
                step_y = fontsize * 4
                y = -step_y
                while y < rect.height + step_y:
                    x = -step_x
                    while x < rect.width + step_x:
                        anchor = pymupdf.Point(x, y)
                        page.insert_text(
                            (x, y),
                            text,
                            fontsize=fontsize,
                            fontfile=str(FONT_PATH),
                            fontname="nanum",
                            color=(0.55, 0.55, 0.55),
                            fill_opacity=opacity,
                            morph=(anchor, mat),
                        )
                        x += step_x
                    y += step_y

        doc.subset_fonts()  # 실제 쓰인 글자만 남겨서 파일 용량을 줄여요
        buffer = io.BytesIO()
        doc.save(buffer, garbage=4, deflate=True)
        return buffer.getvalue()
    finally:
        doc.close()


def render() -> None:
    tool_header(TOOL_META["name"], TOOL_META["description"])

    step_caption(1, "워터마크를 넣을 PDF 파일을 올려주세요")
    file = st.file_uploader("PDF 파일 선택", type=["pdf"])
    if not file:
        st.info("PDF 파일을 1개 올려주세요.")
        return

    step_caption(2, "워터마크 내용을 정해주세요")
    text = st.text_input("워터마크 글자", value="대외비")
    col1, col2 = st.columns(2)
    with col1:
        fontsize = st.slider("글자 크기", min_value=16, max_value=60, value=32)
    with col2:
        opacity = st.slider("진하기 (연하게 ~ 진하게)", min_value=0.1, max_value=0.8, value=0.3)
    placement = st.radio("배치 방식", [TILE_FULL, CENTER_ONLY])

    step_caption(3, "실행 버튼을 눌러주세요")
    if st.button("워터마크 넣기 실행", type="primary"):
        with friendly_errors("PDF 워터마크 넣기"):
            if not text.strip():
                raise ValueError("워터마크로 넣을 글자를 입력해 주세요.")

            result_bytes = _add_watermark(file.getvalue(), text.strip(), fontsize, opacity, placement)

            step_caption(4, "결과 파일을 받아주세요")
            download_result(
                "워터마크 넣은 PDF 내려받기",
                result_bytes,
                f"{file.name.rsplit('.', 1)[0]}_워터마크.pdf",
                "application/pdf",
            )
