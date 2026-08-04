#!/usr/bin/env python3
"""Find company-owned legacy images only through unique exact product names.

The output is a review queue, never an import approval. Every candidate still
requires exact-model visual verification and the existing media import gates.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path


def key(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "").casefold().replace("ё", "е")
    return re.sub(r"[^\w]+", "", value, flags=re.UNICODE)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def build(manifest_path: Path, queue_path: Path, legacy_path: Path, output: Path) -> dict[str, int]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    products = manifest.get("products")
    if not isinstance(products, list):
        raise ValueError("Manifest requires products")
    queue = read_csv(queue_path)
    legacy = read_csv(legacy_path)
    if not queue or not {"product_external_id", "name"}.issubset(queue[0]):
        raise ValueError("Queue requires product_external_id and name")
    required_legacy = {"legacy_element_id", "name", "preview_picture_file_id", "detail_picture_file_id"}
    if not legacy or not required_legacy.issubset(legacy[0]):
        raise ValueError("Legacy products have an unexpected header")

    by_external: dict[str, dict[str, str]] = {}
    for row in queue:
        external_id = row["product_external_id"].strip()
        if not external_id or external_id in by_external:
            raise ValueError("Queue external IDs must be unique and non-empty")
        by_external[external_id] = row
    by_name: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in legacy:
        normalized = key(row.get("name", ""))
        if normalized:
            by_name[normalized].append(row)

    rows: list[dict[str, str]] = []
    ambiguous = 0
    missing = 0
    no_media = 0
    seen: set[str] = set()
    for product in products:
        if not isinstance(product, dict):
            raise ValueError("Manifest product must be an object")
        external_id = str(product.get("external_id", "")).strip()
        if not external_id or external_id in seen:
            raise ValueError("Manifest external IDs must be unique and non-empty")
        seen.add(external_id)
        current = by_external.get(external_id)
        if current is None:
            missing += 1
            continue
        matches = by_name.get(key(current["name"]), [])
        if len(matches) > 1:
            ambiguous += 1
            continue
        if not matches:
            missing += 1
            continue
        legacy_row = matches[0]
        preview = legacy_row.get("preview_picture_file_id", "").strip()
        detail = legacy_row.get("detail_picture_file_id", "").strip()
        if not preview or not detail:
            no_media += 1
            continue
        rows.append({
            "external_id": external_id,
            "current_name": current["name"],
            "legacy_element_id": legacy_row["legacy_element_id"],
            "legacy_name": legacy_row["name"],
            "preview_picture_file_id": preview,
            "detail_picture_file_id": detail,
            "identity_evidence": "unique_exact_normalized_name",
            "decision": "requires_exact_model_visual_check",
        })

    fields = ["external_id", "current_name", "legacy_element_id", "legacy_name",
              "preview_picture_file_id", "detail_picture_file_id", "identity_evidence", "decision"]
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    summary = {"manifest_products": len(products), "candidates": len(rows),
               "ambiguous_exact_names": ambiguous, "missing_exact_name": missing,
               "exact_match_without_both_media": no_media, "automatic_imports": 0}
    output.with_suffix(".summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--legacy-products", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.manifest, args.queue, args.legacy_products, args.output), ensure_ascii=False))


if __name__ == "__main__":
    main()
