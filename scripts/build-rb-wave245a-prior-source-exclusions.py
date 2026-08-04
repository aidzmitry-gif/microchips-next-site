#!/usr/bin/env python3
"""Snapshot all structured source URLs and hashes before Wave245A."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs/audits/generated/rb-wave245a-prior-source-exclusions.json"
URL_KEYS = {"source_url", "image_url", "asset_url"}
HASH_KEYS = {"source_snapshot_sha256", "snapshot_sha256", "source_sha256", "image_sha256", "asset_sha256"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def walk(value: object, origin: str, urls: list[dict[str, str]], hashes: list[dict[str, str]]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in URL_KEYS and isinstance(item, str) and item.strip():
                urls.append({"value": item.strip(), "origin": origin})
            if key in HASH_KEYS and isinstance(item, str) and len(item.strip()) == 64:
                hashes.append({"value": item.strip().lower(), "origin": origin})
            walk(item, origin, urls, hashes)
    elif isinstance(value, list):
        for item in value:
            walk(item, origin, urls, hashes)


def main() -> None:
    candidates: list[Path] = []
    for base in (ROOT / "docs/audits/generated", ROOT / "docs/imports"):
        candidates.extend(base.glob("*.csv")); candidates.extend(base.glob("*.json"))
    candidates.extend((ROOT / "docs/audits/sources").glob("**/registry.json"))
    candidates = sorted({path for path in candidates if "wave245a" not in path.name.lower()})
    urls: list[dict[str, str]] = []; hashes: list[dict[str, str]] = []; scanned = []
    for path in candidates:
        origin = path.relative_to(ROOT).as_posix()
        try:
            if path.suffix == ".csv":
                with path.open(encoding="utf-8-sig", newline="") as handle:
                    payload: object = list(csv.DictReader(handle))
            else:
                payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError, csv.Error):
            continue
        before = (len(urls), len(hashes)); walk(payload, origin, urls, hashes)
        if before != (len(urls), len(hashes)):
            scanned.append({"path": origin, "sha256": sha(path)})
    unique_urls = sorted({(row["value"], row["origin"]) for row in urls})
    unique_hashes = sorted({(row["value"], row["origin"]) for row in hashes})
    OUTPUT.write_text(json.dumps({
        "schema_version": 1, "wave": "wave245a_prior_source_exclusions", "scanned_files": scanned,
        "source_urls": [{"value": value, "origin": origin} for value, origin in unique_urls],
        "snapshot_sha256": [{"value": value, "origin": origin} for value, origin in unique_hashes],
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"files": len(scanned), "urls": len(unique_urls), "hashes": len(unique_hashes)}, sort_keys=True))


if __name__ == "__main__":
    main()
