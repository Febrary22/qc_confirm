"""폴더(zip으로 압축) 안의 파일 구성과 용량을 분석해서 엑셀로 정리하는 도구."""
from __future__ import annotations

import io
import zipfile
from collections import defaultdict
from pathlib import Path

import pandas as pd
import streamlit as st

from common import download_result, friendly_errors, step_caption, tool_header

TOOL_META = {
    "name": "폴더 용량 살펴보기",
    "category": "기타",
    "description": "폴더를 zip으로 압축해서 올리면 안에 뭐가 들었고 용량은 얼마나 되는지 확인하고, 엑셀로 정리해드려요.",
    "icon": "🗂️",
}

# 이 웹 도구는 업로드 용량 제한(현재 200MB) 때문에 아주 큰 폴더는 다루기 어려워요.
# 그런 경우를 위해, 컴퓨터에 설치해서 쓰는 데스크톱 버전(같은 기능, 용량 제한 없음)을 함께 내려받을 수 있게 했어요.
DESKTOP_APP_PATH = Path(__file__).resolve().parent.parent / "assets" / "폴더용량분석기_데스크톱버전.zip"


def _render_desktop_download() -> None:
    if not DESKTOP_APP_PATH.exists():
        return
    with st.expander("🖥️ 폴더가 훨씬 커서(수백 GB~수십 TB) 이 웹 화면으로 안 될 때는?"):
        st.write(
            "이 웹 도구는 업로드 용량 제한이 있어서 아주 큰 폴더는 올리기 어려워요. "
            "대신 컴퓨터에 직접 설치해서 쓰는 **데스크톱 버전**을 내려받으면, 용량 제한 없이 "
            "(예: 20TB짜리 폴더도) 같은 방식으로 용량을 분석하고 엑셀로 내보낼 수 있어요."
        )
        st.caption(
            "⚠️ 담당자가 직접 만들고 확인한, 이 웹 도구와 동일한 기능의 프로그램이라 안심하고 쓰셔도 돼요. "
            "그래도 처음 실행하는 프로그램은 회사 백신 프로그램으로 한 번 검사해보시는 습관을 추천해요."
        )
        st.download_button(
            "데스크톱 버전 내려받기 (폴더용량분석기.exe, zip)",
            data=DESKTOP_APP_PATH.read_bytes(),
            file_name=DESKTOP_APP_PATH.name,
            mime="application/zip",
            use_container_width=True,
        )


def _human_size(num_bytes: float) -> str:
    """바이트 숫자를 사람이 읽기 편한 단위(KB/MB/GB)로 바꿔줍니다."""
    size = float(num_bytes)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024 or unit == "TB":
            return f"{size:.1f}{unit}" if unit != "B" else f"{int(size)}B"
        size /= 1024
    return f"{size:.1f}TB"


def _build_file_table(content: bytes) -> pd.DataFrame:
    try:
        zf = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile as exc:
        raise ValueError("zip 파일이 아니거나 손상됐어요. 폴더를 다시 압축해서 올려주세요.") from exc

    rows = []
    for info in zf.infolist():
        if info.is_dir():
            continue
        # 압축 파일 안 경로는 항상 '/'로 구분돼요 (운영체제와 무관하게)
        rows.append({"경로": info.filename, "크기(바이트)": info.file_size})

    if not rows:
        raise ValueError("압축 파일 안에서 파일을 찾지 못했어요. 폴더 안에 내용물이 있는지 확인해주세요.")

    df = pd.DataFrame(rows)
    df["폴더"] = df["경로"].apply(lambda p: "/".join(p.split("/")[:-1]) or "(최상위)")
    df["파일명"] = df["경로"].apply(lambda p: p.split("/")[-1])
    df["확장자"] = df["파일명"].apply(lambda n: n.rsplit(".", 1)[-1].lower() if "." in n else "(없음)")
    return df


def _build_folder_totals(df: pd.DataFrame, total_bytes: int, file_count: int) -> pd.DataFrame:
    """각 폴더가 하위 폴더까지 전부 포함해서 총 얼마나 차지하는지 계산합니다."""
    dir_totals: dict[str, int] = defaultdict(int)
    dir_counts: dict[str, int] = defaultdict(int)

    for _, row in df.iterrows():
        parts = row["경로"].split("/")[:-1]
        prefix = ""
        for part in parts:
            prefix = f"{prefix}/{part}" if prefix else part
            dir_totals[prefix] += int(row["크기(바이트)"])
            dir_counts[prefix] += 1

    if not dir_totals:
        # 압축 파일 최상위에 파일만 바로 있는 경우
        dir_totals["(최상위)"] = total_bytes
        dir_counts["(최상위)"] = file_count

    dir_df = pd.DataFrame(
        {
            "폴더": list(dir_totals.keys()),
            "크기(바이트)": list(dir_totals.values()),
            "포함된 파일 수": [dir_counts[k] for k in dir_totals],
        }
    )
    return dir_df.sort_values("크기(바이트)", ascending=False).reset_index(drop=True)


def render() -> None:
    tool_header(TOOL_META["name"], TOOL_META["description"])

    st.info(
        "💡 브라우저는 폴더를 통째로 읽을 수 없어서, **폴더를 zip으로 압축**한 뒤 올려주셔야 해요.\n\n"
        "Windows: 폴더 우클릭 → 보내기 → 압축(ZIP) 폴더  /  Mac: 폴더 우클릭 → 압축"
    )
    _render_desktop_download()

    step_caption(1, "분석할 폴더를 압축(zip)해서 올려주세요")
    file = st.file_uploader("zip 파일 선택", type=["zip"])
    if not file:
        st.info("zip 파일을 1개 올려주세요.")
        return

    step_caption(2, "실행 버튼을 눌러주세요")
    if st.button("폴더 용량 분석하기", type="primary"):
        with friendly_errors("폴더 용량 분석"):
            content = file.getvalue()
            df = _build_file_table(content)

            total_bytes = int(df["크기(바이트)"].sum())
            file_count = len(df)
            folder_totals = _build_folder_totals(df, total_bytes, file_count)

            step_caption(3, "결과를 확인하세요")
            col1, col2, col3 = st.columns(3)
            col1.metric("전체 용량", _human_size(total_bytes))
            col2.metric("전체 파일 개수", f"{file_count:,}개")
            col3.metric("폴더 개수", f"{len(folder_totals):,}개")

            display_folders = folder_totals.copy()
            display_folders["크기"] = display_folders["크기(바이트)"].apply(_human_size)
            st.markdown("**용량을 많이 차지하는 폴더 Top 20** (하위 폴더 포함)")
            st.dataframe(
                display_folders[["폴더", "크기", "포함된 파일 수"]].head(20),
                hide_index=True,
                use_container_width=True,
            )

            biggest_files = df.sort_values("크기(바이트)", ascending=False).head(20).copy()
            biggest_files["크기"] = biggest_files["크기(바이트)"].apply(_human_size)
            st.markdown("**용량이 큰 파일 Top 20**")
            st.dataframe(
                biggest_files[["경로", "크기", "확장자"]],
                hide_index=True,
                use_container_width=True,
            )

            step_caption(4, "필요하면 전체 결과를 엑셀로 받아주세요")
            all_files = df.sort_values("경로").copy()
            all_files["크기"] = all_files["크기(바이트)"].apply(_human_size)

            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                display_folders[["폴더", "크기", "크기(바이트)", "포함된 파일 수"]].to_excel(
                    writer, sheet_name="폴더별 용량", index=False
                )
                all_files[["경로", "폴더", "파일명", "확장자", "크기", "크기(바이트)"]].to_excel(
                    writer, sheet_name="전체 파일 목록", index=False
                )
                df.sort_values("크기(바이트)", ascending=False)[["경로", "확장자", "크기(바이트)"]].assign(
                    크기=lambda d: d["크기(바이트)"].apply(_human_size)
                ).to_excel(writer, sheet_name="용량 큰 파일 순", index=False)

            download_result(
                "분석 결과 엑셀로 내려받기",
                buffer.getvalue(),
                f"{file.name.rsplit('.', 1)[0]}_용량분석.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
