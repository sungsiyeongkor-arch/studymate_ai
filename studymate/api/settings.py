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
    records = {
        model.__tablename__: listed(model)
        for model in (
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
    }
    records["account"] = public(g.user)
    return send_file(
        io.BytesIO(json.dumps(records, ensure_ascii=False, indent=2).encode("utf-8")),
        mimetype="application/json",
        as_attachment=True,
        download_name="studymate-learning-records.json",
    )
