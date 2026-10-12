# NEW: Google OAuth routes for StudyMate AI
# This file is entirely new – handles login / callback / logout via Google OAuth.

import os

from authlib.integrations.flask_client import OAuth
from flask import Blueprint, redirect, url_for, session, request, flash, current_app
from flask_login import login_user, logout_user, current_user
import json

from models import db, User

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

oauth = OAuth()


def init_oauth(app):
    """Register the OAuth extension and configure Google provider."""
    oauth.init_app(app)
    google_client_id     = os.environ.get("GOOGLE_CLIENT_ID", "")
    google_client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "")
    github_client_id     = os.environ.get("GITHUB_CLIENT_ID", "")
    github_client_secret = os.environ.get("GITHUB_CLIENT_SECRET", "")

    if google_client_id and google_client_secret:
        oauth.register(
            name="google",
            client_id=google_client_id,
            client_secret=google_client_secret,
            server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
            client_kwargs={"scope": "openid email profile"},
        )
    # Register GitHub OAuth provider if configured
    if github_client_id and github_client_secret:
        oauth.register(
            name="github",
            client_id=github_client_id,
            client_secret=github_client_secret,
            access_token_url="https://github.com/login/oauth/access_token",
            authorize_url="https://github.com/login/oauth/authorize",
            api_base_url="https://api.github.com/",
            client_kwargs={"scope": "user:email"},
        )
    # If credentials aren't set, Google OAuth routes will return a friendly error.


# ── Login ──────────────────────────────────────────────────────────────────────
@auth_bp.route("/login")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("home"))

    google = oauth.create_client("google") if _google_configured() else None
    if google is None:
        flash("Google OAuth가 설정되지 않았습니다. .env 파일에 GOOGLE_CLIENT_ID와 GOOGLE_CLIENT_SECRET을 추가해 주세요.", "error")
        return redirect(url_for("login_page"))

    redirect_uri = url_for("auth.callback", _external=True)
    return google.authorize_redirect(redirect_uri)


# ── Callback ──────────────────────────────────────────────────────────────────
@auth_bp.route("/callback")
def callback():
    google = oauth.create_client("google") if _google_configured() else None
    if google is None:
        flash("Google OAuth가 설정되지 않았습니다.", "error")
        return redirect(url_for("login_page"))

    try:
        token     = google.authorize_access_token()
        userinfo  = token.get("userinfo") or google.userinfo()
    except Exception as exc:
        current_app.logger.error("OAuth callback error: %s", exc)
        flash("Google 로그인 중 오류가 발생했습니다. 다시 시도해 주세요.", "error")
        return redirect(url_for("login_page"))

    google_id  = userinfo.get("sub")
    email      = userinfo.get("email", "")
    name       = userinfo.get("name", email.split("@")[0])
    avatar_url = userinfo.get("picture", "")

    # Find or create user
    user = User.query.filter_by(google_id=google_id).first()
    if user is None:
        user = User.query.filter_by(email=email).first()
    if user is None:
        user = User(google_id=google_id, email=email, name=name, avatar_url=avatar_url)
        db.session.add(user)
    else:
        user.google_id  = google_id
        user.name       = name
        user.avatar_url = avatar_url

    db.session.commit()
    login_user(user, remember=True)
    return redirect(url_for("home"))


# ── Logout ─────────────────────────────────────────────────────────────────────
@auth_bp.route("/logout")
def logout():
    logout_user()
    session.clear()
    return redirect(url_for("login_page"))


# ── Helpers ────────────────────────────────────────────────────────────────────
def _google_configured():
    return bool(os.environ.get("GOOGLE_CLIENT_ID") and os.environ.get("GOOGLE_CLIENT_SECRET"))


@auth_bp.route("/github/login")
def github_login():
    if current_user.is_authenticated:
        return redirect(url_for("materials_page"))

    github = oauth.create_client("github") if _github_configured() or _github_github_configured() else None
    if github is None:
        flash("GitHub OAuth가 설정되지 않았습니다. 환경변수에 GITHUB_CLIENT_ID와 GITHUB_CLIENT_SECRET을 추가해 주세요.", "error")
        return redirect(url_for("login_page"))

    redirect_uri = url_for("auth.github_callback", _external=True)
    return github.authorize_redirect(redirect_uri)


@auth_bp.route("/github/callback")
def github_callback():
    github = oauth.create_client("github") if _github_configured() or _github_github_configured() else None
    if github is None:
        flash("GitHub OAuth가 설정되지 않았습니다.", "error")
        return redirect(url_for("login_page"))

    try:
        token = github.authorize_access_token()
        # fetch basic profile
        resp = github.get("/user")
        profile = resp.json() if resp.ok else {}
        # fetch emails (may include primary/verified)
        emails_resp = github.get("/user/emails")
        emails = emails_resp.json() if emails_resp.ok else []
    except Exception as exc:
        current_app.logger.error("GitHub OAuth callback error: %s", exc)
        flash("GitHub 로그인 중 오류가 발생했습니다. 다시 시도해 주세요.", "error")
        return redirect(url_for("login_page"))

    github_id = str(profile.get("id")) if profile.get("id") is not None else None
    login_name = profile.get("login") or ""
    avatar_url = profile.get("avatar_url", "")

    email = None
    # choose primary verified email if available
    for e in emails:
        if isinstance(e, dict) and e.get("primary") and e.get("verified"):
            email = e.get("email")
            break
    if not email and emails:
        # fallback to first email object
        first = emails[0]
        if isinstance(first, dict):
            email = first.get("email")
    if not email:
        # last fallback: try profile email field
        email = profile.get("email")
    if not email:
        # As a final fallback, synthesize an email to satisfy non-null constraint
        email = f"{login_name}@users.noreply.github.com"

    # Find or create user
    user = None
    if github_id:
        user = User.query.filter_by(github_id=github_id).first()
    if user is None:
        user = User.query.filter_by(email=email).first()
    if user is None:
        name = profile.get("name") or login_name or email.split("@")[0]
        user = User(github_id=github_id, email=email, name=name, avatar_url=avatar_url)
        db.session.add(user)
    else:
        user.github_id = github_id
        user.name = profile.get("name") or user.name
        user.avatar_url = avatar_url or user.avatar_url

    db.session.commit()
    login_user(user, remember=True)
    return redirect(url_for("materials_page"))


def _github_github_configured():
    # backward compatibility helper; same as _github_configured
    return _github_configured()


def _github_configured():
    return bool(os.environ.get("GITHUB_CLIENT_ID") and os.environ.get("GITHUB_CLIENT_SECRET"))
