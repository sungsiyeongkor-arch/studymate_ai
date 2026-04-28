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
