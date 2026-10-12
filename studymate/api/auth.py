from .common import (
    IntegrityError,
    ProviderError,
    User,
    abort,
    api,
    body,
    check_password_hash,
    current_app,
    db,
    g,
    generate_password_hash,
    jsonify,
    limiter,
    public,
    re,
    secrets,
    session,
    shutil,
    text,
)


@api.errorhandler(ProviderError)
def provider_error(error):
    return jsonify(error=str(error), code="provider_unavailable"), 503


@api.get("/health")
def health():
    return {"status": "ok", "version": "2.0.0"}


@api.get("/session")
def get_session():
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return {"csrf": session["csrf"], "user": public(g.user) if g.user else None}


@api.post("/auth/register")
@limiter.limit("5 per minute")
def register():
    data = body()
    email, name, password = (
        text(data, "email", 254, True).lower(),
        text(data, "name", 80, True),
        text(data, "password", 200, True),
    )
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email) or len(password) < 12:
        abort(400, "올바른 이메일과 12자 이상의 비밀번호를 입력해 주세요.")
    user = User(email=email, name=name, password_hash=generate_password_hash(password))
    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        abort(409, "이미 사용 중인 이메일입니다.")
    session.clear()
    session.update(user_id=user.id, csrf=secrets.token_urlsafe(32))
    return {"user": public(user), "csrf": session["csrf"]}, 201


@api.post("/auth/login")
@limiter.limit("10 per minute")
def login():
    data = body()
    user = User.query.filter_by(email=text(data, "email", 254, True).lower()).first()
    password = text(data, "password", 200, True)
    if not user or not check_password_hash(user.password_hash, password):
        abort(401, "이메일 또는 비밀번호를 확인해 주세요.")
    session.clear()
    session.update(user_id=user.id, csrf=secrets.token_urlsafe(32))
    return {"user": public(user), "csrf": session["csrf"]}


@api.post("/auth/logout")
def logout():
    session.clear()
    return {"ok": True}


@api.get("/status")
def status():
    return {
        "ai_ready": bool(current_app.config["OPENAI_API_KEY"]),
        "model": current_app.config["OPENAI_MODEL"],
        "audio_ready": bool(shutil.which("ffmpeg") and shutil.which("ffprobe")),
        "personalization": g.user.personalization,
        "personalization_mode": "confirmed-examples",
        "scheduler": "규칙 기반 간격 복습 · 개인 망각곡선 학습은 검증 전",
        "daily_limit": current_app.config["AI_DAILY_REQUEST_LIMIT"],
    }
