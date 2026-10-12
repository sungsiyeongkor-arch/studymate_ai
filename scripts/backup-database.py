"""Create a DB-only backup and checksum; originals require a separate storage backup."""

import argparse
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy.engine import make_url

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def backup(url, output):
    output.mkdir(parents=True, exist_ok=False)
    parsed = make_url(url)
    if parsed.get_backend_name() == "sqlite":
        source = Path(parsed.database).resolve()
        target = output / "database.sqlite3"
        with sqlite3.connect(source.as_uri() + "?mode=ro", uri=True) as src:
            with sqlite3.connect(target) as dst:
                src.backup(dst)
                if dst.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise RuntimeError("Backup integrity check failed")
    elif parsed.get_backend_name() == "postgresql":
        target = output / "database.dump"
        env = dict(
            os.environ,
            PGHOST=parsed.host or "localhost",
            PGPORT=str(parsed.port or 5432),
            PGUSER=parsed.username or "",
            PGPASSWORD=parsed.password or "",
            PGDATABASE=parsed.database or "",
        )
        for key in ("sslmode", "sslrootcert", "sslcert", "sslkey"):
            if key in parsed.query:
                env["PG" + key.upper()] = parsed.query[key]
        with target.open("xb") as output_stream:
            result = subprocess.run(
                ["pg_dump", "--format=custom", "--no-owner", "--no-acl"],
                env=env,
                stdout=output_stream,
                stderr=subprocess.PIPE,
            )
        if result.returncode:
            message = result.stderr.decode("utf-8", errors="replace")
            if os.getenv("CI") == "true" and (parsed.database or "").endswith("_test"):
                print(
                    message.replace(parsed.password or "test-only", "[REDACTED]"),
                    file=sys.stderr,
                )
            raise RuntimeError(
                "pg_dump failed; check client version, network and database permissions. No credentials were logged."
            )
    else:
        raise ValueError("Unsupported database")
    with target.open("rb") as stream:
        sha = hashlib.file_digest(stream, "sha256").hexdigest()
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "engine": parsed.get_backend_name(),
        "file": target.name,
        "bytes": target.stat().st_size,
        "sha256": sha,
        "scope": "database only; excludes originals, .env and session secrets",
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="New private directory, never an existing directory",
    )
    args = parser.parse_args()
    from studymate import create_app

    app = create_app()
    print(
        json.dumps(backup(app.config["SQLALCHEMY_DATABASE_URI"], args.output), indent=2)
    )
