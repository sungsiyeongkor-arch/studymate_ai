"""Synthetic search-index probe on an explicit CI/test database only."""

import json
import os
import sys
from pathlib import Path
from sqlalchemy import text, insert

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from studymate import create_app
from studymate.extensions import db
from studymate.models import User, Course, Lecture, Material, Segment

app = create_app()
with app.app_context():
    if db.engine.dialect.name != "postgresql" or not db.engine.url.database.endswith(
        "_test"
    ):
        raise SystemExit(
            "Only an explicit PostgreSQL database ending in _test is allowed"
        )
    owner = "e" * 32
    if User.query.count():
        raise SystemExit("Requires an empty application database")
    db.session.add(
        User(
            id=owner,
            email="synthetic@example.test",
            name="synthetic",
            password_hash="disabled",
        )
    )
    db.session.flush()
    db.session.add(Course(id=owner, user_id=owner, title="synthetic"))
    db.session.flush()
    db.session.add(Lecture(id=owner, user_id=owner, course_id=owner, title="synthetic"))
    db.session.flush()
    db.session.add(
        Material(
            id=owner,
            user_id=owner,
            lecture_id=owner,
            name="synthetic.txt",
            kind="text",
            storage_key="synthetic",
            size=0,
            sha256="0" * 64,
        )
    )
    db.session.commit()
    for start in range(0, 20000, 1000):
        db.session.execute(
            insert(Segment),
            [
                {
                    "id": f"{i+1:032x}",
                    "user_id": owner,
                    "material_id": owner,
                    "ordinal": i,
                    "text": (
                        "희귀검색어 반도체 XYZ987"
                        if i == 12345
                        else "학습 자료와 반복되는 일반적인 본문"
                    )
                    + f" {i}",
                }
                for i in range(start, start + 1000)
            ],
        )
        db.session.commit()
    db.session.execute(text("ANALYZE sm_segments"))
    before_cleanup = db.session.execute(
        text(
            "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) SELECT id FROM sm_segments WHERE user_id=:owner AND text LIKE :needle LIMIT 51"
        ),
        {"owner": owner, "needle": "%XYZ987%"},
    ).scalar()
    cleaned_pages = db.session.execute(
        text("SELECT gin_clean_pending_list('ix_sm_segments_text_trgm')")
    ).scalar()
    db.session.execute(text("ANALYZE sm_segments"))
    plan = db.session.execute(
        text(
            "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) SELECT id FROM sm_segments WHERE user_id=:owner AND text LIKE :needle LIMIT 51"
        ),
        {"owner": owner, "needle": "%XYZ987%"},
    ).scalar()
    valid = db.session.execute(
        text(
            "SELECT indisvalid FROM pg_index WHERE indexrelid='ix_sm_segments_text_trgm'::regclass"
        )
    ).scalar()
    count = db.session.execute(
        text(
            "SELECT count(*) FROM sm_segments WHERE user_id=:owner AND text LIKE '%희귀검색어%'"
        ),
        {"owner": owner},
    ).scalar()
    assert count == 1
    assert valid is True
    used = "ix_sm_segments_text_trgm" in json.dumps(plan)
    db.session.commit()
    Path("test-results").mkdir(exist_ok=True)
    Path("test-results/postgres-search-report.json").write_text(
        json.dumps(
            {
                "synthetic_only": True,
                "rows": 20000,
                "plan": plan,
                "before_pending_cleanup": before_cleanup,
                "pending_pages_cleaned": cleaned_pages,
                "trigram_index_used": used,
                "index_valid": valid,
                "korean_match_count": count,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(
        f"20,000-row PostgreSQL search probe passed; pg_trgm selected={used}; pending pages cleaned={cleaned_pages}"
    )
