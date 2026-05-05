import os
import io
import json
import logging
import uuid
from typing import Optional
from datetime import datetime, timezone

import pdfplumber
from flask import (
    Flask, render_template, request, jsonify,
    redirect, url_for, flash, send_from_directory,
)
from flask_login import (
    LoginManager, login_required, current_user,
)
from openai import OpenAI
from dotenv import load_dotenv
from werkzeug.utils import secure_filename

# NEW: begin – import new modules
from models import db, User, Folder, Material, SummaryNote, QuizSet, QuizQuestion, ActivityLog
from auth import auth_bp, init_oauth
# NEW: end

load_dotenv()

# ── Configuration ─────────────────────────────────────────────────────────────
MODEL              = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
MAX_CHARS          = int(os.environ.get("MAX_CHARS", "11900"))
TEMPERATURE        = float(os.environ.get("TEMPERATURE", "0.3"))
ALLOWED_EXTENSIONS = {"pdf"}
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB

# NEW: begin – paths for uploaded files
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
# NEW: end

# ── App setup ─────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH
# NEW: begin – secret key, database, and upload folder config
app.config["SECRET_KEY"]      = os.environ.get("SECRET_KEY", os.urandom(24).hex())
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL", f"sqlite:///{os.path.join(os.path.dirname(__file__), 'studymate.db')}"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
# NEW: end

# NEW: begin – initialise extensions
db.init_app(app)
init_oauth(app)

login_manager = LoginManager(app)
login_manager.login_view = "login_page"
login_manager.login_message = "로그인이 필요합니다."
login_manager.login_message_category = "info"

app.register_blueprint(auth_bp)


@login_manager.user_loader
def load_user(user_id: str):
    return User.query.get(user_id)


with app.app_context():
    db.create_all()
# NEW: end

# ── OpenAI client (singleton) ─────────────────────────────────────────────────
_openai_client: Optional[OpenAI] = None


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
# NEW: begin – structured summary note generation
def generate_summary_note(text: str, *, language: str = "ko") -> dict:
    """
    Return a structured summary note.  AI decides the depth/length.
    Output schema:
      {
        "title": str,
        "overview": str,
        "keywords": [{"term": str, "meaning": str, "related": [str]}],
        "sections": [{"title": str, "type": "text"|"list"|"table"|"callout", "content": any}],
        "comparison_table": {"headers": [str], "rows": [[str]]} | null,
        "key_takeaways": [str]
      }
    """
    truncated = _truncate_text(text)

    if language == "en":
        system_prompt = (
            "You are an expert study assistant AI. Analyze documents and produce rich, "
            "structured study notes in English. Use your judgment to decide the depth and "
            "length of the note based on the document's complexity and content volume."
        )
        user_prompt = (
            "Analyze the following document and return ONLY the JSON below (no extra text).\n"
            "Decide the number of keywords (8-20), sections (4-10), and whether a comparison "
            "table is useful. Do NOT let the user set sentence counts.\n\n"
            'Schema:\n{"title":"...", "overview":"...", '
            '"keywords":[{"term":"...","meaning":"...","related":["..."]}], '
            '"sections":[{"title":"...","type":"text|list|table|callout","content":"..."}], '
            '"comparison_table":{"headers":["..."],"rows":[["..."]]}, '
            '"key_takeaways":["..."]}\n\n'
            f"Document:\n{truncated}"
        )
    else:
        system_prompt = (
            "당신은 전문 학습 보조 AI입니다. 문서를 분석해 풍부하고 구조화된 학습 노트를 한국어로 생성합니다. "
            "문서의 복잡도와 분량에 따라 노트의 깊이와 길이를 스스로 결정합니다."
        )
        user_prompt = (
            "아래 문서를 분석하고 다음 JSON만 반환하세요 (추가 텍스트 없이).\n"
            "키워드 개수(8-20), 섹션 개수(4-10), 비교표 필요 여부를 스스로 판단하세요. "
            "사용자가 문장 수를 설정하지 않습니다.\n\n"
            '스키마:\n{"title":"...", "overview":"...", '
            '"keywords":[{"term":"...","meaning":"...","related":["..."]}], '
            '"sections":[{"title":"...","type":"text|list|table|callout","content":"..."}], '
            '"comparison_table":{"headers":["..."],"rows":[["..."]]}, '
            '"key_takeaways":["..."]}\n\n'
            f"문서 내용:\n{truncated}"
        )

    client = get_openai_client()
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        temperature=TEMPERATURE,
        response_format={"type": "json_object"},
    )
    result = json.loads(response.choices[0].message.content)
    required = {"title", "keywords", "sections"}
    if not required.issubset(result.keys()):
        raise ValueError("GPT 응답 형식이 올바르지 않습니다.")
    return result
# NEW: end


def generate_quiz(
    text: str,
    *,
    language: str = "ko",
    num_questions: int = 5,
) -> dict:
    """Return {questions: [{question, options, answer, explanation}]} from document text."""
    truncated = _truncate_text(text)

    if language == "en":
        system_prompt = (
            "You are a study assistant AI. Generate multiple-choice quiz questions "
            "based on the provided document in English."
        )
        user_prompt = (
            f"Generate exactly {num_questions} multiple-choice questions from the document.\n"
            "Return ONLY this JSON (no other text):\n"
            '{"questions": [{"question": "...", "options": ["A. ...", "B. ...", "C. ...", "D. ..."], '
            '"answer": "A", "explanation": "..."}]}\n\n'
            f"Document:\n{truncated}"
        )
    else:
        system_prompt = (
            "당신은 학습 보조 AI입니다. "
            "제공된 문서를 기반으로 객관식 퀴즈를 한국어로 생성합니다."
        )
        user_prompt = (
            f"다음 문서를 기반으로 객관식 퀴즈를 정확히 {num_questions}개 한국어로 만들어 주세요.\n"
            "반드시 아래 JSON만 반환하세요 (다른 텍스트 없이):\n"
            '{"questions": [{"question": "...", "options": ["A. ...", "B. ...", "C. ...", "D. ..."], '
            '"answer": "A", "explanation": "해설"}]}\n\n'
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


# NEW: begin – activity logging helper
def log_activity(user_id: str, action: str, resource_type: str,
                 resource_id: str = None, resource_name: str = None):
    try:
        entry = ActivityLog(
            user_id=user_id, action=action,
            resource_type=resource_type,
            resource_id=resource_id, resource_name=resource_name,
        )
        db.session.add(entry)
        db.session.commit()
    except Exception as exc:
        logger.warning("Activity log failed: %s", exc)
# NEW: end


# ── Routes: public ─────────────────────────────────────────────────────────────
@app.route("/login")
def login_page():
    if current_user.is_authenticated:
        return redirect(url_for("home"))
    google_configured = bool(
        os.environ.get("GOOGLE_CLIENT_ID") and os.environ.get("GOOGLE_CLIENT_SECRET")
    )
    return render_template("login.html", google_configured=google_configured)


# NEW: begin – multi-page dashboard routes
@app.route("/")
@login_required
def home():
    recent_materials = (
        Material.query
        .filter_by(user_id=current_user.id)
        .order_by(Material.upload_date.desc())
        .limit(5).all()
    )
    recent_activity = (
        ActivityLog.query
        .filter_by(user_id=current_user.id)
        .order_by(ActivityLog.created_at.desc())
        .limit(8).all()
    )
    stats = {
        "materials": Material.query.filter_by(user_id=current_user.id).count(),
        "notes":     SummaryNote.query.filter_by(user_id=current_user.id).count(),
        "quizzes":   QuizSet.query.filter_by(user_id=current_user.id).count(),
        "folders":   Folder.query.filter_by(user_id=current_user.id).count(),
    }
    return render_template("home.html",
                           recent_materials=recent_materials,
                           recent_activity=recent_activity,
                           stats=stats)


@app.route("/upload")
@login_required
def upload_page():
    folders = Folder.query.filter_by(user_id=current_user.id).all()
    return render_template("upload.html", folders=folders)


@app.route("/notes")
@login_required
def notes_page():
    q      = request.args.get("q", "").strip()
    sort   = request.args.get("sort", "newest")
    query  = SummaryNote.query.filter_by(user_id=current_user.id)
    if q:
        query = query.filter(SummaryNote.title.ilike(f"%{q}%"))
    if sort == "oldest":
        query = query.order_by(SummaryNote.created_at.asc())
    else:
        query = query.order_by(SummaryNote.created_at.desc())
    notes  = query.all()
    recent = (SummaryNote.query
              .filter_by(user_id=current_user.id)
              .order_by(SummaryNote.updated_at.desc())
              .limit(5).all())
    return render_template("notes.html", notes=notes, recent=recent, q=q, sort=sort)


@app.route("/notes/<note_id>")
@login_required
def note_detail(note_id):
    note = SummaryNote.query.filter_by(id=note_id, user_id=current_user.id).first_or_404()
    content = {}
    if note.content:
        try:
            content = json.loads(note.content)
        except Exception:
            content = {}
    log_activity(current_user.id, "view", "note", note.id, note.title)
    return render_template("note_detail.html", note=note, content=content)


@app.route("/quizzes")
@login_required
def quizzes_page():
    q      = request.args.get("q", "").strip()
    sort   = request.args.get("sort", "newest")
    query  = QuizSet.query.filter_by(user_id=current_user.id)
    if q:
        query = query.filter(QuizSet.title.ilike(f"%{q}%"))
    if sort == "oldest":
        query = query.order_by(QuizSet.created_at.asc())
    else:
        query = query.order_by(QuizSet.created_at.desc())
    quiz_sets = query.all()
    recent = (QuizSet.query
              .filter_by(user_id=current_user.id)
              .order_by(QuizSet.created_at.desc())
              .limit(5).all())
    return render_template("quizzes.html", quiz_sets=quiz_sets, recent=recent, q=q, sort=sort)


@app.route("/quizzes/<set_id>")
@login_required
def quiz_detail(set_id):
    quiz_set   = QuizSet.query.filter_by(id=set_id, user_id=current_user.id).first_or_404()
    questions  = QuizQuestion.query.filter_by(set_id=set_id).order_by(QuizQuestion.order_idx).all()
    questions_data = []
    for q in questions:
        questions_data.append({
            "id":          q.id,
            "question":    q.question,
            "options":     json.loads(q.options) if q.options else [],
            "answer":      q.answer,
            "explanation": q.explanation or "",
        })
    log_activity(current_user.id, "view", "quiz", quiz_set.id, quiz_set.title)
    return render_template("quiz_detail.html",
                           quiz_set=quiz_set,
                           questions=questions_data,
                           questions_json=json.dumps(questions_data, ensure_ascii=False))


@app.route("/materials")
@login_required
def materials_page():
    q         = request.args.get("q", "").strip()
    folder_id = request.args.get("folder", "")
    sort      = request.args.get("sort", "newest")

    folders   = Folder.query.filter_by(user_id=current_user.id).order_by(Folder.created_at).all()
    mat_query = Material.query.filter_by(user_id=current_user.id)

    if folder_id:
        mat_query = mat_query.filter_by(folder_id=folder_id)
    if q:
        mat_query = mat_query.filter(Material.name.ilike(f"%{q}%"))
    if sort == "oldest":
        mat_query = mat_query.order_by(Material.upload_date.asc())
    elif sort == "name":
        mat_query = mat_query.order_by(Material.name.asc())
    else:
        mat_query = mat_query.order_by(Material.upload_date.desc())

    materials = mat_query.all()
    return render_template("materials.html",
                           folders=folders,
                           materials=materials,
                           q=q, sort=sort,
                           active_folder=folder_id)


@app.route("/profile")
@login_required
def profile_page():
    activity_count = ActivityLog.query.filter_by(user_id=current_user.id).count()
    stats = {
        "materials": Material.query.filter_by(user_id=current_user.id).count(),
        "notes":     SummaryNote.query.filter_by(user_id=current_user.id).count(),
        "quizzes":   QuizSet.query.filter_by(user_id=current_user.id).count(),
        "activity":  activity_count,
    }
    return render_template("profile.html", stats=stats)
# NEW: end


# ── API: file upload + summarize ───────────────────────────────────────────────
# NEW: begin – unified upload endpoint
@app.route("/api/upload", methods=["POST"])
@login_required
def api_upload():
    """Upload a PDF, extract text, optionally generate summary note or quiz."""
    if "file" not in request.files:
        return jsonify({"error": "파일이 업로드되지 않았습니다."}), 400
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "파일이 선택되지 않았습니다."}), 400
    if not allowed_file(file.filename):
        return jsonify({"error": "PDF 파일만 업로드 가능합니다."}), 400

    mode      = request.form.get("mode", "summarize")   # summarize | quiz | upload_only
    language  = request.form.get("language", "ko")
    folder_id = request.form.get("folder_id") or None
    try:
        num_questions = min(int(request.form.get("num_questions", 5)), 15)
    except (ValueError, TypeError):
        num_questions = 5

    filename   = secure_filename(file.filename)
    file_bytes = file.read()
    file_size  = len(file_bytes)
    unique_name = f"{uuid.uuid4().hex}_{filename}"
    save_path   = os.path.join(app.config["UPLOAD_FOLDER"], unique_name)

    try:
        with open(save_path, "wb") as fout:
            fout.write(file_bytes)
        text = extract_text_from_pdf(io.BytesIO(file_bytes))
    except Exception as exc:
        logger.error("PDF extraction failed: %s", exc)
        return jsonify({"error": "PDF 텍스트 추출에 실패했습니다."}), 422

    if not text.strip():
        return jsonify({"error": "PDF에서 텍스트를 추출할 수 없습니다."}), 422

    if folder_id:
        folder = Folder.query.filter_by(id=folder_id, user_id=current_user.id).first()
        if not folder:
            folder_id = None

    material = Material(
        user_id=current_user.id,
        folder_id=folder_id,
        name=filename,
        stored_path=unique_name,
        file_size=file_size,
        extracted_text=text,
    )
    db.session.add(material)
    db.session.commit()
    log_activity(current_user.id, "upload", "material", material.id, material.name)

    if mode == "upload_only":
        return jsonify({"material_id": material.id, "name": material.name})

    try:
        if mode == "quiz":
            result = generate_quiz(text, language=language, num_questions=num_questions)
            quiz_set = QuizSet(
                user_id=current_user.id,
                material_id=material.id,
                title=f"{filename} - 예상 문제",
            )
            db.session.add(quiz_set)
            db.session.flush()
            for idx, q in enumerate(result.get("questions", [])):
                qq = QuizQuestion(
                    set_id=quiz_set.id,
                    order_idx=idx,
                    question=q.get("question", ""),
                    options=json.dumps(q.get("options", []), ensure_ascii=False),
                    answer=str(q.get("answer", "A")).strip().upper(),
                    explanation=q.get("explanation", ""),
                )
                db.session.add(qq)
            db.session.commit()
            log_activity(current_user.id, "create", "quiz", quiz_set.id, quiz_set.title)
            return jsonify({"material_id": material.id, "quiz_set_id": quiz_set.id,
                            "redirect": url_for("quiz_detail", set_id=quiz_set.id)})
        else:
            structured = generate_summary_note(text, language=language)
            note = SummaryNote(
                user_id=current_user.id,
                material_id=material.id,
                title=structured.get("title", filename),
                content=json.dumps(structured, ensure_ascii=False),
            )
            db.session.add(note)
            db.session.commit()
            log_activity(current_user.id, "create", "note", note.id, note.title)
            return jsonify({"material_id": material.id, "note_id": note.id,
                            "redirect": url_for("note_detail", note_id=note.id)})
    except ValueError as exc:
        logger.error("Analysis config error: %s", exc)
        return jsonify({"error": "AI 분석 설정 오류가 발생했습니다."}), 500
    except Exception as exc:
        logger.error("GPT API error: %s", exc, exc_info=True)
        return jsonify({"error": "AI 분석 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."}), 502
# NEW: end


# ── API: CRUD endpoints ────────────────────────────────────────────────────────
# NEW: begin
@app.route("/api/materials/<material_id>", methods=["DELETE"])
@login_required
def api_delete_material(material_id):
    mat = Material.query.filter_by(id=material_id, user_id=current_user.id).first_or_404()
    if mat.stored_path:
        try:
            os.remove(os.path.join(app.config["UPLOAD_FOLDER"], mat.stored_path))
        except OSError:
            pass
    db.session.delete(mat)
    db.session.commit()
    return jsonify({"ok": True})


@app.route("/api/folders", methods=["POST"])
@login_required
def api_create_folder():
    data  = request.get_json(silent=True) or {}
    name  = (data.get("name") or "").strip()
    color = (data.get("color") or "#4f46e5").strip()
    if not name:
        return jsonify({"error": "폴더 이름을 입력해 주세요."}), 400
    folder = Folder(user_id=current_user.id, name=name, color=color)
    db.session.add(folder)
    db.session.commit()
    return jsonify({"id": folder.id, "name": folder.name, "color": folder.color}), 201


@app.route("/api/folders/<folder_id>", methods=["DELETE"])
@login_required
def api_delete_folder(folder_id):
    folder = Folder.query.filter_by(id=folder_id, user_id=current_user.id).first_or_404()
    Material.query.filter_by(folder_id=folder_id).update({"folder_id": None})
    db.session.delete(folder)
    db.session.commit()
    return jsonify({"ok": True})


@app.route("/api/notes/<note_id>", methods=["DELETE"])
@login_required
def api_delete_note(note_id):
    note = SummaryNote.query.filter_by(id=note_id, user_id=current_user.id).first_or_404()
    db.session.delete(note)
    db.session.commit()
    return jsonify({"ok": True})


@app.route("/api/quizsets/<set_id>", methods=["DELETE"])
@login_required
def api_delete_quizset(set_id):
    qs = QuizSet.query.filter_by(id=set_id, user_id=current_user.id).first_or_404()
    db.session.delete(qs)
    db.session.commit()
    return jsonify({"ok": True})
# NEW: end


# ── Legacy /analyze route (kept for backward compatibility) ───────────────────
@app.route("/analyze", methods=["POST"])
def analyze():
    """Original single-page analyze endpoint – kept for backward compat."""
    if "file" not in request.files:
        return jsonify({"error": "파일이 업로드되지 않았습니다."}), 400
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "파일이 선택되지 않았습니다."}), 400
    if not allowed_file(file.filename):
        return jsonify({"error": "PDF 파일만 업로드 가능합니다."}), 400

    mode     = request.form.get("mode", "analyze")
    language = request.form.get("language", "ko")
    try:
        num_questions = min(int(request.form.get("num_questions", 5)), 15)
    except (ValueError, TypeError):
        return jsonify({"error": "설정값이 올바르지 않습니다."}), 400

    filename = secure_filename(file.filename)
    logger.info("Legacy analyze: %s | mode=%s lang=%s", filename, mode, language)
    try:
        file_bytes = io.BytesIO(file.read())
        text = extract_text_from_pdf(file_bytes)
    except Exception as exc:
        logger.error("PDF extraction failed: %s", exc)
        return jsonify({"error": "PDF 텍스트 추출에 실패했습니다."}), 422

    if not text.strip():
        return jsonify({"error": "PDF에서 텍스트를 추출할 수 없습니다."}), 422

    try:
        if mode == "quiz":
            result = generate_quiz(text, language=language, num_questions=num_questions)
        else:
            structured = generate_summary_note(text, language=language)
            result = {
                "summary": structured.get("overview", ""),
                "key_points": structured.get("key_takeaways", []),
                "structured": structured,
            }
    except ValueError as exc:
        logger.error("Analysis failed: %s", exc, exc_info=True)
        return jsonify({"error": "AI 분석 설정 오류가 발생했습니다."}), 500
    except Exception as exc:
        logger.error("GPT API error: %s", exc, exc_info=True)
        return jsonify({"error": "AI 분석 중 오류가 발생했습니다."}), 502
    return jsonify(result)


if __name__ == "__main__":
    debug_mode = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(debug=debug_mode, port=5000)
