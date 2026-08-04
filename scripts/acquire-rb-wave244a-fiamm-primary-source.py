#!/usr/bin/env python3
"""Acquire two new official FIAMM sources after no-repeat checks."""

from __future__ import annotations

import hashlib
import json
import urllib.request
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
EXCLUSIONS = ROOT / "docs/audits/generated/rb-wave244a-prior-source-exclusions.json"
OUTPUT = ROOT / "docs/audits/sources/wave244a-fiamm/registry.json"
CANDIDATES = [
    ("12FGH36", "https://www.fiamm.ru/data/Catalogue/2022/FGH-FGHL_web.pdf", "pdf"),
    ("4SLA150", "https://www.fiamm.ru/services/faq/voprosy-po-podboru/", "html"),
]


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    exclusions = json.loads(EXCLUSIONS.read_text(encoding="utf-8"))
    prior_urls = {item["value"] for item in exclusions["source_urls"]}
    prior_hashes = {item["value"] for item in exclusions["snapshot_sha256"]}
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    sources = []
    for model, url, extension in CANDIDATES:
        if url in prior_urls:
            raise SystemExit(f"candidate URL was already structured before Wave244A: {url}")
        if urlparse(url).hostname != "www.fiamm.ru":
            raise SystemExit("unexpected source host")
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 Wave244A audit"})
        with urllib.request.urlopen(request, timeout=60) as response:
            data = response.read()
            content_type = response.headers.get("Content-Type", "")
        digest = sha(data)
        if extension == "pdf" and (not data.startswith(b"%PDF-") or "pdf" not in content_type.casefold()):
            raise SystemExit("official PDF candidate did not return a PDF")
        if extension == "html" and "html" not in content_type.casefold():
            raise SystemExit("official HTML candidate did not return HTML")
        if digest in prior_hashes:
            raise SystemExit(f"candidate bytes were already structured before Wave244A: {url}")
        snapshot = OUTPUT.parent / f"fiamm-{model.lower()}-{digest[:16]}.{extension}"
        snapshot.write_bytes(data)
        sources.append({
            "source_url": url,
            "source_kind": "official_manufacturer_catalogue" if extension == "pdf" else "official_manufacturer_service_document",
            "source_publisher": "FIAMM Industrial RUS / FIAMM Energy Technology",
            "manufacturer_primary": True,
            "snapshot_path": snapshot.relative_to(ROOT).as_posix(),
            "snapshot_sha256": digest,
            "expected_exact_models": [model],
        })
    payload = {
        "schema_version": 1,
        "checked_at": "2026-07-30",
        "prior_exclusions_sha256": sha(EXCLUSIONS.read_bytes()),
        "sources": sources,
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"sources": len(sources), "sha256": [item["snapshot_sha256"] for item in sources]}, sort_keys=True))


if __name__ == "__main__":
    main()
