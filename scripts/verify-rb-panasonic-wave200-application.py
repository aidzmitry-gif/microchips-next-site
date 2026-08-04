#!/usr/bin/env python3
"""Verify that Panasonic Wave 200 changed only source-backed content fields."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


IMMUTABLE_PRODUCT_FIELDS = ("name", "sku", "mpn", "status")
IMMUTABLE_SITE_FIELDS = ("price", "currency", "availability", "is_published")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def index_products(document: dict[str, Any], path: Path) -> dict[str, dict[str, Any]]:
    rows = document.get("products")
    if not isinstance(rows, list):
        raise ValueError(f"{path}: products must be a list")

    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        external_id = row.get("external_id")
        if not isinstance(external_id, str) or not external_id:
            raise ValueError(f"{path}: every product needs external_id")
        if external_id in indexed:
            raise ValueError(f"{path}: duplicate external_id {external_id}")
        indexed[external_id] = row
    return indexed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    args = parser.parse_args()

    manifest = index_products(load_json(args.manifest), args.manifest)
    before = index_products(load_json(args.before), args.before)
    after = index_products(load_json(args.after), args.after)
    errors: list[str] = []

    if set(manifest) != set(before) or set(manifest) != set(after):
        errors.append("manifest/before/after external_id sets differ")

    description_changes = 0
    manufacturer_changes = 0
    for external_id in sorted(set(manifest) & set(before) & set(after)):
        evidence = manifest[external_id]
        old = before[external_id]
        new = after[external_id]

        for field in IMMUTABLE_PRODUCT_FIELDS:
            if old.get(field) != new.get(field):
                errors.append(f"{external_id}: product field {field} changed")

        for field in IMMUTABLE_SITE_FIELDS:
            if old.get("site_product", {}).get(field) != new.get("site_product", {}).get(field):
                errors.append(f"{external_id}: commercial field {field} changed")

        if old.get("seo") != new.get("seo"):
            errors.append(f"{external_id}: SEO state changed")

        if new.get("manufacturer") != evidence.get("manufacturer"):
            errors.append(f"{external_id}: manufacturer does not match evidence")
        if old.get("manufacturer") != new.get("manufacturer"):
            manufacturer_changes += 1

        if old.get("short_description_sha256") != new.get("short_description_sha256"):
            description_changes += 1

        attributes = new.get("technical_attributes") or {}
        for key, value in (evidence.get("technical_attributes") or {}).items():
            if attributes.get(key) != value:
                errors.append(f"{external_id}: technical attribute {key!r} differs from evidence")

        draft = new.get("latest_draft") or {}
        expected_draft = {
            "status": "applied",
            "source_tier": "manufacturer_primary",
            "source_publisher": "Panasonic Energy Co., Ltd.",
            "identity_scope": "model_core",
        }
        for key, value in expected_draft.items():
            if draft.get(key) != value:
                errors.append(f"{external_id}: latest draft {key} is {draft.get(key)!r}, expected {value!r}")

    if description_changes != len(manifest):
        errors.append(f"description changes: {description_changes}, expected {len(manifest)}")

    summary = {
        "records": len(manifest),
        "description_changes": description_changes,
        "manufacturer_changes": manufacturer_changes,
        "commercial_changes": 0 if not any("commercial field" in error for error in errors) else None,
        "seo_changes": 0 if not any("SEO state changed" in error for error in errors) else None,
        "errors": len(errors),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    for error in errors:
        print(f"ERROR: {error}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
