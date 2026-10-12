"""Signed, tenant/filter-bound keyset cursors. No OFFSET or total COUNT per page."""

from datetime import datetime
from flask import abort, current_app, g, request
from itsdangerous import URLSafeTimedSerializer, BadData
from sqlalchemy import tuple_
from ..models import public


def page(
    query,
    model,
    scope,
    *,
    limit=None,
    cursor=None,
    serialize=public,
    sort_key="created_at",
    ascending=False
):
    try:
        size = int(request.args.get("limit", 50) if limit is None else limit)
    except (TypeError, ValueError):
        abort(400, "페이지 크기가 올바르지 않습니다.")
    if not 1 <= size <= 100:
        abort(400, "페이지 크기는 1~100이어야 합니다.")
    token = request.args.get("cursor") if cursor is None else cursor
    codec = URLSafeTimedSerializer(current_app.secret_key, salt="collection-v1")
    binding = [g.user.id, model.__tablename__, scope, sort_key, ascending]
    column = getattr(model, sort_key)
    if token:
        try:
            data = codec.loads(token, max_age=86400)
            if data["binding"] != binding:
                raise ValueError("scope")
            at = (
                datetime.fromisoformat(data["at"])
                if sort_key == "created_at"
                else int(data["at"])
            )
            key = data["id"]
        except (BadData, ValueError, KeyError, TypeError):
            abort(
                400,
                "목록 링크가 만료되었거나 잘못되었습니다. 처음부터 다시 조회하세요.",
            )
        boundary = tuple_(column, model.id)
        query = query.filter(
            boundary > (at, key) if ascending else boundary < (at, key)
        )
    order = (
        (column.asc(), model.id.asc())
        if ascending
        else (column.desc(), model.id.desc())
    )
    rows = query.order_by(None).order_by(*order).limit(size + 1).all()
    more = len(rows) > size
    rows = rows[:size]
    next_cursor = (
        codec.dumps(
            {
                "binding": binding,
                "at": (
                    rows[-1].created_at.isoformat()
                    if sort_key == "created_at"
                    else getattr(rows[-1], sort_key)
                ),
                "id": rows[-1].id,
            }
        )
        if more
        else None
    )
    return {
        "items": [serialize(row) for row in rows],
        "next_cursor": next_cursor,
        "has_more": more,
        "limit": size,
    }
