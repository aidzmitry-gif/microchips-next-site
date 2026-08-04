#!/usr/bin/env python3
"""Re-evaluate an existing conservative SEO research queue after rule updates.

The input queue is evidence of what was intentionally *not* assigned during a
previous pass.  This helper never guesses a fallback category: it only emits
rows that the current explicit classifier can now recognise, and preserves all
remaining rows for research.
"""
from __future__ import annotations

import argparse
import csv
import importlib.util
from pathlib import Path


def load_classifier(script: Path):
    spec = importlib.util.spec_from_file_location("seo_category_rules", script)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load classifier from {script}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.category


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--assignments", type=Path, required=True)
    parser.add_argument("--remaining", type=Path, required=True)
    parser.add_argument("--classifier", type=Path, default=Path(__file__).with_name("build-one-c-seo-category-assignment.py"))
    parser.add_argument("--exclude", type=Path, action="append", default=[], help="CSV with product_external_id/external_id values that must not be emitted")
    parser.add_argument(
        "--exclude-category",
        action="append",
        default=[],
        help="target category external_id that must remain in the research queue",
    )
    parser.add_argument("--only", type=Path, help="CSV with product_external_id/external_id values currently eligible for reclassification")
    args = parser.parse_args()

    classify = load_classifier(args.classifier)
    rows = list(csv.DictReader(args.input.open(encoding="utf-8-sig", newline="")))
    excluded: set[str] = set()
    for path in args.exclude:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            excluded |= {
                (row.get("product_external_id") or row.get("external_id") or "").strip()
                for row in csv.DictReader(handle)
                if (row.get("product_external_id") or row.get("external_id") or "").strip()
            }
    only: set[str] | None = None
    if args.only:
        with args.only.open(encoding="utf-8-sig", newline="") as handle:
            only = {
                (row.get("product_external_id") or row.get("external_id") or "").strip()
                for row in csv.DictReader(handle)
                if (row.get("product_external_id") or row.get("external_id") or "").strip()
            }
    assignments: list[dict[str, str]] = []
    remaining: list[dict[str, str]] = []
    excluded_categories = set(args.exclude_category)
    skipped = 0
    for row in rows:
        # The live PostgreSQL export uses the canonical Product field name
        # ``external_id``; older research queues used
        # ``product_external_id``.  Supporting both keeps the classifier
        # reusable while still requiring a real catalog identity.
        external_id = (row.get("product_external_id") or row.get("external_id") or "").strip()
        name = (row.get("name") or "").strip()
        if external_id in excluded or (only is not None and external_id not in only):
            skipped += 1
            continue
        category_id, _rule = classify(name, "")
        if external_id and category_id and category_id not in excluded_categories:
            assignments.append({"product_external_id": external_id, "category_external_id": category_id})
        else:
            remaining.append(row)

    args.assignments.parent.mkdir(parents=True, exist_ok=True)
    with args.assignments.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["product_external_id", "category_external_id"])
        writer.writeheader()
        writer.writerows(assignments)
    with args.remaining.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys() if rows else ["product_external_id", "name"])
        writer.writeheader()
        writer.writerows(remaining)
    print(f"input={len(rows)} excluded={skipped} newly_classified={len(assignments)} remaining={len(remaining)}")


if __name__ == "__main__":
    main()
