#!/usr/bin/env python3
"""Acquire the frozen Wave243B manufacturer-primary PDF snapshots."""

from __future__ import annotations

import hashlib
import json
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs/audits/sources/wave243b-fiamm-panasonic"

SOURCES = {
    "fiamm-fg27004.pdf": "https://www.fiamm.co/catalog/FG27004.pdf",
    "fiamm-fg2a007.pdf": "https://www.fiamm.co/catalog/FG2A007.pdf",
    "panasonic-lc-r067r2p.pdf": "https://api.pim.na.industrial.panasonic.com/file_stream/main/fileversion/3533",
    "panasonic-lc-r063r4p.pdf": "https://api.pim.na.industrial.panasonic.com/file_stream/main/fileversion/3541",
    "panasonic-lc-r0612p.pdf": "https://api.pim.na.industrial.panasonic.com/file_stream/main/fileversion/3544",
    "panasonic-lc-p0612p.pdf": "https://api.pim.na.industrial.panasonic.com/file_stream/main/fileversion/3546",
    "panasonic-vrla-recognized-models.pdf": "https://api.pim.na.industrial.panasonic.com/file_stream/main/fileversion/3529",
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    inventory = []
    for filename, url in SOURCES.items():
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 Wave243B evidence acquisition"})
        with urllib.request.urlopen(request, timeout=60) as response:
            data = response.read()
            content_type = response.headers.get("Content-Type", "")
        if not data.startswith(b"%PDF-"):
            raise RuntimeError(f"Expected PDF from {url}, got {content_type!r}")
        path = OUTPUT / filename
        path.write_bytes(data)
        inventory.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "source_url": url,
                "sha256": sha256(data),
                "bytes": len(data),
            }
        )
    inventory_path = OUTPUT / "acquisition.json"
    inventory_path.write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")
    print(f"Acquired {len(inventory)} Wave243B PDFs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
