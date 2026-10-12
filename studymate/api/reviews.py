from .common import (
    Artifact,
    Attempt,
    Card,
    Lecture,
    ReviewState,
    abort,
    api,
    body,
    db,
    g,
    now,
    owned,
    public,
    request,
    schedule,
    text,
)


@api.route("/cards", methods=["GET", "POST"])
def cards():
    if request.method == "GET":
        rows = (
            Card.query.filter_by(user_id=g.user.id)
            .order_by(Card.created_at.desc())
            .all()
        )
        return {
            "items": [
                {
                    **public(c),
                    "review": public(ReviewState.query.filter_by(card_id=c.id).one()),
                }
                for c in rows
            ]
        }
    data = body()
    lecture = owned(Lecture, data.get("lecture_id"))
    row = Card(
        user_id=g.user.id,
        lecture_id=lecture.id,
        question=text(data, "question", 4000, True),
        answer=text(data, "answer", 8000, True),
        explanation=text(data, "explanation", 8000),
        concept=text(data, "concept", 160),
    )
    db.session.add(row)
    db.session.flush()
    db.session.add(ReviewState(user_id=g.user.id, card_id=row.id))
    db.session.commit()
    return public(row), 201


@api.get("/reviews/due")
def due_reviews():
    rows = (
        ReviewState.query.join(Card, Card.id == ReviewState.card_id)
        .outerjoin(Artifact, Card.artifact_id == Artifact.id)
        .filter(
            ReviewState.user_id == g.user.id,
            ReviewState.due <= now(),
            Card.suspended.is_(False),
            (Card.artifact_id.is_(None)) | (Artifact.stale.is_(False)),
        )
        .order_by(ReviewState.due)
        .limit(30)
        .all()
    )
    return {
        "items": [
            {"card": public(db.session.get(Card, r.card_id)), "state": public(r)}
            for r in rows
        ]
    }


@api.post("/cards/<key>/review")
def review(key):
    card = owned(Card, key)
    data = body()
    if card.suspended or (card.artifact_id and owned(Artifact, card.artifact_id).stale):
        abort(409, "오류 신고 또는 원본 변경으로 보류된 문제입니다.")
    request_key = text(data, "request_key", 64, True)
    old = Attempt.query.filter_by(user_id=g.user.id, request_key=request_key).first()
    if old:
        if old.card_id != key:
            abort(409, "다른 문제에 사용된 요청 ID입니다.")
        return public(old)
    grade = data.get("grade")
    confidence = data.get("confidence", 1)
    if (
        type(grade) is not int
        or grade not in range(4)
        or type(confidence) is not int
        or confidence not in range(3)
    ):
        abort(400, "평가 값을 확인해 주세요.")
    state = ReviewState.query.filter_by(card_id=key).one()
    if data.get("state_version") != state.version:
        abort(409, "복습 상태가 변경되었습니다. 목록을 새로고침해 주세요.")
    previous = public(state)
    changes = schedule(state, grade, bool(data.get("hint_used")), now())
    count = ReviewState.query.filter_by(id=state.id, version=state.version).update(
        changes
    )
    if not count:
        db.session.rollback()
        abort(409, "다른 창에서 복습이 저장되었습니다.")
    row = Attempt(
        user_id=g.user.id,
        card_id=key,
        request_key=request_key,
        answer=text(data, "answer", 8000),
        grade=grade,
        hint_used=bool(data.get("hint_used")),
        confidence=confidence,
        snapshot={"question": card.question, "answer": card.answer, "kind": card.kind},
        previous_state=previous,
        next_due=changes["due"],
    )
    db.session.add(row)
    db.session.commit()
    return public(row), 201


@api.post("/cards/<key>/report")
def report_card(key):
    card = owned(Card, key)
    card.suspended = True
    Attempt.query.filter_by(card_id=key).update({"invalidated": True})
    state = ReviewState.query.filter_by(card_id=key).one()
    state.interval, state.successes, state.lapses, state.ease = 0, 0, 0, 2.3
    state.version += 1
    db.session.commit()
    return {"ok": True}
