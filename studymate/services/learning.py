from flask import current_app
from ..extensions import db
from ..models import Artifact, Citation, Card, ReviewState, Term, Lecture, Segment
from .provider import call_json, ProviderError
from .retrieval import segments_for, source_dict
from .validation import learning_result


def source_batches(user_id, lecture_id):
    """Every readable source is processed; no silent whole-document truncation."""
    batch, size = [], 0
    for segment in segments_for(user_id, lecture_id):
        if segment.state in ("uncertain", "unreadable"):
            continue
        for start in range(0, len(segment.text), 6000):
            item = {
                **source_dict(segment),
                "text": segment.text[start : start + 6000],
                "offset": start,
            }
            if size + len(item["text"]) > 18000 and batch:
                yield batch
                batch, size = [], 0
            batch.append(item)
            size += len(item["text"])
    if batch:
        yield batch


def generate_batch(user_id, lecture_id, kind, sources, options):
    lecture = db.session.get(Lecture, lecture_id)
    allowed = {item["id"]: item["revision"] for item in sources}
    prompt = {
        "summary": 'Return {"title":string,"sections":[{"heading":string,"text":string,"source_ids":[string]}]}. The first section is the summary with options.summary_sentences sentences. Subsequent sections are options.key_points key points with conditions and examples. Cite supplied IDs. Preserve uncertainty.',
        "quiz": 'Return {"title":string,"questions":[{"question":string,"answer":string,"options":[string,string,string,string],"explanation":string,"concept":string,"kind":"multiple_choice","source_ids":[string]}]}. Generate options.question_count unambiguous multiple-choice recall/application questions grounded only in the sources. Exactly one option is correct. The answer must exactly equal that option. Vary the correct option position.',
        "concepts": 'Return {"title":string,"nodes":[{"id":string,"label":string}],"edges":[{"from":string,"to":string,"label":string,"condition":string,"source_ids":[string]}]}. Build at most 10 nodes. Label each relation, distinguish causation from association, include conditions.',
        "terms": 'Return {"terms":[{"word":string,"pronunciation":string,"meaning":string,"related":[string],"source_ids":[string]}]}. Extract up to 25 specialist terms actually present. Do not invent synonyms; related words are not replacements.',
    }[kind]
    prompt += " Output in English if options.language is en; otherwise Korean. If source is too short, generate fewer meaningful items instead of inventing or repeating facts."
    value = call_json(
        user_id,
        prompt,
        {
            "lecture": lecture.title,
            "topic": lecture.topic,
            "options": options,
            "sources": sources,
        },
    )
    entries = learning_result(value, kind, sources)
    current_sources = {
        s.id: s
        for s in Segment.query.filter(
            Segment.user_id == user_id, Segment.id.in_(allowed)
        )
        .populate_existing()
        .with_for_update()
        .all()
    }
    stale = any(
        key not in current_sources or current_sources[key].revision != version
        for key, version in allowed.items()
    )
    if set(current_sources) != set(allowed):
        raise ProviderError("분석 중 원문이 삭제되었습니다. 새 분석을 요청해 주세요.")
    if kind == "terms":
        if stale:
            raise ProviderError(
                "용어 추출 중 원문이 수정되었습니다. 새 분석을 요청해 주세요."
            )
        for term in entries:
            word = str(term.get("word", "")).strip()[:120]
            if not Term.query.filter_by(course_id=lecture.course_id, word=word).first():
                db.session.add(
                    Term(
                        user_id=user_id,
                        course_id=lecture.course_id,
                        word=word,
                        pronunciation=str(term.get("pronunciation", ""))[:200],
                        meaning=str(term.get("meaning", ""))[:2000],
                        related=term.get("related", [])[:10],
                        confirmed=False,
                    )
                )
        return None
    artifact = Artifact(
        user_id=user_id,
        lecture_id=lecture_id,
        kind=kind,
        title=str(value.get("title", lecture.title))[:200],
        content=value,
        model=current_app.config["OPENAI_MODEL"],
    )
    artifact.stale = stale
    db.session.add(artifact)
    db.session.flush()
    for source_id in {s for item in entries for s in item["source_ids"]}:
        db.session.add(
            Citation(
                user_id=user_id,
                artifact_id=artifact.id,
                segment_id=source_id,
                revision=allowed[source_id],
            )
        )
    if kind == "quiz":
        for item in entries[:20]:
            card = Card(
                user_id=user_id,
                lecture_id=lecture_id,
                artifact_id=artifact.id,
                question=item["question"],
                answer=item["answer"],
                explanation=str(item.get("explanation", "")),
                concept=str(item.get("concept", ""))[:160],
                kind=str(item.get("kind", "recall"))[:30],
                options=item.get("options", []),
            )
            db.session.add(card)
            db.session.flush()
            db.session.add(ReviewState(user_id=user_id, card_id=card.id))
    # Caller commits artifacts/cards and the batch checkpoint in ONE transaction.
    db.session.flush()
    return artifact.id
