"""이미지 파일 형식을 바꾸는 도구."""
from __future__ import annotations

import io
import zipfile

import streamlit as st
from PIL import Image, ImageOps

from common import download_result, friendly_errors, step_caption, tool_header

TOOL_META = {
    "name": "이미지 형식 변환",
    "category": "이미지",
    "description": "PNG·JPG·WEBP 등 이미지 파일 형식을 원하는 형식으로 바꿔드려요.",
    "icon": "🔄",
}

FORMAT_OPTIONS = {
    "JPG": ("JPEG", "jpg", "image/jpeg"),
    "PNG": ("PNG", "png", "image/png"),
    "WEBP": ("WEBP", "webp", "image/webp"),
    "BMP": ("BMP", "bmp", "image/bmp"),
}


def _load(file) -> Image.Image:
    img = Image.open(io.BytesIO(file.getvalue()))
    return ImageOps.exif_transpose(img)


def _convert(img: Image.Image, pillow_format: str, quality: int) -> bytes:
    if pillow_format == "JPEG" and img.mode in ("RGBA", "P"):
        # JPG는 투명 배경을 지원하지 않아서, 투명한 부분을 흰 배경으로 채워요
        background = Image.new("RGB", img.size, (255, 255, 255))
        rgba = img.convert("RGBA")
        background.paste(rgba, mask=rgba.split()[-1])
        img = background
    elif img.mode not in ("RGB", "RGBA", "L"):
        img = img.convert("RGBA" if "A" in img.mode else "RGB")

    buffer = io.BytesIO()
    save_kwargs = {"quality": quality} if pillow_format in ("JPEG", "WEBP") else {}
    img.save(buffer, format=pillow_format, **save_kwargs)
    return buffer.getvalue()


def render() -> None:
    tool_header(TOOL_META["name"], TOOL_META["description"])

    step_caption(1, "형식을 바꿀 사진들을 올려주세요")
    files = st.file_uploader(
        "이미지 파일 선택 (여러 개 선택 가능)",
        type=["png", "jpg", "jpeg", "bmp", "webp"],
        accept_multiple_files=True,
    )
    if not files:
        st.info("이미지 파일을 1개 이상 올려주세요.")
        return

    step_caption(2, "바꿀 형식을 선택해주세요")
    target_label = st.radio("바꿀 형식", list(FORMAT_OPTIONS.keys()), horizontal=True)
    pillow_format, ext, mime = FORMAT_OPTIONS[target_label]
    quality = 90
    if pillow_format in ("JPEG", "WEBP"):
        quality = st.slider("화질", min_value=10, max_value=100, value=90)

    step_caption(3, "실행 버튼을 눌러주세요")
    if st.button("형식 변환 실행", type="primary"):
        with friendly_errors("이미지 형식 변환"):
            results: list[tuple[str, bytes]] = []
            for f in files:
                img = _load(f)
                data = _convert(img, pillow_format, quality)
                results.append((f"{f.name.rsplit('.', 1)[0]}.{ext}", data))

            step_caption(4, "결과를 확인하고 받아주세요")
            st.image(results[0][1], caption=f"미리보기: {results[0][0]}", width=300)

            if len(results) == 1:
                name, data = results[0]
                download_result(f"변환된 {target_label} 내려받기", data, name, mime)
            else:
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                    for name, data in results:
                        zf.writestr(name, data)
                download_result(
                    f"변환된 {target_label} 모음(zip) 내려받기",
                    zip_buffer.getvalue(),
                    f"{target_label}_변환결과.zip",
                    "application/zip",
                )
