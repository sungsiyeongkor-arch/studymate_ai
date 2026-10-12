from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import json
import pytest
from sqlalchemy import select
from conftest import Client
from studymate.extensions import db
from studymate.models import Course, Segment, User, Upload, Job, JobBatch, Artifact, now
from studymate.services import jobs


def test_keyset_ties_tenant_binding_and_insert(app, client):
    stamp = now()
    with app.app_context():
        db.session.add_all(
            [
                Course(user_id=client.user["id"], title=str(i), created_at=stamp)
                for i in range(137)
            ]
        )
        db.session.commit()
    other = Client(app, "other-page@example.test")
    first = client.send("GET", "/courses?limit=17").json
    token = first["next_cursor"]
    assert other.send("GET", "/courses?limit=17&cursor=" + token).status_code == 400
    assert client.send("GET", "/courses?limit=1000").status_code == 400
    assert client.send("GET", "/courses?cursor=forged").status_code == 400
    client.send("POST", "/courses", {"title": "new after first page"})
    ids = [r["id"] for r in first["items"]]
    while token:
        result = client.send("GET", "/courses?limit=17&cursor=" + token).json
        ids.extend(r["id"] for r in result["items"])
        token = result["next_cursor"]
    assert len(ids) == len(set(ids)) == 137
    assert client.send("GET", "/dashboard").json["counts"]["courses"] == 138


def test_collection_parent_and_search_cursor_binding(app, client):
    lecture = client.setup_lecture()
    _, r = client.upload(lecture)
    with app.app_context():
        db.session.add_all(
            [
                Segment(
                    user_id=client.user["id"],
                    material_id=r.json["id"],
                    ordinal=i,
                    text="자료 alpha beta",
                )
                for i in range(104)
            ]
        )
        db.session.commit()
    first = client.send("GET", "/search?q=alpha&limit=10").json
    assert len(first["items"]) == 10 and first["next_cursor"]
    assert (
        client.send("GET", "/search?q=beta&cursor=" + first["next_cursor"]).status_code
        == 400
    )
    other = Client(app, "other-parent@example.test")
    assert (
        other.send(
            "GET", "/collections/materials?lecture_id=" + lecture["id"]
        ).status_code
        == 404
    )
    assert len(client.send("GET", "/materials/" + r.json["id"]).json["segments"]) == 50
    assert (
        len(
            client.send(
                "GET", "/collections/segments?material_id=" + r.json["id"]
            ).json["items"]
        )
        == 50
    )


def test_stream_export_does_not_truncate_at_page_limit(app, client):
    with app.app_context():
        db.session.add_all(
            [Course(user_id=client.user["id"], title=str(i)) for i in range(251)]
        )
        db.session.commit()
    response = client.send("GET", "/account/export")
    assert response.is_streamed
    body = b"".join(response.response)
    assert len(json.loads(body)["sm_courses"]) == 251
    assert b"password_hash" not in body
    assert response.headers["X-Accel-Buffering"] == "no"


def test_quota_cancel_expire_and_idempotency(app, client):
    lecture = client.setup_lecture()
    app.config["STORAGE_LIMIT_BYTES"] = 100
    first = client.send(
        "POST", "/uploads", {"lecture_id": lecture["id"], "name": "a.txt", "size": 70}
    )
    key = first.json["id"]
    assert (
        client.send(
            "POST",
            "/uploads",
            {"lecture_id": lecture["id"], "name": "b.txt", "size": 40},
        ).status_code
        == 409
    )
    assert client.send("DELETE", "/uploads/" + key).status_code == 200
    assert client.send("DELETE", "/uploads/" + key).status_code == 200
    expired = client.send(
        "POST", "/uploads", {"lecture_id": lecture["id"], "name": "c.txt", "size": 40}
    ).json
    with app.app_context():
        row = db.session.get(Upload, expired["id"])
        row.expires_at = now() - timedelta(seconds=1)
        db.session.commit()
    runner = app.test_cli_runner()
    assert runner.invoke(args=["expire-uploads"]).exit_code == 0
    assert client.send("GET", "/settings").json["storage"]["reserved"] == 40
    assert runner.invoke(args=["expire-uploads", "--apply"]).exit_code == 0
    assert client.send("GET", "/settings").json["storage"]["reserved"] == 0
    _, ready = client.upload(lecture, b"hello world")
    assert ready.status_code == 201
    storage = client.send("GET", "/settings").json["storage"]
    assert storage["used"] == 11 and storage["reserved"] == 0
    with app.app_context():
        jobs.execute(jobs.claim())
    assert client.send("DELETE", "/materials/" + ready.json["id"]).status_code == 200
    assert client.send("GET", "/settings").json["storage"]["used"] == 0


def test_concurrent_reservations_do_not_overbook(app, client):
    lecture = client.setup_lecture()
    app.config["STORAGE_LIMIT_BYTES"] = 100

    def submit(_):
        raw = app.test_client()
        with raw.session_transaction() as session:
            session["user_id"] = client.user["id"]
            session["csrf"] = "concurrent-test"
        return raw.post(
            "/api/uploads",
            headers={"X-CSRF-Token": "concurrent-test"},
            json={"lecture_id": lecture["id"], "name": "x.txt", "size": 60},
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(submit, range(2)))
    assert sorted(statuses) == [201, 409]
    assert client.send("GET", "/settings").json["storage"]["reserved"] == 60


def test_batches_resume_without_repeating_success(app, client, monkeypatch):
    lecture = client.setup_lecture()
    _, material = client.upload(lecture)
    with app.app_context():
        Job.query.delete()
        db.session.add_all(
            [
                Segment(
                    user_id=client.user["id"],
                    material_id=material.json["id"],
                    ordinal=i,
                    text="x" * 18000,
                    state="confirmed",
                )
                for i in range(3)
            ]
        )
        db.session.commit()
    monkeypatch.setattr(jobs, "credentials", lambda _: None)
    seen = []

    def generate(user, lecture_id, kind, sources, options):
        seen.append(sources[0]["id"])
        if len(seen) == 2:
            raise ValueError("transient failure")
        db.session.add(
            Artifact(
                user_id=user,
                lecture_id=lecture_id,
                kind="summary",
                title="test",
                content={},
            )
        )

    monkeypatch.setattr(jobs, "generate_batch", generate)
    result = client.send(
        "POST", "/lectures/" + lecture["id"] + "/generate", {"kind": "summary"}
    )
    with app.app_context():
        jobs.execute(jobs.claim())
        assert Artifact.query.count() == 1
        assert JobBatch.query.filter_by(completed=True).count() == 1
        assert "batches" not in db.session.get(Job, result.json["id"]).payload
    assert (
        client.send("POST", "/jobs/" + result.json["id"] + "/retry").status_code == 200
    )
    with app.app_context():
        jobs.execute(jobs.claim())
        assert Artifact.query.count() == 3
        assert JobBatch.query.filter_by(completed=True).count() == 3
        assert seen.count(seen[0]) == 1


def test_postgres_workers_skip_locked_job(app, client):
    with app.app_context():
        if db.engine.dialect.name != "postgresql":
            pytest.skip("PostgreSQL row-lock integration runs in CI")
        first = Job(
            user_id=client.user["id"],
            kind="extract",
            created_at=now() - timedelta(seconds=5),
        )
        second = Job(user_id=client.user["id"], kind="extract")
        db.session.add_all([first, second])
        db.session.commit()
        first_id, second_id = first.id, second.id
        with db.engine.connect() as connection:
            transaction = connection.begin()
            connection.execute(
                select(Job.id).where(Job.id == first_id).with_for_update()
            )
            claimed = jobs.claim()
            assert claimed.id == second_id
            transaction.rollback()
