# 데이터 품질 검사(QC) 도구

nc(NetCDF) / csv 파일을 올리면 "이 데이터를 믿고 써도 되는지"를 몇 초 안에 판단할 수 있게 해주는 웹 도구입니다.
결측치, 시간 연속성, 값의 범위, 이상치, 메타데이터(CF Convention 등), 중복/버전 문제를 자동으로 점검하고
0~100점의 품질 점수와 상세 리포트를 제공합니다.

![status](https://img.shields.io/badge/status-MVP-blue)

## 주요 기능

- **결측치 검사**: 변수별 결측 비율 계산 + 시간대별 결측 분포 히트맵
- **시간 연속성 검사**: 예상 간격(자동 추정) 대비 실제 간격을 비교해 빠진 구간을 리스트업
- **값의 범위(Range) 검사**: 변수별 정상 범위를 벗어난 값 탐지 (팀 표준값을 설정 파일/UI에서 관리)
- **이상치 검사**: Z-Score 또는 IQR 기반 급격한 튐 값 탐지
- **메타데이터 검증**: 전역 속성, CF Convention 준수 여부, 변수 단위(unit) 일치 여부 확인
- **중복 검사**: 중복 타임스탬프 / 중복 행 탐지
- **품질 점수**: 6개 항목을 가중합산해 0~100점 + 등급(우수/양호/보통/불량)으로 요약
- **배치 비교**: 여러 파일을 한 번에 올리면 점수순으로 정렬된 비교 테이블 제공 (문제 파일이 위로 정렬)
- **PDF 내보내기**: 상세 리포트를 브라우저에서 바로 PDF로 저장
- **팀 표준 프리셋**: 임계값/변수 범위/가중치를 UI에서 편집하고 브라우저에 프리셋으로 저장, JSON 파일로 내보내기/가져오기

## 아키텍처

```
qc_confirm/
├── backend/                 FastAPI + xarray/pandas 기반 QC 엔진
│   ├── main.py               API 서버 (파일 업로드 → QC 실행 → JSON 리포트)
│   ├── qc/
│   │   ├── loader.py          nc/csv → 공통 표현(LoadedDataset) 로더
│   │   ├── checks.py          6개 체크 항목 구현
│   │   ├── scorer.py          체크 결과 → 0~100점 환산
│   │   └── report.py          체크 실행 + 리포트 조립, 설정 병합
│   ├── config/default_rules.yaml   팀 표준 기본값 (임계값/가중치/변수 범위/메타데이터 규칙)
│   └── tests/                pytest 단위 테스트
└── frontend/                 순수 HTML/CSS/JS (빌드 단계 없음)
    ├── index.html
    ├── css/style.css
    ├── js/app.js              업로드, 설정, 리포트 렌더링, PDF 내보내기
    └── vendor/                Chart.js / html2canvas / jsPDF (오프라인 동작을 위해 로컬 포함)
```

데이터가 커질 수 있어 처리는 항상 서버 사이드(Python + xarray)에서 이뤄지고, 프론트엔드는 결과 JSON만
받아 렌더링합니다. FastAPI가 `/api/*` 엔드포인트와 `frontend/` 정적 파일을 같은 서버에서 함께 서빙합니다.

## 빠른 시작

### 방법 1: 스크립트로 실행

```bash
./run.sh
# http://localhost:8000 접속
```

### 방법 2: 수동 실행

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### 방법 3: Docker

```bash
docker compose up --build
# http://localhost:8000 접속
```

## 직원들과 함께 쓰기 (배포)

로컬 실행(`./run.sh`)은 "내 컴퓨터에서 켜져 있는 동안만" 나만 접속할 수 있는 방식입니다. 여러 사람이
설치 없이 링크만 열어서 쓰게 하려면, **누군가 한 명이 서버에 한 번 배포**해두고 그 주소를 공유하면 됩니다.
브라우저만 있으면 되고, 접속하는 직원은 git이나 Python을 몰라도 됩니다.

### 방법 A: 무료 클라우드에 배포 (Render) — 사내 서버가 없을 때 추천

1. [render.com](https://render.com) 가입 (GitHub 계정으로 바로 가능)
2. **New +** → **Blueprint** → 이 저장소(`Febrary22/qc_confirm`) 선택
   - 저장소에 포함된 `render.yaml`을 자동으로 인식해서 설정을 거의 그대로 채워줍니다.
3. `QC_BASIC_AUTH_USER` / `QC_BASIC_AUTH_PASS` 입력 (외부에 공개되지 않게 로그인 계정을 걸고 싶을 때만.
   비워두면 링크를 아는 누구나 접속 가능)
4. **Deploy** 클릭 → 몇 분 후 `https://qc-confirm-xxxx.onrender.com` 같은 주소가 발급됩니다.
5. 이 주소를 직원들에게 공유하면 끝. 각자 브라우저로 열기만 하면 됩니다.

> 무료 플랜은 한동안 접속이 없으면 서버가 잠들어서 첫 접속이 몇 초~수십 초 느릴 수 있습니다.
> 업무용으로 상시 빠르게 쓰려면 유료 플랜(월 몇 달러 수준)을 권장합니다. Railway, Fly.io 등 다른
> PaaS도 이 저장소의 `Dockerfile`을 그대로 인식해 비슷하게 배포할 수 있습니다.

### 방법 B: 사내 서버에 배포 — 데이터를 외부로 내보내고 싶지 않을 때 추천

회사에 상시 켜져 있는 서버(사내 리눅스 서버, 사설 클라우드 VM 등)가 있다면 그 위에서 한 번만 실행합니다.

```bash
git clone https://github.com/Febrary22/qc_confirm.git
cd qc_confirm
docker compose up --build -d   # -d: 백그라운드로 계속 실행
```

이후 직원들은 `http://<그 서버의 사내 IP 또는 주소>:8000` 으로 접속하면 됩니다. 서버가 재부팅되어도
`restart: unless-stopped` 설정 덕분에 자동으로 다시 켜집니다.

### 접속 계정으로 제한하기 (선택)

업로드하는 데이터가 민감할 수 있으므로, 아무나 링크로 못 들어오게 하려면 `QC_BASIC_AUTH_USER` /
`QC_BASIC_AUTH_PASS` 환경변수 두 개를 채워주세요. 설정하면 접속 시 브라우저에 표준 로그인 창이 뜨고,
비워두면(기본값) 인증 없이 누구나 링크로 접속할 수 있습니다.

```bash
# docker compose 예시
QC_BASIC_AUTH_USER=team QC_BASIC_AUTH_PASS='원하는비밀번호' docker compose up --build -d
```

## 사용 방법

바로 체험해보고 싶다면 `samples/` 폴더에 들어있는 예시 파일을 그대로 업로드해도 됩니다.
(정상에 가까운 파일, 문제가 있는 파일, CSV 파일이 하나씩 있어 배치 비교까지 바로 확인할 수 있습니다.)

1. 브라우저에서 nc / csv 파일을 드래그 앤 드롭 (여러 개 선택 시 배치 비교 모드)
2. 필요하면 우측 상단 "⚙️ 검사 기준 설정"에서 임계값 · 변수별 정상 범위 · 가중치를 조정
   - **임계값 & 가중치** 탭: 결측/시간/범위/이상치/메타데이터/중복 각각의 경고·실패 기준과 점수 가중치
   - **변수별 정상 범위** 탭: 변수명(부분 일치) → 최소/최대값/단위 규칙 추가·삭제
   - **고급(JSON)** 탭: 전체 설정을 JSON으로 직접 편집 (메타데이터 규칙 등 세부 항목 포함)
   - 설정은 "프리셋 저장"으로 브라우저에 이름을 붙여 저장하거나, "파일로 내보내기"로 팀과 공유 가능
3. "QC 실행하기" 클릭 → 몇 초 안에 품질 점수와 항목별 리포트 확인
4. 배치 업로드 시 비교 테이블에서 행을 클릭하면 해당 파일의 상세 리포트로 이동
5. "⬇️ PDF로 내보내기"로 리포트를 저장해 보고서에 첨부

## 설정 파일 (`backend/config/default_rules.yaml`)

팀 표준값은 YAML 파일 하나로 관리됩니다. 서버 기본값을 바꾸고 싶다면 이 파일을 직접 수정하세요.
프론트엔드에서 조정한 값은 요청 단위로 이 기본값을 덮어씁니다(서버 파일 자체는 바뀌지 않음).

```yaml
thresholds:
  missing: { warning: 0.01, fail: 0.10 }   # 결측 비율 1%↑ 경고, 10%↑ 실패
  ...
weights:
  missing_values: 20
  time_continuity: 15
  ...
variable_ranges:
  temperature: { min: -90, max: 60, unit: "degC" }
  ...
metadata_rules:
  required_global_attrs: ["Conventions", "title", "institution"]
  ...
```

## API

| Method | Path | 설명 |
| --- | --- | --- |
| GET | `/api/health` | 헬스 체크 |
| GET | `/api/config/default` | 기본 QC 설정(JSON) 조회 |
| POST | `/api/qc/analyze` | 파일 업로드(`files`, 여러 개 가능) + 선택적 `config`(JSON 문자열) → QC 리포트 |

`POST /api/qc/analyze` 응답 예시 (요약):

```json
{
  "batch": true,
  "count": 2,
  "results": [ { "filename": "...", "score": { "total": 87.4, "grade": "..." }, "checks": { ... } } ],
  "comparison": [ { "filename": "...", "score": 29.7, "grade": "불량 (Poor)", "n_fail": 4, "n_warning": 0 } ]
}
```

## 테스트

```bash
cd backend
source .venv/bin/activate
python -m pytest tests/ -v
```

## 알려진 제한 사항

- 파일당 업로드 용량은 안전을 위해 300MB로 제한되어 있습니다 (`backend/qc/loader.py`의 `MAX_UPLOAD_BYTES`).
- 현재 업로드된 파일은 메모리/임시 파일에서만 처리되고 서버에 저장되지 않습니다 (요청이 끝나면 사라짐).
- CSV 파일은 단위·좌표계 등 메타데이터가 없어 메타데이터 검증 범위가 제한적입니다.
- PDF 내보내기는 브라우저에서 화면을 캡처하는 방식이라 매우 긴 리포트는 페이지가 여러 장으로 나뉩니다.

## 향후 확장 아이디어

- 특정 폴더를 감시해 새 파일이 들어올 때마다 자동 QC 실행 + 문제 발생 시 Slack/메일 알림
- 시각화 도구와 연동해 품질 검사에서 이상이 발견된 부분을 그림 위에 바로 하이라이트
- 업로드 이력을 DB에 저장해 시간에 따른 데이터 품질 추이 트렌드 제공
