"""NC/CSV 데이터 품질 검사(QC) 도구로 이동하는 안내 화면."""
from __future__ import annotations

import streamlit as st

from common import tool_header

TOOL_META = {
    "name": "NC/CSV 데이터 품질 확인하기",
    "category": "NC데이터",
    "description": "nc·csv 파일이 얼마나 믿을 만한지 0~100점으로 점검해주는 데이터 품질 검사(QC) 도구로 이동해요.",
    "icon": "✅",
}

QC_TOOL_URL = "https://qc-confirm.onrender.com/"

GRADE_ROWS = [
    ("90~100점", "우수 (Excellent)", "바로 사용 가능", "#2f6f52"),
    ("75~89점", "양호 (Good)", "대체로 안심", "#3a6ea5"),
    ("50~74점", "보통 (Fair)", "주의해서 확인", "#b58a2a"),
    ("0~49점", "불량 (Poor)", "사용 전 재확인 필요", "#a8482c"),
]

CHECK_ITEMS = [
    ("🕳", "결측치", "데이터가 얼마나 비어있는지 확인해요.", "예) 값의 40%가 비어있으면 → 위험 신호"),
    ("⏱️", "시간 연속성", "시간별 데이터에 중간중간 빠진 구간이 있는지 확인해요.", "예) 3시간치 데이터가 통째로 누락"),
    ("📏", "값의 범위", "물리적으로 말이 안 되는 값이 있는지 확인해요.", "예) 습도가 음수, 기온이 -900도"),
    ("📈", "이상치", "주변 값들과 비교했을 때 유난히 튀는 값을 찾아요.", "예) 다른 값은 20인데 혼자 999"),
    ("🏷", "메타데이터", "단위·설명 같은 파일 정보가 잘 갖춰져 있는지 확인해요.", "예) 단위(unit) 정보가 아예 없음"),
    ("🧬", "중복/버전", "같은 시점·같은 행 데이터가 중복으로 들어있는지 확인해요.", "예) 같은 시각 데이터가 2번 저장됨"),
]

BADGE_ROWS = [
    ("✅ 통과", "문제없이 정상이에요."),
    ("⚠️ 경고", "문제가 될 수 있는 수준이에요. 참고해서 사용하세요."),
    ("⛔ 실패", "기준을 크게 벗어났어요. 사용 전 원본 데이터를 다시 확인하세요."),
    ("➖ 해당없음", "이 파일에는 적용할 수 없어 검사를 건너뛴 거예요. '문제없음'이 아니라 '검사하지 못했다'는 뜻이니 주의하세요."),
]


def render() -> None:
    tool_header(TOOL_META["name"], TOOL_META["description"])

    st.write(
        "지금 다루고 계신 NC/CSV 파일을 그대로 써도 되는지 궁금하다면, **데이터 품질 검사(QC) 도구**에서 "
        "파일을 올리기만 하면 0~100점 품질 점수와 항목별 상세 결과를 자동으로 확인할 수 있어요."
    )

    st.link_button(
        "✅ 데이터 품질 검사(QC) 도구로 이동",
        QC_TOOL_URL,
        type="primary",
        use_container_width=True,
    )
    st.caption(f"새 탭에서 열려요 · {QC_TOOL_URL}")

    st.divider()
    st.subheader("📋 결과 읽는 법 (1분 요약)")

    st.markdown("**1. 점수와 등급**")
    cols = st.columns(4)
    for col, (score, grade, desc, color) in zip(cols, GRADE_ROWS):
        with col:
            st.markdown(
                f"""
                <div style="padding:0.8rem; border-radius:10px; background:{color}1a;
                            border:1px solid {color}55; text-align:center;">
                    <div style="font-weight:700; color:{color};">{score}</div>
                    <div style="font-size:0.9rem; margin-top:2px;">{grade}</div>
                    <div style="font-size:0.8rem; opacity:0.75;">{desc}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown("**2. 무엇을 검사하나요? (6가지 항목)**")
    item_cols = st.columns(3)
    for i, (icon, name, desc, example) in enumerate(CHECK_ITEMS):
        with item_cols[i % 3]:
            st.markdown(f"**{icon} {name}**")
            st.caption(f"{desc}\n\n{example}")

    st.markdown("**3. 상태 표시(배지) 의미**")
    for badge, meaning in BADGE_ROWS:
        st.markdown(f"- **{badge}** — {meaning}")

    st.info(
        "💬 예시: 73점이 나왔어도, 실제로 제대로 검사된 항목이 4개뿐이고 그중 결측치가 '실패'라면 "
        "그대로 쓰기보다 원본 데이터를 다시 확인하는 게 좋아요. 점수만 보지 말고 항목별 결과까지 꼭 확인하세요."
    )
