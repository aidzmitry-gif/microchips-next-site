#!/usr/bin/env python3
"""Build a deterministic, no-repeat RB B2B catalogue enrichment queue."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path


B2B_CATEGORY_PRIORITY = {
    "seo:batteries-ups": 60,
    "seo:batteries-industrial": 60,
    "seo:ups-systems": 60,
    "seo:batteries-traction": 55,
    "seo:power-systems": 55,
    "seo:power-supplies": 55,
    "seo:warehouse-equipment": 55,
    "seo:replacement-medical": 55,
    "seo:power-converters": 50,
    "seo:chargers": 45,
    "seo:replacement-tools": 40,
}
MODEL_LIKE = re.compile(
    r"(?<![\w])(?=[A-Za-zА-Яа-яЁё0-9./_-]{3,}\b)"
    r"(?=[A-Za-zА-Яа-яЁё0-9./_-]*\d)[A-Za-zА-Яа-яЁё0-9][A-Za-zА-Яа-яЁё0-9./_-]*"
)


def truth(value: str | None) -> bool:
    return (value or "").strip().lower() == "true"


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    return list(csv.DictReader(path.read_text(encoding="utf-8-sig").splitlines()))


def read_unique_external_ids(path: Path, label: str) -> tuple[list[dict[str, str]], list[str]]:
    rows = read_csv(path)
    if rows and "product_external_id" not in rows[0]:
        raise SystemExit(f"{label} input must contain product_external_id")
    ids = [(row.get("product_external_id") or "").strip() for row in rows]
    if any(not external_id for external_id in ids):
        raise SystemExit(f"{label} input contains an empty product_external_id")
    if len(set(ids)) != len(ids):
        raise SystemExit(f"{label} input repeats product_external_id")
    return rows, ids


def score(row: dict[str, str]) -> tuple[int, list[str]]:
    result = B2B_CATEGORY_PRIORITY[row["category_external_id"]]
    reasons = ["b2b_category"]
    if not truth(row.get("identity_ready")):
        result += 30
        reasons.append("identity_missing")
    if not truth(row.get("has_applied_description")):
        result += 20
        reasons.append("official_description_missing")
    if int(row.get("technical_fact_count") or 0) == 0:
        result += 15
        reasons.append("technical_facts_missing")
    if not truth(row.get("has_displayable_preview_image")):
        result += 12
        reasons.append("display_image_missing")
    if not truth(row.get("has_verified_published_image")):
        result += 8
        reasons.append("rights_verified_image_missing")
    if not (row.get("manufacturer") or "").strip():
        result += 8
        reasons.append("manufacturer_missing")
    if not (row.get("mpn") or "").strip() and not (row.get("sku") or "").strip():
        result += 7
        reasons.append("stable_identifier_missing")
    if MODEL_LIKE.search(row.get("name") or ""):
        result += 5
        reasons.append("model_candidate_present")
    return result, reasons


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--holds", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--expected-input-sha256", required=True)
    parser.add_argument("--expected-hold-sha256", required=True)
    parser.add_argument("--expected-records", type=int, required=True)
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument(
        "--processed",
        "--exclude",
        dest="processed",
        type=Path,
        help="Optional CSV of already processed product_external_id values to exclude",
    )
    parser.add_argument(
        "--expected-processed-sha256",
        "--expected-exclude-sha256",
        dest="expected_processed_sha256",
    )
    parser.add_argument(
        "--expected-processed-records",
        "--expected-exclude-records",
        dest="expected_processed_records",
        type=int,
    )
    args = parser.parse_args()

    if args.limit < 1:
        raise SystemExit("limit must be positive")
    processed_options = (
        args.processed,
        args.expected_processed_sha256,
        args.expected_processed_records,
    )
    if any(value is not None for value in processed_options) and not all(
        value is not None for value in processed_options
    ):
        raise SystemExit(
            "processed exclusion requires --processed, --expected-processed-sha256 "
            "and --expected-processed-records together"
        )
    if args.expected_processed_records is not None and args.expected_processed_records < 0:
        raise SystemExit("expected processed records cannot be negative")
    input_hash = file_hash(args.input)
    hold_hash = file_hash(args.holds)
    if input_hash != args.expected_input_sha256.lower():
        raise SystemExit("input SHA-256 does not match the pinned value")
    if hold_hash != args.expected_hold_sha256.lower():
        raise SystemExit("hold SHA-256 does not match the pinned value")

    rows = read_csv(args.input)
    if len(rows) != args.expected_records:
        raise SystemExit(f"expected {args.expected_records} readiness rows, got {len(rows)}")
    source_external_ids = [(row.get("product_external_id") or "").strip() for row in rows]
    if any(not external_id for external_id in source_external_ids):
        raise SystemExit("readiness input contains an empty product_external_id")
    if any(
        external_id != (row.get("product_external_id") or "")
        for row, external_id in zip(rows, source_external_ids, strict=True)
    ):
        raise SystemExit("readiness input contains surrounding whitespace in product_external_id")
    if len(set(source_external_ids)) != len(rows):
        raise SystemExit("readiness input repeats product_external_id")

    _, hold_ids = read_unique_external_ids(args.holds, "hold")
    holds = set(hold_ids)

    processed_path = None
    processed_hash = None
    processed_ids: list[str] = []
    if args.processed is not None:
        processed_path = str(args.processed)
        processed_hash = file_hash(args.processed)
        if processed_hash != args.expected_processed_sha256.lower():
            raise SystemExit("processed exclusion SHA-256 does not match the pinned value")
        _, processed_ids = read_unique_external_ids(args.processed, "processed exclusion")
        if len(processed_ids) != args.expected_processed_records:
            raise SystemExit(
                f"expected {args.expected_processed_records} processed exclusion rows, "
                f"got {len(processed_ids)}"
            )
    processed = set(processed_ids)

    source_ids = set(source_external_ids)
    unknown_processed = processed - source_ids
    if unknown_processed:
        raise SystemExit(
            "processed exclusion contains product_external_id absent from readiness input: "
            + ", ".join(sorted(unknown_processed)[:5])
        )
    overlap = holds & processed
    if overlap:
        raise SystemExit(
            "hold and processed exclusion inputs overlap: "
            + ", ".join(sorted(overlap)[:5])
        )

    b2b = [row for row in rows if row.get("category_external_id") in B2B_CATEGORY_PRIORITY]
    incomplete = [row for row in b2b if row.get("readiness_class") != "strict_content_ready"]
    incomplete_ids = {row["product_external_id"] for row in incomplete}
    irrelevant_processed = processed - incomplete_ids
    if irrelevant_processed:
        raise SystemExit(
            "processed exclusion contains a product outside the incomplete B2B candidate set: "
            + ", ".join(sorted(irrelevant_processed)[:5])
        )
    skipped = [row for row in incomplete if row.get("product_external_id") in holds]
    processed_skipped = [
        row for row in incomplete if row.get("product_external_id") in processed
    ]
    candidates = [
        row
        for row in incomplete
        if row.get("product_external_id") not in holds
        and row.get("product_external_id") not in processed
    ]

    ranked: list[dict[str, str | int]] = []
    for row in candidates:
        priority_score, reasons = score(row)
        ranked.append({
            "priority_score": priority_score,
            "product_external_id": row.get("product_external_id", ""),
            "name": row.get("name", ""),
            "category_external_id": row.get("category_external_id", ""),
            "readiness_class": row.get("readiness_class", ""),
            "manufacturer": row.get("manufacturer", ""),
            "sku": row.get("sku", ""),
            "mpn": row.get("mpn", ""),
            "technical_fact_count": row.get("technical_fact_count", "0"),
            "has_applied_description": row.get("has_applied_description", "false"),
            "has_displayable_preview_image": row.get("has_displayable_preview_image", "false"),
            "has_verified_published_image": row.get("has_verified_published_image", "false"),
            "priority_reasons": "|".join(reasons),
            "safe_to_apply": "false",
        })
    ranked.sort(key=lambda row: (-int(row["priority_score"]), str(row["product_external_id"])))
    selected = ranked[: args.limit]
    selected_ids = [str(row["product_external_id"]) for row in selected]
    if len(set(selected_ids)) != len(selected_ids):
        raise SystemExit("selected queue repeats product_external_id")
    if set(selected_ids) & (holds | processed):
        raise SystemExit("selected queue contains a held or already processed product")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    fields = list(selected[0]) if selected else [
        "priority_score", "product_external_id", "name", "category_external_id",
        "readiness_class", "manufacturer", "sku", "mpn", "technical_fact_count",
        "has_applied_description", "has_displayable_preview_image",
        "has_verified_published_image", "priority_reasons", "safe_to_apply",
    ]
    with args.output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(selected)

    summary = {
        "source_path": str(args.input),
        "source_sha256": input_hash,
        "hold_path": str(args.holds),
        "hold_sha256": hold_hash,
        "output_path": str(args.output),
        "output_sha256": file_hash(args.output),
        "processed_path": processed_path,
        "processed_sha256": processed_hash,
        "processed_records": len(processed_ids),
        "source_records": len(rows),
        "b2b_records": len(b2b),
        "b2b_strict_ready": len(b2b) - len(incomplete),
        "b2b_incomplete": len(incomplete),
        "already_reviewed_holds_skipped": len(skipped),
        "already_processed_skipped": len(processed_skipped),
        "eligible_unreviewed": len(candidates),
        "eligible_unreviewed_unprocessed": len(candidates),
        "selected_records": len(selected),
        "category_counts": dict(sorted(Counter(str(row["category_external_id"]) for row in selected).items())),
        "readiness_counts": dict(sorted(Counter(str(row["readiness_class"]) for row in selected).items())),
        "automatic_database_mutations": 0,
        "safe_to_apply_records": 0,
    }
    args.summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
