#!/usr/bin/env python3
"""Build the auditable intersection for safe catalogue preview waves.

It does not publish or alter any data. A row is a candidate only when a source
manifest entry, a reviewed Bitrix-to-1C link and both legacy image references
exist. Editorial facts and image contents still require their own gates.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--matches", type=Path, required=True)
    parser.add_argument("--legacy-products", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    source_manifest = json.loads(args.sources.read_text(encoding="utf-8"))
    products = source_manifest.get("products")
    if not isinstance(products, list):
        raise ValueError("source manifest requires products")
    matches = read_csv(args.matches)
    legacy = read_csv(args.legacy_products)
    needed_match_columns = {"Bitrix ID", "1С-код", "brand_ok", "confidence"}
    if not matches or not needed_match_columns.issubset(matches[0]):
        raise ValueError("match CSV has an unexpected header")
    if not legacy or not {"legacy_element_id", "preview_picture_file_id", "detail_picture_file_id"}.issubset(legacy[0]):
        raise ValueError("legacy product CSV has an unexpected header")

    by_external = {row["1С-код"].strip(): row for row in matches if row.get("1С-код", "").strip()}
    by_legacy = {row["legacy_element_id"].strip(): row for row in legacy}
    rows: list[dict[str, str]] = []
    for source in products:
        if not isinstance(source, dict):
            continue
        external_id = str(source.get("external_id", "")).strip()
        match = by_external.get(external_id)
        if match is None:
            continue
        legacy_row = by_legacy.get(match["Bitrix ID"].strip())
        if legacy_row is None:
            continue
        preview = legacy_row.get("preview_picture_file_id", "").strip()
        detail = legacy_row.get("detail_picture_file_id", "").strip()
        if not preview or not detail:
            continue
        rows.append({
            "external_id": external_id,
            "manufacturer": str(source.get("manufacturer", "")).strip(),
            "mpn": str(source.get("mpn", "")).strip(),
            "source_url": str(source.get("source_url", "")).strip(),
            "legacy_element_id": match["Bitrix ID"].strip(),
            "link_confidence": match["confidence"].strip(),
            "link_brand_ok": match["brand_ok"].strip(),
            "preview_picture_file_id": preview,
            "detail_picture_file_id": detail,
            "decision": "requires_model_specific_facts_and_visual_image_check",
        })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else [
            "external_id", "manufacturer", "mpn", "source_url", "legacy_element_id",
            "link_confidence", "link_brand_ok", "preview_picture_file_id", "detail_picture_file_id", "decision",
        ])
        writer.writeheader()
        writer.writerows(sorted(rows, key=lambda row: (row["manufacturer"].lower(), row["mpn"].lower())))
    print(json.dumps({"candidates": len(rows), "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
