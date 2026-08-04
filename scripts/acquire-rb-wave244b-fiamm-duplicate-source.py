#!/usr/bin/env python3
"""Acquire the new official FIAMM FG catalogue snapshot for Wave244B."""

from __future__ import annotations

import hashlib
import json
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs/audits/sources/wave244b-fiamm-duplicates"
URL = "https://www.fiamm.com/fileadmin/user_upload/products/reserve/FG/FG_FOLDER_EN.pdf"
FILENAME = "fiamm-fg-folder-en.pdf"


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(
        URL,
        headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.fiamm.com/"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        data = response.read()
    if not data.startswith(b"%PDF-"):
        raise RuntimeError("Official FIAMM endpoint did not return a PDF")
    snapshot = OUTPUT / FILENAME
    snapshot.write_bytes(data)
    inventory = {
        "source_url": URL,
        "snapshot_path": snapshot.relative_to(ROOT).as_posix(),
        "snapshot_sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
        "acquired_at": "2026-07-30",
    }
    (OUTPUT / "acquisition.json").write_text(
        json.dumps(inventory, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(inventory, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
