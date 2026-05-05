# StudyMate AI 📚

AI 기반 PDF 학습 보조 도구입니다.  
PDF 파일을 업로드하면 ChatGPT가 내용을 **요약**하고 **핵심 포인트**를 추출해 드립니다.
PDF 파일을 업로드하면 ChatGPT가 내용을 **요약**하고 **핵심 포인트**를 추출하거나 **퀴즈**를 생성해 드립니다.

---

## 기능

| 기능 | 설명 |
|------|------|
| PDF 업로드 | 드래그 & 드롭 또는 파일 선택 (최대 16 MB) |
| 내용 요약 | ChatGPT가 핵심 내용을 요약 (길이 조절 가능) |
| 핵심 포인트 추출 | 학습에 중요한 개념을 최대 15개 항목으로 정리 |
| 퀴즈 생성 | 문서 기반 객관식 퀴즈 자동 생성 (3~15문제) |
| 클립보드 복사 | 요약 및 핵심 포인트를 한 번에 복사 |
| 다크모드 | 다크/라이트 테마 전환 (설정 저장됨) |
| 설정 패널 | 언어, 출력 모드, 문항 수 등 실시간 조절 |

---

## 설정 옵션

설정 패널(⚙️)에서 아래 항목을 조절할 수 있습니다:

| 설정 | 옵션 | 기본값 |
|------|------|--------|
| 출력 모드 | 요약+핵심 포인트 / 퀴즈 생성 | 요약+핵심 포인트 |
| 출력 언어 | 한국어 / English | 한국어 |
| 핵심 포인트 수 | 3 ~ 15개 | 10개 |
| 요약 길이 | 3문장 / 5문장 / 7문장 | 5문장 |
| 퀴즈 문제 수 | 3 ~ 15개 | 5개 |

모든 설정은 브라우저 localStorage에 자동 저장됩니다.

---

## 기술 스택

- **백엔드**: Python 3.10+ / Flask
- **PDF 처리**: pdfplumber
- **AI**: OpenAI ChatGPT API (`gpt-4o-mini`)
- **AI**: OpenAI ChatGPT API (`gpt-4o-mini`, 모델 변경 가능)
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
# 또는 디버그 모드
FLASK_DEBUG=1 python app.py
```

브라우저에서 [http://localhost:5000](http://localhost:5000) 에 접속합니다.

---

## 환경 변수

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `OPENAI_API_KEY` | OpenAI API 키 (필수) | — |
| `OPENAI_MODEL` | 사용할 OpenAI 모델 | `gpt-4o-mini` |
| `MAX_CHARS` | 모델에 전달하는 최대 문자 수 | `11900` |
| `TEMPERATURE` | 모델 창의성 (0.0~1.0) | `0.3` |
| `FLASK_DEBUG` | Flask 디버그 모드 | `0` |

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
    │   └── style.css    # 스타일 (CSS 커스텀 프로퍼티 기반 테마)
    └── js/
        └── main.js      # 프론트엔드 로직
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

메인 페이지를 반환합니다.

### `POST /analyze`

PDF 파일을 분석하여 요약·핵심 포인트 또는 퀴즈를 반환합니다.

**Request**: `multipart/form-data`

| 필드 | 타입 | 설명 | 기본값 |
|------|------|------|--------|
| `file` | File | PDF 파일 (필수) | — |
| `mode` | string | `analyze` 또는 `quiz` | `analyze` |
| `language` | string | `ko` 또는 `en` | `ko` |
| `num_points` | int | 핵심 포인트 수 (최대 20) | `10` |
| `summary_sentences` | int | 요약 문장 수 (최대 10) | `5` |
| `num_questions` | int | 퀴즈 문제 수 (최대 15) | `5` |

**Response (mode=analyze)**:
```json
{
  "summary": "문서의 핵심 내용 요약...",
  "key_points": ["핵심 포인트 1", "핵심 포인트 2"]
}
```

**Response (mode=quiz)**:
```json
{
  "questions": [
    {
      "question": "질문 내용",
      "options": ["A. 선택지 1", "B. 선택지 2", "C. 선택지 3", "D. 선택지 4"],
      "answer": "A"
    }
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
