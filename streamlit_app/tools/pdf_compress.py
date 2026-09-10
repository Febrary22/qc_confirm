"""PDF 파일 용량을 줄이는 도구."""
from __future__ import annotations

import io

import pymupdf
import streamlit as st
from PIL import Image

from common import download_result, friendly_errors, human_size, step_caption, tool_header

TOOL_META = {
    "name": "PDF 용량 줄이기",
    "category": "PDF",
    "description": "큰 PDF 파일의 용량을 줄여서 메일 첨부나 저장이 쉬워지게 해드려요.",
    "icon": "🗜️",
}

SAFE_MODE = "안전하게 정리만 하기 (화질 그대로, 용량은 조금만 줄어요)"
STRONG_MODE = "화질을 낮춰서 크게 줄이기 (스캔본·사진 위주 PDF에 효과적이에요)"

# (표시 이름, 렌더링 해상도(DPI), JPEG 화질)
STRENGTH_LEVELS = {
    "약하게 (화질 우선)": (150, 85),
    "보통": (120, 70),
    "강하게 (용량 최소화)": (90, 55),
}


def _compress_safe(content: bytes) -> bytes:
    """페이지 그림은 그대로 두고, 문서 구조만 정리해서 약간 줄입니다."""
    doc = pymupdf.open(stream=content, filetype="pdf")
    try:
        buffer = io.BytesIO()
        doc.save(buffer, garbage=4, deflate=True, clean=True)
        return buffer.getvalue()
    finally:
        doc.close()


def _compress_strong(content: bytes, dpi: int, jpeg_quality: int) -> bytes:
    """각 페이지를 낮은 화질의 그림으로 다시 그려서 용량을 크게 줄입니다.

    이 방식은 페이지를 통째로 이미지로 바꾸기 때문에, 원래 글자를 선택·복사할 수 있던
    PDF였다면 그 기능을 잃게 돼요. 스캔한 문서처럼 원래도 그림 위주였던 PDF에 적합해요.
    """
    doc = pymupdf.open(stream=content, filetype="pdf")
    try:
        page_images: list[Image.Image] = []
        for page in doc:
            pix = page.get_pixmap(dpi=dpi)
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            page_images.append(img)
    finally:
        doc.close()

    if not page_images:
        raise ValueError("이 PDF에서 페이지를 찾지 못했어요.")

    buffer = io.BytesIO()
    first, rest = page_images[0], page_images[1:]
    first.save(
        buffer,
        format="PDF",
        save_all=True,
        append_images=rest,
        quality=jpeg_quality,
    )
    return buffer.getvalue()


def render() -> None:
    tool_header(TOOL_META["name"], TOOL_META["description"])

    step_caption(1, "용량을 줄일 PDF 파일을 올려주세요")
    file = st.file_uploader("PDF 파일 선택", type=["pdf"])
    if not file:
        st.info("PDF 파일을 1개 올려주세요.")
        return

    original_bytes = file.getvalue()
    st.caption(f"원본 용량: {human_size(len(original_bytes))}")

    step_caption(2, "압축 방식을 선택해주세요")
    mode = st.radio("압축 방식", [SAFE_MODE, STRONG_MODE], label_visibility="collapsed")

    strength_label = None
    if mode == STRONG_MODE:
        strength_label = st.select_slider(
            "압축 강도", options=list(STRENGTH_LEVELS.keys()), value="보통"
        )
        st.caption(
            "⚠️ 이 방식은 페이지를 사진처럼 다시 그려서 용량을 줄여요. "
            "원래 글자를 마우스로 선택·복사할 수 있던 PDF라면, 압축 후에는 그게 안 될 수 있어요."
        )

    step_caption(3, "실행 버튼을 눌러주세요")
    if st.button("PDF 용량 줄이기 실행", type="primary"):
        with friendly_errors("PDF 용량 줄이기"):
            if mode == SAFE_MODE:
                result_bytes = _compress_safe(original_bytes)
            else:
                dpi, jpeg_quality = STRENGTH_LEVELS[strength_label]
                result_bytes = _compress_strong(original_bytes, dpi, jpeg_quality)

            step_caption(4, "결과를 확인하고 받아주세요")
            original_size = len(original_bytes)
            new_size = len(result_bytes)

            col1, col2, col3 = st.columns(3)
            col1.metric("원본 용량", human_size(original_size))
            col2.metric("압축 후 용량", human_size(new_size))
            if new_size < original_size:
                reduced_pct = (1 - new_size / original_size) * 100
                col3.metric("줄어든 비율", f"{reduced_pct:.0f}%")
            else:
                col3.metric("줄어든 비율", "0%")
                st.warning(
                    "이 파일은 이미 최적화가 잘 되어 있어서 용량이 거의 줄지 않았어요. "
                    "이미 글자·벡터 위주인 PDF는 원래 용량이 작은 경우가 많아요."
                )

            download_result(
                "압축된 PDF 내려받기",
                result_bytes,
                f"{file.name.rsplit('.', 1)[0]}_압축.pdf",
                "application/pdf",
            )
