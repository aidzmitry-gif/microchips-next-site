#!/usr/bin/env python3
"""Acquire and validate official snapshots for Wave203 remaining exact identities."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_DIR = ROOT / "docs/audits/sources/wave203-remaining"
INDEX = SNAPSHOT_DIR / "snapshot-index.json"
CHECKED_AT = "2026-07-29"

SOURCES = [
    {
        "source_id": "cino_f680bt_accessories",
        "publisher": "Cino Group",
        "url": "https://www.cino.com.tw/cn/products/cordless_cn/F680bt/f680bt_ac.html",
        "kind": "html",
        "filename": "cino-f680bt-accessories-2026-07-29.html",
        "required_exact_tokens": ["F680BT", "BT2100", "2.6Ah"],
    },
    {
        "source_id": "koamtac_kdc_accessories",
        "publisher": "KOAMTAC, Inc.",
        "url": "https://koamtac.com/wp-content/uploads/KDC_Accessories.pdf",
        "kind": "pdf",
        "filename": "koamtac-kdc-accessories-2026-07-29.pdf",
        "required_exact_tokens": ["KDC-BAT100", "KDC100/200", "190mAh"],
    },
    {
        "source_id": "orderman5_regulatory_guide",
        "publisher": "Orderman GmbH (part of NCR Corporation)",
        "url": "https://www.orderman.com/wp-content/uploads/Orderman5.pdf",
        "kind": "pdf",
        "filename": "orderman5-regulatory-guide-2026-07-29.pdf",
        "required_exact_tokens": ["5555-0105-8801", "NCR Orderman5 Battery Pack", "NCR Orderman5"],
    },
]


class VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.hidden_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() in {"script", "style", "noscript"}:
            self.hidden_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript"} and self.hidden_depth:
            self.hidden_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self.hidden_depth:
            self.parts.append(data)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalized_text(path: Path, kind: str) -> str:
    if kind == "pdf":
        reader = PdfReader(path)
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    else:
        raw = path.read_bytes()
        decoded = raw.decode("utf-8", errors="replace")
        parser = VisibleTextParser()
        parser.feed(decoded)
        text = " ".join(parser.parts)
    return re.sub(r"\s+", " ", text).strip()


def download(url: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "microchips.by-catalog-evidence/1.0 (+https://microchips.by/)",
            "Accept": "text/html,application/pdf;q=0.9,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true", help="redownload official sources")
    args = parser.parse_args()

    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    records = []
    for source in SOURCES:
        path = SNAPSHOT_DIR / source["filename"]
        refreshed = args.refresh or not path.exists()
        if refreshed:
            payload = download(source["url"])
            if source["kind"] == "pdf" and not payload.startswith(b"%PDF-"):
                raise SystemExit(f"{source['source_id']}: response is not a PDF")
            if source["kind"] == "html" and b"<html" not in payload[:5000].lower():
                raise SystemExit(f"{source['source_id']}: response is not HTML")
            path.write_bytes(payload)

        text = normalized_text(path, source["kind"])
        token_counts = {token: text.casefold().count(token.casefold()) for token in source["required_exact_tokens"]}
        missing = [token for token, count in token_counts.items() if count == 0]
        if missing:
            raise SystemExit(f"{source['source_id']}: snapshot lacks exact tokens: {', '.join(missing)}")

        records.append({
            "source_id": source["source_id"],
            "publisher": source["publisher"],
            "source_url": source["url"],
            "source_kind": f"official_manufacturer_{source['kind']}",
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
