"""도구 모음 폴더.

새 도구를 추가하는 방법
------------------------
1. 이 폴더(tools/) 안에 파이썬 파일을 하나 만듭니다. (예: tools/pdf_watermark.py)
2. 파일 안에 아래 두 가지를 반드시 넣습니다.

   TOOL_META = {
       "name": "화면에 보여줄 도구 이름",      # 예: "PDF 워터마크 넣기"
       "category": "PDF",                     # PDF / Excel / 한글 / NC데이터 / 기타
       "description": "1줄짜리 쉬운 기능 설명",
       "icon": "💧",                           # 사이드바에 보일 이모지 (선택)
   }

   def render():
       ...  # streamlit 화면 구성 코드 (파일 업로드 → 옵션 선택 → 실행 → 다운로드)

3. 파일을 저장하면 끝입니다. app.py가 tools/ 폴더를 자동으로 훑어보고
   TOOL_META와 render()가 있는 파일을 찾아 메뉴에 자동으로 추가합니다.
   (app.py나 다른 파일을 고칠 필요가 없습니다)

참고
----
- 여러 도구가 함께 쓰는 화면 도우미 함수는 streamlit_app/common.py 에 있습니다.
  (tool_header, friendly_errors, download_result, step_caption, parse_page_ranges 등)
- 파일 이름이 _로 시작하면(예: _helpers.py) 도구로 인식하지 않으니
  공용 코드를 tools/ 폴더 안에 두고 싶다면 이 규칙을 이용하세요.
"""
