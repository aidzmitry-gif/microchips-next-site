#!/usr/bin/env python3
"""Merge Wave230 description packages against the frozen 88-product denominator."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def merge_payloads(payloads: list[tuple[str, dict]], expected_ids: set[str], hold_ids: set[str] | None = None) -> list[dict]:
    hold_ids = hold_ids or set()
    if not hold_ids.issubset(expected_ids):
        raise ValueError("hold list contains an out-of-scope product")
    products: list[dict] = []
    seen: set[str] = set()
    for source, payload in payloads:
        if payload.get("locale") != "ru-BY" or not payload.get("products"):
            raise ValueError(f"{source}: expected ru-BY and non-empty products")
        for row in payload["products"]:
            external_id = row.get("external_id")
            if external_id not in expected_ids:
                raise ValueError(f"{source}: out-of-scope product {external_id}")
            if external_id in seen:
                raise ValueError(f"{source}: duplicate product {external_id}")
            if row.get("identity_scope") not in {"exact", "model_core"}:
                raise ValueError(f"{source}: unsupported identity scope for {external_id}")
            seen.add(external_id)
            products.append(row)
    if seen.intersection(hold_ids):
        raise ValueError("a product cannot be both staged and held")
    missing = expected_ids.difference(seen).difference(hold_ids)
    if missing:
        raise ValueError(f"missing {len(missing)} frozen products")
    products.sort(key=lambda row: int(row["external_id"].split(":", 1)[1]))
    return products


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", action="append", required=True, type=Path)
    parser.add_argument("--targets", required=True, type=Path)
    parser.add_argument("--hold-id", action="append", default=[])
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    with args.targets.open(encoding="utf-8-sig", newline="") as handle:
        expected_ids = {row["product_external_id"] for row in csv.DictReader(handle)}
    if len(expected_ids) != 88:
        raise ValueError(f"frozen target count drift: {len(expected_ids)}")
    products = merge_payloads(
        [(str(path), json.loads(path.read_text(encoding="utf-8-sig"))) for path in args.manifest],
        expected_ids,
        set(args.hold_id),
    )
    payload = {
        "schema_version": 1,
        "purpose": "Wave230 source-backed descriptions for all verified-media cards in the frozen denominator.",
        "locale": "ru-BY",
        "products": products,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"products": len(products), "holds": len(set(args.hold_id)), "database_apply": False}))


if __name__ == "__main__":
    main()
