#!/usr/bin/env python3
"""Archive the two new exact Panasonic Wave245C individual data sheets."""

from __future__ import annotations

import hashlib
import json
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs/audits/sources/wave245c-panasonic"
REGISTRY = OUTPUT / "source-registry.json"
SOURCES = {
    "UP-VW0645P1": "https://mediap.industry.panasonic.eu/assets/imported/industrial.panasonic.com/cdbs/www-data/pdf2/ACD4000/ACD4000C64.pdf",
    "UP-VW1220P1": "https://mediap.industry.panasonic.eu/assets/imported/industrial.panasonic.com/cdbs/www-data/pdf2/ACD4000/ACD4000C65.pdf",
}
ALLOWED_HOSTS = {"mediap.industry.panasonic.eu"}
RIGHTS_URL = "https://industry.panasonic.eu/terms-service"


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for model, url in SOURCES.items():
        if urlparse(url).hostname not in ALLOWED_HOSTS:
            raise SystemExit(f"non-primary source: {url}")
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 Wave245C evidence archiver"})
        with urllib.request.urlopen(request, timeout=60) as response:
            final_url, body = response.geturl(), response.read()
        if urlparse(final_url).hostname not in ALLOWED_HOSTS or not body.startswith(b"%PDF-"):
            raise SystemExit(f"source redirect/type failure: {final_url}")
        path = OUTPUT / f"{model.lower()}-individual-data-sheet.pdf"
        path.write_bytes(body)
        images = PdfReader(path).pages[0].images
        if len(images) != 1:
            raise SystemExit(f"expected one embedded official product image for {model}, got {len(images)}")
        image_path = OUTPUT / f"{model.lower()}-official-product-candidate.png"
        images[0].image.save(image_path, format="PNG")
        image_body = image_path.read_bytes()
        rows.append({
            "model": model, "requested_url": url, "final_url": final_url,
            "snapshot_path": path.relative_to(ROOT).as_posix(),
            "snapshot_sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body),
            "image_candidate_path": image_path.relative_to(ROOT).as_posix(),
            "image_candidate_sha256": hashlib.sha256(image_body).hexdigest(),
            "image_candidate_width": images[0].image.width,
            "image_candidate_height": images[0].image.height,
            "image_rights_status": "manufacturer_hosted_exact_product_image_no_republication_license_found_hold",
        })
    rights_request = urllib.request.Request(RIGHTS_URL, headers={"User-Agent": "Mozilla/5.0 Wave245C rights archiver"})
    with urllib.request.urlopen(rights_request, timeout=60) as response:
        rights_url, rights_body = response.geturl(), response.read()
    if urlparse(rights_url).hostname != "industry.panasonic.eu":
        raise SystemExit(f"rights source redirect failure: {rights_url}")
    rights_path = OUTPUT / "panasonic-industry-terms-service.html"
    rights_path.write_bytes(rights_body)
    registry = {
        "checked_at": "2026-07-30", "sources": rows,
        "rights_source": {"requested_url": RIGHTS_URL, "final_url": rights_url,
            "snapshot_path": rights_path.relative_to(ROOT).as_posix(),
            "snapshot_sha256": hashlib.sha256(rights_body).hexdigest(), "bytes": len(rights_body)},
    }
    REGISTRY.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"sources": len(rows), "registry": REGISTRY.relative_to(ROOT).as_posix()}))


if __name__ == "__main__":
    main()
