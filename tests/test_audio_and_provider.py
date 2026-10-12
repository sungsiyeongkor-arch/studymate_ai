import io
import json
import wave
from pathlib import Path
from types import SimpleNamespace
import httpx
import pytest
from studymate.extensions import db
from studymate.models import Job, Segment, Material, Term, Usage
from studymate.services import jobs, provider
from studymate.services.context import whisper_context


def test_multi_hour_resume_with_context_and_no_duplicate_segments(
    app, client, monkeypatch, tmp_path
):
    lecture = client.setup_lecture()
    _, doc = client.upload(lecture, b"Baddeley working memory lecture source.")
    with app.app_context():
        jobs.execute(jobs.claim())
    client.send(
        "POST",
        "/terms",
        {
            "course_id": lecture["course_id"],
            "word": "Baddeley",
            "pronunciation": "bad-lee",
            "related": "working memory",
        },
    )
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        wav.writeframes(b"\0" * 100)
    _, audio = client.upload(lecture, buf.getvalue(), "two-hours.wav")
    monkeypatch.setattr(jobs, "credentials", lambda _: "test")
    monkeypatch.setattr(jobs.shutil, "which", lambda _: "available")
    monkeypatch.setattr(
        jobs.tempfile, "TemporaryDirectory", lambda **kwargs: TempDir(tmp_path)
    )
    monkeypatch.setattr(
        jobs,
        "run_process",
        lambda args, **kw: (
            json.dumps({"format": {"duration": 7201}}).encode()
            if args[0] == "ffprobe"
            else b""
        ),
    )
    calls = []

    def transcribe(user, path, prompt, language):
        calls.append(prompt)
        if len(calls) == 4:
            raise provider.ProviderError("temporary provider outage")
        return [{"start": 10, "end": 12, "text": "A recognized sentence"}]

    monkeypatch.setattr(jobs, "transcribe", transcribe)
    with app.app_context():
        job = jobs.claim()
        jid = job.id
        jobs.execute(job)
        assert job.status == "blocked"
        assert job.payload["completed_chunks"] == [0, 1, 2]
        assert "Baddeley" in calls[0]
        assert "source" in calls[0]
        assert len(calls[0].encode("utf-8")) <= 224
    client.send("POST", "/jobs/" + jid + "/retry")
    with app.app_context():
        job = jobs.claim()
        jobs.execute(job)
        assert job.status == "completed"
        assert job.progress == 25
        # Last 1-second chunk has no midpoint in range in this synthetic provider output.
        rows = Segment.query.filter_by(material_id=audio.json["id"]).all()
        assert len(rows) == 24
        assert len({r.ordinal for r in rows}) == 24
        assert (
            len(calls) == 26
        )  # 25 successful requests and one failed request; 3 completed skipped.


class TempDir:
    def __init__(self, path):
        self.path = path

    def __enter__(self):
        return str(self.path)

    def __exit__(self, *args):
        pass


def test_context_byte_budget_in_korean():
    prompt = whisper_context(
        "인지심리학" * 20,
        "단원 내용" * 100,
        [
            SimpleNamespace(
                word="작업기억", pronunciation="작업기억", related=["중앙집행기"]
            )
        ],
        [{"text": "장기기억의 개념과 특성 " * 100}],
    )
    assert len(prompt.encode("utf-8")) <= 224
    assert "작업기억" in prompt


def test_provider_schema_and_no_mock_fallback(app, client, monkeypatch):
    app.config["OPENAI_API_KEY"] = "unit-test-only"
    captured = []

    def post(url, **kw):
        captured.append(kw["json"])
        return httpx.Response(
            200,
            request=httpx.Request("POST", url),
            json={
                "status": "completed",
                "output": [
                    {"content": [{"type": "output_text", "text": '{"answer":"ok"}'}]}
                ],
                "usage": {"input_tokens": 10, "output_tokens": 5},
            },
        )

    monkeypatch.setattr(provider.httpx, "post", post)
    with app.app_context():
        result = provider.call_json(
            client.user["id"], "Return JSON", {"source": "text"}
        )
        assert result == {"answer": "ok"}
        assert Usage.query.count() == 1
        assert captured[0]["store"] is False
        assert captured[0]["text"]["format"]["type"] == "json_object"
    monkeypatch.setattr(
        provider.httpx,
        "post",
        lambda *a, **k: httpx.Response(
            401, request=httpx.Request("POST", a[0]), json={"secret": "not returned"}
        ),
    )
    with app.app_context():
        with pytest.raises(provider.ProviderError, match="401") as error:
            provider.call_json(client.user["id"], "x", {})
        assert "secret" not in str(error.value)
