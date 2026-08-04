#!/usr/bin/env python3
"""Freeze Wave230 description targets from Wave229 verified media and the post-apply queue."""

from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MEDIA = ROOT / "docs/imports/rb-reviewed-legacy-preview-media-wave229-2026-07-29.json"
QUEUE = ROOT / "docs/audits/generated/rb-enrichment-queue-wave229.csv"
OUTPUT = ROOT / "docs/audits/generated/rb-wave230-description-targets.csv"


def main() -> None:
    media = json.loads(MEDIA.read_text(encoding="utf-8-sig"))["images"]
    with QUEUE.open(encoding="utf-8-sig", newline="") as handle:
        queue = {row["product_external_id"]: row for row in csv.DictReader(handle)}

    rows = []
    for image in media:
        row = queue.get(image["external_id"])
        if row is None or row["has_applied_description"] != "false":
            continue
        if row["has_verified_published_image"] != "true":
            raise RuntimeError(f"{image['external_id']} lost its verified published image")
        if row["mpn"] != image["mpn"]:
            raise RuntimeError(f"{image['external_id']} MPN drift between media and queue")
        rows.append(
            {
                "product_external_id": image["external_id"],
                "name": row["name"],
                "manufacturer": row["manufacturer"],
                "mpn": row["mpn"],
                "category_external_id": row["category_external_id"],
                "category_name": row["category_name"],
                "media_id": image["media_id"],
                "media_sha256": image["content_sha256"],
                "identity_evidence_level": image["identity_evidence_level"],
            }
        )

    rows.sort(key=lambda item: (item["manufacturer"].casefold(), item["mpn"].casefold(), item["product_external_id"]))
    if len(rows) != 88 or len({row["product_external_id"] for row in rows}) != 88:
        raise RuntimeError(f"Wave230 frozen denominator drift: expected 88, got {len(rows)}")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({"targets": len(rows), "database_apply": False}))


if __name__ == "__main__":
    main()
