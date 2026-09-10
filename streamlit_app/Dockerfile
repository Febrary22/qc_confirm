# Render.com에 배포하기 위한 Streamlit 앱 전용 Dockerfile.
# 빌드 컨텍스트는 저장소 루트 기준입니다 (render.yaml의 dockerfilePath 참고).
FROM python:3.11-slim

WORKDIR /app

# 스캔본 글자 인식(OCR) 도구가 쓰는 tesseract 엔진 (한국어 + 영어 언어팩 포함)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr tesseract-ocr-kor \
    && rm -rf /var/lib/apt/lists/*

COPY streamlit_app/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY streamlit_app .

# Render는 컨테이너에 PORT 환경변수를 내려줍니다. (기본값 8501은 로컬 docker run용)
ENV PORT=8501
EXPOSE 8501

CMD streamlit run app.py \
    --server.port=$PORT \
    --server.address=0.0.0.0 \
    --server.headless=true
