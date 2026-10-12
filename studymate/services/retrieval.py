import re
from ..models import Segment, Material, public


def segments_for(user_id, lecture_id):
    return (
        Segment.query.join(Material, Segment.material_id == Material.id)
        .filter(
            Segment.user_id == user_id,
            Material.lecture_id == lecture_id,
            Segment.state != "unreadable",
        )
        .order_by(Material.created_at, Segment.ordinal)
        .all()
    )


def retrieve(user_id, lecture_id, query, limit=12):
    """Auditable lexical baseline; interchangeable with a semantic retriever."""
    words = re.findall(r"[\w]+", query.lower())
    records = segments_for(user_id, lecture_id)

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
