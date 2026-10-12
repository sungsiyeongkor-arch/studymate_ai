"""Versioned source records are immutable; current projections may be rebuilt."""

from datetime import datetime, timezone
from uuid import uuid4
from .extensions import db


def uid():
    return uuid4().hex


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Record:
    id = db.Column(db.String(32), primary_key=True, default=uid)
    created_at = db.Column(db.DateTime, nullable=False, default=now)


class User(Record, db.Model):
    __tablename__ = "sm_users"
    email = db.Column(db.String(254), unique=True, nullable=False)
    name = db.Column(db.String(80), nullable=False)
    password_hash = db.Column(db.Text, nullable=False)
    storage_used = db.Column(
        db.BigInteger, nullable=False, default=0, server_default="0"
    )
    storage_reserved = db.Column(
        db.BigInteger, nullable=False, default=0, server_default="0"
    )
    personalization = db.Column(db.Boolean, default=False, nullable=False)


class Owned(Record):
    user_id = db.Column(
        db.String(32), db.ForeignKey("sm_users.id"), nullable=False, index=True
    )


class Course(Owned, db.Model):
    __tablename__ = "sm_courses"
    title = db.Column(db.String(160), nullable=False)
    color = db.Column(db.String(20), default="#386b54")
    description = db.Column(db.Text, default="")


class Lecture(Owned, db.Model):
    __tablename__ = "sm_lectures"
    course_id = db.Column(
        db.String(32), db.ForeignKey("sm_courses.id"), nullable=False, index=True
    )
    title = db.Column(db.String(200), nullable=False)
    topic = db.Column(db.Text, default="")
    language = db.Column(db.String(10), default="ko")


class Material(Owned, db.Model):
    __tablename__ = "sm_materials"
    lecture_id = db.Column(
        db.String(32), db.ForeignKey("sm_lectures.id"), nullable=False, index=True
    )
    name = db.Column(db.String(255), nullable=False)
    kind = db.Column(db.String(20), nullable=False)
    storage_key = db.Column(db.String(160), nullable=False)
    size = db.Column(db.BigInteger, nullable=False)
    sha256 = db.Column(db.String(64), nullable=False)
    status = db.Column(db.String(30), nullable=False, default="queued")
    page_count = db.Column(db.Integer, default=0)
    duration = db.Column(db.Float, default=0)


class Segment(Owned, db.Model):
    __tablename__ = "sm_segments"
    material_id = db.Column(
        db.String(32), db.ForeignKey("sm_materials.id"), nullable=False, index=True
    )
    ordinal = db.Column(db.Integer, nullable=False)
    page = db.Column(db.Integer)
    start = db.Column(db.Float)
    end = db.Column(db.Float)
    bbox = db.Column(db.JSON)
    text = db.Column(db.Text, default="", nullable=False)
    revision = db.Column(db.Integer, default=1, nullable=False)
    state = db.Column(db.String(24), default="automatic", nullable=False)
    __table_args__ = (db.UniqueConstraint("material_id", "ordinal"),)


class Revision(Owned, db.Model):
    __tablename__ = "sm_revisions"
    segment_id = db.Column(
        db.String(32), db.ForeignKey("sm_segments.id"), nullable=False, index=True
    )
    number = db.Column(db.Integer, nullable=False)
    text = db.Column(db.Text, nullable=False)
    author = db.Column(db.String(20), nullable=False)
    reason = db.Column(db.String(30), default="transcription")
    __table_args__ = (db.UniqueConstraint("segment_id", "number"),)


class Term(Owned, db.Model):
    __tablename__ = "sm_terms"
    course_id = db.Column(
        db.String(32), db.ForeignKey("sm_courses.id"), nullable=False, index=True
    )
    word = db.Column(db.String(120), nullable=False)
    pronunciation = db.Column(db.String(200), default="")
    meaning = db.Column(db.Text, default="")
    related = db.Column(db.JSON, default=list)
    confirmed = db.Column(db.Boolean, default=True)
    __table_args__ = (db.UniqueConstraint("course_id", "word"),)


class Job(Owned, db.Model):
    __tablename__ = "sm_jobs"
    material_id = db.Column(db.String(32), db.ForeignKey("sm_materials.id"), index=True)
    lecture_id = db.Column(db.String(32), db.ForeignKey("sm_lectures.id"), index=True)
    kind = db.Column(db.String(30), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="queued", index=True)
    payload = db.Column(db.JSON, default=dict)
    progress = db.Column(db.Integer, default=0)
    total = db.Column(db.Integer, default=0)
    error = db.Column(db.Text, default="")
    attempts = db.Column(db.Integer, default=0)
    heartbeat = db.Column(db.DateTime)
    lease_token = db.Column(db.String(32))


class JobBatch(Owned, db.Model):
    __tablename__ = "sm_job_batches"
    job_id = db.Column(db.String(32), db.ForeignKey("sm_jobs.id"), nullable=False)
    ordinal = db.Column(db.Integer, nullable=False)
    sources = db.Column(db.JSON, nullable=False)
    completed = db.Column(db.Boolean, nullable=False, default=False)
    __table_args__ = (
        db.UniqueConstraint("job_id", "ordinal", name="uq_sm_job_batches_position"),
        db.Index("ix_sm_job_batches_pending", "job_id", "completed", "ordinal"),
    )


class Artifact(Owned, db.Model):
    __tablename__ = "sm_artifacts"
    lecture_id = db.Column(
        db.String(32), db.ForeignKey("sm_lectures.id"), nullable=False, index=True
    )
    kind = db.Column(db.String(30), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.JSON, nullable=False)
    stale = db.Column(db.Boolean, default=False, nullable=False)
    model = db.Column(db.String(80), default="manual")


class Citation(Owned, db.Model):
    __tablename__ = "sm_citations"
    artifact_id = db.Column(
        db.String(32), db.ForeignKey("sm_artifacts.id"), nullable=False, index=True
    )
    segment_id = db.Column(
        db.String(32), db.ForeignKey("sm_segments.id"), nullable=False, index=True
    )
    revision = db.Column(db.Integer, nullable=False)


class Card(Owned, db.Model):
    __tablename__ = "sm_cards"
    lecture_id = db.Column(
        db.String(32), db.ForeignKey("sm_lectures.id"), nullable=False, index=True
    )
    artifact_id = db.Column(db.String(32), db.ForeignKey("sm_artifacts.id"), index=True)
    question = db.Column(db.Text, nullable=False)
    answer = db.Column(db.Text, nullable=False)
    explanation = db.Column(db.Text, default="")
    concept = db.Column(db.String(160), default="")
    kind = db.Column(db.String(30), default="recall")
    options = db.Column(db.JSON, default=list)
    suspended = db.Column(db.Boolean, default=False)


class ReviewState(Owned, db.Model):
    __tablename__ = "sm_review_states"
    card_id = db.Column(
        db.String(32), db.ForeignKey("sm_cards.id"), nullable=False, unique=True
    )
    due = db.Column(db.DateTime, default=now, nullable=False, index=True)
    interval = db.Column(db.Float, default=0)
    ease = db.Column(db.Float, default=2.3)
    successes = db.Column(db.Integer, default=0)
    lapses = db.Column(db.Integer, default=0)
    version = db.Column(db.Integer, default=1)
    algorithm = db.Column(db.String(40), default="transparent-spacing-v1")


class Attempt(Owned, db.Model):
    __tablename__ = "sm_attempts"
    card_id = db.Column(
        db.String(32), db.ForeignKey("sm_cards.id"), nullable=False, index=True
    )
    request_key = db.Column(db.String(64), nullable=False)
    answer = db.Column(db.Text, nullable=False)
    grade = db.Column(db.Integer, nullable=False)
    hint_used = db.Column(db.Boolean, default=False)
    confidence = db.Column(db.Integer, default=1)
    snapshot = db.Column(db.JSON, nullable=False)
    previous_state = db.Column(db.JSON, nullable=False)
    next_due = db.Column(db.DateTime, nullable=False)
    invalidated = db.Column(db.Boolean, default=False)
    __table_args__ = (db.UniqueConstraint("user_id", "request_key"),)


class Chat(Owned, db.Model):
    __tablename__ = "sm_chats"
    lecture_id = db.Column(
        db.String(32), db.ForeignKey("sm_lectures.id"), nullable=False, index=True
    )
    role = db.Column(db.String(12), nullable=False)
    text = db.Column(db.Text, nullable=False)
    sources = db.Column(db.JSON, default=list)
    mode = db.Column(db.String(20), default="sources")


class HandwritingExample(Owned, db.Model):
    __tablename__ = "sm_handwriting_examples"
    segment_id = db.Column(
        db.String(32), db.ForeignKey("sm_segments.id"), nullable=False, unique=True
    )
    revision = db.Column(db.Integer, nullable=False)
    text = db.Column(db.Text, nullable=False)


class Upload(Owned, db.Model):
    __tablename__ = "sm_uploads"
    lecture_id = db.Column(
        db.String(32), db.ForeignKey("sm_lectures.id"), nullable=False
    )
    name = db.Column(db.String(255), nullable=False)
    size = db.Column(db.BigInteger, nullable=False)
    chunk_size = db.Column(db.Integer, default=4 * 1024 * 1024)
    status = db.Column(db.String(20), default="pending")
    material_id = db.Column(db.String(32), db.ForeignKey("sm_materials.id"))
    expires_at = db.Column(db.DateTime, nullable=True, index=True)


class UploadChunk(Owned, db.Model):
    __tablename__ = "sm_upload_chunks"
    upload_id = db.Column(
        db.String(32), db.ForeignKey("sm_uploads.id"), nullable=False, index=True
    )
    number = db.Column(db.Integer, nullable=False)
    sha256 = db.Column(db.String(64), nullable=False)
    storage_key = db.Column(db.String(160), nullable=False)
    size = db.Column(db.Integer, nullable=False)
    __table_args__ = (db.UniqueConstraint("upload_id", "number"),)


class Usage(Owned, db.Model):
    __tablename__ = "sm_usage"
    operation = db.Column(db.String(30), nullable=False)
    model = db.Column(db.String(80), nullable=False)
    input_tokens = db.Column(db.Integer, default=0)
    output_tokens = db.Column(db.Integer, default=0)


def public(record, exclude=()):
    out = {}
    for col in record.__table__.columns:
        if (
            col.name in {"password_hash", "storage_key", "lease_token"}
            or col.name in exclude
        ):
            continue
        value = getattr(record, col.name)
        out[col.name] = (
            value.isoformat() + "Z" if isinstance(value, datetime) else value
        )
    return out


# Tenant-first keyset indexes: stable ties use the immutable primary key.
for _model in (
    Course,
    Lecture,
    Material,
    Segment,
    Revision,
    Term,
    Job,
    Artifact,
    Citation,
    Card,
    ReviewState,
    Attempt,
    Chat,
    HandwritingExample,
    Upload,
    Usage,
):
    db.Index(
        f"ix_{_model.__tablename__}_owner_page",
        _model.user_id,
        _model.created_at,
        _model.id,
    )
for _model, _parent in (
    (Lecture, "course_id"),
    (Material, "lecture_id"),
    (Artifact, "lecture_id"),
    (Term, "course_id"),
    (Chat, "lecture_id"),
    (Job, "lecture_id"),
    (Revision, "segment_id"),
    (Card, "lecture_id"),
):
    db.Index(
        f"ix_{_model.__tablename__}_parent_page",
        _model.user_id,
        getattr(_model, _parent),
        _model.created_at,
        _model.id,
    )
db.Index("ix_sm_review_due_owner", ReviewState.user_id, ReviewState.due, ReviewState.id)
db.Index(
    "ix_sm_inbox_owner_state",
    Segment.user_id,
    Segment.state,
    Segment.created_at,
    Segment.id,
)
db.Index("ix_sm_jobs_claim", Job.status, Job.created_at, Job.id)
db.Index("ix_sm_jobs_recover", Job.status, Job.heartbeat)

db.Index(
    "ix_sm_attempts_card_latest",
    Attempt.user_id,
    Attempt.card_id,
    Attempt.invalidated,
    Attempt.created_at,
    Attempt.id,
)
