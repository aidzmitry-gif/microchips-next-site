#!/usr/bin/env python3
"""Pin primary OEM snapshots for Wave204 industrial remote-control batteries."""

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
SNAPSHOT_DIR = ROOT / "docs/audits/sources/wave204-remote-control"
INDEX = SNAPSHOT_DIR / "snapshot-index.json"
CHECKED_AT = "2026-07-29"

SOURCES = [
    {
        "source_id": "autec_mbm06mh_manual",
        "publisher": "AUTEC Srl",
        "url": "https://store.autecsafety.com/get-product-attachment/?file=920&language=106",
        "kind": "pdf",
        "filename": "autec-mbm06mh-manual-2026-07-29.pdf",
        "required_exact_tokens": ["MBM06MH", "Ni-MH", "7.2V", "750mAh"],
    },
    {
        "source_id": "autec_nc_mh0707l_manual",
        "publisher": "AUTEC Srl",
        "url": "https://store.autecsafety.com/get-product-attachment/?file=902&language=106",
        "kind": "pdf",
        "filename": "autec-nc-mh0707l-manual-2026-07-29.pdf",
        "required_exact_tokens": ["NC0707L", "MH0707L", "NiCd 7.2 Vdc (0.7 Ah)", "NiMH 7.2 Vdc (1.3 Ah)"],
    },
    {
        "source_id": "autec_official_battery_store",
        "publisher": "AUTEC Srl",
        "url": "https://store.autecsafety.com/en/batteries/",
        "kind": "html",
        "filename": "autec-official-battery-store-2026-07-29.html",
        "required_exact_tokens": ["LBM02MH", "MBM06MH", "MH0707L"],
    },
    {
        "source_id": "autec_official_lithium_store",
        "publisher": "AUTEC Srl",
        "url": "https://store.autecsafety.com/en/li-ion-battery/",
        "kind": "html",
        "filename": "autec-official-lithium-store-2026-07-29.html",
        "required_exact_tokens": ["AIRBM3V7L", "LI BATTERY", "LPM02", "LI-ION BATTERY"],
    },
    {
        "source_id": "elca_official_battery_store",
        "publisher": "ELCA Srl",
        "url": "https://store.elcaradio.com/en/page/2",
        "kind": "html",
        "filename": "elca-official-battery-store-2026-07-29.html",
        "required_exact_tokens": ["PINC-07MH", "0401BA000112", "PINC-GEH", "0401BA000113"],
    },
    {
        "source_id": "hiab_red_parts_batteries",
        "publisher": "Hiab",
        "url": "https://webshop.hiab.com/en/hiab-red-parts/",
        "kind": "html",
        "filename": "hiab-red-parts-batteries-2026-07-29.html",
        "required_exact_tokens": ["9836721B", "3786692B", "9847669B", "COMBIDRIVE BATTERY", "XS DRIVE BATTERY", "HIDRIVE BATTERY"],
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
        text = "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)
    else:
        parser = VisibleTextParser()
        parser.feed(path.read_bytes().decode("utf-8", errors="replace"))
        text = " ".join(parser.parts)
        # Some official shops render product cards from embedded JSON. Exact
        # tokens in that first-party response remain useful pinned evidence.
        text += " " + path.read_bytes().decode("utf-8", errors="replace")
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
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    records = []
    for source in SOURCES:
        path = SNAPSHOT_DIR / source["filename"]
        if args.refresh or not path.exists():
            payload = download(source["url"])
            if source["kind"] == "pdf" and not payload.startswith(b"%PDF-"):
                raise SystemExit(f"{source['source_id']}: response is not PDF")
            if source["kind"] == "html" and b"<html" not in payload[:10000].lower():
                raise SystemExit(f"{source['source_id']}: response is not HTML")
            path.write_bytes(payload)

        text = normalized_text(path, source["kind"])
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
