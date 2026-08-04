#!/usr/bin/env python3
"""Acquire and validate the official Verifone VX680 accessory snapshot."""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_URL = "https://go.verifone.com/sv/se/webshop"
SOURCE_DIR = ROOT / "docs/audits/sources/verifone-wave203"
SNAPSHOT = SOURCE_DIR / "verifone-se-webshop-2026-07-29.html"
METADATA = SOURCE_DIR / "verifone-se-webshop-2026-07-29.json"
REQUIRED_TOKENS = ("BPK268-001-01-A", "VX680", "Batteripack")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate(data: bytes) -> dict[str, int]:
    text = data.decode("utf-8", errors="replace")
    counts = {token: text.casefold().count(token.casefold()) for token in REQUIRED_TOKENS}
    missing = [token for token, count in counts.items() if count == 0]
    if missing:
        raise SystemExit("Official HTML lacks required exact tokens: " + ", ".join(missing))
    return counts


def download() -> tuple[bytes, str]:
    request = urllib.request.Request(
        SOURCE_URL,
        headers={
            "User-Agent": "microchips.by-audit/1.0 (+source-evidence; no-crawl)",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "sv-SE,sv;q=0.9,en;q=0.5",
        },
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        status = getattr(response, "status", 200)
        content_type = response.headers.get_content_type()
        if status != 200:
            raise SystemExit(f"Official source returned HTTP {status}")
        if content_type not in {"text/html", "application/xhtml+xml"}:
            raise SystemExit(f"Unexpected official source content type: {content_type}")
        return response.read(), content_type


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Download the current official page even when the pinned snapshot exists.",
    )
    args = parser.parse_args()

    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    acquired = args.refresh or not SNAPSHOT.exists()
    if acquired:
        data, content_type = download()
        token_counts = validate(data)
        SNAPSHOT.write_bytes(data)
    else:
        data = SNAPSHOT.read_bytes()
        content_type = "text/html"
        token_counts = validate(data)

    if acquired:
        metadata = {
            "schema_version": 1,
            "source_url": SOURCE_URL,
            "publisher": "Verifone Sweden AB",
            "source_kind": "official_manufacturer_accessory_catalogue",
            "snapshot_path": SNAPSHOT.relative_to(ROOT).as_posix(),
            "snapshot_sha256": sha256(data),
            "snapshot_bytes": len(data),
            "content_type": content_type,
            "required_exact_tokens": list(REQUIRED_TOKENS),
            "token_counts": token_counts,
            "acquired_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "network_refresh_performed": True,
        }
        METADATA.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    else:
        if not METADATA.is_file():
            raise SystemExit("Pinned snapshot metadata is missing")
        metadata = json.loads(METADATA.read_text(encoding="utf-8-sig"))
        expected = {
            "source_url": SOURCE_URL,
            "snapshot_path": SNAPSHOT.relative_to(ROOT).as_posix(),
            "snapshot_sha256": sha256(data),
            "required_exact_tokens": list(REQUIRED_TOKENS),
            "token_counts": token_counts,
        }
        mismatches = {
            key: {"expected": value, "actual": metadata.get(key)}
            for key, value in expected.items()
            if metadata.get(key) != value
        }
        if mismatches:
            raise SystemExit(
                "Pinned snapshot metadata mismatch: "
                + json.dumps(mismatches, ensure_ascii=False, sort_keys=True)
            )
    print(json.dumps(metadata, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
