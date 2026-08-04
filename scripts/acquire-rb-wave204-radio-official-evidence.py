#!/usr/bin/env python3
"""Pin official Alinco accessory evidence used by the Wave204 radio-pack audit."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import urllib.request
from pathlib import Path

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_DIR = ROOT / "docs/audits/sources/wave204-radio"
INDEX = SNAPSHOT_DIR / "snapshot-index.json"
CHECKED_AT = "2026-07-29"

SOURCES = [
    {
        "source_id": "alinco_handheld_accessories_2006",
        "publisher": "Alinco, Inc.",
        "url": "https://www.alinco.com/Products/accessoryHT_2006.pdf",
        "filename": "alinco-handheld-accessories-2006-snapshot.pdf",
        "required_exact_tokens": [
            "EBP-50N", "EBP-51N", "EBP-64", "EBP-65",
            "9.6V 700mAh", "9.6V 1500mAh", "7.4V 1600mAh", "7.2V 700mAh",
        ],
    },
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalized_pdf_text(path: Path) -> str:
    text = "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)
    return re.sub(r"\s+", " ", text).strip()


def download(url: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "microchips.by-catalog-evidence/1.0 (+https://microchips.by/)",
            "Accept": "application/pdf,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    records = []
    for source in SOURCES:
        path = SNAPSHOT_DIR / source["filename"]
        if args.refresh or not path.exists():
            payload = download(source["url"])
            if not payload.startswith(b"%PDF-"):
                raise SystemExit(f"{source['source_id']}: response is not a PDF")
            path.write_bytes(payload)

        text = normalized_pdf_text(path)
        compact = re.sub(r"\s+", " ", text)
        token_counts = {
            token: compact.casefold().count(token.casefold())
            for token in source["required_exact_tokens"]
        }
        missing = [token for token, count in token_counts.items() if count == 0]
        if missing:
            raise SystemExit(f"{source['source_id']}: snapshot lacks exact tokens: {', '.join(missing)}")
        records.append({
            "source_id": source["source_id"],
            "publisher": source["publisher"],
            "source_url": source["url"],
            "source_kind": "official_manufacturer_pdf",
            "checked_at": CHECKED_AT,
            "snapshot_path": path.relative_to(ROOT).as_posix(),
            "snapshot_sha256": sha256(path),
            "snapshot_bytes": path.stat().st_size,
            "required_exact_tokens": source["required_exact_tokens"],
            "token_counts": token_counts,
        })

    INDEX.write_text(
        json.dumps({"schema_version": 1, "checked_at": CHECKED_AT, "sources": records}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"sources": len(records), "index": INDEX.relative_to(ROOT).as_posix()}, ensure_ascii=False))


if __name__ == "__main__":
    main()
