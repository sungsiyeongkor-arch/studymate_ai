# NEW: Database models for StudyMate AI
# This file is entirely new – added for user authentication and data persistence.

import uuid
from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()


def _now():
    return datetime.now(timezone.utc)


def _uuid():
    return str(uuid.uuid4())


# ── User ──────────────────────────────────────────────────────────────────────
class User(UserMixin, db.Model):
    __tablename__ = "users"

    id         = db.Column(db.String(36), primary_key=True, default=_uuid)
    google_id  = db.Column(db.String(128), unique=True, nullable=True)
    email      = db.Column(db.String(255), unique=True, nullable=False)
    name       = db.Column(db.String(255), nullable=False)
    avatar_url = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=_now)
    updated_at = db.Column(db.DateTime(timezone=True), default=_now, onupdate=_now)

    folders    = db.relationship("Folder",      backref="owner", lazy="dynamic", cascade="all, delete-orphan")
    materials  = db.relationship("Material",    backref="owner", lazy="dynamic", cascade="all, delete-orphan")
    notes      = db.relationship("SummaryNote", backref="owner", lazy="dynamic", cascade="all, delete-orphan")
    quiz_sets  = db.relationship("QuizSet",     backref="owner", lazy="dynamic", cascade="all, delete-orphan")
    activities = db.relationship("ActivityLog", backref="owner", lazy="dynamic", cascade="all, delete-orphan")


# ── Folder ────────────────────────────────────────────────────────────────────
class Folder(db.Model):
    __tablename__ = "folders"

    id         = db.Column(db.String(36), primary_key=True, default=_uuid)
    user_id    = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    name       = db.Column(db.String(255), nullable=False)
    color      = db.Column(db.String(20), default="#4f46e5")
    created_at = db.Column(db.DateTime(timezone=True), default=_now)

    materials  = db.relationship("Material", backref="folder", lazy="dynamic")


# ── Material ──────────────────────────────────────────────────────────────────
class Material(db.Model):
    __tablename__ = "materials"

    id             = db.Column(db.String(36), primary_key=True, default=_uuid)
    user_id        = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    folder_id      = db.Column(db.String(36), db.ForeignKey("folders.id"), nullable=True)
    name           = db.Column(db.String(255), nullable=False)
    stored_path    = db.Column(db.Text, nullable=True)   # relative path under uploads/
    file_size      = db.Column(db.Integer, default=0)    # bytes
    tags           = db.Column(db.Text, default="")      # comma-separated
    extracted_text = db.Column(db.Text, nullable=True)
    upload_date    = db.Column(db.DateTime(timezone=True), default=_now)

    notes     = db.relationship("SummaryNote", backref="material", lazy="dynamic")
    quiz_sets = db.relationship("QuizSet",     backref="material", lazy="dynamic")

    @property
    def tags_list(self):
        return [t.strip() for t in (self.tags or "").split(",") if t.strip()]

    @property
    def file_size_display(self):
        if self.file_size < 1024:
            return f"{self.file_size} B"
        if self.file_size < 1024 * 1024:
            return f"{self.file_size / 1024:.1f} KB"
        return f"{self.file_size / (1024 * 1024):.1f} MB"


# ── SummaryNote ───────────────────────────────────────────────────────────────
class SummaryNote(db.Model):
    __tablename__ = "summary_notes"

    id          = db.Column(db.String(36), primary_key=True, default=_uuid)
    user_id     = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    material_id = db.Column(db.String(36), db.ForeignKey("materials.id"), nullable=True)
    title       = db.Column(db.String(255), nullable=False)
    content     = db.Column(db.Text, nullable=True)   # JSON string of structured note
    created_at  = db.Column(db.DateTime(timezone=True), default=_now)
    updated_at  = db.Column(db.DateTime(timezone=True), default=_now, onupdate=_now)


# ── QuizSet ───────────────────────────────────────────────────────────────────
class QuizSet(db.Model):
    __tablename__ = "quiz_sets"

    id          = db.Column(db.String(36), primary_key=True, default=_uuid)
    user_id     = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    material_id = db.Column(db.String(36), db.ForeignKey("materials.id"), nullable=True)
    title       = db.Column(db.String(255), nullable=False)
    created_at  = db.Column(db.DateTime(timezone=True), default=_now)

    questions   = db.relationship("QuizQuestion", backref="quiz_set", lazy="dynamic",
                                  cascade="all, delete-orphan", order_by="QuizQuestion.order_idx")

    @property
    def question_count(self):
        return self.questions.count()


# ── QuizQuestion ──────────────────────────────────────────────────────────────
class QuizQuestion(db.Model):
    __tablename__ = "quiz_questions"

    id        = db.Column(db.String(36), primary_key=True, default=_uuid)
    set_id    = db.Column(db.String(36), db.ForeignKey("quiz_sets.id"), nullable=False)
    order_idx = db.Column(db.Integer, default=0)
    question  = db.Column(db.Text, nullable=False)
    options   = db.Column(db.Text, nullable=False)   # JSON array
    answer    = db.Column(db.String(4), nullable=False)  # "A" | "B" | "C" | "D"
    explanation = db.Column(db.Text, nullable=True)


# ── ActivityLog ───────────────────────────────────────────────────────────────
class ActivityLog(db.Model):
    __tablename__ = "activity_logs"

    id            = db.Column(db.String(36), primary_key=True, default=_uuid)
    user_id       = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    action        = db.Column(db.String(50), nullable=False)   # view / create / upload
    resource_type = db.Column(db.String(50), nullable=False)   # material / note / quiz
    resource_id   = db.Column(db.String(36), nullable=True)
    resource_name = db.Column(db.String(255), nullable=True)
    created_at    = db.Column(db.DateTime(timezone=True), default=_now)

    _ACTION_LABELS = {
        "view":   "열람",
        "create": "생성",
        "upload": "업로드",
    }

    @property
    def action_display(self):
        return self._ACTION_LABELS.get(self.action, self.action)
