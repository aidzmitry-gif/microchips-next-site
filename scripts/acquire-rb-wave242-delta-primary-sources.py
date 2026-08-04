#!/usr/bin/env python3
"""Acquire the explicitly allowlisted Wave242 Delta first-party pages.

This is the only Wave242 component with network access.  The downstream
builder is offline and accepts only the hash-pinned registry emitted here.
"""

from __future__ import annotations

import hashlib
import json
import urllib.request
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs/audits/sources/wave242-delta"
REGISTRY = OUTPUT / "registry.json"
CHECKED_AT = "2026-07-29"
ALLOWED_HOSTS = {"delta-batt.com", "www.delta-batt.com", "kz.delta-batt.com", "www.kz.delta-batt.com"}
SOURCES = {
    "cgd": "https://delta-batt.com/catalog/akkumulyatory_statsionarnye/filter/series-cgd/general-scope-alternativnaya_energetika/",
    "ct": "https://delta-batt.com/series/ct/",
    "dt": "https://delta-batt.com/series/dt/",
    "dtm": "https://delta-batt.com/series/dtm/",
    "ft_m": "https://delta-batt.com/series/ft_m/",
    "fts_x": "https://delta-batt.com/series/fts_x/",
    "hr_w": "https://delta-batt.com/series/hr_w/",
    "hrl_w": "https://delta-batt.com/series/hrl_w/",
    "hrl_x": "https://delta-batt.com/series/hrl_x/",
    "stc": "https://delta-batt.com/series/stc/",
}


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for source_id, url in sorted(SOURCES.items()):
        print(f"acquire {source_id}: {url}", flush=True)
        if urlparse(url).hostname not in ALLOWED_HOSTS:
            raise ValueError(f"non-Delta host rejected: {url}")
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 Wave242 evidence archiver"})
        with urllib.request.urlopen(request, timeout=45) as response:
            final_url = response.geturl()
            body = response.read()
            content_type = response.headers.get("Content-Type", "")
        if urlparse(final_url).hostname not in ALLOWED_HOSTS:
            raise ValueError(f"redirect left Delta host: {final_url}")
        is_pdf = body.startswith(b"%PDF")
        if len(body) < 5_000 or (not is_pdf and b"<html" not in body[:5_000].lower()):
            raise ValueError(f"unexpected response for {url}: {content_type}, {len(body)} bytes")
        sha256 = hashlib.sha256(body).hexdigest()
        path = OUTPUT / f"{source_id}-{sha256[:16]}{'.pdf' if is_pdf else '.html'}"
        path.write_bytes(body)
        rows.append({
            "source_id": source_id,
            "source_url": final_url,
            "source_kind": "official_manufacturer_catalogue" if is_pdf else "official_manufacturer_series_page",
            "source_publisher": "DELTA Battery / ENERGON",
            "checked_at": CHECKED_AT,
            "snapshot_path": path.relative_to(ROOT).as_posix(),
            "snapshot_sha256": sha256,
            "content_type": content_type,
        })
    REGISTRY.write_text(json.dumps({"schema_version": 1, "sources": rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"sources": len(rows), "registry": REGISTRY.relative_to(ROOT).as_posix()}, sort_keys=True))


if __name__ == "__main__":
    main()
