#!/usr/bin/env python3
"""Acquire byte-new official Panasonic evidence for the two Wave245B rows."""

from __future__ import annotations

import hashlib
import io
import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
EXCLUSIONS = ROOT / "docs/audits/generated/rb-wave245b-prior-source-exclusions.json"
OUTPUT = ROOT / "docs/audits/sources/wave245b-panasonic-new-rows/acquisition.json"
CANDIDATES = (
    {
        "id": "short-form-catalog",
        "url": "https://eu.industrial.panasonic.com/sites/default/pidseu/files/downloads/files/panasonic-batteries-short-form-catalog-2018-for-professionals_interactive_08_11_18.pdf",
        "expected_models": ["LC-XC1238P/AP", "LC-XD1217PG/APG"],
        "role": "exact_model_specification",
    },
    {
        "id": "vrla-handbook-media-portal",
        "url": "https://mediap.industry.panasonic.eu/assets/imported/industrial.panasonic.com/cdbs/www-data/pdf2/ACD4000/ACD4000C62.pdf",
        "expected_models": ["LC-XC1238P/AP"],
        "role": "exact_individual_datasheet_and_image_candidate",
    },
)
DISCOVERY_TEMPLATE = "https://mediap.industry.panasonic.eu/assets/imported/industrial.panasonic.com/cdbs/www-data/pdf2/ACD4000/ACD4000C{index:02d}.pdf"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def download(url: str) -> tuple[bytes, str]:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 Wave245B evidence audit"})
    with urllib.request.urlopen(request, timeout=90) as response:
        return response.read(), response.headers.get("Content-Type", "")


def pdf_text(data: bytes) -> str:
    reader = PdfReader(io.BytesIO(data))
    return " ".join(page.extract_text() or "" for page in reader.pages)


def main() -> None:
    exclusions = json.loads(EXCLUSIONS.read_text(encoding="utf-8"))
    prior_urls = {item["value"] for item in exclusions["source_urls"]}
    prior_hashes = {item["value"] for item in exclusions["snapshot_sha256"]}
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    for stale in OUTPUT.parent.glob("*.pdf"):
        stale.unlink()
    sources = []
    rejected = []
    for candidate in CANDIDATES:
        url = candidate["url"]
        host = (urlparse(url).hostname or "").casefold()
        if host not in {"eu.industrial.panasonic.com", "mediap.industry.panasonic.eu"}:
            raise SystemExit(f"unexpected publisher host: {host}")
        if url in prior_urls:
            rejected.append({**candidate, "reason": "PRIOR_URL"})
            continue
        data, content_type = download(url)
        digest = sha(data)
        if not data.startswith(b"%PDF-"):
            rejected.append({
                **candidate,
                "reason": "NOT_PDF_RESPONSE",
                "response_sha256": digest,
                "content_type": content_type,
                "bytes": len(data),
            })
            continue
        if digest in prior_hashes:
            rejected.append({**candidate, "reason": "PRIOR_SHA256", "snapshot_sha256": digest})
            continue
        text = pdf_text(data)
        if not all(model in text for model in candidate["expected_models"]):
            rejected.append({**candidate, "reason": "NON_EXACT_MODEL_PDF", "snapshot_sha256": digest})
            continue
        path = OUTPUT.parent / f"{candidate['id']}-{digest[:16]}.pdf"
        path.write_bytes(data)
        sources.append({
            **candidate,
            "source_url": url,
            "source_kind": "official_manufacturer_pdf",
            "source_publisher": "Panasonic Industry Europe",
            "manufacturer_primary": True,
            "snapshot_path": path.relative_to(ROOT).as_posix(),
            "snapshot_sha256": digest,
            "bytes": len(data),
            "content_type": content_type,
        })
    discovery_urls = [DISCOVERY_TEMPLATE.format(index=index) for index in range(100)]
    discovery_urls = [url for url in discovery_urls if url not in prior_urls and url not in {item["source_url"] for item in sources}]
    discovery = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(download, url): url for url in discovery_urls}
        for future in as_completed(futures):
            url = futures[future]
            try:
                data, content_type = future.result()
                digest = sha(data)
                if data.startswith(b"%PDF-") and digest not in prior_hashes and "LC-XD1217PG/APG" in pdf_text(data):
                    discovery.append((url, data, content_type, digest))
            except Exception:
                continue
    if len(discovery) > 1:
        raise SystemExit(f"ambiguous LC-XD1217PG/APG Media Portal matches: {len(discovery)}")
    if discovery:
        url, data, content_type, digest = discovery[0]
        path = OUTPUT.parent / f"vrla-handbook-media-portal-xd1217-{digest[:16]}.pdf"
        path.write_bytes(data)
        sources.append({
            "id": "vrla-handbook-media-portal-xd1217",
            "url": url,
            "expected_models": ["LC-XD1217PG/APG"],
            "role": "exact_individual_datasheet_and_image_candidate",
            "source_url": url,
            "source_kind": "official_manufacturer_pdf",
            "source_publisher": "Panasonic Industry Europe",
            "manufacturer_primary": True,
            "snapshot_path": path.relative_to(ROOT).as_posix(),
            "snapshot_sha256": digest,
            "bytes": len(data),
            "content_type": content_type,
        })
    else:
        rejected.append({
            "id": "vrla-handbook-media-portal-xd1217-discovery",
            "expected_models": ["LC-XD1217PG/APG"],
            "reason": "NO_NEW_EXACT_OFFICIAL_PDF_IN_BOUNDED_DISCOVERY",
        })
    payload = {
        "schema_version": 1,
        "checked_at": "2026-07-30",
        "prior_exclusions_sha256": sha(EXCLUSIONS.read_bytes()),
        "sources": sources,
        "rejected_candidates": rejected,
        "xd1217_discovery": {"candidate_urls": len(discovery_urls), "exact_matches": len(discovery)},
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"accepted": len(sources), "rejected": rejected}, sort_keys=True))


if __name__ == "__main__":
    main()
