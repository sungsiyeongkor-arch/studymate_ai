‎static/css/style.css‎
+197
Lines changed: 197 additions & 0 deletions
‎static/js/main.js‎
+175
Lines changed: 175 additions & 0 deletions
Original file line number	Diff line number	Diff line change
'use strict';
const fileInput    = document.getElementById('fileInput');
const dropZone     = document.getElementById('dropZone');
const fileHint     = document.getElementById('fileHint');
const uploadForm   = document.getElementById('uploadForm');
const analyzeBtn   = document.getElementById('analyzeBtn');
const errorBanner  = document.getElementById('errorBanner');
const errorMessage = document.getElementById('errorMessage');
const resultsSection = document.getElementById('resultsSection');
const summaryText  = document.getElementById('summaryText');
const keyPointsList = document.getElementById('keyPointsList');
const resetBtn     = document.getElementById('resetBtn');
const uploadSection = document.getElementById('uploadSection');
// ── File selection ──────────────────────────────────
fileInput.addEventListener('change', () => {
  handleFileSelection(fileInput.files[0]);
});
dropZone.addEventListener('click', (e) => {
  if (e.target !== fileInput && !e.target.closest('label')) {
    fileInput.click();
  }
});
dropZone.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' || e.key === ' ') {
    e.preventDefault();
    fileInput.click();
  }
});
// ── Drag & drop ─────────────────────────────────────
['dragenter', 'dragover'].forEach(evt => {
  dropZone.addEventListener(evt, (e) => {
    e.preventDefault();
    dropZone.classList.add('drag-over');
  });
});
['dragleave', 'drop'].forEach(evt => {
  dropZone.addEventListener(evt, (e) => {
    e.preventDefault();
    dropZone.classList.remove('drag-over');
  });
});
dropZone.addEventListener('drop', (e) => {
  const file = e.dataTransfer.files[0];
  handleFileSelection(file);
});
// ── Helpers ──────────────────────────────────────────
function handleFileSelection(file) {
  hideError();
  if (!file) return;
  if (!file.name.toLowerCase().endsWith('.pdf')) {
    showError('PDF 파일만 업로드 가능합니다.');
    analyzeBtn.disabled = true;
    return;
  }
  if (file.size > 16 * 1024 * 1024) {
    showError('파일 크기는 16 MB를 초과할 수 없습니다.');
    analyzeBtn.disabled = true;
    return;
  }
  fileHint.textContent = `선택된 파일: ${file.name} (${formatFileSize(file.size)})`;
  analyzeBtn.disabled = false;
}
function formatFileSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
function showError(msg) {
  errorMessage.textContent = msg;
  errorBanner.hidden = false;
}
function hideError() {
  errorBanner.hidden = true;
  errorMessage.textContent = '';
}
function setLoading(loading) {
  if (loading) {
    analyzeBtn.classList.add('btn--loading');
    analyzeBtn.disabled = true;
  } else {
    analyzeBtn.classList.remove('btn--loading');
    analyzeBtn.disabled = false;
  }
}
// ── Form submit ──────────────────────────────────────
uploadForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  hideError();
  const file = fileInput.files[0];
  if (!file) {
    showError('파일을 선택해 주세요.');
    return;
  }
  setLoading(true);
  const formData = new FormData();
  formData.append('file', file);
  try {
    const response = await fetch('/analyze', {
      method: 'POST',
      body: formData,
    });
    const data = await response.json();
    if (!response.ok) {
      showError(data.error || '알 수 없는 오류가 발생했습니다.');
      return;
    }
    renderResults(data);
  } catch (err) {
    console.error('Upload failed:', err);
    showError('서버와 통신 중 오류가 발생했습니다. 네트워크 연결을 확인해 주세요.');
  } finally {
    setLoading(false);
  }
});
// ── Render results ───────────────────────────────────
function renderResults(data) {
  summaryText.textContent = data.summary || '요약을 가져올 수 없습니다.';
  keyPointsList.innerHTML = '';
  const points = Array.isArray(data.key_points) ? data.key_points : [];
  if (points.length === 0) {
    const li = document.createElement('li');
    li.textContent = '핵심 포인트를 가져올 수 없습니다.';
    keyPointsList.appendChild(li);
  } else {
    points.forEach((point) => {
      const li = document.createElement('li');
      li.textContent = point;
      keyPointsList.appendChild(li);
    });
  }
  uploadSection.hidden = true;
  resultsSection.hidden = false;
}
// ── Reset ────────────────────────────────────────────
resetBtn.addEventListener('click', () => {
  uploadForm.reset();
  fileHint.textContent = '최대 16 MB · PDF 형식만 지원';
  analyzeBtn.disabled = true;
  hideError();
  resultsSection.hidden = true;
  uploadSection.hidden = false;
});
‎templates/index.html‎
+85
Lines changed: 85 additions & 0 deletions
Original file line number	Diff line number	Diff line change
<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>StudyMate AI — PDF 학습 보조 도구</title>
  <link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}" />
</head>
<body>
  <div class="container">
    <!-- Header -->
    <header class="header">
      <div class="logo">
        <span class="logo-icon">📚</span>
        <h1>StudyMate AI</h1>
      </div>
      <p class="subtitle">PDF를 업로드하면 AI가 내용을 요약하고 핵심 포인트를 추출해 드립니다.</p>
    </header>
    <!-- Upload Section -->
    <section class="upload-section" id="uploadSection">
      <form id="uploadForm" enctype="multipart/form-data">
        <div
          class="drop-zone"
          id="dropZone"
          role="button"
          tabindex="0"
          aria-label="PDF 파일을 드래그하거나 클릭하여 업로드하세요"
        >
          <div class="drop-zone__icon">📄</div>
          <p class="drop-zone__text">PDF 파일을 여기에 드래그하거나</p>
          <label class="btn btn--primary" for="fileInput">
            파일 선택
          </label>
          <input
            type="file"
            id="fileInput"
            name="file"
            accept=".pdf"
            class="visually-hidden"
          />
          <p class="drop-zone__hint" id="fileHint">최대 16 MB · PDF 형식만 지원</p>
        </div>
        <button type="submit" class="btn btn--analyze" id="analyzeBtn" disabled>
          <span class="btn__label">AI 분석 시작</span>
          <span class="btn__spinner" aria-hidden="true"></span>
        </button>
      </form>
    </section>
    <!-- Error Banner -->
    <div class="error-banner" id="errorBanner" role="alert" aria-live="polite" hidden>
      <span class="error-banner__icon">⚠️</span>
      <span id="errorMessage"></span>
    </div>
    <!-- Results Section -->
    <section class="results-section" id="resultsSection" hidden>
      <!-- Summary Card -->
      <div class="card" id="summaryCard">
        <div class="card__header">
          <span class="card__icon">📝</span>
          <h2 class="card__title">내용 요약</h2>
        </div>
        <p class="card__body" id="summaryText"></p>
      </div>
      <!-- Key Points Card -->
      <div class="card" id="keyPointsCard">
        <div class="card__header">
          <span class="card__icon">🎯</span>
          <h2 class="card__title">핵심 포인트</h2>
        </div>
        <ul class="key-points-list" id="keyPointsList"></ul>
      </div>
      <!-- Reset Button -->
      <button class="btn btn--reset" id="resetBtn">다른 파일 분석하기</button>
    </section>
  </div>
  <script src="{{ url_for('static', filename='js/main.js') }}"></script>
</body>
</html>
‎.env.example‎
+5
Lines changed: 5 additions & 0 deletions
Original file line number	Diff line number	Diff line change
# OpenAI API Key - get yours at https://platform.openai.com/api-keys
OPENAI_API_KEY=your_openai_api_key_here
# Set to 1 to enable Flask debug mode (development only, never in production)
FLASK_DEBUG=0
‎.gitignore‎
+30
Lines changed: 30 additions & 0 deletions
Original file line number	Diff line number	Diff line change
# Environment variables (never commit this file)
.env
# Python cache
__pycache__/
*.py[cod]
*.pyo
*.pyd
# Virtual environments
venv/
.venv/
env/
ENV/
# Distribution / packaging
dist/
build/
*.egg-info/
# IDE settings
.vscode/
.idea/
# OS files
.DS_Store
Thumbs.db
# Uploaded files (if saved to disk)
uploads/
‎app.py‎
+132
Lines changed: 132 additions & 0 deletions
Original file line number	Diff line number	Diff line change
import os
import io
import json
import logging
import pdfplumber
from flask import Flask, render_template, request, jsonify
from openai import OpenAI
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
load_dotenv()
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB limit
ALLOWED_EXTENSIONS = {"pdf"}
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
def extract_text_from_pdf(file_stream: io.BytesIO) -> str:
    """Extract all text from a PDF file stream."""
    text_parts = []
    with pdfplumber.open(file_stream) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
    return "\n\n".join(text_parts)
def analyze_text_with_gpt(text: str) -> dict:
    """Send extracted text to ChatGPT and return summary and key points."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable is not set.")
    client = OpenAI(api_key=api_key)
    # Truncate text to avoid exceeding token limits (approx 12,000 chars ≈ 3,000 tokens)
    MAX_CHARS = 11900
    suffix = "\n\n[... 텍스트가 너무 길어 일부만 분석되었습니다 ...]"
    if len(text) > MAX_CHARS:
        truncated = text[:MAX_CHARS] + suffix
    else:
        truncated = text
    system_prompt = (
        "당신은 학습 보조 AI입니다. 사용자가 제공한 문서를 분석하여 "
        "한국어로 명확하고 유익한 학습 자료를 제공합니다."
    )
    user_prompt = (
        "다음 문서를 분석하여 아래 두 가지를 JSON 형식으로 반환해 주세요:\n"
        "1. \"summary\": 문서의 핵심 내용을 3~5문장으로 요약\n"
        "2. \"key_points\": 학습에 중요한 핵심 포인트를 최대 10개의 항목 리스트로 정리\n\n"
        "반드시 다음 JSON 형식만 반환하세요 (다른 텍스트 없이):\n"
        "{\"summary\": \"...\", \"key_points\": [\"...\", \"...\"]}\n\n"
        f"문서 내용:\n{truncated}"
    )
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.3,
        response_format={"type": "json_object"},
    )
    result_text = response.choices[0].message.content
    result = json.loads(result_text)
    if "summary" not in result or "key_points" not in result:
        raise ValueError("GPT 응답 형식이 올바르지 않습니다.")
    return result
@app.route("/")
def index():
    return render_template("index.html")
@app.route("/analyze", methods=["POST"])
def analyze():
    if "file" not in request.files:
        return jsonify({"error": "파일이 업로드되지 않았습니다."}), 400
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "파일이 선택되지 않았습니다."}), 400
    if not allowed_file(file.filename):
        return jsonify({"error": "PDF 파일만 업로드 가능합니다."}), 400
    filename = secure_filename(file.filename)
    logger.info("Processing file: %s", filename)
    try:
        file_bytes = io.BytesIO(file.read())
        text = extract_text_from_pdf(file_bytes)
    except Exception as exc:
        logger.error("PDF extraction failed: %s", exc)
        return jsonify({"error": "PDF 텍스트 추출에 실패했습니다. 파일이 손상되었거나 이미지 기반 PDF일 수 있습니다."}), 422
    if not text.strip():
        return jsonify({"error": "PDF에서 텍스트를 추출할 수 없습니다. 이미지 기반 PDF는 지원되지 않습니다."}), 422
    try:
        result = analyze_text_with_gpt(text)
    except ValueError:
        logger.error("Analysis failed: configuration or response format error")
        return jsonify({"error": "AI 분석 설정 오류가 발생했습니다. 서버 관리자에게 문의해 주세요."}), 500
    except Exception as exc:
        logger.error("GPT API error: %s", exc)
        return jsonify({"error": "AI 분석 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."}), 502
    return jsonify(result)
if __name__ == "__main__":
    debug_mode = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(debug=debug_mode, port=5000)
‎README.md‎
+129
-1
Lines changed: 129 additions & 1 deletion


Original file line number	Diff line number	Diff line change
# studymate_ai
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
‎requirements.txt‎
+5
Lines changed: 5 additions & 0 deletions


Original file line number	Diff line number	Diff line change
Flask==3.1.0
openai==1.76.0
pdfplumber==0.11.6
python-dotenv==1.1.0
Werkzeug==3.1.3