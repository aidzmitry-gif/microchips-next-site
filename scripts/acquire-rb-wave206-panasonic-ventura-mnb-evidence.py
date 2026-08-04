#!/usr/bin/env python3
"""Pin first-party catalogue snapshots for Wave206 VRLA battery evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import urllib.request
from pathlib import Path

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_DIR = ROOT / "docs/audits/sources/wave206-panasonic-ventura-mnb"
INDEX = SNAPSHOT_DIR / "snapshot-index.json"
CHECKED_AT = "2026-07-29"

SOURCES = [
    {
        "source_id": "panasonic_vrla_professional_catalogue",
        "publisher": "Panasonic Industry Europe GmbH",
        "url": "https://mediap.industry.panasonic.eu/assets/custom-upload/Energy%20%26%20Building/Batteries/Secondary%20Batteries/Valve%20Regulated%20Lead-Acid%20Batteries/Panasonic%20VRLA%20Batteries%20VRLA%20Handbook.pdf",
        "filename": "panasonic-vrla-for-professionals.pdf",
        "required_exact_tokens": ["LC-P12120P", "LC-P12150BP", "LC-P12200BP"],
    },
    {
        "source_id": "ventura_2023_catalogue",
        "publisher": "Ventura",
        "url": "https://ventura-battery.ru/upload/iblock/836/n52d2cyekiv52rav9o0vwctttvggje9j/Catalog_Ventura_2023.pdf",
        "filename": "ventura-catalogue-2023.pdf",
        "required_exact_tokens": ["GP 12-100", "GPL 12-200", "HRL 12500W"],
    },
    {
        "source_id": "mnb_official_catalogue",
        "publisher": "MNB Battery",
        "url": "https://mnb-battery.ru/pdf/MNB%20%D0%BA%D0%B0%D1%82%D0%B0%D0%BB%D0%BE%D0%B6%D0%B5%D0%BA%20%D0%BF%D0%BE%20%D1%81%D0%B2%D0%B8%D0%BD%D1%86%D1%83%20%D0%B8%20%D0%BB%D0%B8%D1%82%D0%B8%D1%8E.pdf",
        "filename": "mnb-official-catalogue.pdf",
        "required_exact_tokens": ["MM 100-12", "MNG 100-12", "MR 125-12 FT"],
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
    with urllib.request.urlopen(request, timeout=90) as response:
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
                raise SystemExit(f"{source['source_id']}: response is not PDF")
            path.write_bytes(payload)

        text = normalized_pdf_text(path)
        text_path = path.with_suffix(".txt")
        text_path.write_text(text + "\n", encoding="utf-8")
        token_counts = {
            token: text.casefold().count(token.casefold())
            for token in source["required_exact_tokens"]
        }
        missing = [token for token, count in token_counts.items() if count == 0]
        if missing:
            raise SystemExit(f"{source['source_id']}: missing exact tokens: {', '.join(missing)}")
        records.append({
            "source_id": source["source_id"],
            "publisher": source["publisher"],
            "source_url": source["url"],
            "source_kind": "official_manufacturer_catalogue",
            "checked_at": CHECKED_AT,
            "snapshot_path": path.relative_to(ROOT).as_posix(),
            "snapshot_sha256": sha256(path),
            "snapshot_bytes": path.stat().st_size,
            "extracted_text_path": text_path.relative_to(ROOT).as_posix(),
            "extracted_text_sha256": sha256(text_path),
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
