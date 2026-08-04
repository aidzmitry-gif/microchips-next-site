#!/usr/bin/env python3
"""Acquire the new Panasonic Wave245A primary PDF with strict no-repeat gates."""

from __future__ import annotations

import hashlib
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUSIONS = ROOT / "docs/audits/generated/rb-wave245a-prior-source-exclusions.json"
OUT_DIR = ROOT / "docs/audits/sources/wave245a-panasonic"
URLS = {
    "LC-XC1222P": "https://mediap.industry.panasonic.eu/assets/imported/industrial.panasonic.com/cdbs/www-data/pdf2/ACD4000/ACD4000C70.PDF",
    "LC-XC1228P": "https://mediap.industry.panasonic.eu/assets/imported/industrial.panasonic.com/cdbs/www-data/pdf2/ACD4000/ACD4000C61.pdf",
}


def main() -> None:
    exclusions = json.loads(EXCLUSIONS.read_text(encoding="utf-8"))
    prior_urls = {row["value"] for row in exclusions["source_urls"]}
    prior_hashes = {row["value"].lower() for row in exclusions["snapshot_sha256"]}
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    assets = []
    for model, url in URLS.items():
        if url in prior_urls:
            raise SystemExit(f"Source URL was already used before Wave245A: {url}")
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 Wave245A evidence auditor"})
        with urllib.request.urlopen(request, timeout=60) as response:
            data = response.read()
            content_type = response.headers.get("Content-Type", "")
        if not data.startswith(b"%PDF-"):
            raise SystemExit(f"Expected PDF for {model}, got {content_type!r}")
        digest = hashlib.sha256(data).hexdigest()
        if digest in prior_hashes:
            raise SystemExit(f"Downloaded bytes repeat a prior source SHA-256: {model}")
        asset = OUT_DIR / f"{model.lower()}-{digest[:16]}.pdf"
        asset.write_bytes(data)
        assets.append({
            "model": model,
            "source_url": url,
            "publisher": "Panasonic Industry Europe GmbH",
            "source_kind": "official_manufacturer_individual_datasheet_pdf",
            "local_path": asset.relative_to(ROOT).as_posix(),
            "sha256": digest,
            "bytes": len(data),
            "content_type": content_type,
            "prior_url_overlap": False,
            "prior_sha256_overlap": False,
        })
    registry = {
        "schema_version": 1,
        "wave": "wave245a_panasonic",
        "checked_at": "2026-07-30",
        "assets": assets,
    }
    (OUT_DIR / "registry.json").write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(registry, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
