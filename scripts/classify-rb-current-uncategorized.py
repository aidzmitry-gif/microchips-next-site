#!/usr/bin/env python3
"""Classify only the current RB no-category residue without rebuilding the tree.

The established high-signal taxonomy rules remain the single rule source.  A
row is either emitted as one proposed leaf, explicitly deferred by market
policy, or kept on hold.  This script never mutates the database.
"""
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path


RULES_PATH = Path(__file__).with_name("build-one-c-seo-category-assignment.py")


def load_rules():
    spec = importlib.util.spec_from_file_location("one_c_seo_category_rules", RULES_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load taxonomy rules from {RULES_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def classify(source: Path, out_dir: Path, prefix: str, deferred_categories: set[str]) -> dict[str, object]:
    rules = load_rules()
    with source.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    seen: set[str] = set()
    assignments: list[dict[str, str]] = []
    deferred: list[dict[str, str]] = []
    holds: list[dict[str, str]] = []
    distribution: Counter[str] = Counter()

    for row in rows:
        external_id = row.get("product_external_id", "").strip()
        name = row.get("name", "").strip()
        if not external_id or not name or external_id in seen:
            raise ValueError("Source requires unique non-empty product_external_id and name values")
        seen.add(external_id)
        category_id, rule = rules.category(name, "")
        evidence = {
            "product_external_id": external_id,
            "name": name,
            "category_external_id": category_id or "",
            "rule": rule,
            "safe_to_apply": "false",
        }
        if category_id is None:
            holds.append(evidence)
        elif category_id in deferred_categories:
            evidence["decision"] = "deferred_by_market_scope"
            deferred.append(evidence)
        else:
            evidence["safe_to_apply"] = "true"
            assignments.append(evidence)
            distribution[category_id] += 1

    fields = ["product_external_id", "name", "category_external_id", "rule", "safe_to_apply"]
    write_csv(out_dir / f"{prefix}-assignments.csv", assignments, fields)
    write_csv(out_dir / f"{prefix}-holds.csv", holds, fields)
    write_csv(out_dir / f"{prefix}-deferred-scope.csv", deferred, fields + ["decision"])
    summary: dict[str, object] = {
        "source_rows": len(rows),
        "unique_external_ids": len(seen),
        "assigned_high_signal": len(assignments),
        "deferred_by_market_scope": len(deferred),
        "unclassified_hold": len(holds),
        "distribution": dict(sorted(distribution.items())),
        "automatic_database_mutations": 0,
        "invariant": "each proposed assignment has exactly one leaf; holds are never forced",
    }
    (out_dir / f"{prefix}-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--prefix", default="rb-current-uncategorized")
    parser.add_argument("--defer-category", action="append", default=[])
    args = parser.parse_args()
    summary = classify(args.source, args.out_dir, args.prefix, set(args.defer_category))
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
