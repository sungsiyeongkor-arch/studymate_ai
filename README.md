# StudyMate AI 📚

AI 기반 PDF 학습 보조 도구입니다.  
PDF 파일을 업로드하면 ChatGPT가 내용을 **요약**하고 **핵심 포인트**를 추출해 드립니다.

---

## 기능

| 기능 | 설명 |
|------|------|
| PDF 업로드 | 드래그 & 드롭 또는 파일 선택 (최대 16 MB) |
| 내용 요약 | ChatGPT가 핵심 내용을 3~5문장으로 요약 |
| 핵심 포인트 추출 | 학습에 중요한 개념을 최대 10개 항목으로 정리 |

---

## 기술 스택

- **백엔드**: Python 3.10+ / Flask
- **PDF 처리**: pdfplumber
- **AI**: OpenAI ChatGPT API (`gpt-4o-mini`)
- **프론트엔드**: HTML / CSS / Vanilla JavaScript (Flask 템플릿으로 제공)

---

## 설치 및 실행

### 1. 저장소 클론

```bash
git clone https://github.com/sungsiyeongkor-arch/studymate_ai.git
cd studymate_ai
```

### 2. 가상환경 생성 및 활성화

```bash
python -m venv venv
# macOS/Linux
source venv/bin/activate
# Windows
venv\Scripts\activate
```

### 3. 의존성 설치

```bash
pip install -r requirements.txt
```

### 4. 환경 변수 설정

```bash
cp .env.example .env
```

`.env` 파일을 열고 OpenAI API 키를 입력합니다:

```
OPENAI_API_KEY=sk-...your-key-here...
```

> OpenAI API 키는 [https://platform.openai.com/api-keys](https://platform.openai.com/api-keys) 에서 발급받을 수 있습니다.

### 5. 서버 실행

```bash
python app.py
```

브라우저에서 [http://localhost:5000](http://localhost:5000) 에 접속합니다.

---

## 프로젝트 구조

```
studymate_ai/
├── app.py               # Flask 애플리케이션 (백엔드 API)
├── requirements.txt     # Python 의존성
├── .env.example         # 환경 변수 템플릿
├── .gitignore
├── README.md
├── templates/
│   └── index.html       # 프론트엔드 UI
└── static/
    ├── css/
    │   └── style.css
    └── js/
        └── main.js
```

---

## API 엔드포인트

### `GET /`
메인 페이지를 반환합니다.

### `POST /analyze`
PDF 파일을 분석하여 요약 및 핵심 포인트를 반환합니다.

**Request**: `multipart/form-data` — `file` 필드에 PDF 파일

**Response (200 OK)**:
```json
{
  "summary": "문서의 핵심 내용 요약...",
  "key_points": [
    "핵심 포인트 1",
    "핵심 포인트 2",
    "..."
  ]
}
```

**Error Response**:
```json
{ "error": "에러 메시지" }
```

---

## 주의사항

- 이미지 기반 PDF(스캔된 문서 등)는 텍스트 추출이 불가능합니다.
- OpenAI API 사용 요금이 발생할 수 있습니다.
- `.env` 파일에 포함된 API 키는 절대 공개 저장소에 커밋하지 마세요.
