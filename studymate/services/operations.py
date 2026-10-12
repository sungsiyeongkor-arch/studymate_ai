"""Explicit operator commands: read-only diagnostics by default, bounded maintenance."""

import json
from datetime import timedelta
from pathlib import Path
import click
from sqlalchemy import text, func
from ..extensions import db
from ..models import User, Material, Upload, UploadChunk, Job, JobBatch, now
from . import storage, quota


def register_commands(app):
    @app.cli.command("db-report")
    def report():
        """Aggregate operational metrics; never emit credentials or source text."""
        value = {
            "dialect": db.engine.dialect.name,
            "users": User.query.count(),
            "materials": Material.query.count(),
            "original_bytes": db.session.query(
                func.coalesce(func.sum(Material.size), 0)
            ).scalar(),
            "reserved_bytes": db.session.query(
                func.coalesce(func.sum(User.storage_reserved), 0)
            ).scalar(),
            "jobs": dict(
                db.session.query(Job.status, func.count()).group_by(Job.status).all()
            ),
        }
        if db.engine.dialect.name == "postgresql":
            value["database_bytes"] = db.session.execute(
                text("SELECT pg_database_size(current_database())")
            ).scalar()
        click.echo(json.dumps(value))

    @app.cli.command("expire-uploads")
    @click.option(
        "--apply",
        is_flag=True,
        help="Without this flag only report expired pending uploads.",
    )
    @click.option("--batch-size", default=100, type=click.IntRange(1, 1000))
    def expire(apply, batch_size):
        """Release expired reservations. Never touch active assembling uploads."""
        rows = (
            Upload.query.filter(Upload.status == "pending", Upload.expires_at < now())
            .order_by(Upload.expires_at)
            .limit(batch_size)
            .all()
        )
        count = 0
        for row in rows:
            if not apply:
                count += 1
                continue
            quota.lock_owner(row.user_id)
            db.session.refresh(row)
            if row.status != "pending" or row.expires_at >= now():
                db.session.rollback()
                continue
            row.status = "expired"
            quota.release(row.user_id, row.size)
            keys = [
                c.storage_key for c in UploadChunk.query.filter_by(upload_id=row.id)
            ]
            UploadChunk.query.filter_by(upload_id=row.id).delete()
            db.session.commit()
            for key in keys:
                storage.path(key).unlink(missing_ok=True)
            count += 1
        click.echo(
            json.dumps({"count": count, "applied": apply, "batch_size": batch_size})
        )

    @app.cli.command("prune-job-snapshots")
    @click.option("--days", default=30, type=click.IntRange(1, 3650))
    @click.option("--batch-size", default=100, type=click.IntRange(1, 1000))
    @click.option("--apply", is_flag=True)
    def prune(days, batch_size, apply):
        """Remove only completed-job source snapshots, preserving learning artifacts."""
        rows = (
            Job.query.filter(
                Job.status == "completed",
                Job.heartbeat < now() - timedelta(days=days),
                JobBatch.query.filter(JobBatch.job_id == Job.id).exists(),
            )
            .order_by(Job.heartbeat)
            .limit(batch_size)
            .all()
        )
        ids = [r.id for r in rows]
        count = JobBatch.query.filter(JobBatch.job_id.in_(ids)).count()
        if apply:
            JobBatch.query.filter(JobBatch.job_id.in_(ids)).delete(
                synchronize_session=False
            )
            for row in rows:
                row.payload = {}
            db.session.commit()
        click.echo(
            json.dumps({"jobs": len(ids), "source_batches": count, "applied": apply})
        )

    @app.cli.command("search-index")
    def search_index():
        """Install optional PostgreSQL pg_trgm and a non-blocking GIN index."""
        if db.engine.dialect.name != "postgresql":
            raise click.ClickException(
                "Requires PostgreSQL; SQLite is the development fallback."
            )
        # Deliberately not inside an Alembic transaction: large live indexes use CONCURRENTLY.
        with db.engine.connect().execution_options(
            isolation_level="AUTOCOMMIT"
        ) as conn:
            conn.execute(text("SET statement_timeout = 0"))
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
            invalid = conn.execute(
                text(
                    "SELECT NOT i.indisvalid FROM pg_index i JOIN pg_class c ON c.oid=i.indexrelid WHERE c.relname='ix_sm_segments_text_trgm'"
                )
            ).scalar()
            if invalid:
                conn.execute(
                    text("DROP INDEX CONCURRENTLY IF EXISTS ix_sm_segments_text_trgm")
                )
            conn.execute(
                text(
                    "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_sm_segments_text_trgm ON sm_segments USING gin (text gin_trgm_ops)"
                )
            )
            conn.execute(text("ANALYZE sm_segments"))
            conn.execute(text("RESET statement_timeout"))
        click.echo(
            "Search index ready. Very short/common queries may still scan many rows."
        )
