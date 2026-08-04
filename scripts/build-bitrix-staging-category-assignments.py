#!/usr/bin/env python3
"""Build safe product-to-legacy-category links from the staging snapshot."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path


ALLOWED_STATUSES = {
    "strict_mapped_evidence",
    "candidate_mapped_evidence",
    "candidate_duplicate_group",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--sections", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    args = parser.parse_args()

    payload = json.loads(args.manifest.read_text(encoding="utf-8-sig"))
    with args.sections.open("r", encoding="utf-8-sig", newline="") as handle:
        sections = list(csv.DictReader(handle))
    section_by_path = {
        row["source_section_path"].strip().strip("/"): row["legacy_section_id"].strip()
        for row in sections
    }

    pairs: dict[tuple[str, str], str] = {}
    selection_reasons = Counter()
    skipped_statuses = Counter()
    for record in payload.get("records", []):
        status = str(record.get("transfer_status", ""))
        if status not in ALLOWED_STATUSES:
            skipped_statuses[status] += 1
            continue
        product_id = str(record.get("one_c_external_id", "")).strip()
        primary = str(record.get("legacy_primary_section_path", "")).strip().strip("/")
        target = section_by_path.get(primary)
        reason = "primary_section"
        if target is None:
            matched = [
                part.strip().strip("/")
                for part in str(record.get("legacy_matched_section_paths", "")).split("|")
                if part.strip()
            ]
            candidates = [section_by_path[path] for path in matched if path in section_by_path]
            target = candidates[0] if candidates else None
            reason = "additional_membership_fallback"
        if not product_id or target is None:
            raise ValueError(f"Mapped legacy row {record.get('legacy_element_id')} has no category target")
        pairs[(product_id, target)] = reason
        selection_reasons[reason] += 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["product_external_id", "category_external_id"])
        writer.writeheader()
        for product_id, category_id in sorted(pairs):
            writer.writerow({"product_external_id": product_id, "category_external_id": category_id})

    summary = {
        "assignment_rows": len(pairs),
        "unique_products": len({product_id for product_id, _ in pairs}),
        "unique_categories": len({category_id for _, category_id in pairs}),
        "selection_reasons_before_pair_deduplication": dict(selection_reasons),
        "skipped_status_counts": dict(sorted(skipped_statuses.items())),
        "publication_changes": 0,
    }
    args.summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
