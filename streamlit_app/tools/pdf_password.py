"""PDF에 비밀번호를 걸거나 푸는 도구."""
from __future__ import annotations

import io

import streamlit as st
from pypdf import PdfReader, PdfWriter

from common import download_result, friendly_errors, step_caption, tool_header

TOOL_META = {
    "name": "PDF 비밀번호 걸기·풀기",
    "category": "PDF",
    "description": "PDF 파일에 열람 비밀번호를 새로 걸거나, 걸려있는 비밀번호를 풀어드려요.",
    "icon": "🔒",
}

LOCK_MODE = "🔒 비밀번호 걸기 (지금 비밀번호가 없는 PDF에)"
UNLOCK_MODE = "🔓 비밀번호 풀기 (지금 비밀번호가 걸린 PDF에서)"


def _lock_pdf(content: bytes, password: str) -> bytes:
    reader = PdfReader(io.BytesIO(content))
    if reader.is_encrypted:
        raise ValueError("이미 비밀번호가 걸려있는 PDF예요. 먼저 '비밀번호 풀기'로 풀고 나서 다시 걸어주세요.")

    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.encrypt(user_password=password, algorithm="AES-256")

    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def _unlock_pdf(content: bytes, password: str) -> bytes:
    reader = PdfReader(io.BytesIO(content))
    if not reader.is_encrypted:
        raise ValueError("이 PDF에는 애초에 비밀번호가 걸려있지 않아요.")

    result = reader.decrypt(password)
    if int(result) == 0:
        raise ValueError("비밀번호가 맞지 않아요. 다시 확인하고 입력해 주세요.")

    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)

    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def render() -> None:
    tool_header(TOOL_META["name"], TOOL_META["description"])

    step_caption(1, "무엇을 할지 정하고, 대상 PDF 파일을 올려주세요")
    mode = st.radio("작업 선택", [LOCK_MODE, UNLOCK_MODE], label_visibility="collapsed")
    file = st.file_uploader("PDF 파일 선택", type=["pdf"])
    if not file:
        st.info("PDF 파일을 1개 올려주세요.")
        return

    step_caption(2, "비밀번호를 입력해주세요")
    if mode == LOCK_MODE:
        password = st.text_input("새로 설정할 비밀번호", type="password")
        password_confirm = st.text_input("비밀번호 확인 (다시 한번 입력)", type="password")
    else:
        password = st.text_input("현재 걸려있는 비밀번호", type="password")
        password_confirm = None

    step_caption(3, "실행 버튼을 눌러주세요")
    button_label = "비밀번호 걸기 실행" if mode == LOCK_MODE else "비밀번호 풀기 실행"
    if st.button(button_label, type="primary"):
        with friendly_errors("PDF 비밀번호 처리"):
            if not password:
                raise ValueError("비밀번호를 입력해 주세요.")
            if mode == LOCK_MODE:
                if len(password) < 4:
                    raise ValueError("비밀번호는 4자 이상으로 설정해 주세요.")
                if password != password_confirm:
                    raise ValueError("비밀번호 확인이 일치하지 않아요. 다시 입력해 주세요.")
                result_bytes = _lock_pdf(file.getvalue(), password)
                result_name = f"{file.name.rsplit('.', 1)[0]}_잠금.pdf"
                success_label = "비밀번호가 걸린 PDF 내려받기"
            else:
                result_bytes = _unlock_pdf(file.getvalue(), password)
                result_name = f"{file.name.rsplit('.', 1)[0]}_잠금해제.pdf"
                success_label = "비밀번호가 풀린 PDF 내려받기"

            step_caption(4, "결과 파일을 받아주세요")
            download_result(success_label, result_bytes, result_name, "application/pdf")
            if mode == LOCK_MODE:
                st.warning("⚠️ 설정하신 비밀번호는 저장되지 않아요. 잊어버리지 않게 따로 기록해 두세요.")
