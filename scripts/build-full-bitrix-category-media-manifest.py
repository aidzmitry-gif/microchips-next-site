#!/usr/bin/env python3
"""Build an exact Bitrix-element media extraction manifest for one SEO category.

The result is an extraction queue, not a visual-verification or indexing
approval. Only `legacy_only_draft_candidate` rows are selected: their media can
be shown on the same namespaced Bitrix product as a noindex legacy preview.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path


REQUIRED_INDEX_FIELDS = {
    "legacy_element_id",
    "active",
    "name",
    "preview_picture_file_id",
    "detail_picture_file_id",
}


def read_index(path: Path) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows or not REQUIRED_INDEX_FIELDS.issubset(rows[0]):
        raise ValueError("Full Bitrix media index has an unexpected schema")
    result: dict[str, dict[str, str]] = {}
    for row in rows:
        legacy_id = row["legacy_element_id"].strip()
        if not legacy_id.isdigit() or legacy_id in result:
            raise ValueError("Media index IDs must be unique decimal values")
        result[legacy_id] = row
    return result


def build(
    staging_path: Path,
    index_path: Path,
    category: str | list[str],
    output: Path,
) -> dict[str, object]:
    staging = json.loads(staging_path.read_text(encoding="utf-8-sig"))
    source_records = staging.get("records")
    if not isinstance(source_records, list) or not source_records:
        raise ValueError("Full Bitrix staging manifest requires records")
    media_by_id = read_index(index_path)

    categories = [category] if isinstance(category, str) else list(dict.fromkeys(category))
    if not categories or any(not item.strip() for item in categories):
        raise ValueError("At least one non-empty category is required")
    scoped = [
        row for row in source_records
        if isinstance(row, dict) and row.get("target_category_external_id") in categories
    ]
    if not scoped:
        raise ValueError(f"No staging records found for categories {', '.join(categories)}")

    transfer_statuses = Counter(str(row.get("transfer_status", "")) for row in scoped)
    records: list[dict[str, str]] = []
    missing_index = 0
    without_media = 0
    for row in scoped:
        if row.get("transfer_status") != "legacy_only_draft_candidate":
            continue
        legacy_id = str(row.get("bitrix_id", "")).strip()
        media = media_by_id.get(legacy_id)
        if media is None:
            missing_index += 1
            continue
        if media["active"].strip().upper() != "Y":
            raise ValueError(f"Safe staging row {legacy_id} is inactive in the media index")
        preview = media["preview_picture_file_id"].strip()
        detail = media["detail_picture_file_id"].strip()
        if not preview and not detail:
            without_media += 1
            continue
        records.append({
            "legacy_element_id": legacy_id,
            "legacy_name": str(row.get("name", "")).strip() or media["name"].strip(),
            "preview_picture_file_id": preview,
            "detail_picture_file_id": detail,
            "target_category_external_id": str(row.get("target_category_external_id")),
            "transfer_status": "legacy_only_draft_candidate",
            "identity_evidence": "exact_same_bitrix_element_only",
            "publication_scope": "same_namespaced_product_noindex_preview",
        })

    records.sort(key=lambda row: int(row["legacy_element_id"]))
    if len({row["legacy_element_id"] for row in records}) != len(records):
        raise ValueError("Output repeats a Bitrix element")
    summary: dict[str, object] = {
        "categories": categories,
        "category_record_counts": dict(sorted(Counter(
            str(row.get("target_category_external_id", "")) for row in scoped
        ).items())),
        "scoped_staging_records": len(scoped),
        "transfer_statuses": dict(sorted(transfer_statuses.items())),
        "safe_legacy_drafts": transfer_statuses.get("legacy_only_draft_candidate", 0),
        "records_with_media_reference": len(records),
        "unique_selected_file_references": len({
            row["detail_picture_file_id"] or row["preview_picture_file_id"] for row in records
        }),
        "safe_drafts_without_media_reference": without_media,
        "safe_drafts_missing_media_index": missing_index,
        "canonical_one_c_media_imports": 0,
        "indexable_pages_changed": 0,
    }
    payload = {
        "schema_version": 1,
        "purpose": "Exact Bitrix-element media extraction for same-product noindex preview only.",
        "source_staging_manifest": staging_path.name,
        "source_media_index": index_path.name,
        "summary": summary,
        "records": records,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    selected_file_ids = sorted(
        {row["detail_picture_file_id"] or row["preview_picture_file_id"] for row in records},
        key=int,
    )
    output.with_suffix(".file-ids.txt").write_text("\n".join(selected_file_ids) + "\n", encoding="utf-8")
    output.with_suffix(".summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--staging", type=Path, required=True)
    parser.add_argument("--media-index", type=Path, required=True)
    parser.add_argument("--category", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.staging, args.media_index, args.category, args.output), ensure_ascii=False))


if __name__ == "__main__":
    main()
