"""스캔본 PDF(사진처럼 찍힌 문서)에서 글자를 인식해서 뽑아내는 도구(OCR)."""
from __future__ import annotations

import pymupdf
import pytesseract
import streamlit as st
from PIL import Image

from common import download_result, friendly_errors, step_caption, tool_header

TOOL_META = {
    "name": "스캔본 글자 인식 (OCR)",
    "category": "PDF",
    "description": "사진처럼 찍힌 스캔본 PDF에서 글자를 읽어내서 보여주고, 텍스트 파일로 내려받을 수 있어요.",
    "icon": "🔍",
}

# 페이지가 너무 많으면 무료 서버에서 시간이 오래 걸려요. 필요하면 'PDF 분할하기'로 나눠서 올려달라고 안내해요.
MAX_PAGES = 40

LANG_OPTIONS = {
    "한국어 + 영어 (기본, 추천)": "kor+eng",
    "한국어만": "kor",
    "영어만": "eng",
}


def render() -> None:
    tool_header(TOOL_META["name"], TOOL_META["description"])

    st.info(
        "💡 이 도구는 사진처럼 찍혀서 글자를 선택·복사할 수 없는 PDF(스캔본)에서 "
        "글자만 읽어서 텍스트로 뽑아드려요. 이미 글자를 선택할 수 있는 일반 PDF라면 "
        "이 도구 없이 그냥 복사하시면 돼요."
    )

    step_caption(1, "글자를 인식할 스캔본 PDF 파일을 올려주세요")
    file = st.file_uploader("PDF 파일 선택", type=["pdf"])
    if not file:
        st.info("PDF 파일을 1개 올려주세요.")
        return

    with friendly_errors("PDF 페이지 수 확인"):
        doc = pymupdf.open(stream=file.getvalue(), filetype="pdf")
        total_pages = doc.page_count
        doc.close()
    st.caption(f"이 파일은 총 {total_pages}쪽이에요.")

    if total_pages > MAX_PAGES:
        st.warning(
            f"⚠️ 페이지가 {total_pages}쪽으로 너무 많아요. 한 번에 최대 {MAX_PAGES}쪽까지 처리할 수 있어요. "
            "**'PDF 분할하기'** 도구로 먼저 나눈 뒤, 나눠서 올려주세요."
        )
        return

    step_caption(2, "인식할 언어를 선택해주세요")
    lang_label = st.radio("언어 선택", list(LANG_OPTIONS.keys()), label_visibility="collapsed")

    step_caption(3, "실행 버튼을 눌러주세요")
    st.caption("페이지 수에 따라 몇십 초 정도 걸릴 수 있어요.")
    if st.button("글자 인식 실행", type="primary"):
        with friendly_errors("스캔본 글자 인식"):
            lang = LANG_OPTIONS[lang_label]
            doc = pymupdf.open(stream=file.getvalue(), filetype="pdf")
            try:
                progress = st.progress(0.0, text="글자를 읽는 중이에요...")
                page_texts: list[str] = []
                for i, page in enumerate(doc):
                    pix = page.get_pixmap(dpi=300)
                    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                    text = pytesseract.image_to_string(img, lang=lang).strip()
                    page_texts.append(f"--- {i + 1}쪽 ---\n{text if text else '(글자를 찾지 못했어요)'}")
                    progress.progress((i + 1) / total_pages, text=f"글자를 읽는 중이에요... ({i + 1}/{total_pages}쪽)")
                progress.empty()
            finally:
                doc.close()

            full_text = "\n\n".join(page_texts)

            step_caption(4, "결과를 확인하고 필요하면 텍스트 파일로 받아주세요")
            st.text_area("인식된 글자", full_text, height=400)

            download_result(
                "인식된 글자 텍스트 파일(.txt)로 내려받기",
                full_text.encode("utf-8-sig"),
                f"{file.name.rsplit('.', 1)[0]}_OCR결과.txt",
                "text/plain",
            )
