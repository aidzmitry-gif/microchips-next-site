#!/usr/bin/env python3
"""Materialize a reviewed dealer-backed admission list without retyping facts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def build(source_path: Path, admission_path: Path, output_path: Path) -> dict[str, int]:
    source = json.loads(source_path.read_text(encoding="utf-8-sig"))
    admission = json.loads(admission_path.read_text(encoding="utf-8-sig"))
    policy = admission["admission_policy"]
    admitted = set(admission["candidate_external_ids"])
    excluded = set(admission["excluded_pending_cache_recheck"])
    products = source.get("products")
    if not isinstance(products, list) or not products:
        raise ValueError("source manifest must contain products")
    ids = [row.get("external_id") for row in products]
    if any(not isinstance(value, str) or not value for value in ids) or len(ids) != len(set(ids)):
        raise ValueError("source external IDs must be unique and non-empty")
    if admitted & excluded or admitted | excluded != set(ids):
        raise ValueError("admission and exclusion IDs must exactly partition the source manifest")
    required_policy = {
        "source_kind": "official_dealer_product_page",
        "source_tier": "dealer_backed",
        "manufacturer_primary": False,
        "evidence_scope": "model_core",
    }
    for key, expected in required_policy.items():
        if policy.get(key) != expected:
            raise ValueError(f"admission policy {key} must be {expected!r}")

    output_products = []
    for row in products:
        if row["external_id"] not in admitted:
            continue
        materialized = dict(row)
        for key in [
            "source_kind", "source_tier", "source_publisher", "manufacturer_primary",
            "evidence_scope", "checked_at",
        ]:
            materialized[key] = policy[key]
        output_products.append(materialized)

    output = {
        "schema_version": 2,
        "purpose": "Dealer-backed model-core technical facts with explicit non-manufacturer provenance.",
        "locale": source["locale"],
        "products": output_products,
    }
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = {
        "source_records": len(products),
        "dealer_backed_records": len(output_products),
        "excluded_pending_recheck": len(excluded),
    }
    output_path.with_suffix(".summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--admission", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.source, args.admission, args.output), ensure_ascii=False))


if __name__ == "__main__":
    main()
