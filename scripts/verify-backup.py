"""Restore a checksummed backup into a NEW SQLite file or an EMPTY *_restore_check PostgreSQL DB."""

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


def verify(backup_dir, sqlite_output=None):
    manifest = json.loads((backup_dir / "manifest.json").read_text(encoding="utf-8"))
    source = (backup_dir / manifest["file"]).resolve()
    if source.parent != backup_dir.resolve():
        raise ValueError("Invalid manifest path")
    with source.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != manifest["sha256"]:
            raise ValueError("Backup checksum mismatch")
    if manifest["engine"] == "sqlite":
        if sqlite_output is None:
            raise ValueError("--sqlite-output is required")
        with sqlite_output.open("xb") as target, source.open("rb") as stream:
            shutil.copyfileobj(stream, target)
        with sqlite3.connect(sqlite_output) as connection:
            if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise RuntimeError("Restored database integrity check failed")
            if connection.execute("PRAGMA foreign_key_check").fetchall():
                raise RuntimeError("Restored database foreign-key check failed")
            tables = [
                r[0]
                for r in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'sm_%'"
                )
            ]
            counts = {
                name: connection.execute(
                    'SELECT count(*) FROM "' + name.replace('"', '""') + '"'
                ).fetchone()[0]
                for name in tables
            }
    elif manifest["engine"] == "postgresql":
        url = make_url(os.environ["RESTORE_DATABASE_URL"])
        if url.get_backend_name() != "postgresql" or not (url.database or "").endswith(
            "_restore_check"
        ):
            raise ValueError("Restore database name must end with _restore_check")
        engine = create_engine(url)
        with engine.connect() as connection:
            if connection.execute(
                text(
                    "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'"
                )
            ).scalar():
                raise ValueError("Restore database is not empty")
        env = dict(
            os.environ,
            PGHOST=url.host or "localhost",
            PGPORT=str(url.port or 5432),
            PGUSER=url.username or "",
            PGPASSWORD=url.password or "",
            PGDATABASE=url.database,
        )
        for key in ("sslmode", "sslrootcert", "sslcert", "sslkey"):
            if key in url.query:
                env["PG" + key.upper()] = url.query[key]
        result = subprocess.run(
            [
                "pg_restore",
                "--exit-on-error",
                "--single-transaction",
                "--no-owner",
                "--no-acl",
                "--dbname",
                url.database,
                str(source),
            ],
            env=env,
            capture_output=True,
        )
        if result.returncode:
            raise RuntimeError(
                "Restore failed; check versions and permissions. Credentials are not logged."
            )
        with engine.connect() as connection:
            names = (
                connection.execute(
                    text(
                        "SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name LIKE 'sm_%'"
                    )
                )
                .scalars()
                .all()
            )
            counts = {
                name: connection.execute(
                    text('SELECT count(*) FROM "' + name.replace('"', '""') + '"')
                ).scalar()
                for name in names
            }
        engine.dispose()
    else:
        raise ValueError("Unsupported backup engine")
    return {
        "checksum_verified": True,
        "restored_table_counts": counts,
        "limitations": "Database restore only. Check original files separately.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument("--sqlite-output", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.backup, args.sqlite_output), indent=2))
