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

import board
import tools as tools_package

# 카테고리는 이 순서로 보여줍니다. (목록에 없는 새 카테고리가 생기면 맨 뒤에 자동으로 붙어요)
CATEGORY_ORDER = ["PDF", "Excel", "한글", "NC데이터", "이미지", "기타"]
CATEGORY_ICON = {
    "PDF": "📄",
    "Excel": "📊",
    "한글": "📝",
    "NC데이터": "🌊",
    "이미지": "🖼️",
    "기타": "🧰",
}

CONTACT_EMAIL = "kimyj3718@gmail.com"
RELAY_URL = "https://claude.ai/code/artifact/411b3c7f-2246-4b28-89d1-4b350eb428cc"


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


def render_home(all_tools: list[ToolInfo]) -> None:
    """처음 들어왔을 때(또는 홈으로 돌아왔을 때) 보여줄 소개 화면."""
    st.title("🧰 업무 자동화 올인원에 오신 걸 환영해요!")
    st.write(
        "반복되는 사무 작업(파일 합치기, 나누기, 순서 바꾸기 같은 것들)을 "
        "몇 번의 클릭만으로 끝낼 수 있도록 만든 사내 공용 도구예요."
    )

    st.subheader("🚀 이렇게 써보세요")
    step_cols = st.columns(4)
    steps = [
        ("1️⃣", "카테고리 선택", "왼쪽 사이드바에서 PDF / Excel / 한글 / NC데이터 중 원하는 분류를 골라요."),
        ("2️⃣", "도구 선택", "그 안에서 하고 싶은 작업(예: PDF 합치기)을 클릭해요."),
        ("3️⃣", "파일 올리고 옵션 선택", "화면 안내를 따라 파일을 올리고, 필요한 옵션을 정해요."),
        ("4️⃣", "실행 → 다운로드", "실행 버튼을 누르면 결과 파일을 바로 받을 수 있어요."),
    ]
    for col, (icon, title, desc) in zip(step_cols, steps):
        with col:
            st.markdown(f"**{icon} {title}**")
            st.caption(desc)

    st.caption(
        "💡 어떤 도구든 **① 파일 올리기 → ② 옵션 선택 → ③ 실행 → ④ 결과 받기** 순서로 "
        "똑같이 동작해서, 하나만 써봐도 나머지는 금방 익숙해져요. "
        "원하는 도구를 못 찾겠으면 위쪽 검색창에 이름을 입력해 보세요."
    )

    st.divider()

    if all_tools:
        st.subheader("📦 지금 사용할 수 있는 도구")
        by_category: dict[str, list[ToolInfo]] = {}
        for t in all_tools:
            by_category.setdefault(t.category, []).append(t)

        ordered_categories = sorted(by_category.keys(), key=category_sort_key)
        for category in ordered_categories:
            st.markdown(f"#### {CATEGORY_ICON.get(category, '📁')} {category}")
            cols = st.columns(3)
            for i, t in enumerate(by_category[category]):
                with cols[i % 3]:
                    st.markdown(f"**{t.icon} {t.name}**")
                    st.caption(t.description)

    st.divider()
    st.info(
        "💬 자유롭게 이야기 나누거나 아이디어를 공유하고 싶으면 왼쪽 사이드바의 "
        "**'📋 게시판'** 버튼을, 필요한 도구가 없거나 개선하고 싶은 점이 있으면 "
        f"**'✉️ 문의 및 기능 추가 요청하기'** 버튼을 눌러주세요. ({CONTACT_EMAIL})"
    )


def render_contact() -> None:
    """문의 및 기능 추가 요청 안내 화면."""
    st.title("✉️ 문의 및 기능 추가 요청")
    st.write(
        "이 도구를 쓰다가 불편한 점, 오류, 새로 만들었으면 하는 기능이 있으면 "
        "아래 이메일로 편하게 알려주세요. 캡처 화면을 함께 보내주시면 더 빨리 확인할 수 있어요."
    )

    st.markdown(
        f"""
        <div style="padding:1.2rem 1.5rem; border-radius:12px; background:rgba(120,120,120,0.08);
                    border:1px solid rgba(120,120,120,0.25); margin:1rem 0;">
            <div style="font-size:0.9rem; opacity:0.75;">문의 · 요청 보낼 곳</div>
            <div style="font-size:1.4rem; font-weight:700; margin-top:0.2rem;">📧 {CONTACT_EMAIL}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander("📋 문의할 때 이렇게 적어주시면 더 빨리 처리돼요"):
        st.markdown(
            "- **어떤 도구**를 쓰다가 그런 건지 (예: PDF 합치기, 엑셀 시트 이름 변경 등)\n"
            "- **무엇을 하려고 했는지**, **어떤 문제**가 생겼는지\n"
            "- 가능하면 **오류 화면 캡처**\n"
            "- 새 기능 요청이라면, **어떤 상황에서 왜 필요한지** 간단한 설명"
        )

    st.caption("왼쪽 사이드바에서 다른 도구를 선택하면 이 화면에서 바로 빠져나갈 수 있어요.")


def _reset_navigation(page: str) -> None:
    """검색어·카테고리 선택을 초기화하고, 홈/문의/게시판 중 어떤 화면을 보여줄지 정합니다.

    st.button(on_click=...)의 콜백 안에서만 호출해야 해요. 콜백은 화면이 다시 그려지기
    '전'에 실행되기 때문에, 이미 만들어진 위젯의 session_state를 안전하게 바꿀 수 있어요.
    (콜백 밖, 위젯이 이미 그려진 뒤에 같은 코드를 실행하면 StreamlitWidgetAlreadyInstantiatedError가 나요.)
    """
    st.session_state["search_box"] = ""
    st.session_state["category_radio"] = None
    st.session_state["show_contact"] = page == "contact"
    st.session_state["show_board"] = page == "board"


def main() -> None:
    st.set_page_config(
        page_title="업무 자동화 올인원",
        page_icon="🧰",
        layout="wide",
    )

    all_tools = load_tools()
    categories = sorted({t.category for t in all_tools} | set(CATEGORY_ORDER), key=category_sort_key)

    st.sidebar.title("🧰 업무 자동화 올인원")

    st.sidebar.button(
        "🏠 홈으로 돌아가기",
        use_container_width=True,
        on_click=_reset_navigation,
        args=("home",),
    )
    st.sidebar.link_button(
        "📡 Relay (팀 채팅·보드·달력)",
        RELAY_URL,
        use_container_width=True,
    )
    st.sidebar.button(
        "📋 게시판 (자유·문의·아이디어)",
        use_container_width=True,
        on_click=_reset_navigation,
        args=("board",),
    )

    st.sidebar.divider()
    search_keyword = st.sidebar.text_input(
        "🔍 도구 이름으로 검색",
        placeholder="예: 병합, 분할, 시트 이름...",
        key="search_box",
    )

    selected_tool: ToolInfo | None = None
    selected_category: str | None = None

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
            picked = st.sidebar.radio(
                "검색된 도구", labels, index=None, label_visibility="collapsed", key="search_result_radio"
            )
            if picked is not None:
                selected_tool = matched[labels.index(picked)]
        else:
            st.sidebar.info("일치하는 도구가 없어요. 다른 검색어로 찾아보세요.")
    else:
        st.sidebar.markdown("### 카테고리")
        selected_category = st.sidebar.radio(
            "카테고리를 선택하세요",
            categories,
            index=None,
            format_func=lambda c: f"{CATEGORY_ICON.get(c, '📁')} {c}",
            label_visibility="collapsed",
            key="category_radio",
        )

        if selected_category is not None:
            tools_in_category = [t for t in all_tools if t.category == selected_category]

            st.sidebar.markdown("### 도구 목록")
            if not tools_in_category:
                st.sidebar.info("이 카테고리는 준비 중이에요. 곧 추가될 예정입니다!")
            else:
                labels = [f"{t.icon} {t.name}" for t in tools_in_category]
                picked = st.sidebar.radio(
                    "도구를 선택하세요",
                    labels,
                    index=None,
                    label_visibility="collapsed",
                    key=f"tool_radio_{selected_category}",
                )
                if picked is not None:
                    selected_tool = tools_in_category[labels.index(picked)]

    # 카테고리를 고르거나 검색을 하면(=실제로 둘러보기 시작하면) 문의·게시판 화면은 자동으로 닫아요.
    if selected_category is not None or search_keyword.strip():
        st.session_state["show_contact"] = False
        st.session_state["show_board"] = False

    st.sidebar.divider()
    st.sidebar.button(
        "✉️ 문의 및 기능 추가 요청하기",
        use_container_width=True,
        on_click=_reset_navigation,
        args=("contact",),
    )
    st.sidebar.caption(f"문의·요청 메일: {CONTACT_EMAIL}")

    if st.session_state.get("show_board"):
        board.render()
        return

    if st.session_state.get("show_contact"):
        render_contact()
        return

    if selected_tool is None:
        render_home(all_tools)
        return

    selected_tool.render()


if __name__ == "__main__":
    main()
