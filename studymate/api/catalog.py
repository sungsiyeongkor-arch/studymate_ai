from ..services.pagination import page
from sqlalchemy import func, select
from .common import (
    Artifact,
    Attempt,
    Card,
    Course,
    Job,
    Lecture,
    Material,
    ReviewState,
    Segment,
    Term,
    abort,
    api,
    body,
    db,
    g,
    listed,
    now,
    owned,
    public,
    re,
    request,
    text,
)


@api.get("/dashboard")
def dashboard():
    due = (
        ReviewState.query.join(Card, Card.id == ReviewState.card_id)
        .outerjoin(Artifact, Card.artifact_id == Artifact.id)
        .filter(
            ReviewState.user_id == g.user.id,
            ReviewState.due <= now(),
            Card.suspended.is_(False),
            (Card.artifact_id.is_(None)) | Artifact.stale.is_(False),
        )
        .count()
    )
    return {
        "courses": listed(Course),
        "lectures": listed(Lecture),
        "collections_url": "/api/collections/courses",
        "lecture_counts": dict(
            db.session.execute(
                select(Lecture.course_id, func.count())
                .where(
                    Lecture.user_id == g.user.id,
                    Lecture.course_id.in_(
                        select(Course.id)
                        .where(Course.user_id == g.user.id)
                        .order_by(Course.created_at.desc(), Course.id.desc())
                        .limit(50)
                    ),
                )
                .group_by(Lecture.course_id)
            ).all()
        ),
        "counts": {
            "courses": Course.query.filter_by(user_id=g.user.id).count(),
            "materials": Material.query.filter_by(user_id=g.user.id).count(),
            "due": due,
            "attempts": Attempt.query.filter_by(
                user_id=g.user.id, invalidated=False
            ).count(),
            "review": Segment.query.filter(
                Segment.user_id == g.user.id,
                Segment.state.in_(["unreadable", "uncertain"]),
            ).count(),
        },
        "jobs": [
            public(j, ("payload",))
            for j in Job.query.filter_by(user_id=g.user.id)
            .order_by(Job.created_at.desc())
            .limit(12)
        ],
    }


@api.route("/courses", methods=["GET", "POST"])
def courses():
    if request.method == "GET":
        return page(Course.query.filter_by(user_id=g.user.id), Course, {})
    data = body()
    color = text(data, "color", 20) or "#386b54"
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
        abort(400, "색상 형식 오류")
    row = Course(
        user_id=g.user.id,
        title=text(data, "title", 160, True),
        description=text(data, "description", 3000),
        color=color,
    )
    db.session.add(row)
    db.session.commit()
    return public(row), 201


@api.post("/lectures")
def add_lecture():
    data = body()
    course = owned(Course, data.get("course_id"))
    language = data.get("language", "ko")
    if language not in ("ko", "en"):
        abort(400, "지원 언어는 한국어와 영어입니다.")
    row = Lecture(
        user_id=g.user.id,
        course_id=course.id,
        title=text(data, "title", 200, True),
        topic=text(data, "topic", 4000),
        language=language,
    )
    db.session.add(row)
    db.session.commit()
    return public(row), 201


@api.route("/lectures/<key>", methods=["GET", "PATCH"])
def lecture(key):
    row = owned(Lecture, key)
    if request.method == "PATCH":
        data = body()
        row.title, row.topic = text(data, "title", 200, True), text(data, "topic", 4000)
        db.session.commit()
    return {
        "lecture": public(row),
        "materials": listed(Material, lecture_id=key),
        "artifacts": listed(Artifact, lecture_id=key),
        "jobs": [
            public(j, ("payload",))
            for j in Job.query.filter_by(user_id=g.user.id, lecture_id=key)
            .order_by(Job.created_at.desc())
            .limit(50)
        ],
        "terms": listed(Term, course_id=row.course_id),
    }


@api.get("/search")
def search():
    query = request.args.get("q", "").strip()[:150]
    if len(query) < 2:
        return {"items": []}
    rows = Segment.query.filter(
        Segment.user_id == g.user.id, Segment.text.contains(query, autoescape=True)
    )
    return page(
        rows,
        Segment,
        {"q": query},
        serialize=lambda s: {**public(s), "text": s.text[:1000]},
    )
