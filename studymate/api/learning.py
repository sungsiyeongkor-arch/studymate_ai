from .common import (
    Artifact,
    Chat,
    Citation,
    Course,
    IntegrityError,
    Job,
    Lecture,
    Material,
    ProviderError,
    Segment,
    Term,
    abort,
    api,
    body,
    call_json,
    db,
    g,
    io,
    json,
    limiter,
    listed,
    owned,
    public,
    request,
    retrieve,
    send_file,
    source_dict,
    text,
)


@api.route("/terms", methods=["GET", "POST"])
def terms():
    if request.method == "GET":
        course = owned(Course, request.args.get("course_id"))
        return {"items": listed(Term, course_id=course.id)}
    data = body()
    course = owned(Course, data.get("course_id"))
    row = Term(
        user_id=g.user.id,
        course_id=course.id,
        word=text(data, "word", 120, True),
        pronunciation=text(data, "pronunciation", 200),
        meaning=text(data, "meaning", 3000),
        related=[
            s.strip() for s in text(data, "related", 1000).split(",") if s.strip()
        ],
    )
    db.session.add(row)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        abort(409, "이미 등록된 용어입니다.")
    return public(row), 201


@api.route("/terms/<key>", methods=["PATCH", "DELETE"])
def edit_term(key):
    row = owned(Term, key)
    if request.method == "DELETE":
        db.session.delete(row)
    else:
        data = body()
        row.confirmed = bool(data.get("confirmed", True))
        for field, maximum in [("meaning", 3000), ("pronunciation", 200)]:
            if field in data:
                setattr(row, field, text(data, field, maximum))
    db.session.commit()
    return {"ok": True}


@api.post("/lectures/<key>/generate")
def generate(key):
    owned(Lecture, key)
    data = body()
    kind = data.get("kind")
    if kind not in ("summary", "quiz", "concepts", "terms"):
        abort(400, "지원하지 않는 생성 작업입니다.")
    existing = Job.query.filter(
        Job.user_id == g.user.id,
        Job.lecture_id == key,
        Job.kind == kind,
        Job.status.in_(["queued", "running"]),
    ).first()
    if existing:
        return public(existing, ("payload",)), 202
    options = {
        "purpose": text(data, "purpose", 80) or "처음 배우기",
        "language": data.get("language", "ko"),
        "summary_sentences": data.get("summary_sentences", 5),
        "key_points": data.get("key_points", 10),
        "question_count": data.get("question_count", 5),
    }
    if options["language"] not in ("ko", "en"):
        abort(400, "지원 언어는 한국어와 영어입니다.")
    if options["summary_sentences"] not in (3, 5, 7):
        abort(400, "요약 길이는 3, 5, 7문장 중 선택하세요.")
    if any(
        type(options[k]) is not int or not 1 <= options[k] <= 20
        for k in ("key_points", "question_count")
    ):
        abort(400, "핵심 포인트와 문제 수는 1~20개입니다.")
    row = Job(
        user_id=g.user.id, lecture_id=key, kind=kind, payload={"options": options}
    )
    db.session.add(row)
    db.session.commit()
    return public(row, ("payload",)), 202


@api.post("/jobs/<key>/retry")
def retry_job(key):
    row = owned(Job, key)
    if row.status not in ("failed", "blocked"):
        abort(409, "실패하거나 설정을 기다리는 작업만 재시도할 수 있습니다.")
    row.status, row.error = "queued", ""
    db.session.commit()
    return public(row, ("payload",))


@api.get("/artifacts/<key>")
def artifact(key):
    row = owned(Artifact, key)
    return {
        "artifact": public(row),
        "sources": [public(c) for c in Citation.query.filter_by(artifact_id=key)],
    }


@api.get("/artifacts/<key>/export")
def export_artifact(key):
    row = owned(Artifact, key)
    citations = Citation.query.filter_by(artifact_id=key).all()
    content = (
        "# "
        + row.title
        + "\n\n"
        + ("> 원본 수정으로 재검토가 필요합니다.\n\n" if row.stale else "")
    )
    content += json.dumps(row.content, ensure_ascii=False, indent=2)
    content += "\n\n## 출처\n" + "\n".join(
        f"- 자료 구간 {c.segment_id}, 버전 {c.revision}" for c in citations
    )
    return send_file(
        io.BytesIO(content.encode("utf-8")),
        mimetype="text/markdown",
        as_attachment=True,
        download_name="studymate-note.md",
    )


@api.route("/lectures/<key>/chat", methods=["GET", "POST"])
@limiter.limit("20 per minute")
def chat(key):
    lecture = owned(Lecture, key)
    if request.method == "GET":
        return {
            "items": [
                public(c)
                for c in Chat.query.filter_by(
                    user_id=g.user.id, lecture_id=key
                ).order_by(Chat.created_at)
            ]
        }
    data = body()
    question = text(data, "question", 4000, True)
    mode = data.get("mode", "sources")
    if mode not in ("sources", "background", "hint"):
        abort(400, "답변 모드 오류")
    sources = retrieve(g.user.id, key, question)
    selected = data.get("segment_id")
    if selected:
        selected_row = owned(Segment, selected)
        if owned(Material, selected_row.material_id).lecture_id != key:
            abort(400, "다른 강의의 선택 영역입니다.")
        sources = [{**source_dict(selected_row), "text": selected_row.text[:12000]}] + [
            s for s in sources if s["id"] != selected
        ][:8]
    history = (
        Chat.query.filter_by(user_id=g.user.id, lecture_id=key)
        .order_by(Chat.created_at.desc())
        .limit(8)
        .all()
    )
    result = call_json(
        g.user.id,
        'Return {"answer":string,"source_ids":[string],"additional_explanation":string}. '
        "Answer in Korean. In sources mode, abstain when evidence is insufficient. "
        "In background mode, put outside knowledge ONLY in additional_explanation. "
        "In hint mode, provide a next-step hint without revealing the final answer. "
        "Cite only supplied source IDs. Note uncertain OCR/transcription. Do not claim unprovided evidence.",
        {
            "question": question,
            "mode": mode,
            "lecture": lecture.title,
            "sources": sources,
            "history": [{"role": c.role, "text": c.text} for c in reversed(history)],
        },
    )
    answer, ids = result.get("answer"), result.get("source_ids", [])
    if (
        not isinstance(answer, str)
        or not isinstance(ids, list)
        or not set(ids) <= {s["id"] for s in sources}
    ):
        raise ProviderError("답변 또는 출처 형식을 확인할 수 없습니다.")
    if mode == "sources" and not ids:
        answer = "선택한 강의자료에서 충분한 근거를 확인하지 못했습니다. 질문 범위를 좁히거나 자료를 추가해 주세요."
    if mode == "background" and result.get("additional_explanation"):
        answer += "\n\n[자료 밖의 추가 설명]\n" + str(result["additional_explanation"])
    db.session.add(
        Chat(user_id=g.user.id, lecture_id=key, role="user", text=question, mode=mode)
    )
    row = Chat(
        user_id=g.user.id,
        lecture_id=key,
        role="assistant",
        text=answer,
        mode=mode,
        sources=[
            {k: v for k, v in s.items() if k != "text"}
            for s in sources
            if s["id"] in ids
        ],
    )
    db.session.add(row)
    db.session.commit()
    return public(row)
