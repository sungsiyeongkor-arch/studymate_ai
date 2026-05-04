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

# ── Configuration ─────────────────────────────────────────────────────────────
MODEL              = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
MAX_CHARS          = int(os.environ.get("MAX_CHARS", "11900"))
TEMPERATURE        = float(os.environ.get("TEMPERATURE", "0.3"))
ALLOWED_EXTENSIONS = {"pdf"}
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB

# ── App setup ─────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

# ── OpenAI client (singleton) ─────────────────────────────────────────────────
_openai_client: "OpenAI | None" = None


def get_openai_client() -> OpenAI:
    global _openai_client
    if _openai_client is None:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set.")
        _openai_client = OpenAI(api_key=api_key)
    return _openai_client


# ── PDF helpers ────────────────────────────────────────────────────────────────
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


def _truncate_text(text: str) -> str:
    suffix = "\n\n[... 텍스트가 너무 길어 일부만 분석되었습니다 ...]"
    if len(text) > MAX_CHARS:
        return text[:MAX_CHARS] + suffix
    return text


# ── AI services ────────────────────────────────────────────────────────────────
def analyze_text(
    text: str,
    *,
    language: str = "ko",
    num_points: int = 10,
    summary_sentences: int = 5,
) -> dict:
    """Return {summary, key_points} from document text."""
    truncated = _truncate_text(text)

    if language == "en":
        system_prompt = (
            "You are a study assistant AI. Analyze the provided document and "
            "generate clear, informative study materials in English."
        )
        user_prompt = (
            f"Analyze the following document and return ONLY this JSON (no other text):\n"
            f'{{"summary": "<{summary_sentences}-sentence summary>", '
            f'"key_points": ["<up to {num_points} key learning points>", "..."]}}\n\n'
            f"Document:\n{truncated}"
        )
    else:
        system_prompt = (
            "당신은 학습 보조 AI입니다. 사용자가 제공한 문서를 분석하여 "
            "한국어로 명확하고 유익한 학습 자료를 제공합니다."
        )
        user_prompt = (
            f"다음 문서를 분석하여 아래 JSON만 반환해 주세요 (다른 텍스트 없이):\n"
            f'{{"summary": "<{summary_sentences}문장으로 핵심 내용 요약>", '
            f'"key_points": ["<학습에 중요한 핵심 포인트 최대 {num_points}개>", "..."]}}\n\n'
            f"문서 내용:\n{truncated}"
        )

    client = get_openai_client()
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=TEMPERATURE,
        response_format={"type": "json_object"},
    )
    result = json.loads(response.choices[0].message.content)
    if "summary" not in result or "key_points" not in result:
        raise ValueError("GPT 응답 형식이 올바르지 않습니다.")
    return result


def generate_quiz(
    text: str,
    *,
    language: str = "ko",
    num_questions: int = 5,
) -> dict:
    """Return {questions: [{question, options, answer}]} from document text."""
    truncated = _truncate_text(text)

    if language == "en":
        system_prompt = (
            "You are a study assistant AI. Generate multiple-choice quiz questions "
            "based on the provided document in English."
        )
        user_prompt = (
            f"Generate exactly {num_questions} multiple-choice questions from the document.\n"
            f"Return ONLY this JSON (no other text):\n"
            f'{{"questions": [{{'
            f'"question": "...", '
            f'"options": ["A. ...", "B. ...", "C. ...", "D. ..."], '
            f'"answer": "A"'
            f'}}, ...]}}\n\n'
            f"Document:\n{truncated}"
        )
    else:
        system_prompt = (
            "당신은 학습 보조 AI입니다. "
            "제공된 문서를 기반으로 객관식 퀴즈를 한국어로 생성합니다."
        )
        user_prompt = (
            f"다음 문서를 기반으로 객관식 퀴즈를 정확히 {num_questions}개 한국어로 만들어 주세요.\n"
            f"반드시 아래 JSON만 반환하세요 (다른 텍스트 없이):\n"
            f'{{"questions": [{{'
            f'"question": "...", '
            f'"options": ["A. ...", "B. ...", "C. ...", "D. ..."], '
            f'"answer": "A"'
            f'}}, ...]}}\n\n'
            f"문서 내용:\n{truncated}"
        )

    client = get_openai_client()
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=TEMPERATURE,
        response_format={"type": "json_object"},
    )
    result = json.loads(response.choices[0].message.content)
    if "questions" not in result:
        raise ValueError("GPT 응답 형식이 올바르지 않습니다.")
    return result


# ── Routes ─────────────────────────────────────────────────────────────────────
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

    # Settings from form data
    mode              = request.form.get("mode", "analyze")            # analyze | quiz
    language          = request.form.get("language", "ko")             # ko | en
    num_points        = min(int(request.form.get("num_points", 10)), 20)
    summary_sentences = min(int(request.form.get("summary_sentences", 5)), 10)
    num_questions     = min(int(request.form.get("num_questions", 5)), 15)

    filename = secure_filename(file.filename)
    logger.info("Processing file: %s | mode=%s lang=%s", filename, mode, language)

    try:
        file_bytes = io.BytesIO(file.read())
        text = extract_text_from_pdf(file_bytes)
    except Exception as exc:
        logger.error("PDF extraction failed: %s", exc)
        return jsonify({
            "error": "PDF 텍스트 추출에 실패했습니다. 파일이 손상되었거나 이미지 기반 PDF일 수 있습니다."
        }), 422

    if not text.strip():
        return jsonify({
            "error": "PDF에서 텍스트를 추출할 수 없습니다. 이미지 기반 PDF는 지원되지 않습니다."
        }), 422

    try:
        if mode == "quiz":
            result = generate_quiz(text, language=language, num_questions=num_questions)
        else:
            result = analyze_text(
                text,
                language=language,
                num_points=num_points,
                summary_sentences=summary_sentences,
            )
    except ValueError:
        logger.error("Analysis failed: configuration or response format error")
        return jsonify({
            "error": "AI 분석 설정 오류가 발생했습니다. 서버 관리자에게 문의해 주세요."
        }), 500
    except Exception as exc:
        logger.error("GPT API error: %s", exc)
        return jsonify({
            "error": "AI 분석 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."
        }), 502

    return jsonify(result)


if __name__ == "__main__":
    debug_mode = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(debug=debug_mode, port=5000)
