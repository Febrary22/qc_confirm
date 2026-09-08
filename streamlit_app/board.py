"""사내 게시판 (자유 / 문의 / 아이디어).

app.py 사이드바의 '📋 게시판' 버튼에서 연결되는 화면입니다. tools/ 폴더의 파일 변환
도구들과 달리 글·사진을 계속 저장해둬야 해서, Postgres 데이터베이스(Render의
DATABASE_URL 환경변수)에 저장합니다. DATABASE_URL이 설정돼 있지 않으면 안내 메시지만
보여주고 오류 없이 넘어가요.
"""
from __future__ import annotations

import os
from typing import Any, Optional

import psycopg2
import psycopg2.extras
import streamlit as st

DATABASE_URL_ENV = "DATABASE_URL"
MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5MB

BOARDS: dict[str, str] = {
    "free": "🗨️ 자유게시판",
    "inquiry": "❓ 문의게시판",
    "idea": "💡 아이디어게시판",
}


@st.cache_resource(show_spinner=False)
def _get_connection():
    """DB에 연결하고, 처음이라면 필요한 테이블도 만들어 둡니다."""
    url = os.environ.get(DATABASE_URL_ENV)
    if not url:
        return None
    conn = psycopg2.connect(url, sslmode="require")
    conn.autocommit = True
    _ensure_schema(conn)
    return conn


def _ensure_schema(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS board_posts (
                id SERIAL PRIMARY KEY,
                board TEXT NOT NULL,
                title TEXT NOT NULL,
                author TEXT NOT NULL,
                content TEXT NOT NULL,
                image BYTEA,
                image_mime TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS board_comments (
                id SERIAL PRIMARY KEY,
                post_id INTEGER NOT NULL REFERENCES board_posts(id) ON DELETE CASCADE,
                author TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )


def _fetch_posts(conn, board: str) -> list[dict[str, Any]]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "SELECT id, title, author, content, image, image_mime, created_at "
            "FROM board_posts WHERE board = %s ORDER BY created_at DESC",
            (board,),
        )
        return list(cur.fetchall())


def _fetch_comments(conn, post_id: int) -> list[dict[str, Any]]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "SELECT author, content, created_at FROM board_comments "
            "WHERE post_id = %s ORDER BY created_at ASC",
            (post_id,),
        )
        return list(cur.fetchall())


def _insert_post(
    conn, board: str, title: str, author: str, content: str,
    image_bytes: Optional[bytes], image_mime: Optional[str],
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO board_posts (board, title, author, content, image, image_mime) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (
                board,
                title,
                author,
                content,
                psycopg2.Binary(image_bytes) if image_bytes else None,
                image_mime,
            ),
        )


def _insert_comment(conn, post_id: int, author: str, content: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO board_comments (post_id, author, content) VALUES (%s, %s, %s)",
            (post_id, author, content),
        )


def _render_new_post_form(conn, board_key: str) -> None:
    with st.expander("✏️ 새 글 쓰기", expanded=False):
        with st.form(f"new_post_form_{board_key}", clear_on_submit=True):
            author = st.text_input("작성자 이름(닉네임)")
            title = st.text_input("제목")
            content = st.text_area("내용", height=150)
            image = st.file_uploader("사진 첨부 (선택, 5MB 이하)", type=["png", "jpg", "jpeg", "gif", "webp"])
            submitted = st.form_submit_button("등록하기", type="primary")

            if not submitted:
                return
            if not author.strip() or not title.strip() or not content.strip():
                st.error("작성자, 제목, 내용은 모두 입력해 주세요.")
                return
            if image is not None and len(image.getvalue()) > MAX_IMAGE_BYTES:
                st.error("사진 용량이 너무 커요. 5MB 이하 사진으로 올려주세요.")
                return

            try:
                image_bytes = image.getvalue() if image is not None else None
                image_mime = image.type if image is not None else None
                _insert_post(conn, board_key, title.strip(), author.strip(), content.strip(), image_bytes, image_mime)
            except Exception as exc:  # noqa: BLE001
                st.error(f"글을 저장하지 못했어요. 잠시 후 다시 시도해 주세요. ({exc})")
                return

            st.success("글이 등록됐어요!")
            st.rerun()


def _render_post(conn, post: dict[str, Any]) -> None:
    with st.container(border=True):
        st.markdown(f"**{post['title']}**")
        st.caption(f"{post['author']} · {post['created_at'].strftime('%Y-%m-%d %H:%M')}")
        st.write(post["content"])
        if post["image"]:
            try:
                st.image(bytes(post["image"]))
            except Exception:  # noqa: BLE001
                st.caption("⚠️ 사진을 불러오지 못했어요. (파일이 손상됐을 수 있어요)")

        try:
            comments = _fetch_comments(conn, post["id"])
        except Exception as exc:  # noqa: BLE001
            st.caption(f"댓글을 불러오지 못했어요. ({exc})")
            comments = []

        if comments:
            st.markdown("**댓글**")
            for c in comments:
                st.caption(f"— **{c['author']}**: {c['content']}")

        with st.form(f"comment_form_{post['id']}", clear_on_submit=True):
            c_cols = st.columns([1, 3])
            c_author = c_cols[0].text_input("이름", key=f"c_author_{post['id']}", label_visibility="collapsed", placeholder="이름")
            c_content = c_cols[1].text_input("댓글", key=f"c_content_{post['id']}", label_visibility="collapsed", placeholder="댓글을 남겨보세요")
            if st.form_submit_button("댓글 달기"):
                if not c_author.strip() or not c_content.strip():
                    st.error("이름과 댓글 내용을 입력해 주세요.")
                else:
                    try:
                        _insert_comment(conn, post["id"], c_author.strip(), c_content.strip())
                    except Exception as exc:  # noqa: BLE001
                        st.error(f"댓글을 저장하지 못했어요. ({exc})")
                    else:
                        st.rerun()


def render() -> None:
    st.title("📋 사내 게시판")
    st.caption("자유롭게 이야기 나누고, 궁금한 점을 묻고, 아이디어를 남겨보세요. 사진도 함께 올릴 수 있어요.")

    conn = _get_connection()
    if conn is None:
        st.warning(
            "아직 게시판 저장소가 연결되지 않았어요.\n\n"
            "Render 대시보드에서 **Postgres 데이터베이스**를 만든 뒤, 이 서비스"
            "(office-tools-streamlit)의 환경변수에 `DATABASE_URL`을 연결해야 글이 사라지지 "
            "않고 안전하게 저장돼요. (관리자에게 설정을 요청해 주세요)"
        )
        return

    board_key = st.radio(
        "게시판 선택",
        list(BOARDS.keys()),
        format_func=lambda k: BOARDS[k],
        horizontal=True,
        key="board_kind_radio",
    )

    _render_new_post_form(conn, board_key)
    st.divider()

    try:
        posts = _fetch_posts(conn, board_key)
    except Exception as exc:  # noqa: BLE001
        st.error(f"게시글을 불러오지 못했어요. 잠시 후 다시 시도해 주세요. ({exc})")
        return

    if not posts:
        st.info("아직 글이 없어요. 첫 글을 남겨보세요!")
        return

    for post in posts:
        _render_post(conn, post)
