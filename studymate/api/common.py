"""HTTP boundary. Ownership is checked before every resource access."""

import hashlib
import io
import json
import math
import re
import secrets
import shutil
from pathlib import Path
from flask import Blueprint, abort, current_app, g, jsonify, request, session, send_file
from werkzeug.security import check_password_hash, generate_password_hash
from sqlalchemy.exc import IntegrityError
from ..extensions import db, limiter
from ..models import (
    User,
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
    UploadChunk,
    Usage,
    now,
    uid,
    public,
)
from ..services import storage
from ..services.documents import validate, render_pdf
from ..services.provider import call_json, ProviderError
from ..services.retrieval import retrieve, source_dict
from ..services.review import schedule

api = Blueprint("api", __name__)


def body():
    value = request.get_json(silent=True)
    if not isinstance(value, dict):
        abort(400, "JSON 객체가 필요합니다.")
    return value


def text(data, name, maximum=200, required=False):
    value = data.get(name, "")
    if (
        not isinstance(value, str)
        or len(value) > maximum
        or (required and not value.strip())
    ):
        abort(400, f"{name}: 입력값을 확인해 주세요. 최대 {maximum}자입니다.")
    return value.strip()


def owned(model, key):
    if not isinstance(key, str) or not re.fullmatch(r"[0-9a-f]{32}", key):
        abort(404, "자료를 찾을 수 없습니다.")
    row = db.session.get(model, key)
    if not row or row.user_id != g.user.id:
        abort(404, "자료를 찾을 수 없습니다.")
    return row


def listed(model, **filters):
    return [
        public(r)
        for r in model.query.filter_by(user_id=g.user.id, **filters)
        .order_by(model.created_at.desc(), model.id.desc())
        .limit(50)
    ]
