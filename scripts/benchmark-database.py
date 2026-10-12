"""Reproducible isolated SQLite scaling probe. Never reads the application DB."""

import argparse
import json
import statistics
import sys
import time
import tracemalloc
from datetime import datetime
from pathlib import Path
from sqlalchemy import create_engine, insert, select, text, tuple_

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from studymate.extensions import db
from studymate.models import User, Course, Lecture, Material, Segment


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=1000000)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not 1000 <= args.rows <= 10000000:
        parser.error("rows must be between 1,000 and 10,000,000")
    args.output.mkdir(parents=True, exist_ok=False)
    path = (args.output / "synthetic.db").resolve()
    engine = create_engine("sqlite:///" + path.as_posix())
    db.metadata.create_all(engine)
    at = datetime(2026, 1, 1)
    with engine.begin() as conn:
        for i in range(10):
            key = f"{i+1:032x}"
            conn.execute(
                insert(User),
                dict(
                    id=key,
                    email=f"synthetic-{i}@example.test",
                    name="SYNTHETIC",
                    password_hash="disabled",
                ),
            )
            conn.execute(insert(Course), dict(id=key, user_id=key, title="SYNTHETIC"))
            conn.execute(
                insert(Lecture),
                dict(id=key, user_id=key, course_id=key, title="SYNTHETIC"),
            )
            conn.execute(
                insert(Material),
                dict(
                    id=key,
                    user_id=key,
                    lecture_id=key,
                    name="synthetic.txt",
                    kind="text",
                    storage_key="synthetic/not-a-real-file",
                    size=0,
                    sha256="0" * 64,
                ),
            )
    tracemalloc.start()
    start = time.perf_counter()
    for offset in range(0, args.rows, 2000):
        rows = []
        for i in range(offset, min(offset + 2000, args.rows)):
            owner = f"{i%10+1:032x}"
            rows.append(
                dict(
                    id=f"{i+1:032x}",
                    user_id=owner,
                    material_id=owner,
                    ordinal=i // 10,
                    created_at=at,
                    text="SYNTHETIC 학습 자료: 인출 연습과 작업기억. " * 4,
                )
            )
        with engine.begin() as conn:
            conn.execute(insert(Segment), rows)
        if offset % 100000 == 0:
            print(
                f"Inserted {min(offset+2000,args.rows):,} / {args.rows:,}", flush=True
            )
    insert_seconds = time.perf_counter() - start
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    owner = f"{1:032x}"
    base = select(Segment.id, Segment.text).where(Segment.user_id == owner)
    order = (Segment.created_at.desc(), Segment.id.desc())
    timings = {}
    with engine.connect() as conn:
        conn.execute(text("ANALYZE"))
        for label, statement in {
            "first_page": base.order_by(*order).limit(51),
            "deep_keyset": base.where(
                tuple_(Segment.created_at, Segment.id) < (at, f"{args.rows//10:032x}")
            )
            .order_by(*order)
            .limit(51),
            "deep_offset_comparison": base.order_by(*order)
            .offset(args.rows // 10 * 9 // 10)
            .limit(51),
        }.items():
            samples = []
            for _ in range(30):
                tick = time.perf_counter()
                result = conn.execute(statement).all()
                samples.append((time.perf_counter() - tick) * 1000)
            timings[label] = {
                "rows_returned": len(result),
                "median_ms": round(statistics.median(samples), 3),
                "p95_ms": round(sorted(samples)[28], 3),
            }
        plan = conn.execute(
            text(
                "EXPLAIN QUERY PLAN SELECT id,text FROM sm_segments WHERE user_id=:owner ORDER BY created_at DESC,id DESC LIMIT 51"
            ),
            {"owner": owner},
        ).all()
        count = conn.execute(text("SELECT COUNT(*) FROM sm_segments")).scalar_one()
    assert count == args.rows
    report = {
        "synthetic_only": True,
        "database": "SQLite",
        "tenants": 10,
        "segment_rows": count,
        "database_bytes": path.stat().st_size,
        "insert_seconds": round(insert_seconds, 2),
        "python_insertion_peak_bytes": peak,
        "batch_size": 2000,
        "measurements": timings,
        "query_plan": [list(row) for row in plan],
        "limitations": "Local warm-cache single-process SELECT probe, not PostgreSQL production throughput, concurrency, AI quality, or maximum capacity.",
    }
    (args.output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    run()
