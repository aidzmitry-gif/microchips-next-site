#!/usr/bin/env python3
"""Pin exact first-party Casil and ROBITON product pages for Wave208-S."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import urllib.request
from html import unescape
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_DIR = ROOT / "docs/audits/sources/wave208s-stationary"
INDEX = SNAPSHOT_DIR / "snapshot-index.json"
CHECKED_AT = "2026-07-29"


def casil(external_id: str, model: str, detail: str, voltage: str, capacity: str) -> dict:
    return {
        "external_id": external_id,
        "manufacturer": "Casil",
        "publisher": "Chee Yuen Plastic Products (Huizhou) Co., Ltd.",
        "model": model,
        "url": f"https://en.casilbattery.com/product_detail/{detail}.html",
        "filename": f"casil-{model.casefold()}-2026-07-29.html",
        # Several legacy Chee Yuen detail pages retain the exact model title
        # but no longer render their technical table.  That is sufficient for
        # manufacturer+MPN identity only; voltage/capacity remain unsupported.
        "required_tokens": [model, "Chee Yuen"],
    }


def robiton(external_id: str, model: str, product_id: str, voltage: str, capacity: str) -> dict:
    return {
        "external_id": external_id,
        "manufacturer": "ROBITON",
        "publisher": "ROBITON",
        "model": model,
        "url": f"https://www.robiton.ru/product/{product_id}/",
        "filename": f"robiton-{model.casefold()}-2026-07-29.html",
        "required_tokens": [model, voltage, capacity, "ROBITON"],
    }


SOURCES = [
    casil("bitrix:1397", "CA1208", "1409843489126408192", "12V", "0.8AH"),
    casil("bitrix:1410", "CA613", "53", "6V", "1.3AH"),
    casil("bitrix:1472", "CA12120", "89", "12V", "12AH"),
    casil("bitrix:1473", "CA6120", "68", "6V", "12AH"),
    casil("bitrix:1536", "CA12180", "70", "12V", "18AH"),
    casil("bitrix:1547", "CA1222", "41", "12V", "2.2AH"),
    casil("bitrix:1555", "CA628", "1409840518925725696", "6V", "2.8AH"),
    casil("bitrix:1576", "CA12260", "72", "12V", "26AH"),
    casil("bitrix:1582", "CA1233", "61", "12V", "3.3AH"),
    casil("bitrix:1583", "CA633", "21", "6V", "3.3AH"),
    robiton("bitrix:1399", "VRLA12-0.8", "07629", "12 В", "0,8 Ач"),
    robiton("bitrix:1413", "VRLA12-1.3", "07630", "12 В", "1,3 Ач"),
    robiton("bitrix:1414", "VRLA6-1.3", "07624", "6 В", "1,3 Ач"),
    robiton("bitrix:1491", "VRLA12-12", "07635", "12 В", "12 Ач"),
    robiton("bitrix:1492", "VRLA6-12", "07628", "6 В", "12 Ач"),
    robiton("bitrix:1544", "VRLA12-18", "07636", "12 В", "18 Ач"),
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalized(value: str) -> str:
    return re.sub(r"[^0-9a-zа-я]+", "", value.casefold().replace("ё", "е"))


def extract_text(payload: bytes) -> str:
    text = payload.decode("utf-8", errors="replace")
    text = re.sub(r"<script\b[^>]*>.*?</script>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
    text = unescape(re.sub(r"<[^>]+>", " ", text))
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
    records = []
    for source in SOURCES:
        path = SNAPSHOT_DIR / source["filename"]
        if args.refresh or not path.exists():
            payload = download(source["url"])
            if b"<html" not in payload[:4096].lower() and b"<!doctype html" not in payload[:4096].lower():
                raise SystemExit(f"{source['external_id']}: response is not HTML")
            path.write_bytes(payload)
        text = extract_text(path.read_bytes())
        compact = normalized(text)
        token_counts = {token: compact.count(normalized(token)) for token in source["required_tokens"]}
        missing = [token for token, count in token_counts.items() if count == 0]
        if missing:
            raise SystemExit(f"{source['external_id']}: exact official page lacks {', '.join(missing)}")
        records.append({
            "external_id": source["external_id"],
            "manufacturer": source["manufacturer"],
            "model": source["model"],
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
        json.dumps({"schema_version": 1, "checked_at": CHECKED_AT, "sources": records}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"sources": len(records), "index": INDEX.relative_to(ROOT).as_posix()}, ensure_ascii=False))


if __name__ == "__main__":
    main()
