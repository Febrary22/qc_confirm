"""업무 자동화 올인원 웹앱 - 메인 진입점.

실행 방법: streamlit run app.py

이 파일은 tools/ 폴더 안의 도구 파일들을 자동으로 찾아서
왼쪽 사이드바 메뉴(카테고리 → 도구 목록)를 만들어 줍니다.
새 도구를 추가하고 싶으면 tools/ 폴더에 파일 하나만 추가하면 됩니다.
자세한 방법은 tools/__init__.py 안의 설명을 참고하세요.
"""
from __future__ import annotations

import importlib
import pkgutil
from dataclasses import dataclass
from typing import Callable

import streamlit as st

import tools as tools_package

# 카테고리는 이 순서로 보여줍니다. (목록에 없는 새 카테고리가 생기면 맨 뒤에 자동으로 붙어요)
CATEGORY_ORDER = ["PDF", "Excel", "한글", "NC데이터", "기타"]
CATEGORY_ICON = {
    "PDF": "📄",
    "Excel": "📊",
    "한글": "📝",
    "NC데이터": "🌊",
    "기타": "🧰",
}


@dataclass(frozen=True)
class ToolInfo:
    key: str  # 모듈 이름 (예: pdf_merge)
    name: str  # 화면에 보여줄 이름 (예: "PDF 합치기")
    category: str
    description: str
    icon: str
    render: Callable[[], None]


@st.cache_resource(show_spinner=False)
def load_tools() -> list[ToolInfo]:
    """tools/ 폴더 안의 모든 도구 파일을 찾아서 등록합니다."""
    found: list[ToolInfo] = []
    for module_info in pkgutil.iter_modules(tools_package.__path__):
        module_name = module_info.name
        if module_name.startswith("_"):
            continue  # _로 시작하는 파일(공용 코드 등)은 도구가 아니므로 건너뜁니다
        module = importlib.import_module(f"tools.{module_name}")

        meta = getattr(module, "TOOL_META", None)
        render_fn = getattr(module, "render", None)
        if meta is None or render_fn is None:
            # 인터페이스(TOOL_META, render())를 지키지 않은 파일은 메뉴에 넣지 않습니다
            continue

        found.append(
            ToolInfo(
                key=module_name,
                name=meta.get("name", module_name),
                category=meta.get("category", "기타"),
                description=meta.get("description", ""),
                icon=meta.get("icon", "🔧"),
                render=render_fn,
            )
        )
    found.sort(key=lambda t: t.name)
    return found


def category_sort_key(category: str) -> tuple[int, str]:
    if category in CATEGORY_ORDER:
        return (CATEGORY_ORDER.index(category), category)
    return (len(CATEGORY_ORDER), category)


def main() -> None:
    st.set_page_config(
        page_title="업무 자동화 올인원",
        page_icon="🧰",
        layout="wide",
    )

    all_tools = load_tools()
    categories = sorted({t.category for t in all_tools} | set(CATEGORY_ORDER), key=category_sort_key)

    st.sidebar.title("🧰 업무 자동화 올인원")
    search_keyword = st.sidebar.text_input(
        "🔍 도구 이름으로 검색",
        placeholder="예: 병합, 분할, 시트 이름...",
    )

    selected_tool: ToolInfo | None = None

    if search_keyword.strip():
        # 검색어가 있으면 카테고리와 상관없이 이름/설명에 검색어가 들어간 도구만 보여줍니다
        keyword = search_keyword.strip().lower()
        matched = [
            t for t in all_tools
            if keyword in t.name.lower() or keyword in t.description.lower()
        ]
        st.sidebar.caption(f"검색 결과 {len(matched)}개")
        if matched:
            labels = [f"{t.icon} {t.name}" for t in matched]
            picked = st.sidebar.radio("검색된 도구", labels, label_visibility="collapsed")
            selected_tool = matched[labels.index(picked)]
        else:
            st.sidebar.info("일치하는 도구가 없어요. 다른 검색어로 찾아보세요.")
    else:
        st.sidebar.markdown("### 카테고리")
        selected_category = st.sidebar.radio(
            "카테고리를 선택하세요",
            categories,
            format_func=lambda c: f"{CATEGORY_ICON.get(c, '📁')} {c}",
            label_visibility="collapsed",
        )

        tools_in_category = [t for t in all_tools if t.category == selected_category]

        st.sidebar.markdown("### 도구 목록")
        if not tools_in_category:
            st.sidebar.info("이 카테고리는 준비 중이에요. 곧 추가될 예정입니다!")
        else:
            labels = [f"{t.icon} {t.name}" for t in tools_in_category]
            picked = st.sidebar.radio(
                "도구를 선택하세요", labels, label_visibility="collapsed"
            )
            selected_tool = tools_in_category[labels.index(picked)]

    st.sidebar.divider()
    st.sidebar.caption("문의나 새 도구 요청은 담당자에게 말씀해 주세요 🙂")

    if selected_tool is None:
        st.title("🧰 업무 자동화 올인원")
        st.write(
            "왼쪽에서 카테고리를 고르거나, 검색창에 원하는 도구 이름을 입력해 보세요.\n\n"
            "모든 도구는 **① 파일 올리기 → ② 옵션 선택 → ③ 실행 → ④ 결과 받기** "
            "순서로 똑같이 동작해서 처음 써도 어렵지 않아요."
        )
        if all_tools:
            st.subheader("현재 사용할 수 있는 도구")
            cols = st.columns(3)
            for i, t in enumerate(all_tools):
                with cols[i % 3]:
                    st.markdown(f"**{t.icon} {t.name}** ({t.category})")
                    st.caption(t.description)
        return

    selected_tool.render()


if __name__ == "__main__":
    main()
