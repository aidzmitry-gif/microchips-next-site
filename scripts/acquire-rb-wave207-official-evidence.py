#!/usr/bin/env python3
"""Pin the bounded first-party web evidence used by Wave207.

The acquisition list is intentionally small.  A 404/discontinued product is
recorded as unavailable; it is never converted into positive evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_DIR = ROOT / "docs/audits/sources/wave207-device-small"
INDEX = SNAPSHOT_DIR / "snapshot-index.json"
CHECKED_AT = "2026-07-29"

SOURCES = [
    *[
        {
            "source_id": f"icom_{model.casefold().replace('-', '_')}",
            "publisher": "Icom Inc.",
            "url": f"https://www.icomjapan.com/lineup/options/{model}/",
            "filename": f"icom-{model.casefold()}-2026-07-29.html",
            "required_tokens": [model, "BATTERY PACK"],
        }
        for model in (
            "BP-202", "BP-209N", "BP-210N", "BP-227FM", "BP-232N", "BP-234",
            "BP-235", "BP-236", "BP-245N", "BP-252", "BP-256", "BP-264",
        )
    ],
    {
        "source_id": "baofeng_uv5r_1800",
        "publisher": "Baofeng",
        "url": "https://www.baofengradio.com/products/battery-1800mah-for-uv-5r",
        "filename": "baofeng-uv5r-1800-2026-07-29.html",
        "required_tokens": ["UV-5R", "1800"],
    },
    {
        "source_id": "baofeng_uv5r_3800",
        "publisher": "Baofeng",
        "url": "https://www.baofengradio.com/products/battery-3800mah-for-uv-5r",
        "filename": "baofeng-uv5r-3800-2026-07-29.html",
        "required_tokens": ["UV-5R", "3800"],
    },
    {
        "source_id": "baofeng_uv82_2000",
        "publisher": "Baofeng",
        "url": "https://www.baofengradio.com/products/battery-for-uv-82l",
        "filename": "baofeng-uv82-2000-2026-07-29.html",
        "required_tokens": ["UV-82", "2000"],
    },
    {
        "source_id": "baofeng_dm1701",
        "publisher": "Baofeng",
        "url": "https://www.baofengradio.com/collections/analog/products/dm-1701",
        "filename": "baofeng-dm1701-2026-07-29.html",
        "required_tokens": ["DM-1701", "2200"],
    },
    {
        "source_id": "baofeng_bf888s_1500",
        "publisher": "Baofeng",
        "url": "https://www.baofengradio.com/products/battery-for-bf-888s",
        "filename": "baofeng-bf888s-1500-2026-07-29.html",
        "required_tokens": ["BF-888S", "1500"],
    },
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compact_text(payload: bytes) -> str:
    text = payload.decode("utf-8", errors="replace")
    text = re.sub(r"<script\b[^>]*>.*?</script>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def download(url: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "microchips.by-catalog-evidence/1.0 (+https://microchips.by/)",
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        return response.read()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    available: list[dict] = []
    unavailable: list[dict] = []
    for source in SOURCES:
        path = SNAPSHOT_DIR / source["filename"]
        if args.refresh or not path.exists():
            try:
                payload = download(source["url"])
            except urllib.error.HTTPError as error:
                if error.code in {403, 404, 410, 429}:
                    unavailable.append({
                        "source_id": source["source_id"],
                        "source_url": source["url"],
                        "http_status": error.code,
                    })
                    if error.code in {404, 410} and path.exists():
                        path.unlink()
                    continue
                raise
            if b"<html" not in payload[:4096].lower() and b"<!doctype html" not in payload[:4096].lower():
                raise SystemExit(f"{source['source_id']}: response is not HTML")
            path.write_bytes(payload)

        payload = path.read_bytes()
        text = compact_text(payload)
        token_counts = {
            token: text.casefold().count(token.casefold())
            for token in source["required_tokens"]
        }
        if not all(token_counts.values()):
            unavailable.append({
                "source_id": source["source_id"],
                "source_url": source["url"],
                "http_status": 200,
                "reason": "required_tokens_missing",
                "token_counts": token_counts,
            })
            continue
        available.append({
            "source_id": source["source_id"],
            "publisher": source["publisher"],
            "source_url": source["url"],
            "source_kind": "official_manufacturer_product_page",
            "checked_at": CHECKED_AT,
            "snapshot_path": path.relative_to(ROOT).as_posix(),
            "snapshot_sha256": sha256(path),
            "snapshot_bytes": path.stat().st_size,
            "required_tokens": source["required_tokens"],
            "token_counts": token_counts,
        })

    INDEX.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "checked_at": CHECKED_AT,
                "sources": available,
                "unavailable": unavailable,
            },
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"available": len(available), "unavailable": len(unavailable)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
