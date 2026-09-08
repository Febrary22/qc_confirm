"""한글(HWP/HWPX) 파일에서 글자만 뽑아내는 도구."""
from __future__ import annotations

import io
import zipfile
from xml.etree import ElementTree as ET

import olefile
import streamlit as st

from common import download_result, friendly_errors, step_caption, tool_header

TOOL_META = {
    "name": "한글 파일 텍스트 꺼내기",
    "category": "한글",
    "description": "한글(.hwp, .hwpx) 파일 안의 글자 내용만 뽑아서 보여주고, 텍스트 파일로 내려받을 수 있어요.",
    "icon": "📝",
}


def _local_tag(tag: str) -> str:
    """XML 태그에서 네임스페이스를 떼고 이름만 돌려줍니다. (예: '{...}t' → 't')"""
    return tag.split("}")[-1] if "}" in tag else tag


def _extract_hwpx_text(content: bytes) -> str:
    """hwpx(신 버전 한글, zip+xml 구조)에서 본문 글자를 그대로 뽑아냅니다."""
    try:
        zf = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile as exc:
        raise ValueError("hwpx 파일 형식이 이상해요. 파일이 손상되지 않았는지 확인해 주세요.") from exc

    section_names = sorted(
        name for name in zf.namelist() if name.startswith("Contents/section") and name.endswith(".xml")
    )
    if not section_names:
        raise ValueError("이 파일에서 본문 내용을 찾지 못했어요. hwpx(한글 2014 이후 저장) 파일이 맞는지 확인해 주세요.")

    paragraphs: list[str] = []
    for name in section_names:
        root = ET.fromstring(zf.read(name))
        for elem in root.iter():
            if _local_tag(elem.tag) != "p":
                continue
            runs = [child.text for child in elem.iter() if _local_tag(child.tag) == "t" and child.text]
            paragraphs.append("".join(runs))
    return "\n".join(paragraphs)


def _extract_hwp_preview_text(content: bytes) -> str:
    """구버전 hwp(OLE 압축 문서) 파일의 '미리보기 텍스트' 스트림에서 글자를 뽑아냅니다.

    구버전 hwp는 본문이 압축·암호화에 가까운 이진 구조로 저장되어 있어 정확한 전체 본문
    추출이 매우 복잡해요. 대신 한글 프로그램이 자동으로 만들어 두는 '미리보기(PrvText)'
    글자를 사용합니다. 문서가 길면 앞부분 위주로만 나올 수 있어요.
    """
    try:
        ole = olefile.OleFileIO(io.BytesIO(content))
    except Exception as exc:
        raise ValueError(
            "hwp 파일을 열지 못했어요. 진짜 한글(.hwp) 파일이 맞는지, 파일이 손상되지 않았는지 확인해 주세요."
        ) from exc

    try:
        streams = ["PrvText"]
        stream_path = next((s for s in ole.listdir() if s and s[-1] in streams), None)
        if stream_path is None:
            raise ValueError(
                "이 파일에서 미리보기 텍스트를 찾지 못했어요. 정상적인 한글(.hwp) 파일인지 확인해 주세요."
            )
        raw = ole.openstream(stream_path).read()
    finally:
        ole.close()

    return raw.decode("utf-16-le", errors="ignore")


def render() -> None:
    tool_header(TOOL_META["name"], TOOL_META["description"])

    st.info(
        "💡 **hwpx**(한글 2014 이후 '한글2020 XML 문서'로 저장한 파일)는 본문 전체를 그대로 뽑아드려요.\n\n"
        "**hwp**(예전 방식 문서)는 문서 안에 저장된 '미리보기 글자'만 뽑을 수 있어서, "
        "문서가 길면 앞부분만 나올 수 있어요. 전체 내용이 필요하면 한글 프로그램에서 "
        "**다른 이름으로 저장 → HWPX** 로 바꾼 뒤 다시 올려주세요."
    )

    step_caption(1, "글자를 뽑아낼 한글 파일을 올려주세요")
    file = st.file_uploader("한글 파일 선택 (.hwp 또는 .hwpx)", type=["hwp", "hwpx"])
    if not file:
        st.info("hwp 또는 hwpx 파일을 1개 올려주세요.")
        return

    step_caption(2, "실행 버튼을 눌러주세요")
    if st.button("글자 뽑아내기 실행", type="primary"):
        with friendly_errors("한글 파일에서 글자 뽑기"):
            content = file.getvalue()
            is_hwpx = file.name.lower().endswith(".hwpx") or content[:2] == b"PK"

            if is_hwpx:
                text = _extract_hwpx_text(content)
            else:
                text = _extract_hwp_preview_text(content)

            text = text.strip()
            if not text:
                st.warning("이 파일에서는 글자를 찾지 못했어요. 표나 그림만 있는 문서일 수 있어요.")
                return

            step_caption(3, "결과를 확인하고 필요하면 텍스트 파일로 받아주세요")
            st.text_area("뽑아낸 글자", text, height=400)

            download_result(
                "글자 내용 텍스트 파일(.txt)로 내려받기",
                text.encode("utf-8-sig"),
                f"{file.name.rsplit('.', 1)[0]}_텍스트.txt",
                "text/plain",
            )
