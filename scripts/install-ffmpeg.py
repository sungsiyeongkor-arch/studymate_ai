"""Install Windows FFmpeg locally; no system PATH changes or administrator access."""

import hashlib
import io
import os
import sys
import urllib.request
import zipfile
from pathlib import Path

if sys.platform != "win32":
    raise SystemExit(
        "Use your OS package manager or the project Docker image on Linux/macOS."
    )
root = Path(__file__).resolve().parents[1] / ".tools"
root.mkdir(exist_ok=True)
url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
expected = (
    urllib.request.urlopen(url + ".sha256", timeout=60)
    .read()
    .decode()
    .split()[0]
    .lower()
)
archive = root / "ffmpeg-download.zip"
digest = hashlib.sha256()
with urllib.request.urlopen(url, timeout=120) as response, archive.open("wb") as output:
    while chunk := response.read(1024 * 1024):
        output.write(chunk)
        digest.update(chunk)
if digest.hexdigest() != expected:
    raise SystemExit("Checksum mismatch; nothing was installed.")
destination = root / "ffmpeg" / "bin"
destination.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(archive) as z:
    for executable in ("ffmpeg.exe", "ffprobe.exe"):
        matches = [n for n in z.namelist() if n.endswith("/bin/" + executable)]
        if len(matches) != 1:
            raise SystemExit("Unexpected archive layout")
        (destination / executable).write_bytes(z.read(matches[0]))
(destination.parent / "SOURCE.txt").write_text(
    url
    + "\nSHA256 "
    + expected
    + "\nWindows build: GPLv3, see https://www.gyan.dev/ffmpeg/builds/\n",
    encoding="utf-8",
)
print("FFmpeg and ffprobe installed in " + str(destination))
print("SHA256 " + expected)
