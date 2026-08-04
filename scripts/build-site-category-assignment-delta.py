#!/usr/bin/env python3
"""Build the safe-to-apply category delta for one current site snapshot."""
from __future__ import annotations

import argparse
import csv
from pathlib import Path


def read_pairs(path: Path) -> dict[str, str]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        pairs = {}
        for row in csv.DictReader(handle):
            product = str(row.get("product_external_id", "")).strip()
            category = str(row.get("category_external_id", "")).strip()
            if product and category:
                pairs[product] = category
        return pairs


def read_ids(path: Path) -> set[str]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return {str(row.get("product_external_id", "")).strip() for row in csv.DictReader(handle) if str(row.get("product_external_id", "")).strip()}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--current-site-products", type=Path, required=True)
    parser.add_argument("--existing-assignments", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    candidates = read_pairs(args.candidates)
    current = read_ids(args.current_site_products)
    existing = read_pairs(args.existing_assignments)
    delta = [
        {"product_external_id": product, "category_external_id": category}
        for product, category in sorted(candidates.items())
        if product in current and product not in existing
    ]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["product_external_id", "category_external_id"])
        writer.writeheader()
        writer.writerows(delta)
    print(f"candidate_assignments={len(candidates)} current_site_drafts={len(current)} existing_assignments={len(existing)} delta={len(delta)}")


if __name__ == "__main__":
    main()
