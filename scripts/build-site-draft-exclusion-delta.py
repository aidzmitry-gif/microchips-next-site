#!/usr/bin/env python3
"""Intersect evidence-backed exclusions with currently linked site drafts."""
from __future__ import annotations

import argparse
import csv
from pathlib import Path


def ids(path: Path) -> set[str]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise SystemExit(f"{path} has no CSV header")
        column = "product_external_id" if "product_external_id" in reader.fieldnames else "external_id"
        if column not in reader.fieldnames:
            raise SystemExit(f"{path} requires product_external_id or external_id")
        return {str(row.get(column, "")).strip() for row in reader if str(row.get(column, "")).strip()}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--current-site-products", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    candidate_ids = ids(args.candidates)
    current_ids = ids(args.current_site_products)
    overlap = sorted(candidate_ids & current_ids)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["product_external_id", "reason"])
        writer.writeheader()
        writer.writerows({"product_external_id": external_id, "reason": "explicit_out_of_scope_after_live_sample_review"} for external_id in overlap)
    print(f"candidates={len(candidate_ids)} current_site_drafts={len(current_ids)} delta={len(overlap)}")


if __name__ == "__main__":
    main()
