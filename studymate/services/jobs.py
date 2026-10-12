"""Durable DB queue. CAS leases prevent duplicate claim; checkpoints allow resume."""

import json
import math
import shutil
import subprocess
import tempfile
import time
from datetime import timedelta
from pathlib import Path
from flask import current_app
from sqlalchemy import or_
from ..extensions import db
from ..models import JobBatch, Job, Material, Segment, Revision, Lecture, Term, now, uid
from .storage import path
from .documents import extract
from .provider import transcribe, credentials, ProviderError
from .learning import source_batches, generate_batch
from .retrieval import retrieve
from .context import whisper_context


class LostLease(RuntimeError):
    pass


def fence(job):
    token = getattr(job, "_claimed_token", job.lease_token)
    changed = Job.query.filter_by(
        id=job.id, lease_token=token, status="running"
    ).update({"heartbeat": now()}, synchronize_session=False)
    if not changed:
        db.session.rollback()
        raise LostLease("Worker lease expired")


def claim():
    cutoff = now() - timedelta(minutes=15)
    candidates = Job.query.filter(
        or_(
            Job.status == "queued",
            (Job.status == "running") & (Job.heartbeat < cutoff),
        )
    ).order_by(Job.created_at, Job.id)
    if db.engine.dialect.name == "postgresql":
        candidates = candidates.with_for_update(skip_locked=True)
    candidate = candidates.first()
    if not candidate:
        db.session.rollback()
        return None
    token = uid()
    changed = Job.query.filter(
        Job.id == candidate.id,
        Job.status == candidate.status,
        Job.attempts == candidate.attempts,
    ).update(
        {
            Job.status: "running",
            Job.heartbeat: now(),
            Job.lease_token: token,
            Job.attempts: Job.attempts + 1,
        },
        synchronize_session=False,
    )
    db.session.commit()
    db.session.expire_all()
    job = db.session.get(Job, candidate.id) if changed else None
    if job:
        job._claimed_token = token
    return job


def checkpoint(job, progress, total):
    fence(job)
    job.progress, job.total, job.heartbeat = progress, total, now()
    db.session.commit()


def add_segment(material, ordinal, item):
    if Segment.query.filter_by(material_id=material.id, ordinal=ordinal).first():
        return
    text = item.pop("text")
    segment = Segment(
        user_id=material.user_id,
        material_id=material.id,
        ordinal=ordinal,
        text=text,
        state="automatic" if text.strip() else "unreadable",
        **item
    )
    db.session.add(segment)
    db.session.flush()
    db.session.add(
        Revision(
            user_id=material.user_id,
            segment_id=segment.id,
            number=1,
            text=text,
            author="extractor",
        )
    )


def process_document(job):
    material = db.session.get(Material, job.material_id)
    material.status = "processing"
    db.session.commit()
    count = 0
    for index, item in enumerate(extract(material)):
        add_segment(material, index, item)
        count = index + 1
        checkpoint(job, count, 0)
    material.page_count = count
    material.status = (
        "review"
        if Segment.query.filter_by(material_id=material.id, state="unreadable").first()
        else "ready"
    )
    checkpoint(job, count, count)


def run_process(args, timeout=120):
    result = subprocess.run(args, capture_output=True, timeout=timeout)
    if result.returncode:
        raise ValueError(
            "음성 파일을 해석하지 못했습니다. 지원 형식과 파일 손상을 확인해 주세요."
        )
    return result.stdout


def process_audio(job):
    credentials(job.user_id)
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise ProviderError("장시간 음성 처리에는 서버의 FFmpeg 설치가 필요합니다.")
    material = db.session.get(Material, job.material_id)
    lecture = db.session.get(Lecture, material.lecture_id)
    if Material.query.filter(
        Material.lecture_id == lecture.id,
        Material.kind != "audio",
        Material.status.in_(["queued", "processing"]),
    ).first():
        raise ProviderError(
            "사전 강의자료를 읽고 있습니다. 자료 처리가 끝나면 받아쓰기를 재시도해 주세요."
        )
    info = json.loads(
        run_process(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "json",
                str(path(material.storage_key)),
            ]
        )
    )
    duration = float(info["format"]["duration"])
    if not 0 < duration <= 12 * 3600:
        raise ValueError(
            "녹음은 12시간 이하 파일로 나누어 주세요. 실제 인식 품질은 녹음 환경에 따라 달라집니다."
        )
    material.duration, material.status = duration, "processing"
    terms = (
        Term.query.filter_by(
            user_id=job.user_id, course_id=lecture.course_id, confirmed=True
        )
        .limit(70)
        .all()
    )
    sources = retrieve(job.user_id, lecture.id, lecture.topic or lecture.title, limit=4)
    sources = [s for s in sources if s["material_id"] != material.id]
    # Prepare compact source context, not model training. Snapshot makes retries auditable.
    payload = dict(job.payload or {})
    prompt = payload.get("context_prompt")
    if prompt is None:
        prompt = whisper_context(lecture.title, lecture.topic or "", terms, sources)
        payload["context_prompt"] = prompt
        payload["context_sources"] = [
            {k: v for k, v in s.items() if k != "text"} for s in sources
        ]
        job.payload = dict(payload)
    # Each 5 minute mono PCM part is ~9.6MB, below provider limits.
    length = 300
    total = math.ceil(duration / length)
    completed = set(payload.get("completed_chunks", []))
    with tempfile.TemporaryDirectory(prefix="studymate-audio-") as temp:
        for index in range(total):
            if index in completed:
                continue
            core_start = index * length
            start = max(0, core_start - 2)
            end = min(duration, core_start + length + 2)
            audio_path = Path(temp) / "part.wav"
            checkpoint(job, len(completed), total)
            run_process(
                [
                    "ffmpeg",
                    "-v",
                    "error",
                    "-y",
                    "-ss",
                    str(start),
                    "-i",
                    str(path(material.storage_key)),
                    "-t",
                    str(end - start),
                    "-vn",
                    "-ac",
                    "1",
                    "-ar",
                    "16000",
                    str(audio_path),
                ],
                timeout=180,
            )
            items = transcribe(job.user_id, audio_path, prompt, lecture.language)
            fence(job)
            local = 0
            for item in items:
                a, b = float(item["start"]) + start, float(item["end"]) + start
                midpoint = (a + b) / 2
                if (
                    not core_start
                    <= midpoint
                    < min(duration + 0.01, core_start + length)
                ):
                    continue
                add_segment(
                    material,
                    index * 10000 + local,
                    {"text": str(item["text"]), "start": a, "end": b},
                )
                local += 1
            completed.add(index)
            payload["completed_chunks"] = sorted(completed)
            job.payload = dict(payload)
            checkpoint(job, len(completed), total)
    material.status = "ready"


def process_learning(job):
    credentials(job.user_id)
    payload = dict(job.payload or {})
    if not payload.get("snapshot_ready"):
        fence(job)
        JobBatch.query.filter_by(job_id=job.id).delete()
        db.session.commit()
        # Import old checkpoints once so deployment does not charge for completed batches again.
        legacy = payload.get("batches")
        completed = (
            set(payload.get("completed_batches", [])) if legacy is not None else set()
        )
        count = 0
        for index, sources in enumerate(
            legacy
            if legacy is not None
            else source_batches(job.user_id, job.lecture_id)
        ):
            fence(job)
            db.session.add(
                JobBatch(
                    user_id=job.user_id,
                    job_id=job.id,
                    ordinal=index,
                    sources=sources,
                    completed=index in completed,
                )
            )
            db.session.commit()
            count += 1
        if not count:
            raise ValueError(
                "읽을 수 있는 자료가 없습니다. 추출 또는 판독 확인을 먼저 완료해 주세요."
            )
        payload.pop("batches", None)
        payload["completed_batches"] = (
            []
        )  # old response compatibility; progress is stored in rows now
        payload["snapshot_ready"] = True
        job.payload = payload
        checkpoint(job, len(completed), count)
    while True:
        batch = (
            JobBatch.query.filter_by(job_id=job.id, completed=False)
            .order_by(JobBatch.ordinal)
            .first()
        )
        if batch is None:
            break
        checkpoint(job, job.progress, job.total)
        generate_batch(
            job.user_id,
            job.lecture_id,
            job.kind,
            batch.sources,
            payload.get("options", {}),
        )
        batch.completed = True
        checkpoint(job, job.progress + 1, job.total)


def execute(job):
    job_id = job.id
    try:
        if job.kind == "extract":
            process_document(job)
        elif job.kind == "transcribe":
            process_audio(job)
        else:
            process_learning(job)
        fence(job)
        job.status, job.error, job.heartbeat = "completed", "", now()
        db.session.commit()
    except Exception as error:
        db.session.rollback()
        if isinstance(error, LostLease):
            return
        job = db.session.get(Job, job_id)
        try:
            fence(job)
        except LostLease:
            return
        job.status = "blocked" if isinstance(error, ProviderError) else "failed"
        job.error = (
            str(error)[:500]
            if isinstance(error, (ProviderError, ValueError))
            else "처리 오류가 발생했습니다. 파일 상태를 확인하고 재시도해 주세요."
        )
        job.heartbeat = now()
        if job.material_id:
            db.session.get(Material, job.material_id).status = "review"
        db.session.commit()
        current_app.logger.warning("Job %s stopped: %s", job_id, type(error).__name__)


def work(once=False):
    while True:
        job = claim()
        if job:
            execute(job)
        db.session.remove()
        if once:
            break
        if not job:
            time.sleep(2)
