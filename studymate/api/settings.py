from flask import Response, stream_with_context, current_app
from ..models import User, now
from .common import (
    Artifact,
    Attempt,
    Card,
    Chat,
    Citation,
    Course,
    HandwritingExample,
    Lecture,
    Material,
    ReviewState,
    Revision,
    Segment,
    Term,
    Usage,
    api,
    body,
    db,
    g,
    io,
    json,
    listed,
    owned,
    public,
    request,
    send_file,
)


@api.route("/settings", methods=["GET", "PATCH"])
def settings():
    if request.method == "PATCH":
        data = body()
        if "personalization" in data:
            g.user.personalization = bool(data["personalization"])
        db.session.commit()
    return {
        "user": public(g.user),
        "storage": {
            "used": g.user.storage_used,
            "reserved": g.user.storage_reserved,
            "limit": current_app.config["STORAGE_LIMIT_BYTES"],
        },
        "examples": listed(HandwritingExample),
        "usage": [
            public(u)
            for u in Usage.query.filter_by(user_id=g.user.id)
            .order_by(Usage.created_at.desc())
            .limit(30)
        ],
    }


@api.delete("/handwriting-examples/<key>")
def delete_example(key):
    db.session.delete(owned(HandwritingExample, key))
    db.session.commit()
    return {"ok": True}


@api.get("/account/export")
def account_export():
    user_id = g.user.id
    account = public(g.user)
    started = now()
    models = (
        Course,
        Lecture,
        Material,
        Segment,
        Revision,
        Term,
        Artifact,
        Citation,
        Card,
        ReviewState,
        Attempt,
        Chat,
        HandwritingExample,
        Usage,
    )

    def generate():
        yield '{"export_meta":' + json.dumps(
            {
                "started_at": started.isoformat() + "Z",
                "consistency": "per-table read; concurrent edits can be included; not a database backup",
            }
        )
        yield ',"account":' + json.dumps(account, ensure_ascii=False)
        for model in models:
            yield "," + json.dumps(model.__tablename__) + ":["
            first = True
            query = model.query.filter(
                model.user_id == user_id, model.created_at <= started
            ).order_by(model.created_at, model.id)
            for row in query.yield_per(100):
                if not first:
                    yield ","
                first = False
                yield json.dumps(public(row), ensure_ascii=False)
            yield "]"
        yield "}"

    return Response(
        stream_with_context(generate()),
        mimetype="application/json",
        headers={
            "Content-Disposition": 'attachment; filename="studymate-learning-records.json"',
            "X-Accel-Buffering": "no",
        },
    )
