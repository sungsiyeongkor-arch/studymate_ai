"""Storage accounting shares the upload/material transaction, including reservations."""

from flask import abort, current_app
from ..extensions import db
from ..models import User


def lock_owner(user_id):
    # An UPDATE works as a write lock on SQLite and a row lock on PostgreSQL.
    User.query.filter_by(id=user_id).update(
        {User.storage_reserved: User.storage_reserved}, synchronize_session=False
    )


def reserve(user_id, size):
    limit = current_app.config["STORAGE_LIMIT_BYTES"]
    if not User.query.filter(
        User.id == user_id, User.storage_used + User.storage_reserved + size <= limit
    ).update(
        {User.storage_reserved: User.storage_reserved + size}, synchronize_session=False
    ):
        abort(
            409,
            "저장 공간이 부족합니다. 사용하지 않는 자료나 대기 중인 업로드를 정리하세요.",
        )


def complete(user_id, size):
    changed = User.query.filter(
        User.id == user_id, User.storage_reserved >= size
    ).update(
        {
            User.storage_reserved: User.storage_reserved - size,
            User.storage_used: User.storage_used + size,
        },
        synchronize_session=False,
    )
    if changed != 1:
        raise RuntimeError("Storage reservation accounting mismatch")


def release(user_id, size):
    User.query.filter(User.id == user_id, User.storage_reserved >= size).update(
        {User.storage_reserved: User.storage_reserved - size}, synchronize_session=False
    )
