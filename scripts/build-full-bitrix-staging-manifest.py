#!/usr/bin/env python3
"""Build a fail-closed staging manifest for the complete Bitrix catalogue.

The manifest is deliberately non-releasing.  It gives every active legacy row
one canonical SEO leaf, preserves the Bitrix identity namespace and separates
existing-1C candidates from genuinely legacy-only candidates.  Duplicate and
collision evidence is never converted into an arbitrary merge decision.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


ELECTRONIC_CATEGORY = "seo:electronic-components"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def source_rules(path: Path) -> list[tuple[str, str]]:
    rules: list[tuple[str, str]] = []
    for row in read_csv(path):
        slug = row.get("slug", "").strip()
        source_rule = row.get("source_rule", "").strip()
        if not slug or not source_rule or source_rule == "target_root":
            continue
        for prefix in source_rule.split("|"):
            normalized = prefix.strip().strip("/")
            if normalized:
                rules.append((normalized, f"seo:{slug}"))
    if not rules:
        raise ValueError("SEO tree does not contain any leaf source rules")
    rules.sort(key=lambda item: len(item[0]), reverse=True)
    return rules


def target_category(path: str, rules: list[tuple[str, str]]) -> str:
    normalized = path.strip().strip("/")
    matches = [
        (len(prefix), category)
        for prefix, category in rules
        if normalized == prefix or normalized.startswith(prefix + "/")
    ]
    if not matches:
        raise ValueError(f"Legacy path {path!r} maps to 0 SEO leaves")
    longest = max(length for length, _category in matches)
    winners = {category for length, category in matches if length == longest}
    if len(winners) != 1:
        raise ValueError(f"Legacy path {path!r} maps ambiguously to {len(winners)} SEO leaves")
    return next(iter(winners))


def transfer_status(row: dict[str, str], category: str) -> str:
    if row.get("is_active") != "true":
        return "excluded_inactive_legacy"
    if category == ELECTRONIC_CATEGORY:
        return "scope_excluded_electronics"

    identity = row.get("identity_status", "").strip()
    if identity == "duplicate_candidate":
        return "hold_duplicate_candidate"
    if identity == "one_c_collision_candidate":
        return "hold_one_c_collision"
    if identity == "linked_exact_name":
        return "existing_one_c_exact_link"
    if identity == "linked_candidate":
        return "hold_linked_identity_candidate"
    if identity == "unresolved_identity":
        return "legacy_only_draft_candidate"
    raise ValueError(
        f"Unsupported active identity status {identity!r} for {row.get('registry_id')}"
    )


def stable_checksum(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build(registry_path: Path, tree_path: Path, output: Path) -> dict[str, Any]:
    registry = read_csv(registry_path)
    rules = source_rules(tree_path)
    records: list[dict[str, Any]] = []
    statuses: Counter[str] = Counter()
    categories: Counter[str] = Counter()
    seen_ids: set[str] = set()

    for row in registry:
        registry_id = row.get("registry_id", "").strip()
        bitrix_id = row.get("bitrix_id", "").strip()
        name = row.get("name", "").strip()
        legacy_path = row.get("legacy_section_path", "").strip().strip("/")
        if not registry_id or registry_id != f"bitrix:{bitrix_id}":
            raise ValueError(f"Invalid namespaced identity for Bitrix ID {bitrix_id!r}")
        if not bitrix_id.isdigit() or bitrix_id in seen_ids:
            raise ValueError(f"Invalid or duplicate Bitrix ID {bitrix_id!r}")
        if not name or not legacy_path:
            raise ValueError(f"Bitrix row {bitrix_id} misses name or section path")

        category = target_category(legacy_path, rules)
        status = transfer_status(row, category)
        record: dict[str, Any] = {
            "registry_id": registry_id,
            "bitrix_id": bitrix_id,
            "name": name,
            "legacy_section_path": legacy_path,
            "legacy_url": row.get("legacy_url", "").strip(),
            "target_category_external_id": category,
            "one_c_external_id": row.get("one_c_code", "").strip(),
            "identity_status": row.get("identity_status", "").strip(),
            "duplicate_candidate_key": row.get("duplicate_candidate_key", "").strip(),
            "transfer_status": status,
            "allow_product_create": status == "legacy_only_draft_candidate",
            "allow_publication": False,
            "allow_indexing": False,
            "allow_merge": False,
        }
        record["source_checksum"] = stable_checksum(record)
        records.append(record)
        statuses[status] += 1
        if row.get("is_active") == "true":
            categories[category] += 1
        seen_ids.add(bitrix_id)

    records.sort(key=lambda item: int(item["bitrix_id"]))
    summary: dict[str, Any] = {
        "records": len(records),
        "active_records": sum(
            count for status, count in statuses.items()
            if status != "excluded_inactive_legacy"
        ),
        "status_counts": dict(sorted(statuses.items())),
        "active_category_counts": dict(sorted(categories.items())),
        "publication_changes": 0,
        "indexable_urls": 0,
        "merges": 0,
    }
    payload = {
        "schema_version": 1,
        "site_key": "microchips-by",
        "purpose": "Complete Bitrix catalogue staging; no merge, publication or indexing.",
        "source": {
            "registry": registry_path.name,
            "registry_sha256": hashlib.sha256(registry_path.read_bytes()).hexdigest(),
            "seo_tree": tree_path.name,
            "seo_tree_sha256": hashlib.sha256(tree_path.read_bytes()).hexdigest(),
        },
        "summary": summary,
        "records": records,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    output.with_suffix(".summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--seo-tree", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-records", type=int, default=17207)
    args = parser.parse_args()
    summary = build(args.registry, args.seo_tree, args.output)
    if summary["records"] != args.expected_records:
        raise SystemExit(
            f"Expected {args.expected_records} records; received {summary['records']}"
        )
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
