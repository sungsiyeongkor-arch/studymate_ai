from sqlalchemy import or_
import re
from ..models import Segment, Material, public


def segments_for(user_id, lecture_id):
    # Keyset batches allow the worker to commit checkpoints without an open server cursor.
    last = None
    while True:
        query = Segment.query.join(Material, Segment.material_id == Material.id).filter(
            Segment.user_id == user_id,
            Material.user_id == user_id,
            Material.lecture_id == lecture_id,
            Segment.state != "unreadable",
        )
        if last is not None:
            created, material_id, ordinal = last
            query = query.filter(
                or_(
                    Material.created_at > created,
                    (Material.created_at == created) & (Material.id > material_id),
                    (Material.created_at == created)
                    & (Material.id == material_id)
                    & (Segment.ordinal > ordinal),
                )
            )
        rows = (
            query.add_columns(Material.created_at)
            .order_by(Material.created_at, Material.id, Segment.ordinal)
            .limit(100)
            .all()
        )
        if not rows:
            return
        for segment, created in rows:
            last = (created, segment.material_id, segment.ordinal)
            yield segment


def retrieve(user_id, lecture_id, query, limit=12):
    """Auditable lexical baseline; interchangeable with a semantic retriever."""
    words = re.findall(r"[\w]+", query.lower())
    # Bound candidate memory; filtering stays in SQL and can use the optional trigram index.
    tokens = list(dict.fromkeys(w for w in words if len(w) > 1))[:12]
    base = Segment.query.join(Material, Segment.material_id == Material.id).filter(
        Segment.user_id == user_id,
        Material.user_id == user_id,
        Material.lecture_id == lecture_id,
        Segment.state != "unreadable",
    )
    matches = (
        base.filter(
            or_(
                *(
                    Segment.text.ilike("%" + w.replace("_", "\\_") + "%", escape="\\")
                    for w in tokens
                )
            )
        )
        if tokens
        else base
    )
    records = (
        matches.order_by(Segment.created_at.desc(), Segment.id.desc()).limit(300).all()
    )
    if not records:
        records = (
            base.order_by(Segment.created_at.desc(), Segment.id.desc())
            .limit(limit)
            .all()
        )

    def score(segment):
        body = segment.text.lower()
        return sum(body.count(word) for word in words if len(word) > 1)

    ranked = sorted(records, key=score, reverse=True)
    result, size = [], 0
    for segment in ranked[:limit]:
        content = segment.text[:7000]
        if size + len(content) > 35000:
            break
        result.append(
            {
                "id": segment.id,
                "revision": segment.revision,
                "text": content,
                "state": segment.state,
                "page": segment.page,
                "start": segment.start,
                "material_id": segment.material_id,
                "excerpt_only": len(content) != len(segment.text),
            }
        )
        size += len(content)
    return result


def source_dict(segment):
    return {
        "id": segment.id,
        "revision": segment.revision,
        "material_id": segment.material_id,
        "page": segment.page,
        "start": segment.start,
        "state": segment.state,
    }
