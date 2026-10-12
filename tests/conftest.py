import os
import pytest
from studymate import create_app
from studymate.extensions import db


@pytest.fixture
def app(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-only",
            "SQLALCHEMY_DATABASE_URI": os.getenv(
                "TEST_DATABASE_URL", "sqlite:///" + str(tmp_path / "test.db")
            ),
            "DATA_DIR": str(tmp_path),
            "RATELIMIT_ENABLED": False,
            "OPENAI_API_KEY": "",
        }
    )
    with app.app_context():
        db.create_all()
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


class Client:
    def __init__(self, app, email="student@example.test"):
        self.raw = app.test_client()
        self.csrf = self.raw.get("/api/session").json["csrf"]
        response = self.send(
            "POST",
            "/auth/register",
            {"email": email, "name": "Study Student", "password": "test-password-1234"},
        )
        assert response.status_code == 201, response.json
        self.user = response.json["user"]
        self.csrf = response.json["csrf"]

    def send(self, method, path, data=None):
        return self.raw.open(
            "/api" + path, method=method, json=data, headers={"X-CSRF-Token": self.csrf}
        )

    def setup_lecture(self):
        course = self.send("POST", "/courses", {"title": "Cognitive science"}).json
        return self.send(
            "POST",
            "/lectures",
            {"course_id": course["id"], "title": "Memory", "topic": "working memory"},
        ).json

    def upload(
        self, lecture, raw=b"Working memory has limited capacity.", name="lecture.txt"
    ):
        upload = self.send(
            "POST",
            "/uploads",
            {"lecture_id": lecture["id"], "name": name, "size": len(raw)},
        ).json
        response = self.raw.put(
            "/api/uploads/" + upload["id"] + "/chunks/0",
            data=raw,
            headers={
                "X-CSRF-Token": self.csrf,
                "Content-Type": "application/octet-stream",
            },
        )
        assert response.status_code == 200, response.json
        return upload, self.send("POST", "/uploads/" + upload["id"] + "/complete")


@pytest.fixture
def client(app):
    return Client(app)
