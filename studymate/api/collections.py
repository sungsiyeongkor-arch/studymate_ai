"""Bounded collection endpoints used by navigation and external clients."""

from .common import (
    api,
    abort,
    request,
    g,
    owned,
    public,
    Course,
    Lecture,
    Material,
    Artifact,
    Term,
    Job,
    Segment,
    Revision,
    HandwritingExample,
    Attempt,
    Usage,
    Chat,
    Card,
    Upload,
)
from ..services.pagination import page

COLLECTIONS = {
    "uploads": (Upload, "lecture_id", Lecture),
    "courses": (Course, None, None),
    "lectures": (Lecture, "course_id", Course),
    "materials": (Material, "lecture_id", Lecture),
    "artifacts": (Artifact, "lecture_id", Lecture),
    "terms": (Term, "course_id", Course),
    "jobs": (Job, "lecture_id", Lecture),
    "segments": (Segment, "material_id", Material),
    "revisions": (Revision, "segment_id", Segment),
    "examples": (HandwritingExample, None, None),
    "attempts": (Attempt, "card_id", Card),
    "usage": (Usage, None, None),
    "chats": (Chat, "lecture_id", Lecture),
    "cards": (Card, "lecture_id", Lecture),
}


@api.get("/collections/<name>")
def collection(name):
    if name not in COLLECTIONS:
        abort(404)
    model, field, parent = COLLECTIONS[name]
    query = model.query.filter_by(user_id=g.user.id)
    scope = {}
    if field and request.args.get(field):
        key = owned(parent, request.args[field]).id
        scope[field] = key
        query = query.filter(getattr(model, field) == key)

    def serialize(row):
        value = public(row, ("payload", "content"))
        if model is Segment and "text" in value:
            value["text"] = value["text"][:1000]
        return value

    return page(query, model, scope, serialize=serialize)
