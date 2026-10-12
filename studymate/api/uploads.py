from datetime import timedelta
from ..models import now
from ..services import quota
from .common import (
    IntegrityError,
    Job,
    Lecture,
    Material,
    Path,
    Upload,
    UploadChunk,
    abort,
    api,
    body,
    current_app,
    db,
    g,
    hashlib,
    math,
    owned,
    public,
    request,
    shutil,
    storage,
    text,
    uid,
    validate,
)


@api.post("/uploads")
def start_upload():
    data = body()
    lecture = owned(Lecture, data.get("lecture_id"))
    size = data.get("size")
    if (
        not isinstance(size, int)
        or not 0 < size <= current_app.config["MAX_FILE_BYTES"]
    ):
        abort(400, "파일은 512MB 이하여야 합니다.")
    quota.reserve(g.user.id, size)
    row = Upload(
        expires_at=now() + timedelta(hours=current_app.config["UPLOAD_TTL_HOURS"]),
        user_id=g.user.id,
        lecture_id=lecture.id,
        name=text(data, "name", 255, True),
        size=size,
    )
    db.session.add(row)
    db.session.commit()
    return public(row), 201


@api.get("/uploads/<key>")
def upload_status(key):
    row = owned(Upload, key)
    return {
        **public(row),
        "received": [
            c.number for c in UploadChunk.query.filter_by(upload_id=key).all()
        ],
    }


@api.put("/uploads/<key>/chunks/<int:number>")
def upload_chunk(key, number):
    quota.lock_owner(g.user.id)
    row = owned(Upload, key)
    db.session.refresh(row)
    if row.expires_at and row.expires_at < now():
        abort(409, "업로드가 만료되었습니다. 취소 후 다시 시작하세요.")
    if row.status != "pending" or not 0 <= number < math.ceil(
        row.size / row.chunk_size
    ):
        abort(409, "업로드 상태를 확인해 주세요.")
    expected = min(row.chunk_size, row.size - number * row.chunk_size)
    if request.content_length != expected:
        abort(400, "파일 조각의 크기가 맞지 않습니다.")
    raw = request.get_data()
    sha = hashlib.sha256(raw).hexdigest()
    existing = UploadChunk.query.filter_by(upload_id=key, number=number).first()
    if existing:
        if existing.sha256 != sha:
            abort(409, "다른 파일입니다. 새 업로드를 시작해 주세요.")
        db.session.commit()
        return {"ok": True}
    storage_key = f"chunks/{uid()}.part"
    storage.path(storage_key).write_bytes(raw)
    db.session.add(
        UploadChunk(
            user_id=g.user.id,
            upload_id=key,
            number=number,
            sha256=sha,
            storage_key=storage_key,
            size=len(raw),
        )
    )
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        storage.path(storage_key).unlink(missing_ok=True)
        abort(409, "업로드가 중복되었습니다. 상태를 확인한 뒤 재시도해 주세요.")
    return {"ok": True}


@api.post("/uploads/<key>/complete")
def complete_upload(key):
    quota.lock_owner(g.user.id)
    row = owned(Upload, key)
    db.session.refresh(row)
    if row.status == "completed":
        return public(owned(Material, row.material_id))
    if row.status != "pending" or (row.expires_at and row.expires_at < now()):
        abort(409, "업로드 상태 또는 만료 시각을 확인하세요.")
    chunks = (
        UploadChunk.query.filter_by(upload_id=key).order_by(UploadChunk.number).all()
    )
    if (
        len(chunks) != math.ceil(row.size / row.chunk_size)
        or sum(c.size for c in chunks) != row.size
    ):
        abort(409, "업로드가 아직 완료되지 않았습니다.")
    if not Upload.query.filter_by(id=key, status="pending").update(
        {"status": "assembling"}
    ):
        abort(409, "파일을 확인하고 있습니다. 잠시 후 상태를 확인해 주세요.")
    db.session.commit()
    ext = Path(row.name).suffix.lower()
    file_key = f"originals/{uid()}{ext}"
    target = storage.path(file_key)
    try:
        with target.open("wb") as stream:
            for chunk in chunks:
                with storage.path(chunk.storage_key).open("rb") as source:
                    shutil.copyfileobj(source, stream)
        kind = validate(target, row.name)
        material = Material(
            user_id=g.user.id,
            lecture_id=row.lecture_id,
            name=row.name,
            kind=kind,
            storage_key=file_key,
            size=row.size,
            sha256=storage.digest(target),
        )
        db.session.add(material)
        db.session.flush()
        db.session.add(
            Job(
                user_id=g.user.id,
                material_id=material.id,
                lecture_id=row.lecture_id,
                kind="transcribe" if kind == "audio" else "extract",
            )
        )
        quota.complete(g.user.id, row.size)
        row.status, row.material_id = "completed", material.id
        db.session.commit()
    except Exception as error:
        db.session.rollback()
        row = db.session.get(Upload, key)
        row.status = "pending"
        db.session.commit()
        target.unlink(missing_ok=True)
        abort(
            400,
            (
                str(error)
                if isinstance(error, (ValueError, UnicodeError))
                else "파일 내용을 읽지 못했습니다. 형식과 손상 여부를 확인해 주세요."
            ),
        )
    for chunk in chunks:
        storage.path(chunk.storage_key).unlink(missing_ok=True)
    return public(material), 201


@api.delete("/uploads/<key>")
def cancel_upload(key):
    quota.lock_owner(g.user.id)
    row = owned(Upload, key)
    db.session.refresh(row)
    if row.status == "cancelled":
        db.session.commit()
        return {"ok": True}
    if row.status != "pending":
        abort(409, "대기 중인 업로드만 취소할 수 있습니다.")
    row.status = "cancelled"
    quota.release(g.user.id, row.size)
    keys = [c.storage_key for c in UploadChunk.query.filter_by(upload_id=key)]
    UploadChunk.query.filter_by(upload_id=key).delete()
    db.session.commit()
    for key in keys:
        storage.path(key).unlink(missing_ok=True)
    return {"ok": True}
