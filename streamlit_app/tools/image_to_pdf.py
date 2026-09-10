"""여러 장의 사진을 순서대로 하나의 PDF로 만드는 도구."""
from __future__ import annotations

import io

import pandas as pd
import streamlit as st
from PIL import Image, ImageOps

from common import download_result, friendly_errors, step_caption, tool_header

TOOL_META = {
    "name": "이미지를 PDF로 만들기",
    "category": "PDF",
    "description": "사진 여러 장을 원하는 순서로 하나의 PDF 파일로 합쳐드려요.",
    "icon": "🖼️",
}


def _load_as_rgb(file) -> Image.Image:
    img = Image.open(io.BytesIO(file.getvalue()))
    img = ImageOps.exif_transpose(img)  # 휴대폰 사진의 회전 정보를 반영해요
    if img.mode != "RGB":
        img = img.convert("RGB")
    return img


def render() -> None:
    tool_header(TOOL_META["name"], TOOL_META["description"])

    step_caption(1, "PDF로 합칠 사진들을 올려주세요")
    files = st.file_uploader(
        "이미지 파일 선택 (여러 개 선택 가능)",
        type=["png", "jpg", "jpeg", "bmp", "webp"],
        accept_multiple_files=True,
    )
    if not files:
        st.info("이미지 파일을 1개 이상 올려주세요.")
        return

    step_caption(2, "PDF 안에 들어갈 순서를 정해주세요 (숫자가 작을수록 앞 페이지예요)")
    order_df = pd.DataFrame(
        {
            "파일명": [f.name for f in files],
            "순서": list(range(1, len(files) + 1)),
        }
    )
    edited = st.data_editor(
        order_df,
        hide_index=True,
        use_container_width=True,
        disabled=["파일명"],
        key="image_to_pdf_order_editor",
    )

    step_caption(3, "실행 버튼을 눌러주세요")
    if st.button("PDF 만들기 실행", type="primary"):
        with friendly_errors("이미지를 PDF로 만들기"):
            files_by_name: dict[str, list] = {}
            for f in files:
                files_by_name.setdefault(f.name, []).append(f)

            ordered_rows = edited.sort_values("순서")
            used_index: dict[str, int] = {}
            images: list[Image.Image] = []
            for _, row in ordered_rows.iterrows():
                name = row["파일명"]
                idx = used_index.get(name, 0)
                used_index[name] = idx + 1
                images.append(_load_as_rgb(files_by_name[name][idx]))

            if not images:
                raise ValueError("변환할 이미지가 없어요.")

            buffer = io.BytesIO()
            first, rest = images[0], images[1:]
            first.save(buffer, format="PDF", save_all=True, append_images=rest)

            step_caption(4, "결과 파일을 받아주세요")
            download_result(
                "만들어진 PDF 내려받기",
                buffer.getvalue(),
                "이미지_모음.pdf",
                "application/pdf",
            )
