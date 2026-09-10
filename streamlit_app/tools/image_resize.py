"""이미지 크기를 바꾸는 도구."""
from __future__ import annotations

import io
import zipfile

import streamlit as st
from PIL import Image, ImageOps

from common import download_result, friendly_errors, step_caption, tool_header

TOOL_META = {
    "name": "이미지 크기 조절",
    "category": "이미지",
    "description": "사진의 가로·세로 크기를 원하는 크기 또는 비율로 바꿔드려요.",
    "icon": "📐",
}

BY_PERCENT = "비율로 (%)"
BY_WIDTH = "가로 픽셀 지정 (세로는 비율에 맞춰 자동)"
BY_EXACT = "가로·세로 픽셀 직접 지정"


def _load(file) -> Image.Image:
    img = Image.open(io.BytesIO(file.getvalue()))
    return ImageOps.exif_transpose(img)


def _resize(img: Image.Image, mode: str, percent: int, width: int, exact_w: int, exact_h: int) -> Image.Image:
    if mode == BY_PERCENT:
        new_w = max(1, int(img.width * percent / 100))
        new_h = max(1, int(img.height * percent / 100))
    elif mode == BY_WIDTH:
        ratio = width / img.width
        new_w = width
        new_h = max(1, int(img.height * ratio))
    else:
        new_w, new_h = exact_w, exact_h
    return img.resize((new_w, new_h), Image.LANCZOS)


def render() -> None:
    tool_header(TOOL_META["name"], TOOL_META["description"])

    step_caption(1, "크기를 바꿀 사진들을 올려주세요")
    files = st.file_uploader(
        "이미지 파일 선택 (여러 개 선택 가능)",
        type=["png", "jpg", "jpeg", "bmp", "webp"],
        accept_multiple_files=True,
    )
    if not files:
        st.info("이미지 파일을 1개 이상 올려주세요.")
        return

    step_caption(2, "크기 조절 방식을 선택해주세요")
    mode = st.radio("방식", [BY_PERCENT, BY_WIDTH, BY_EXACT])
    percent, width, exact_w, exact_h = 50, 800, 800, 600
    if mode == BY_PERCENT:
        percent = st.slider("원본 대비 비율 (%)", min_value=5, max_value=200, value=50)
    elif mode == BY_WIDTH:
        width = st.number_input("가로 픽셀", min_value=1, value=800)
    else:
        col1, col2 = st.columns(2)
        exact_w = col1.number_input("가로 픽셀", min_value=1, value=800)
        exact_h = col2.number_input("세로 픽셀", min_value=1, value=600)
        st.caption("⚠️ 원본 비율과 다르면 사진이 눌리거나 늘어날 수 있어요.")

    step_caption(3, "실행 버튼을 눌러주세요")
    if st.button("크기 조절 실행", type="primary"):
        with friendly_errors("이미지 크기 조절"):
            results: list[tuple[str, bytes, str]] = []
            for f in files:
                img = _load(f)
                resized = _resize(img, mode, percent, width, exact_w, exact_h)
                out_format = (img.format or "PNG").upper()
                if out_format not in ("PNG", "JPEG", "BMP", "WEBP"):
                    out_format = "PNG"
                buffer = io.BytesIO()
                if out_format == "JPEG" and resized.mode != "RGB":
                    resized = resized.convert("RGB")
                resized.save(buffer, format=out_format)
                results.append((f.name, buffer.getvalue(), out_format.lower()))

            step_caption(4, "결과를 받아주세요")
            first_img = _load(files[0])
            first_resized = _resize(first_img, mode, percent, width, exact_w, exact_h)
            st.caption(f"예시 ('{files[0].name}'): {first_img.width}×{first_img.height} → {first_resized.width}×{first_resized.height}")
            st.image(results[0][1], caption="결과 미리보기", width=300)

            if len(results) == 1:
                name, data, ext = results[0]
                download_result(
                    "크기 조절된 이미지 내려받기",
                    data,
                    f"{name.rsplit('.', 1)[0]}_크기조절.{ext}",
                    f"image/{ext}",
                )
            else:
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                    for name, data, ext in results:
                        zf.writestr(f"{name.rsplit('.', 1)[0]}_크기조절.{ext}", data)
                download_result(
                    "크기 조절된 이미지 모음(zip) 내려받기",
                    zip_buffer.getvalue(),
                    "크기조절_결과.zip",
                    "application/zip",
                )
