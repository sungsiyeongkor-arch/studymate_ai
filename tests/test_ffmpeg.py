"""Real media processing with a synthetic 2-hour file; ASR responses remain mocked."""

import shutil
import subprocess
import tempfile
import wave
import pytest
from studymate.models import Segment
from studymate.services import jobs


def test_real_two_hour_media_pipeline(app, client, monkeypatch, tmp_path):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("FFmpeg/ffprobe required for actual media integration")
    source = tmp_path / "two-hours-silence.flac"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=16000:cl=mono",
            "-t",
            "7210",
            "-c:a",
            "flac",
            str(source),
        ],
        check=True,
        timeout=120,
    )
    lecture = client.setup_lecture()
    _, response = client.upload(lecture, source.read_bytes(), source.name)
    assert response.status_code == 201
    calls = []

    def fake_asr(user_id, path, prompt, language):
        with wave.open(str(path), "rb") as stream:
            duration = stream.getnframes() / stream.getframerate()
            assert stream.getframerate() == 16000
            assert stream.getnchannels() == 1
            assert 0 < duration <= 304.1
            assert path.stat().st_size < 25 * 1024**2
        calls.append(duration)
        return [
            {"start": 5, "end": 7, "text": "Synthetic test response; not actual ASR."}
        ]

    monkeypatch.setattr(jobs, "credentials", lambda _: "test")
    monkeypatch.setattr(jobs, "transcribe", fake_asr)
    real_temporary_directory = tempfile.TemporaryDirectory
    monkeypatch.setattr(
        jobs.tempfile,
        "TemporaryDirectory",
        lambda **kw: real_temporary_directory(dir=tmp_path, **kw),
    )
    with app.app_context():
        job = jobs.claim()
        jobs.execute(job)
        assert job.status == "completed", job.error
        assert job.progress == 25
        assert Segment.query.filter_by(material_id=response.json["id"]).count() == 25
    assert len(calls) == 25
