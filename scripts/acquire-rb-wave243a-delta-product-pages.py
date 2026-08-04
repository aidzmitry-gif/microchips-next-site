#!/usr/bin/env python3
"""Acquire only new allowlisted official Delta product pages for Wave243A."""

from __future__ import annotations

import hashlib
import json
import re
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs/audits/sources/wave243a-delta"
REGISTRY = OUTPUT / "registry.json"
EXCLUSIONS = ROOT / "docs/audits/generated/rb-wave243a-prior-source-exclusions.json"
BASE = "https://delta-batt.com"
CHECKED_AT = "2026-07-29"
ALLOWED_HOSTS = {"delta-batt.com", "www.delta-batt.com"}
CANDIDATES = {
    "bitrix:20130": ("CGD 1255", "/products/cgd_1255/"),
    "bitrix:20131": ("CGD 12100", "/products/cgd_12100/"),
    "bitrix:20132": ("CGD 12200", "/products/cgd_12200/"),
    "bitrix:1448": ("CT 1212.2", "/products/ct_1212_2/"),
    "bitrix:1523": ("CT 1216", "/products/ct_1216/"),
    "bitrix:1450": ("CT 1216.1", "/products/ct_1216_1/"),
    "bitrix:1537": ("CT 1218", "/products/ct_1218/"),
    "bitrix:2890": ("CT 1220", "/products/ct_1220/"),
    "bitrix:1452": ("CT 1220.1", "/products/ct_1220_1/"),
    "bitrix:2963": ("CT 1230", "/products/ct_1230/"),
    "bitrix:20109": ("DT 12008 (T13)", "/products/dt_12008_t13/"),
    "bitrix:20110": ("DT 12008 (T9)", "/products/dt_12008_t9/"),
    "bitrix:1398": ("DTM 12008", "/products/dtm_12008/"),
    "bitrix:20116": ("DTM 12100 I", "/products/dtm_12100_i/"),
    "bitrix:20118": ("DTM 12150 I", "/products/dtm_12150_i/"),
    "bitrix:20119": ("DTM 12200 I", "/products/dtm_12200_i/"),
    "bitrix:20120": ("DTM 12250 I", "/products/dtm_12250_i/"),
    "bitrix:20111": ("DTM 1233 I", "/products/dtm_1233_i/"),
    "bitrix:20112": ("DTM 1240 I", "/products/dtm_1240_i/"),
    "bitrix:20113": ("DTM 1255 I", "/products/dtm_1255_i/"),
    "bitrix:20114": ("DTM 1265 I", "/products/dtm_1265_i/"),
    "bitrix:20115": ("DTM 1275 I", "/products/dtm_1275_i/"),
    "bitrix:2896": ("DTM 12230 L", "/products/dtm_12230_l/"),
    "bitrix:20169": ("HRL 12-320 W", "/products/hrl_12_320_w_xpert/"),
    "bitrix:20167": ("HRL 12-420 W", "/products/hrl_12_420_w_xpert/"),
    "bitrix:20166": ("HRL 12-560 W", "/products/hrl_12_560_w_xpert/"),
    "bitrix:20165": ("HRL 12-600 W", "/products/hrl_12_600_w_xpert/"),
    "bitrix:20164": ("HRL 12-650 W", "/products/hrl_12_650_w_xpert/"),
    "bitrix:20163": ("HRL 12-890 W", "/products/hrl_12_890_w_xpert/"),
}


def canonical(value: str) -> str:
    value = re.sub(r"^DELTA\s+", "", value.strip(), flags=re.I)
    value = re.sub(r"^XPERT\s+", "", value, flags=re.I)
    value = re.sub(r"\s+XPERT$", "", value, flags=re.I)
    return "".join(char for char in value.casefold() if char.isalnum())


def main() -> None:
    prior = json.loads(EXCLUSIONS.read_text(encoding="utf-8"))
    prior_urls = {row["value"] for row in prior["source_urls"]}
    prior_hashes = {row["value"] for row in prior["snapshot_sha256"]}
    OUTPUT.mkdir(parents=True, exist_ok=True)
    successes = []
    failures = []
    for external_id, (expected_model, route) in sorted(CANDIDATES.items()):
        url = BASE + route
        if url in prior_urls:
            failures.append({"external_id": external_id, "expected_model": expected_model, "url": url,
                             "reason": "PRIOR_SOURCE_URL"})
            continue
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 Wave243A evidence archiver"})
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                final_url = response.geturl()
                body = response.read()
                content_type = response.headers.get("Content-Type", "")
        except (urllib.error.URLError, TimeoutError) as error:
            failures.append({"external_id": external_id, "expected_model": expected_model, "url": url,
                             "reason": f"DOWNLOAD_FAILED:{type(error).__name__}"})
            continue
        snapshot_hash = hashlib.sha256(body).hexdigest()
        soup = BeautifulSoup(body, "html.parser")
        heading = soup.find("h1")
        heading_text = heading.get_text(" ", strip=True) if heading else ""
        if urlparse(final_url).hostname not in ALLOWED_HOSTS or final_url in prior_urls:
            reason = "REDIRECT_NOT_NEW_OFFICIAL_URL"
        elif snapshot_hash in prior_hashes:
            reason = "PRIOR_SNAPSHOT_SHA256"
        elif len(body) < 5_000 or "html" not in content_type.casefold():
            reason = "INVALID_HTML_RESPONSE"
        elif canonical(heading_text) != canonical(expected_model):
            reason = "HEADING_NOT_EXACT_MODEL"
        else:
            reason = ""
        if reason:
            failures.append({"external_id": external_id, "expected_model": expected_model,
                             "url": url, "final_url": final_url, "heading": heading_text, "reason": reason})
            continue
        path = OUTPUT / f"{external_id.replace(':', '-')}-{snapshot_hash[:16]}.html"
        path.write_bytes(body)
        successes.append({
            "external_id": external_id, "expected_model": expected_model,
            "source_url": final_url, "source_kind": "official_manufacturer_product_page",
            "source_publisher": "DELTA Battery / ENERGON", "checked_at": CHECKED_AT,
            "snapshot_path": path.relative_to(ROOT).as_posix(), "snapshot_sha256": snapshot_hash,
            "heading": heading_text,
        })
    REGISTRY.write_text(json.dumps({
        "schema_version": 1,
        "prior_exclusions_sha256": hashlib.sha256(EXCLUSIONS.read_bytes()).hexdigest(),
        "sources": successes,
        "failed_candidates": failures,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"success": len(successes), "failed": len(failures)}, sort_keys=True))


if __name__ == "__main__":
    main()
