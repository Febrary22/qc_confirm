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
