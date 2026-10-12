import hashlib
from pathlib import Path
from flask import current_app


def path(key):
    root = (Path(current_app.config["DATA_DIR"]) / "files").resolve()
    root.mkdir(parents=True, exist_ok=True)
    target = (root / key).resolve()
    if not target.is_relative_to(root):
        raise ValueError("Invalid storage key")
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def digest(file_path):
    h = hashlib.sha256()
    with open(file_path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()
