import httpx
import pytest
from studymate.extensions import db
from studymate.models import Artifact, Chat, Segment, Term
from studymate.services import jobs, learning, provider
from studymate.api import learning as chat_api


def source(app, client):
    lecture = client.setup_lecture()
    _, material = client.upload(lecture)
    with app.app_context():
        jobs.execute(jobs.claim())
    segment = client.send("GET", "/materials/" + material.json["id"]).json["segments"][
        0
    ]
    return lecture, segment


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {"status": "completed", "output": [None]},
        {"status": "completed", "output": [{"content": [None]}]},
    ],
)
def test_malformed_provider_envelope_is_controlled(app, client, monkeypatch, payload):
    app.config["OPENAI_API_KEY"] = "test-only"
    monkeypatch.setattr(
        provider.httpx,
        "post",
        lambda url, **kw: httpx.Response(
            200, request=httpx.Request("POST", url), json=payload
        ),
    )
    with app.app_context(), pytest.raises(provider.ProviderError):
        provider.call_json(client.user["id"], "Return JSON", {})


@pytest.mark.parametrize(
    "segments",
    [
        None,
        {},
        [None],
        [{"start": -1, "end": 2, "text": "x"}],
        [{"start": 2, "end": 1, "text": "x"}],
        [{"start": 0, "end": "NaN", "text": "x"}],
        [{"start": 0, "end": 1, "text": {}}],
    ],
)
def test_malformed_transcription_is_rejected(
    app, client, monkeypatch, tmp_path, segments
):
    app.config["OPENAI_API_KEY"] = "test-only"
    path = tmp_path / "clip.wav"
    path.write_bytes(b"test")
    monkeypatch.setattr(
        provider.httpx,
        "post",
        lambda url, **kw: httpx.Response(
            200, request=httpx.Request("POST", url), json={"segments": segments}
        ),
    )
    with app.app_context(), pytest.raises(provider.ProviderError):
        provider.transcribe(client.user["id"], path, "", "ko")


@pytest.mark.parametrize("ids", [[{}], ["invented"], None])
def test_chat_rejects_malformed_or_invented_citations(app, client, monkeypatch, ids):
    lecture, segment = source(app, client)
    monkeypatch.setattr(
        chat_api, "call_json", lambda *a, **k: {"answer": "answer", "source_ids": ids}
    )
    response = client.send(
        "POST", "/lectures/" + lecture["id"] + "/chat", {"question": "memory"}
    )
    assert response.status_code == 503
    with app.app_context():
        assert Chat.query.count() == 0


def test_chat_abstains_without_sources_without_calling_model(app, client, monkeypatch):
    lecture = client.setup_lecture()

    def unexpected(*a, **kw):
        pytest.fail("No-evidence question must not call provider")

    monkeypatch.setattr(chat_api, "call_json", unexpected)
    response = client.send(
        "POST", "/lectures/" + lecture["id"] + "/chat", {"question": "memory"}
    )
    assert response.status_code == 200
    assert "근거" in response.json["text"]
    assert response.json["sources"] == []


def test_chat_rejects_source_changed_during_generation(app, client, monkeypatch):
    lecture, segment = source(app, client)

    def changed(*a, **kw):
        Segment.query.filter_by(id=segment["id"]).update(
            {"revision": 2, "text": "Changed"}
        )
        db.session.commit()
        return {"answer": "Old answer", "source_ids": [segment["id"]]}

    monkeypatch.setattr(chat_api, "call_json", changed)
    response = client.send(
        "POST", "/lectures/" + lecture["id"] + "/chat", {"question": "memory"}
    )
    assert response.status_code == 409
    with app.app_context():
        assert Chat.query.count() == 0


@pytest.mark.parametrize(
    "kind,value",
    [
        ("summary", {"sections": [None]}),
        ("summary", {"sections": [{"text": "x", "source_ids": [{}]}]}),
        (
            "quiz",
            {"questions": [{"question": "Q", "answer": "A", "source_ids": ["SOURCE"]}]},
        ),
        (
            "concepts",
            {
                "nodes": [{"id": [], "label": "x"}],
                "edges": [
                    {"from": "a", "to": "a", "label": "x", "source_ids": ["SOURCE"]}
                ],
            },
        ),
        ("terms", {"terms": [{"word": "invented-term", "source_ids": ["SOURCE"]}]}),
        (
            "terms",
            {"terms": [{"word": "memory", "source_ids": ["SOURCE", "invented"]}]},
        ),
        ("terms", {"terms": [None]}),
    ],
)
def test_learning_rejects_invalid_results_atomically(
    app, client, monkeypatch, kind, value
):
    import json

    lecture, segment = source(app, client)
    value = json.loads(json.dumps(value).replace("SOURCE", segment["id"]))
    monkeypatch.setattr(learning, "call_json", lambda *a, **kw: value)
    with app.app_context():
        sources = list(learning.source_batches(client.user["id"], lecture["id"]))[0]
        with pytest.raises(provider.ProviderError):
            learning.generate_batch(client.user["id"], lecture["id"], kind, sources, {})
        assert Artifact.query.count() == 0
        assert Term.query.count() == 0


@pytest.mark.parametrize(
    "kind,value",
    [
        (
            "summary",
            {
                "sections": [
                    {
                        "heading": "Memory",
                        "text": "Working memory is limited.",
                        "source_ids": ["s"],
                    }
                ]
            },
        ),
        (
            "quiz",
            {
                "questions": [
                    {
                        "question": "Which has limited capacity?",
                        "answer": "Working memory",
                        "kind": "multiple_choice",
                        "options": ["Working memory", "A", "B", "C"],
                        "source_ids": ["s"],
                    }
                ]
            },
        ),
        (
            "concepts",
            {
                "nodes": [
                    {"id": "a", "label": "Memory"},
                    {"id": "b", "label": "Capacity"},
                ],
                "edges": [
                    {"from": "a", "to": "b", "label": "limited", "source_ids": ["s"]}
                ],
            },
        ),
        (
            "terms",
            {
                "terms": [
                    {
                        "word": "Working memory",
                        "meaning": "A memory system",
                        "source_ids": ["s"],
                    }
                ]
            },
        ),
    ],
)
def test_valid_learning_contracts(kind, value):
    from studymate.services.validation import learning_result

    assert learning_result(
        value, kind, [{"id": "s", "text": "Working memory has limited capacity."}]
    )


def test_chat_accepts_current_reference_and_separates_background(
    app, client, monkeypatch
):
    lecture, segment = source(app, client)
    monkeypatch.setattr(
        chat_api,
        "call_json",
        lambda *a, **kw: {
            "answer": "Working memory is limited.",
            "source_ids": [segment["id"]],
            "additional_explanation": "General information",
        },
    )
    response = client.send(
        "POST",
        "/lectures/" + lecture["id"] + "/chat",
        {"question": "memory", "mode": "background"},
    )
    assert response.status_code == 200
    assert "자료 밖의 추가 설명" in response.json["text"]
    assert response.json["sources"][0]["revision"] == 1


def test_ocr_rejects_revision_changed_during_call(app, client, monkeypatch):
    import io
    from pypdf import PdfWriter
    from studymate.api import sources as source_api

    lecture = client.setup_lecture()
    pdf = PdfWriter()
    pdf.add_blank_page(width=600, height=800)
    buffer = io.BytesIO()
    pdf.write(buffer)
    _, material = client.upload(lecture, buffer.getvalue(), "handwriting.pdf")
    with app.app_context():
        jobs.execute(jobs.claim())
    segment = client.send("GET", "/materials/" + material.json["id"]).json["segments"][
        0
    ]

    def changed(*a, **kw):
        Segment.query.filter_by(id=segment["id"]).update(
            {"revision": 2, "text": "User edit"}
        )
        db.session.commit()
        return {"visual_text": "Old reading"}

    monkeypatch.setattr(source_api, "call_json", changed)
    assert (
        client.send("POST", "/segments/" + segment["id"] + "/recognize").status_code
        == 409
    )
