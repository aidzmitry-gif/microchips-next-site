#!/usr/bin/env python3
"""Acquire only the new, allowlisted Schneider Electric Wave243C PDF."""

from __future__ import annotations

import hashlib
import json
import urllib.request
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs/audits/sources/wave243c-apc"
REGISTRY = OUTPUT / "source-registry.json"
URLS = {
    "APCRBC109": "https://iportal.se.com/Contents/docs/UPS-APCRBC109_Data%20sheet.pdf",
}
ALLOWED_HOSTS = {"iportal.se.com"}


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for model, url in URLS.items():
        if urlparse(url).hostname not in ALLOWED_HOSTS:
            raise SystemExit(f"non-primary host: {url}")
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 Wave243C evidence archiver"})
        with urllib.request.urlopen(request, timeout=45) as response:
            final_url = response.geturl()
            body = response.read()
        if urlparse(final_url).hostname not in ALLOWED_HOSTS:
            raise SystemExit(f"redirect left primary host: {final_url}")
        path = OUTPUT / f"{model.lower()}.pdf"
        path.write_bytes(body)
        rows.append({
            "model": model,
            "requested_url": url,
            "final_url": final_url,
            "snapshot_path": path.relative_to(ROOT).as_posix(),
            "snapshot_sha256": hashlib.sha256(body).hexdigest(),
            "bytes": len(body),
        })
    REGISTRY.write_text(json.dumps({"checked_at": "2026-07-29", "sources": rows}, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"sources": len(rows), "registry": REGISTRY.relative_to(ROOT).as_posix()}))


if __name__ == "__main__":
    main()
