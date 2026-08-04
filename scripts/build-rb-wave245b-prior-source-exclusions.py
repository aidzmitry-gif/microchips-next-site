#!/usr/bin/env python3
"""Freeze every pre-Wave245B source URL and local evidence hash."""

from __future__ import annotations

import hashlib
import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs/audits/generated/rb-wave245b-prior-source-exclusions.json"
URL_RE = re.compile(r"https?://[^\s\"'<>),]+")
URL_KEYS = {"source_url", "image_url", "asset_url", "datasheet_url", "product_url"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def structured_urls(value: object) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key in URL_KEYS and isinstance(item, str) and item.startswith(("http://", "https://")):
                found.add(item.strip())
            found.update(structured_urls(item))
    elif isinstance(value, list):
        for item in value:
            found.update(structured_urls(item))
    return found


def main() -> None:
    urls: dict[str, set[str]] = {}
    hashes: dict[str, set[str]] = {}
    scanned: list[dict[str, object]] = []
    candidates = set((ROOT / "docs/audits/sources").rglob("*"))
    candidates.update((ROOT / "docs/audits/generated").glob("*"))
    candidates.update((ROOT / "docs/audits").glob("*.md"))
    candidates.update((ROOT / "docs/imports").glob("*"))
    for path in sorted(candidates):
        if (not path.is_file() or "wave245b" in path.as_posix().casefold()
                or "prior-source-exclusions" in path.name.casefold()):
            continue
        origin = path.relative_to(ROOT).as_posix()
        try:
            digest = sha(path)
        except OSError:
            continue
        hashes.setdefault(digest, set()).add(origin)
        file_urls: set[str] = set()
        if path.suffix.casefold() == ".json":
            try:
                file_urls = structured_urls(json.loads(path.read_text(encoding="utf-8-sig")))
            except (UnicodeError, OSError, json.JSONDecodeError):
                file_urls = set()
        elif path.suffix.casefold() == ".csv":
            try:
                with path.open(encoding="utf-8-sig", newline="") as handle:
                    file_urls = structured_urls(list(csv.DictReader(handle)))
            except (UnicodeError, OSError, csv.Error):
                file_urls = set()
        elif path.suffix.casefold() == ".md":
            try:
                text = path.read_text(encoding="utf-8-sig", errors="strict")
            except (UnicodeError, OSError):
                text = ""
            file_urls = {match.rstrip(".]") for match in URL_RE.findall(text)}
        for url in file_urls:
            urls.setdefault(url, set()).add(origin)
        scanned.append({"path": origin, "sha256": digest, "url_count": len(file_urls)})
    payload = {
        "schema_version": 1,
        "wave": "wave245b_prior_source_exclusions",
        "scope": "all source-tree files plus top-level generated/import/report artifacts before Wave245B; caches excluded",
        "scanned_files": scanned,
        "source_urls": [{"value": value, "origins": sorted(origins)} for value, origins in sorted(urls.items())],
        "snapshot_sha256": [{"value": value, "origins": sorted(origins)} for value, origins in sorted(hashes.items())],
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"files": len(scanned), "urls": len(urls), "hashes": len(hashes)}, sort_keys=True))


if __name__ == "__main__":
    main()
