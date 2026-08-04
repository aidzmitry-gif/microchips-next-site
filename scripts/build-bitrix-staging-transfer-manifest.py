#!/usr/bin/env python3
"""Build a complete, evidence-only Bitrix staging transfer manifest.

The manifest preserves the old RB catalogue before cleanup. It never decides
publication, never renders legacy HTML, and never creates a product missing
from 1C. Ambiguous links are retained as reviewable evidence instead of being
silently discarded or applied.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--products", type=Path, required=True)
    parser.add_argument("--content", type=Path, required=True)
    parser.add_argument("--matches", type=Path, required=True)
    parser.add_argument("--safe-evidence", type=Path, required=True)
    parser.add_argument("--site-state", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    args = parser.parse_args()

    products = [
        row for row in read_csv(args.products)
        if row.get("is_first_focus_candidate", "").lower() == "true"
    ]
    contents = {row["legacy_element_id"].strip(): row for row in read_csv(args.content)}
    matches = {row["Bitrix ID"].strip(): row for row in read_csv(args.matches)}
    safe_payload = json.loads(args.safe_evidence.read_text(encoding="utf-8-sig"))
    safe_ids = {
        clean(row.get("legacy_element_id")): clean(row.get("one_c_external_id"))
        for row in safe_payload.get("records", [])
    }
    site_rows = json.loads(args.site_state.read_text(encoding="utf-8-sig"))
    site_by_external_id = {
        clean(row.get("product", {}).get("external_id")): row
        for row in site_rows
        if clean(row.get("product", {}).get("external_id"))
    }

    mapped_groups: dict[str, list[str]] = defaultdict(list)
    for product in products:
        legacy_id = clean(product.get("legacy_element_id"))
        one_c_id = clean(matches.get(legacy_id, {}).get("1С-код"))
        if one_c_id:
            mapped_groups[one_c_id].append(legacy_id)

    records: list[dict[str, object]] = []
    for product in products:
        legacy_id = clean(product.get("legacy_element_id"))
        content = contents.get(legacy_id)
        if content is None:
            raise ValueError(f"Missing content evidence for legacy element {legacy_id}")
        match = matches.get(legacy_id, {})
        one_c_id = clean(match.get("1С-код"))
        site_row = site_by_external_id.get(one_c_id)
        category_ids = sorted({
            clean(category.get("external_id"))
            for category in (site_row or {}).get("categories", [])
            if clean(category.get("external_id"))
        })
        is_safe = safe_ids.get(legacy_id) == one_c_id and bool(one_c_id)

        if clean(product.get("active")).upper() != "Y":
            status = "excluded_inactive_legacy"
        elif not one_c_id:
            status = "hold_missing_1c_identity"
        elif site_row is None:
            status = "hold_missing_rb_site_product"
        elif "seo:electronic-components" in category_ids:
            status = "scope_excluded_electronics"
        elif is_safe:
            status = "strict_mapped_evidence"
        elif len(mapped_groups[one_c_id]) > 1:
            status = "candidate_duplicate_group"
        else:
            status = "candidate_mapped_evidence"

        raw_text = clean(content.get("detail_text")) or clean(content.get("preview_text"))
        records.append({
            "legacy_element_id": legacy_id,
            "legacy_iblock_id": clean(product.get("legacy_iblock_id")),
            "legacy_name": clean(product.get("name")),
            "legacy_url_candidate": clean(product.get("legacy_url_candidate")),
            "legacy_primary_section_path": clean(product.get("primary_section_path")),
            "legacy_matched_section_paths": clean(product.get("matched_section_paths")),
            "preview_picture_file_id": clean(product.get("preview_picture_file_id")),
            "detail_picture_file_id": clean(product.get("detail_picture_file_id")),
            "preview_text_type": clean(content.get("preview_text_type")),
            "preview_text": clean(content.get("preview_text")),
            "detail_text_type": clean(content.get("detail_text_type")),
            "detail_text": clean(content.get("detail_text")),
            "legacy_text_sha256": hashlib.sha256(raw_text.encode("utf-8")).hexdigest() if raw_text else "",
            "one_c_external_id": one_c_id,
            "one_c_name": clean(match.get("1С-наименование")),
            "one_c_article": clean(match.get("1С-артикул")),
            "legacy_price": clean(match.get("Цена сайта")),
            "one_c_price": clean(match.get("1С-цена")),
            "match_method": clean(match.get("match_method")),
            "match_score": clean(match.get("match_score")),
            "mapped_legacy_count": len(mapped_groups.get(one_c_id, [])) if one_c_id else 0,
            "rb_site_product_id": (site_row or {}).get("id"),
            "rb_is_published": bool((site_row or {}).get("is_published")),
            "rb_category_external_ids": category_ids,
            "transfer_status": status,
            "render_legacy_html": False,
            "change_publication": False,
        })

    records.sort(key=lambda row: int(row["legacy_element_id"]))
    if len({row["legacy_element_id"] for row in records}) != len(records):
        raise ValueError("Duplicate legacy_element_id in focus manifest")

    statuses = Counter(str(row["transfer_status"]) for row in records)
    summary = {
        "focus_rows": len(records),
        "active_rows": sum(1 for row in products if clean(row.get("active")).upper() == "Y"),
        "rows_with_detail_text": sum(1 for row in records if row["detail_text"]),
        "rows_with_any_media_reference": sum(
            1 for row in records
            if row["preview_picture_file_id"] or row["detail_picture_file_id"]
        ),
        "unique_mapped_one_c_products": len(mapped_groups),
        "status_counts": dict(sorted(statuses.items())),
        "renderable_rows": 0,
        "publication_changes": 0,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({
        "schema_version": 1,
        "purpose": "Complete noindex Bitrix staging evidence before cleanup",
        "records": records,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
