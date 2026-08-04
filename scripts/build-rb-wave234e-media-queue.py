#!/usr/bin/env python3
"""Build the bounded media-review queue for applied Wave234 identities."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs/imports/rb-verified-oem-identities-wave234c-general-security-2026-07-29.json"
QUEUE = ROOT / "docs/audits/generated/rb-wave234e-general-security-media-queue.csv"
EMPTY_LEDGER = ROOT / "docs/audits/generated/rb-wave234e-empty-reviewed-media-ledger.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-wave234e-general-security-media-queue.summary.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    products = json.loads(MANIFEST.read_text(encoding="utf-8"))["products"]
    if len(products) != 29 or len({row["external_id"] for row in products}) != 29:
        raise SystemExit(f"Wave234-E identity manifest drift: rows={len(products)}")
    with QUEUE.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["product_external_id", "mpn", "model_core", "manufacturer"], lineterminator="\n")
        writer.writeheader()
        for row in products:
            writer.writerow({"product_external_id": row["external_id"], "mpn": row["mpn"], "model_core": "", "manufacturer": row["manufacturer"]})
    with EMPTY_LEDGER.open("w", encoding="utf-8", newline="") as handle:
        csv.DictWriter(handle, fieldnames=["external_id", "media_id"], lineterminator="\n").writeheader()
    summary = {
        "schema_version": 1, "batch": "wave234e_general_security_media_queue", "checked_at": "2026-07-29",
        "input": {"path": MANIFEST.relative_to(ROOT).as_posix(), "sha256": sha256(MANIFEST), "rows": len(products)},
        "queue": {"path": QUEUE.relative_to(ROOT).as_posix(), "sha256": sha256(QUEUE), "rows": len(products)},
        "empty_review_ledger": {"path": EMPTY_LEDGER.relative_to(ROOT).as_posix(), "sha256": sha256(EMPTY_LEDGER), "rows": 0},
        "database_mutations": 0,
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"queue_rows": len(products)}))


if __name__ == "__main__":
    main()
