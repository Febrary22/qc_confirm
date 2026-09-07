#!/usr/bin/env bash
# 로컬에서 QC 도구를 실행하기 위한 편의 스크립트.
# 사용법: ./run.sh
set -euo pipefail
cd "$(dirname "$0")/backend"

if [ ! -d ".venv" ]; then
  echo "[run.sh] 가상환경을 생성합니다 (.venv)"
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q -r requirements.txt

echo "[run.sh] http://localhost:8000 에서 서버를 시작합니다"
exec uvicorn main:app --host 0.0.0.0 --port 8000
