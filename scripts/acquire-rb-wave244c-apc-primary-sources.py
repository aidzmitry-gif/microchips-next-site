#!/usr/bin/env python3
"""Archive only the new official Schneider Electric Wave244C PDFs."""

from __future__ import annotations

import hashlib
import json
import urllib.request
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs/audits/sources/wave244c-apc"
REGISTRY = OUTPUT / "source-registry.json"
SOURCES = {
    "RBC7_RBC23_RBC31": "https://iportal.se.com/Contents/docs/UPS-GWOG-8WTJM8_R0_EN.PDF",
    "APCRBC141": "https://iportal.se.com/Contents/docs/UPS-JGNY-9NNEDA_R1_EN.PDF",
}
ALLOWED_HOSTS = {"iportal.se.com"}


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for label, url in SOURCES.items():
        if urlparse(url).hostname not in ALLOWED_HOSTS:
            raise SystemExit(f"non-primary host: {url}")
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 Wave244C evidence archiver"})
        with urllib.request.urlopen(request, timeout=60) as response:
            final_url = response.geturl()
            body = response.read()
        if urlparse(final_url).hostname not in ALLOWED_HOSTS:
            raise SystemExit(f"redirect left primary host: {final_url}")
        if not body.startswith(b"%PDF-"):
            raise SystemExit(f"official source is not a PDF: {final_url}")
        path = OUTPUT / ("rbc7-rbc23-rbc31-eoli.pdf" if label.startswith("RBC7") else "apcrbc141-installation-guide.pdf")
        path.write_bytes(body)
        rows.append({
            "label": label,
            "requested_url": url,
            "final_url": final_url,
            "snapshot_path": path.relative_to(ROOT).as_posix(),
            "snapshot_sha256": hashlib.sha256(body).hexdigest(),
            "bytes": len(body),
        })
    REGISTRY.write_text(json.dumps({"checked_at": "2026-07-30", "sources": rows}, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"sources": len(rows), "registry": REGISTRY.relative_to(ROOT).as_posix()}))


if __name__ == "__main__":
    main()
