#!/usr/bin/env python3
"""Acquire only previously unseen official datasheets linked by Wave243A pages."""

from __future__ import annotations

import hashlib
import json
import re
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]
EXCLUSIONS = ROOT / "docs/audits/generated/rb-wave243a-prior-source-exclusions.json"
PRODUCT_REGISTRY = ROOT / "docs/audits/sources/wave243a-delta/registry.json"
OUTPUT = ROOT / "docs/audits/sources/wave243a-delta/datasheet-registry.json"
CHECKED_AT = "2026-07-29"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    exclusions = json.loads(EXCLUSIONS.read_text(encoding="utf-8"))
    prior_urls = {item["value"] for item in exclusions["source_urls"]}
    prior_hashes = {item["value"] for item in exclusions["snapshot_sha256"]}
    product_registry = json.loads(PRODUCT_REGISTRY.read_text(encoding="utf-8"))
    sources: list[dict[str, str]] = []
    holds: list[dict[str, str]] = []

    for product in product_registry["sources"]:
        page = ROOT / product["snapshot_path"]
        soup = BeautifulSoup(page.read_text(encoding="utf-8"), "html.parser")
        urls = sorted({
            link.get("href", "") for link in soup.find_all("a", href=True)
            if re.fullmatch(r"https://pim\.energon\.ru/.+\.pdf", link.get("href", ""), re.I)
        })
        if len(urls) != 1:
            holds.append({"external_id": product["external_id"], "reason": "DATASHEET_LINK_NOT_UNIQUE"})
            continue
        url = urls[0]
        if url in prior_urls:
            holds.append({"external_id": product["external_id"], "reason": "PRIOR_SOURCE_URL", "url": url})
            continue
        if urlparse(url).hostname != "pim.energon.ru":
            raise SystemExit(f"unexpected datasheet host: {url}")
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 Wave243A audit"})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                data = response.read()
                content_type = response.headers.get("Content-Type", "")
        except Exception as exc:
            holds.append({"external_id": product["external_id"], "reason": "DOWNLOAD_FAILED", "detail": str(exc)})
            continue
        digest = sha(data)
        if not data.startswith(b"%PDF-") or "pdf" not in content_type.casefold():
            holds.append({"external_id": product["external_id"], "reason": "NOT_PDF", "url": url})
            continue
        if digest in prior_hashes:
            holds.append({"external_id": product["external_id"], "reason": "PRIOR_SOURCE_SHA256", "url": url})
            continue
        filename = f"{product['external_id'].replace(':', '-')}-{digest[:16]}.pdf"
        path = OUTPUT.parent / filename
        path.write_bytes(data)
        sources.append({
            "external_id": product["external_id"],
            "expected_model": product["expected_model"],
            "source_url": url,
            "source_kind": "official_manufacturer_technical_datasheet",
            "source_publisher": "DELTA Battery / ENERGON",
            "checked_at": CHECKED_AT,
            "snapshot_path": path.relative_to(ROOT).as_posix(),
            "snapshot_sha256": digest,
            "linked_from_product_url": product["source_url"],
            "linked_from_product_snapshot_sha256": product["snapshot_sha256"],
        })

    payload = {
        "schema_version": 1,
        "prior_exclusions_sha256": sha(EXCLUSIONS.read_bytes()),
        "product_registry_sha256": sha(PRODUCT_REGISTRY.read_bytes()),
        "sources": sources,
        "holds": holds,
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"sources": len(sources), "holds": len(holds)}, sort_keys=True))


if __name__ == "__main__":
    main()
