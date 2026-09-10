"""이미지 파일 용량을 줄이는 도구."""
from __future__ import annotations

import io
import zipfile

import streamlit as st
from PIL import Image, ImageOps

from common import download_result, friendly_errors, human_size, step_caption, tool_header

TOOL_META = {
    "name": "이미지 용량 줄이기",
    "category": "이미지",
    "description": "사진의 화질을 적당히 낮춰서 용량을 줄여드려요. 메일 첨부나 업로드가 쉬워져요.",
    "icon": "🗜️",
}


def _load(file) -> Image.Image:
    img = Image.open(io.BytesIO(file.getvalue()))
    return ImageOps.exif_transpose(img)


def _compress(img: Image.Image, quality: int, max_width: int | None) -> bytes:
    if img.mode != "RGB":
        img = img.convert("RGB")
    if max_width and img.width > max_width:
        ratio = max_width / img.width
        img = img.resize((max_width, max(1, int(img.height * ratio))), Image.LANCZOS)
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=quality, optimize=True)
    return buffer.getvalue()


def render() -> None:
    tool_header(TOOL_META["name"], TOOL_META["description"])

    step_caption(1, "용량을 줄일 사진들을 올려주세요")
    files = st.file_uploader(
        "이미지 파일 선택 (여러 개 선택 가능)",
        type=["png", "jpg", "jpeg", "bmp", "webp"],
        accept_multiple_files=True,
    )
    if not files:
        st.info("이미지 파일을 1개 이상 올려주세요.")
        return

    step_caption(2, "압축 강도를 정해주세요")
    st.caption("결과는 항상 JPG 형식으로 저장돼요. (투명 배경이 있던 PNG는 흰 배경으로 바뀌어요)")
    quality = st.slider("화질 (낮을수록 용량이 더 줄어요)", min_value=10, max_value=95, value=70)
    limit_width = st.checkbox("가로 폭도 함께 줄이기 (용량을 더 크게 줄여요)")
    max_width = None
    if limit_width:
        max_width = st.number_input("최대 가로 픽셀", min_value=100, value=1600)

    step_caption(3, "실행 버튼을 눌러주세요")
    if st.button("용량 줄이기 실행", type="primary"):
        with friendly_errors("이미지 용량 줄이기"):
            results: list[tuple[str, bytes, int]] = []
            total_original = 0
            for f in files:
                original_size = len(f.getvalue())
                total_original += original_size
                img = _load(f)
                compressed = _compress(img, quality, max_width)
                results.append((f.name, compressed, original_size))

            step_caption(4, "결과를 확인하고 받아주세요")
            total_new = sum(len(d) for _, d, _ in results)
            col1, col2, col3 = st.columns(3)
            col1.metric("원본 용량 합계", human_size(total_original))
            col2.metric("압축 후 용량 합계", human_size(total_new))
            if total_new < total_original:
                col3.metric("줄어든 비율", f"{(1 - total_new / total_original) * 100:.0f}%")
            else:
                col3.metric("줄어든 비율", "0%")

            st.image(results[0][1], caption=f"미리보기: {results[0][0]}", width=300)

            if len(results) == 1:
                name, data, _ = results[0]
                download_result(
                    "압축된 이미지 내려받기",
                    data,
                    f"{name.rsplit('.', 1)[0]}_압축.jpg",
                    "image/jpeg",
                )
            else:
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                    for name, data, _ in results:
                        zf.writestr(f"{name.rsplit('.', 1)[0]}_압축.jpg", data)
                download_result(
                    "압축된 이미지 모음(zip) 내려받기",
                    zip_buffer.getvalue(),
                    "압축_결과.zip",
                    "application/zip",
                )
