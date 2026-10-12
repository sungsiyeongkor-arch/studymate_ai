from .common import (
    Artifact,
    Citation,
    HandwritingExample,
    Job,
    Lecture,
    Material,
    ProviderError,
    Revision,
    Segment,
    Upload,
    UploadChunk,
    abort,
    api,
    body,
    call_json,
    db,
    g,
    io,
    limiter,
    listed,
    owned,
    public,
    render_pdf,
    request,
    retrieve,
    send_file,
    storage,
    text,
)


@api.get("/materials/<key>")
def material(key):
    row = owned(Material, key)
    return {
        "material": public(row),
        "segments": [
            public(s)
            for s in Segment.query.filter_by(material_id=key).order_by(Segment.ordinal)
        ],
    }


@api.get("/materials/<key>/export")
def export_material(key):
    row = owned(Material, key)
    segments = Segment.query.filter_by(material_id=key).order_by(Segment.ordinal).all()
    blocks = [row.name, "StudyMate · 현재 수정본 (원본 파일과 별도)\n"]
    for s in segments:
        position = (
            f"p. {s.page}"
            if s.page
            else (f"{s.start:.1f}–{s.end:.1f}초" if s.start is not None else "본문")
        )
        blocks.append(f"[{position} · 버전 {s.revision} · {s.state}]\n{s.text}\n")
    return send_file(
        io.BytesIO("\n".join(blocks).encode("utf-8")),
        mimetype="text/plain",
        as_attachment=True,
        download_name="studymate-transcript.txt",
    )


@api.get("/materials/<key>/file")
def material_file(key):
    row = owned(Material, key)
    return send_file(
        storage.path(row.storage_key),
        download_name=row.name,
        as_attachment=row.kind not in ("pdf", "audio"),
        conditional=True,
    )


@api.get("/materials/<key>/pages/<int:page>")
def page_image(key, page):
    row = owned(Material, key)
    if row.kind != "pdf":
        abort(400, "PDF만 페이지 보기를 지원합니다.")
    try:
        raw = render_pdf(row, page)
    except ValueError as error:
        abort(400, str(error))
    return send_file(io.BytesIO(raw), mimetype="image/png")


@api.post("/materials/<key>/crop")
@limiter.limit("10 per minute")
def crop(key):
    row = owned(Material, key)
    data = body()
    page, bbox = data.get("page", 1), data.get("bbox")
    if (
        row.kind != "pdf"
        or not isinstance(page, int)
        or not isinstance(bbox, list)
        or len(bbox) != 4
    ):
        abort(400, "PDF 페이지와 영역을 선택해 주세요.")
    try:
        raw = render_pdf(row, page, bbox, scale=5)
    except (ValueError, TypeError) as error:
        abort(400, str(error))
    # Allocate separately from extraction ordinals; user operations do not overwrite pages.
    ordinal = 10000000 + Segment.query.filter_by(material_id=key).count()
    segment = Segment(
        user_id=g.user.id,
        material_id=key,
        ordinal=ordinal,
        page=page,
        bbox=bbox,
        text="",
        state="uncertain",
    )
    db.session.add(segment)
    db.session.flush()
    db.session.add(
        Revision(
            user_id=g.user.id, segment_id=segment.id, number=1, text="", author="user"
        )
    )
    db.session.commit()
    return public(segment), 201


@api.get("/segments/<key>/image")
def segment_image(key):
    segment = owned(Segment, key)
    row = owned(Material, segment.material_id)
    if row.kind != "pdf" or not segment.page:
        abort(400, "PDF 영역만 지원합니다.")
    return send_file(
        io.BytesIO(render_pdf(row, segment.page, segment.bbox, scale=5)),
        mimetype="image/png",
    )


@api.post("/segments/<key>/recognize")
@limiter.limit("10 per minute")
def recognize(key):
    segment = owned(Segment, key)
    material = owned(Material, segment.material_id)
    if material.kind != "pdf" or not segment.page:
        abort(400, "PDF 영역을 선택해 주세요.")
    lecture = owned(Lecture, material.lecture_id)
    examples = []
    images = [render_pdf(material, segment.page, segment.bbox, scale=5)]
    if g.user.personalization:
        for sample in (
            HandwritingExample.query.filter_by(user_id=g.user.id)
            .order_by(HandwritingExample.created_at.desc())
            .limit(3)
        ):
            source = owned(Segment, sample.segment_id)
            if source.revision != sample.revision or source.id == segment.id:
                continue
            original = owned(Material, source.material_id)
            if original.kind == "pdf":
                images.append(render_pdf(original, source.page, source.bbox, scale=4))
                examples.append(sample.text)
    context = retrieve(g.user.id, lecture.id, lecture.topic, limit=4)
    result = call_json(
        g.user.id,
        "The FIRST image is the target. Remaining images are user-confirmed handwriting examples in order. "
        "Transcribe only the target faithfully. Do not repair factual errors. Separate visual reading from context-based proposals. "
        'Return {"visual_text":string,"contextual_suggestion":string,"uncertain_spans":[string],"explanation":string}. Use □ for unreadable characters.',
        {"topic": lecture.topic, "context": context, "confirmed_examples": examples},
        images,
    )
    if not isinstance(result.get("visual_text"), str):
        raise ProviderError("판독 결과 형식 오류")
    return {"proposal": result, "segment_revision": segment.revision}


@api.route("/segments/<key>", methods=["GET", "PATCH"])
def segment(key):
    row = owned(Segment, key)
    if request.method == "PATCH":
        data = body()
        value = text(data, "text", 100000)
        reason = data.get("reason", "transcription")
        if reason not in ("transcription", "content_edit"):
            abort(400, "수정 유형 오류")
        expected = data.get("revision")
        if expected != row.revision:
            abort(409, "다른 창에서 수정되었습니다. 새로고침 후 확인해 주세요.")
        changed = Segment.query.filter_by(id=key, revision=expected).update(
            {
                "text": value,
                "revision": expected + 1,
                "state": "confirmed" if reason == "transcription" else "edited",
            }
        )
        if not changed:
            abort(409, "수정 충돌이 발생했습니다.")
        db.session.add(
            Revision(
                user_id=g.user.id,
                segment_id=key,
                number=expected + 1,
                text=value,
                author="user",
                reason=reason,
            )
        )
        ids = [c.artifact_id for c in Citation.query.filter_by(segment_id=key).all()]
        if ids:
            Artifact.query.filter(Artifact.id.in_(ids)).update(
                {"stale": True}, synchronize_session=False
            )
        HandwritingExample.query.filter_by(segment_id=key).delete()
        if data.get("save_example"):
            if (
                not g.user.personalization
                or not row.bbox
                or reason != "transcription"
                or not data.get("own_handwriting")
                or not value
            ):
                db.session.rollback()
                abort(
                    400,
                    "개인화를 켜고, 본인의 필기 영역을 원문 그대로 확인한 경우에만 예시로 저장할 수 있습니다.",
                )
            db.session.add(
                HandwritingExample(
                    user_id=g.user.id, segment_id=key, revision=expected + 1, text=value
                )
            )
        db.session.commit()
        db.session.refresh(row)
    return {"segment": public(row), "revisions": listed(Revision, segment_id=key)}


@api.get("/review-inbox")
def review_inbox():
    rows = Segment.query.filter(
        Segment.user_id == g.user.id, Segment.state.in_(["uncertain", "unreadable"])
    ).all()
    return {"items": [public(row) for row in rows]}


@api.delete("/materials/<key>")
def delete_material(key):
    material = owned(Material, key)
    if Job.query.filter(
        Job.material_id == key, Job.status.in_(["queued", "running"])
    ).first():
        abort(409, "처리 중인 자료는 작업이 끝난 뒤 삭제해 주세요.")
    # Avoid deleting evidence while a generation job is using a snapshot of this lecture.
    if Job.query.filter(
        Job.lecture_id == material.lecture_id, Job.status.in_(["queued", "running"])
    ).first():
        abort(409, "이 강의의 AI 작업이 끝난 뒤 삭제해 주세요.")
    segments = Segment.query.filter_by(material_id=key).all()
    ids = [s.id for s in segments]
    if ids:
        affected = [
            c.artifact_id for c in Citation.query.filter(Citation.segment_id.in_(ids))
        ]
        if affected:
            Artifact.query.filter(Artifact.id.in_(affected)).update(
                {"stale": True}, synchronize_session=False
            )
        Citation.query.filter(Citation.segment_id.in_(ids)).delete(
            synchronize_session=False
        )
        Revision.query.filter(Revision.segment_id.in_(ids)).delete(
            synchronize_session=False
        )
        HandwritingExample.query.filter(HandwritingExample.segment_id.in_(ids)).delete(
            synchronize_session=False
        )
        Segment.query.filter(Segment.id.in_(ids)).delete(synchronize_session=False)
    uploads = Upload.query.filter_by(material_id=key).all()
    for upload in uploads:
        UploadChunk.query.filter_by(upload_id=upload.id).delete()
        db.session.delete(upload)
    Job.query.filter_by(material_id=key).delete()
    # Remove generation checkpoints containing source text for this lecture.
    for job in Job.query.filter_by(lecture_id=material.lecture_id):
        job.payload = {}
    db.session.delete(material)
    db.session.commit()
    storage.path(material.storage_key).unlink(missing_ok=True)
    return {
        "ok": True,
        "notice": "원본·전사·개인 필체 예시를 삭제했습니다. 기존 노트·대화는 별도 기록으로 남습니다.",
    }
