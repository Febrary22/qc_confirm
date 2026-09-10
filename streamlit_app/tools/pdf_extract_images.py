"""PDF 안에 들어있는 그림·사진만 뽑아내는 도구."""
from __future__ import annotations

import io
import zipfile

import pymupdf
import streamlit as st

from common import download_result, friendly_errors, step_caption, tool_header

TOOL_META = {
    "name": "PDF 이미지 추출",
    "category": "PDF",
    "description": "PDF 안에 들어있는 사진·그림만 따로 뽑아서 파일로 내려받을 수 있어요.",
    "icon": "🏞️",
}


def _extract_images(content: bytes) -> list[tuple[str, bytes]]:
    doc = pymupdf.open(stream=content, filetype="pdf")
    try:
        results: list[tuple[str, bytes]] = []
        seen_xrefs: set[int] = set()
        for page_num, page in enumerate(doc, start=1):
            for img_index, img in enumerate(page.get_images(full=True), start=1):
                xref = img[0]
                if xref in seen_xrefs:
                    continue  # 같은 그림이 여러 페이지에 반복해서 쓰였다면 한 번만 뽑아요
                seen_xrefs.add(xref)
                base_image = doc.extract_image(xref)
                ext = base_image["ext"]
                name = f"{page_num:03d}쪽_이미지{img_index}.{ext}"
                results.append((name, base_image["image"]))
        return results
    finally:
        doc.close()


def render() -> None:
    tool_header(TOOL_META["name"], TOOL_META["description"])

    step_caption(1, "이미지를 뽑아낼 PDF 파일을 올려주세요")
    file = st.file_uploader("PDF 파일 선택", type=["pdf"])
    if not file:
        st.info("PDF 파일을 1개 올려주세요.")
        return

    step_caption(2, "실행 버튼을 눌러주세요")
    if st.button("이미지 추출 실행", type="primary"):
        with friendly_errors("PDF 이미지 추출"):
            images = _extract_images(file.getvalue())

            if not images:
                st.warning("이 PDF 안에서 이미지를 찾지 못했어요. 글자로만 이루어진 문서일 수 있어요.")
                return

            step_caption(3, "결과를 확인하세요")
            st.caption(f"이미지 {len(images)}개를 찾았어요.")
            preview_cols = st.columns(4)
            for i, (name, data) in enumerate(images[:8]):
                with preview_cols[i % 4]:
                    st.image(data, caption=name, use_container_width=True)
            if len(images) > 8:
                st.caption(f"...외 {len(images) - 8}개 (내려받은 zip 파일 안에서 모두 확인할 수 있어요)")

            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                for name, data in images:
                    zf.writestr(name, data)

            step_caption(4, "결과 파일을 받아주세요")
            download_result(
                "추출된 이미지 모음(zip) 내려받기",
                zip_buffer.getvalue(),
                f"{file.name.rsplit('.', 1)[0]}_이미지모음.zip",
                "application/zip",
            )
