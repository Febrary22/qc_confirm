"""QC 확인 도구 백엔드 (FastAPI).

실행: uvicorn main:app --reload --port 8000  (backend/ 디렉터리에서)
"""
from __future__ import annotations

import base64
import json
import os
import secrets
from typing import List, Optional

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from qc.loader import UnsupportedFileError, load_file
from qc.report import load_default_config, run_qc

app = FastAPI(title="데이터 품질 검사(QC) 도구", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# (선택) 사내 공유 배포용 간단한 접근 제어
# QC_BASIC_AUTH_USER / QC_BASIC_AUTH_PASS 환경변수가 둘 다 설정된 경우에만 활성화된다.
# 설정하지 않으면(로컬 실습 등) 기존처럼 인증 없이 접근 가능.
# ---------------------------------------------------------------------------
_BASIC_AUTH_USER = os.environ.get("QC_BASIC_AUTH_USER")
_BASIC_AUTH_PASS = os.environ.get("QC_BASIC_AUTH_PASS")


class BasicAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if not (_BASIC_AUTH_USER and _BASIC_AUTH_PASS):
            return await call_next(request)

        header = request.headers.get("authorization", "")
        if header.startswith("Basic "):
            try:
                user, _, pw = base64.b64decode(header[6:]).decode("utf-8").partition(":")
            except Exception:  # noqa: BLE001
                user, pw = "", ""
            if secrets.compare_digest(user, _BASIC_AUTH_USER) and secrets.compare_digest(pw, _BASIC_AUTH_PASS):
                return await call_next(request)

        return Response(
            content="인증이 필요합니다. (관리자에게 접속 계정을 문의하세요)",
            status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="QC Tool"'},
        )


if _BASIC_AUTH_USER and _BASIC_AUTH_PASS:
    app.add_middleware(BasicAuthMiddleware)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/config/default")
def get_default_config():
    return load_default_config()


@app.post("/api/qc/analyze")
async def analyze(files: List[UploadFile] = File(...), config: Optional[str] = Form(None)):
    override_cfg = None
    if config:
        try:
            override_cfg = json.loads(config)
        except json.JSONDecodeError as exc:
            return JSONResponse(status_code=400, content={"error": f"설정(config) JSON 파싱 오류: {exc}"})

    results = []
    for uf in files:
        filename = uf.filename or "unnamed"
        try:
            content = await uf.read()
            loaded = load_file(filename, content)
            report = run_qc(loaded, override_cfg)
            results.append(report)
        except UnsupportedFileError as exc:
            results.append({"filename": filename, "error": str(exc)})
        except Exception as exc:  # noqa: BLE001
            results.append({"filename": filename, "error": f"처리 중 예상치 못한 오류가 발생했습니다: {exc}"})

    ok_results = [r for r in results if "error" not in r]
    comparison = sorted(
        (
            {
                "filename": r["filename"],
                "file_type": r["file_type"],
                "score": r["score"]["total"],
                "grade": r["score"]["grade"],
                "n_fail": sum(1 for c in r["checks"].values() if c.get("status") == "fail"),
                "n_warning": sum(1 for c in r["checks"].values() if c.get("status") == "warning"),
            }
            for r in ok_results
        ),
        key=lambda x: x["score"],
    )

    return {"batch": len(files) > 1, "count": len(files), "results": results, "comparison": comparison}


# ---------------------------------------------------------------------------
# 프론트엔드 정적 파일 서빙 (backend와 같은 서버에서 제공)
# ---------------------------------------------------------------------------
_FRONTEND_DIR = os.environ.get("QC_FRONTEND_DIR") or os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "frontend")
)
_frontend_ok = os.path.isdir(_FRONTEND_DIR) and os.path.isfile(os.path.join(_FRONTEND_DIR, "index.html"))

print(f"[startup] __file__ = {os.path.abspath(__file__)}", flush=True)
print(f"[startup] frontend dir resolved to: {_FRONTEND_DIR}", flush=True)
print(f"[startup] frontend dir usable: {_frontend_ok}", flush=True)
if os.path.isdir(_FRONTEND_DIR):
    print(f"[startup] contents: {os.listdir(_FRONTEND_DIR)}", flush=True)

if _frontend_ok:
    app.mount("/", StaticFiles(directory=_FRONTEND_DIR, html=True), name="frontend")
else:
    # 정적 파일을 못 찾은 경우에도 조용히 404가 뜨지 않도록, 원인을 알 수 있는 안내를 보여준다.
    @app.get("/")
    def frontend_missing():
        return JSONResponse(
            status_code=500,
            content={
                "error": "프론트엔드 정적 파일을 찾을 수 없습니다.",
                "checked_path": _FRONTEND_DIR,
                "hint": "배포 환경에 frontend/ 디렉터리가 이미지에 포함되었는지 확인하세요.",
            },
        )
