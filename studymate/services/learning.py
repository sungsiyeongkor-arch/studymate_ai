import json
from flask import current_app
from ..extensions import db
from ..models import Artifact, Citation, Card, ReviewState, Term, Lecture, Segment
from .provider import call_json, ProviderError
from .retrieval import segments_for, source_dict


def source_batches(user_id, lecture_id):
    """Every readable source is processed; no silent whole-document truncation."""
    batches, batch, size = [], [], 0
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
                batches.append(batch)
                batch, size = [], 0
            batch.append(item)
            size += len(item["text"])
    if batch:
        batches.append(batch)
    return batches


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
    if kind == "terms":
        terms = value.get("terms")
        if not isinstance(terms, list):
            raise ProviderError("용어 응답 형식이 올바르지 않습니다.")
        for term in terms[:25]:
            word = str(term.get("word", "")).strip()[:120]
            if not word or not set(term.get("source_ids", [])) & allowed.keys():
                continue
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
    field = {"summary": "sections", "quiz": "questions", "concepts": "edges"}[kind]
    entries = value.get(field)
    if not isinstance(entries, list) or not entries:
        raise ProviderError("AI 결과에 필요한 항목이 없습니다.")
    # Reject unsupported references rather than displaying invented citations.
    for item in entries:
        ids = item.get("source_ids", [])
        if not isinstance(ids, list) or not ids or not set(ids) <= allowed.keys():
            raise ProviderError(
                "AI 결과의 출처를 확인할 수 없습니다. 결과를 저장하지 않았습니다."
            )
        if kind == "summary" and not isinstance(item.get("text"), str):
            raise ProviderError("요약 형식 오류")
        if kind == "quiz" and not all(
            isinstance(item.get(k), str) and item[k].strip()
            for k in ("question", "answer")
        ):
            raise ProviderError("문제 형식 오류")
        if kind == "quiz" and item.get("options"):
            choices = item["options"]
            if (
                not isinstance(choices, list)
                or not 2 <= len(choices) <= 6
                or not all(isinstance(v, str) and v.strip() for v in choices)
                or len(set(choices)) != len(choices)
                or item["answer"] not in choices
            ):
                raise ProviderError("객관식 선택지와 정답을 확인할 수 없습니다.")
    if kind == "concepts":
        nodes = value.get("nodes", [])
        node_ids = {n.get("id") for n in nodes if isinstance(n, dict)}
        if not nodes or any(
            e.get("from") not in node_ids
            or e.get("to") not in node_ids
            or not e.get("label")
            for e in entries
        ):
            raise ProviderError("개념도 연결 형식 오류")
    artifact = Artifact(
        user_id=user_id,
        lecture_id=lecture_id,
        kind=kind,
        title=str(value.get("title", lecture.title))[:200],
        content=value,
        model=current_app.config["OPENAI_MODEL"],
    )
    current_sources = {
        s.id: s
        for s in Segment.query.filter(Segment.id.in_(allowed))
        .populate_existing()
        .with_for_update()
        .all()
    }
    artifact.stale = any(
        key not in current_sources or current_sources[key].revision != version
        for key, version in allowed.items()
    )
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
