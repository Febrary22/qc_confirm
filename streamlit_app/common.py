"""여러 도구에서 함께 쓰는 화면 구성 도우미 모음.

tools/ 아래 각 도구 파일이 공통으로 사용하는 함수들을 모아둔 곳입니다.
(이 파일은 도구 목록에 자동으로 나타나지 않습니다 - tools/ 폴더 밖에 있어요)
"""
from __future__ import annotations

import contextlib
import traceback
from typing import Iterator

import streamlit as st


def tool_header(title: str, description: str) -> None:
    """도구 맨 위에 제목과 1줄 설명을 보여줍니다."""
    st.markdown(f"## {title}")
    st.caption(description)
    st.divider()


@contextlib.contextmanager
def friendly_errors(step_name: str = "작업") -> Iterator[None]:
    """작업 중 오류가 나면 사용자에게 이해하기 쉬운 안내 메시지를 보여줍니다."""
    try:
        yield
    except Exception as exc:  # noqa: BLE001 - 사용자에게 보여주기 위해 모두 잡습니다
        st.error(
            f"😥 {step_name} 중 문제가 생겼어요.\n\n"
            f"**원인 추정:** {exc}\n\n"
            "파일이 손상되지 않았는지, 요청하신 옵션(페이지 번호, 시트 이름 등)이 "
            "올바른지 다시 한번 확인해 주세요. 그래도 안 되면 담당자에게 이 메시지를 "
            "함께 전달해 주세요."
        )
        with st.expander("자세한 오류 내용 보기 (담당자 전달용)"):
            st.code(traceback.format_exc())


def download_result(label: str, data: bytes, file_name: str, mime: str) -> None:
    """결과 파일을 내려받는 버튼을 보여줍니다."""
    st.success("✅ 작업이 끝났어요! 아래 버튼으로 결과 파일을 받아주세요.")
    st.download_button(
        label=label,
        data=data,
        file_name=file_name,
        mime=mime,
        use_container_width=True,
    )


def step_caption(number: int, text: str) -> None:
    """1) 파일 업로드 → 2) 옵션 선택 → 3) 실행 → 4) 다운로드 흐름을 표시합니다."""
    st.markdown(f"**{number}단계. {text}**")


def parse_page_ranges(text: str, total_pages: int) -> list[int]:
    """"1-3, 5, 7-9" 같은 글자를 0부터 시작하는 페이지 번호 목록으로 바꿔줍니다.

    사람이 이해하는 페이지 번호(1부터 시작)를 그대로 입력받고,
    내부적으로만 0부터 시작하는 번호로 바꿔서 돌려줍니다.
    """
    text = (text or "").strip()
    if not text:
        raise ValueError("페이지 번호를 입력해 주세요. 예: 1-3, 5, 7-9")

    pages: list[int] = []
    for chunk in text.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "-" in chunk:
            start_str, end_str = chunk.split("-", 1)
            try:
                start, end = int(start_str.strip()), int(end_str.strip())
            except ValueError as exc:
                raise ValueError(f"'{chunk}' 부분이 숫자 범위가 아니에요. 예: 1-3") from exc
            if start > end:
                start, end = end, start
            pages.extend(range(start, end + 1))
        else:
            try:
                pages.append(int(chunk))
            except ValueError as exc:
                raise ValueError(f"'{chunk}' 부분이 숫자가 아니에요.") from exc

    for page in pages:
        if page < 1 or page > total_pages:
            raise ValueError(
                f"{page}쪽은 이 파일에 없어요. 이 파일은 1쪽부터 {total_pages}쪽까지 있어요."
            )

    # 순서를 지키면서 중복 제거, 0부터 시작하는 번호로 변환
    seen: set[int] = set()
    result: list[int] = []
    for page in pages:
        zero_based = page - 1
        if zero_based not in seen:
            seen.add(zero_based)
            result.append(zero_based)
    return result
