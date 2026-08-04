#!/usr/bin/env python3
"""Build fail-closed action manifests from the reviewed RB uncategorized queue.

The input review is a human/audit artifact, not a command to mutate the
catalogue.  This tool validates every row before it writes any output and
creates only CSV/JSON manifests for later, explicit import commands.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path


REQUIRED_COLUMNS = {
    "site_id",
    "product_external_id",
    "name",
    "manufacturer",
    "mpn",
    "is_published",
    "decision",
    "target_category",
    "reason",
}
ALLOWED_DECISIONS = {
    "existing_leaf_candidate",
    "electronics_defer",
    "obvious_nonprofile",
    "hold",
}
EXCLUSION_DECISIONS = {"electronics_defer", "obvious_nonprofile"}
CATEGORY_EXTERNAL_ID = re.compile(r"^seo:[a-z0-9][a-z0-9-]*$")
PUBLISHED_VALUES = {"1", "true", "t", "yes", "y"}


def is_published(value: str) -> bool:
    return (value or "").strip().casefold() in PUBLISHED_VALUES


def load_and_validate(path: Path) -> list[dict[str, str]]:
    """Read the complete review and reject an unsafe action before output."""
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = set(reader.fieldnames or [])
        missing = REQUIRED_COLUMNS - columns
        if missing:
            raise ValueError("Review CSV is missing required columns: " + ", ".join(sorted(missing)))

        rows: list[dict[str, str]] = []
        seen_ids: set[str] = set()
        for line_number, source in enumerate(reader, start=2):
            row = {key: (value or "").strip() for key, value in source.items() if key is not None}
            external_id = row["product_external_id"]
            decision = row["decision"]
            category = row["target_category"]

            if not external_id:
                raise ValueError(f"Review CSV has an empty product_external_id at line {line_number}")
            if external_id in seen_ids:
                raise ValueError(f"Review CSV duplicates product_external_id '{external_id}' at line {line_number}")
            seen_ids.add(external_id)
            if decision not in ALLOWED_DECISIONS:
                raise ValueError(f"Review CSV has unsupported decision '{decision}' at line {line_number}")

            is_candidate = decision == "existing_leaf_candidate"
            if is_candidate and not category:
                raise ValueError(f"Leaf candidate has no target_category at line {line_number}")
            if not is_candidate and category:
                raise ValueError(f"Non-leaf decision has target_category at line {line_number}")
            if category and not CATEGORY_EXTERNAL_ID.fullmatch(category):
                raise ValueError(f"Unsafe target_category '{category}' at line {line_number}")
            if decision in EXCLUSION_DECISIONS and is_published(row["is_published"]):
                raise ValueError(
                    f"Refusing exclusion of published product '{external_id}' at line {line_number}"
                )
            rows.append(row)
    return rows


def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def build(review_path: Path, out_dir: Path, prefix: str) -> dict[str, object]:
    rows = load_and_validate(review_path)
    # Validation precedes directory creation and every write: an unsafe review
    # cannot leave a partial-looking action package behind.
    assignments = [
        {"product_external_id": row["product_external_id"], "category_external_id": row["target_category"]}
        for row in rows
        if row["decision"] == "existing_leaf_candidate"
    ]
    exclusions = [
        {
            "product_external_id": row["product_external_id"],
            "reason": f"{row['decision']}: {row['reason']}",
        }
        for row in rows
        if row["decision"] in EXCLUSION_DECISIONS
    ]
    holds = [
        {"product_external_id": row["product_external_id"], "reason": row["reason"]}
        for row in rows
        if row["decision"] == "hold"
    ]

    out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(out_dir / f"{prefix}-assignments.csv", ["product_external_id", "category_external_id"], assignments)
    write_csv(out_dir / f"{prefix}-exclusions.csv", ["product_external_id", "reason"], exclusions)
    write_csv(out_dir / f"{prefix}-holds.csv", ["product_external_id", "reason"], holds)

    counts = Counter(row["decision"] for row in rows)
    summary: dict[str, object] = {
        "source": str(review_path),
        "total_rows": len(rows),
        "unique_product_external_ids": len({row["product_external_id"] for row in rows}),
        "decision_counts": dict(sorted(counts.items())),
        "assignment_candidates": len(assignments),
        "exclusion_candidates": len(exclusions),
        "hold_candidates": len(holds),
        "automatic_database_mutations": 0,
        "safety_invariant": (
            "Manifests only: published products cannot enter exclusion output; "
            "no category assignment, exclusion, or database mutation is performed."
        ),
    }
    (out_dir / f"{prefix}-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--prefix", default="rb-uncategorized-review-actions")
    args = parser.parse_args()
    print(json.dumps(build(args.review, args.out_dir, args.prefix), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
