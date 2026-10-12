import os
import secrets
from pathlib import Path
import click
from dotenv import load_dotenv
from flask import Flask, jsonify, request, session, g, render_template
from werkzeug.exceptions import HTTPException
from .extensions import db, migrate, limiter


def create_app(config=None):
    load_dotenv()
    root = Path(__file__).resolve().parent.parent
    tools_dir = root / ".tools" / "ffmpeg" / "bin"
    if tools_dir.is_dir() and str(tools_dir) not in os.environ.get("PATH", "").split(
        os.pathsep
    ):
        os.environ["PATH"] = str(tools_dir) + os.pathsep + os.environ.get("PATH", "")
    data = Path(os.getenv("DATA_DIR", root / "instance")).resolve()
    data.mkdir(parents=True, exist_ok=True)
    app = Flask(__name__, template_folder="templates", static_folder="static")
    production = os.getenv("APP_ENV") == "production"
    secret = os.getenv("SECRET_KEY")
    if not secret:
        if production:
            raise RuntimeError("SECRET_KEY is required in production")
        secret_file = data / ".session-secret"
        if not secret_file.exists():
            secret_file.write_text(secrets.token_hex(32), encoding="utf-8")
        secret = secret_file.read_text(encoding="utf-8")
    uri = os.getenv(
        "DATABASE_URL", "sqlite:///" + (data / "studymate-v2.db").as_posix()
    )
    for prefix in ("postgres://", "postgresql://"):
        if uri.startswith(prefix):
            uri = uri.replace(prefix, "postgresql+psycopg://", 1)
    app.config.update(
        SECRET_KEY=secret,
        SQLALCHEMY_DATABASE_URI=uri,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SQLALCHEMY_ENGINE_OPTIONS={"pool_pre_ping": True},
        DATA_DIR=str(data),
        MAX_CONTENT_LENGTH=520 * 1024 * 1024,
        STORAGE_LIMIT_BYTES=int(os.getenv("STORAGE_LIMIT_BYTES", str(10 * 1024**3))),
        UPLOAD_TTL_HOURS=int(os.getenv("UPLOAD_TTL_HOURS", "24")),
        MAX_FILE_BYTES=512 * 1024 * 1024,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=production,
        RATELIMIT_STORAGE_URI=os.getenv("RATELIMIT_STORAGE_URI", "memory://"),
        OPENAI_API_KEY=os.getenv("OPENAI_API_KEY", ""),
        OPENAI_MODEL=os.getenv("OPENAI_MODEL", "gpt-6-astra"),
        TRANSCRIPTION_MODEL=os.getenv("TRANSCRIPTION_MODEL", "whisper-1"),
        AI_DAILY_REQUEST_LIMIT=int(os.getenv("AI_DAILY_REQUEST_LIMIT", "100")),
        TESTING=False,
    )
    if config:
        app.config.update(config)
    if app.config["SQLALCHEMY_DATABASE_URI"].startswith("postgresql"):
        app.config["SQLALCHEMY_ENGINE_OPTIONS"].update(
            pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
            max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "5")),
            pool_timeout=int(os.getenv("DB_POOL_TIMEOUT", "10")),
            pool_recycle=1800,
            connect_args={
                "options": "-c statement_timeout=30000 -c lock_timeout=5000 -c idle_in_transaction_session_timeout=600000"
            },
        )
    db.init_app(app)
    migrate.init_app(app, db)
    limiter.init_app(app)
    from .models import User
    from .api import api

    app.register_blueprint(api, url_prefix="/api")

    @app.before_request
    def authenticate():
        g.user = (
            db.session.get(User, session.get("user_id"))
            if session.get("user_id")
            else None
        )
        if request.path.startswith("/api/") and request.method not in (
            "GET",
            "HEAD",
            "OPTIONS",
        ):
            token = request.headers.get("X-CSRF-Token", "")
            if not token or not secrets.compare_digest(token, session.get("csrf", "")):
                return (
                    jsonify(error="보안 토큰이 만료되었습니다. 새로고침해 주세요."),
                    403,
                )
        public_paths = (
            "/api/session",
            "/api/auth/login",
            "/api/auth/register",
            "/api/health",
            "/api/ready",
        )
        if (
            request.path.startswith("/api/")
            and request.path not in public_paths
            and not g.user
        ):
            return jsonify(error="로그인이 필요합니다."), 401

    @app.after_request
    def headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data: blob:; media-src 'self' blob:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; frame-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'"
        )
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.errorhandler(HTTPException)
    def http_error(error):
        return jsonify(error=error.description), error.code

    @app.errorhandler(Exception)
    def unexpected(error):
        db.session.rollback()
        app.logger.exception("Request failed")
        return (
            jsonify(
                error="요청을 처리하지 못했습니다. 저장 상태를 확인하고 다시 시도해 주세요."
            ),
            500,
        )

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.cli.command("init-db")
    def init_db():
        """Development-only bootstrap. Production uses flask db upgrade."""
        db.create_all()
        click.echo("Database initialized")

    @app.cli.command("worker")
    @click.option("--once", is_flag=True)
    def worker(once):
        from .services.jobs import work

        work(once)

    from .services.operations import register_commands

    register_commands(app)
    return app
