# StudyMate AI 📚

AI 기반 PDF 학습 보조 플랫폼입니다.  
PDF를 업로드하면 AI가 **구조화된 요약 노트**(키워드·의미·비교표 포함)와 **예상 문제**를 자동으로 생성합니다.  
Google 계정 또는 이메일로 로그인하면 모든 데이터가 계정에 저장되어 언제든 다시 확인할 수 있습니다.

---

## ⚡ 빠른 시작 (3단계)

```bash
# 1. 저장소 클론
git clone https://github.com/sungsiyeongkor-arch/studymate_ai.git
cd studymate_ai

# 2. 의존성 설치 (Python 3.10+ 필요)
pip install -r requirements.txt

# 3. 환경 변수 설정 후 서버 실행
cp .env.example .env
# .env 파일을 열어 OPENAI_API_KEY 를 입력하세요
python app.py
```

브라우저에서 **http://localhost:5000** 을 열고, 이메일 주소를 입력해 바로 로그인하세요.  
> Google OAuth나 별도 DB 설정 없이도 바로 사용할 수 있습니다.

---

## 주요 기능 (NEW)

| 기능 | 설명 |
|------|------|
| Google 로그인 | Google OAuth로 로그인 → 데이터가 계정에 귀속 |
| PDF 업로드 | 드래그 & 드롭 또는 파일 선택 (최대 16 MB) |
| AI 요약 노트 | AI가 자동으로 분량·구조 결정 (키워드·의미·비교표·callout 포함) |
| AI 예상 문제 | 객관식 문제 자동 생성 + 정답·해설 포함 |
| 자료 관리 | 폴더별 파일 정리, 검색, 정렬 |
| 최근 활동 기록 | 로그인 후 자동 기록, 대시보드에서 확인 |
| 다크모드 | 다크/라이트 테마 전환 |

---

## 기술 스택

- **백엔드**: Python 3.10+ / Flask + Flask-SQLAlchemy + Flask-Login
- **데이터베이스**: SQLite (기본) / PostgreSQL (옵션)
- **인증**: Google OAuth 2.0 (Authlib)
- **AI**: OpenAI ChatGPT API (`gpt-4o-mini`)
- **PDF 처리**: pdfplumber
- **프론트엔드**: HTML / CSS / Vanilla JavaScript (Jinja2 템플릿)

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

`.env` 파일을 열고 아래 항목을 설정합니다:

```env
# 필수: OpenAI API 키
OPENAI_API_KEY=sk-...your-key-here...

# 필수: Flask 세션 비밀 키 (무작위 문자열)
SECRET_KEY=replace_with_a_long_random_string

# Google OAuth (로그인 기능 사용 시 필수 – 아래 설정 가이드 참조)
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
```

> **Google OAuth를 설정하지 않아도** 이메일 로그인으로 바로 사용할 수 있습니다.  
> OpenAI API 키가 없어도 앱은 실행되나 AI 분석 기능이 비활성화됩니다.

### 5. 서버 실행

```bash
python app.py
# 또는 디버그 모드
FLASK_DEBUG=1 python app.py
```

브라우저에서 [http://localhost:5000](http://localhost:5000) 에 접속합니다.

---

## Google OAuth 설정

Google 로그인을 활성화하려면 아래 단계를 따르세요.

### 1. Google Cloud 프로젝트 생성

1. [Google Cloud Console](https://console.cloud.google.com/) 에 접속합니다.
2. 새 프로젝트를 생성하거나 기존 프로젝트를 선택합니다.

### 2. OAuth 동의 화면 구성

1. **APIs & Services → OAuth consent screen** 으로 이동합니다.
2. **User Type**: `External` 선택 → 저장
3. 앱 이름 (예: `StudyMate AI`), 이메일을 입력하고 저장합니다.

### 3. OAuth 2.0 클라이언트 ID 생성

1. **APIs & Services → Credentials → Create Credentials → OAuth client ID**
2. **Application type**: `Web application`
3. **Authorized redirect URIs** 에 아래를 추가:
   - 로컬 개발: `http://localhost:5000/auth/callback`
   - 프로덕션: `https://yourdomain.com/auth/callback`
4. 생성 후 **Client ID** 와 **Client Secret** 을 복사합니다.

### 4. `.env` 파일에 입력

```env
GOOGLE_CLIENT_ID=1234567890-xxx.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-xxxxxxxxxxxxxxxxxxxx
```

### 5. 서버 재시작

```bash
python app.py
```

---

## 환경 변수

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `OPENAI_API_KEY` | OpenAI API 키 (필수) | — |
| `SECRET_KEY` | Flask 세션 비밀 키 (필수) | 랜덤 생성 |
| `GOOGLE_CLIENT_ID` | Google OAuth 클라이언트 ID | — |
| `GOOGLE_CLIENT_SECRET` | Google OAuth 클라이언트 시크릿 | — |
| `DATABASE_URL` | DB 연결 문자열 | `sqlite:///studymate.db` |
| `OPENAI_MODEL` | 사용할 OpenAI 모델 | `gpt-4o-mini` |
| `MAX_CHARS` | 모델에 전달하는 최대 문자 수 | `11900` |
| `TEMPERATURE` | 모델 창의성 (0.0~1.0) | `0.3` |
| `FLASK_DEBUG` | Flask 디버그 모드 | `0` |

---

## 프로젝트 구조

```
studymate_ai/
├── app.py               # Flask 애플리케이션 (라우트 + AI 서비스)
├── models.py            # NEW: SQLAlchemy 데이터 모델
├── auth.py              # NEW: Google OAuth 인증 라우트
├── requirements.txt     # Python 의존성
├── .env.example         # 환경 변수 템플릿
├── .gitignore
├── README.md
├── studymate.db         # SQLite DB (자동 생성, gitignore됨)
├── uploads/             # 업로드 파일 저장 (자동 생성, gitignore됨)
├── templates/
│   ├── base.html        # NEW: 공통 레이아웃 (사이드바 + 상단바)
│   ├── login.html       # NEW: 로그인 페이지
│   ├── home.html        # NEW: 홈 대시보드
│   ├── upload.html      # NEW: 자료 업로드 페이지
│   ├── notes.html       # NEW: 요약 노트 목록
│   ├── note_detail.html # NEW: 요약 노트 상세
│   ├── quizzes.html     # NEW: 예상 문제 목록
│   ├── quiz_detail.html # NEW: 예상 문제 상세
│   ├── materials.html   # NEW: 자료 관리
│   ├── profile.html     # NEW: 개인 설정
│   └── index.html       # 기존 단일 페이지 (레거시, /analyze 호환)
└── static/
    ├── css/
    │   ├── style.css    # 기존 CSS (공통 테마)
    │   └── dashboard.css # NEW: 대시보드 레이아웃 스타일
    └── js/
        ├── main.js      # 기존 JS (레거시)
        ├── dashboard.js # NEW: 사이드바·테마·드롭다운
        └── upload.js    # NEW: 업로드 폼 로직
```

---

## AI 요약 노트 형식 (NEW)

사용자가 문장 수를 설정하지 않습니다. AI가 문서의 복잡도와 분량에 따라 자동으로 결정합니다.

출력 구조:

```json
{
  "title": "문서 제목",
  "overview": "한 단락 개요",
  "keywords": [
    { "term": "키워드", "meaning": "정의/의미", "related": ["관련개념"] }
  ],
  "sections": [
    { "title": "섹션명", "type": "text|list|table|callout", "content": "..." }
  ],
  "comparison_table": { "headers": ["항목"], "rows": [["내용"]] },
  "key_takeaways": ["핵심 포인트 1", "핵심 포인트 2"]
}
```

이 구조는 UI에서 **키워드 칩**, **비교표**, **callout 블록** 등으로 직관적으로 렌더링됩니다.

---

## 주의사항

- 이미지 기반 PDF(스캔된 문서)는 텍스트 추출이 불가능합니다.
- OpenAI API 사용 요금이 발생할 수 있습니다.
- `.env` 파일의 API 키와 시크릿은 절대 공개 저장소에 커밋하지 마세요.
- SQLite는 로컬 개발용입니다. 프로덕션에서는 `DATABASE_URL`을 PostgreSQL로 변경하세요.
