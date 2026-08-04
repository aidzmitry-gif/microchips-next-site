#!/usr/bin/env python3
"""Build a fail-closed focus decision manifest for the staged Bitrix tree.

The 1,569-record RB focus is narrower than the full legacy catalog. Therefore a
category with zero focus members is not called globally empty or removable. The
output is evidence only: every row is non-releasing and requires a later
URL/content/traffic decision before it may affect the public taxonomy.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

VISIBLE_STATUSES = {
    "strict_mapped_evidence",
    "candidate_mapped_evidence",
    "candidate_duplicate_group",
    "hold_missing_1c_identity",
    "hold_missing_rb_site_product",
}

HEADER = [
    "legacy_external_id",
    "legacy_path",
    "legacy_name",
    "focus_membership_count",
    "focus_direct_count",
    "global_direct_count",
    "global_aggregate_count",
    "global_recommended_state",
    "normalized_name_duplicate_group",
    "canonical_category_external_id",
    "strict_product_count",
    "strict_target_votes",
    "preliminary_seo_target",
    "preview_decision",
    "release_allowed",
    "decision_reason",
]


def normalize_path(value: str) -> str:
    path = value.strip().strip("/")
    return path[8:] if path.startswith("catalog/") else path


def normalize_name(value: str) -> str:
    text = unicodedata.normalize("NFKC", value).casefold().replace("ё", "е")
    return re.sub(r"[^a-zа-я0-9]+", "", text)


def record_paths(record: dict[str, Any]) -> set[str]:
    paths = {
        normalize_path(path)
        for path in re.split(r"\s*\|\s*", str(record.get("legacy_matched_section_paths", "")))
        if normalize_path(path)
    }
    primary = normalize_path(str(record.get("legacy_primary_section_path", "")))
    if primary:
        paths.add(primary)
    return paths


def load_overrides(path: Path | None) -> dict[str, set[str]]:
    if path is None:
        return {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    result: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        product_id = row.get("product_external_id", "").strip()
        target = row.get("category_external_id", "").strip()
        if product_id and target.startswith("seo:"):
            result[product_id].add(target)
    return dict(result)


def build(
    categories: list[dict[str, str]],
    records: list[dict[str, Any]],
    overrides: dict[str, set[str]],
    global_rows: list[dict[str, str]] | None = None,
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    category_by_path = {normalize_path(row["path"]): row for row in categories}
    if len(category_by_path) != len(categories):
        raise ValueError("Duplicate normalized legacy category path.")

    global_by_path = {
        normalize_path(row.get("legacy_path", "")): row for row in (global_rows or [])
    }
    membership: dict[str, set[str]] = defaultdict(set)
    direct: dict[str, set[str]] = defaultdict(set)
    strict_members: dict[str, set[str]] = defaultdict(set)
    strict_votes: dict[str, Counter[str]] = defaultdict(Counter)

    for record in records:
        if str(record.get("transfer_status", "")) not in VISIBLE_STATUSES:
            continue
        legacy_id = str(record.get("legacy_element_id", "")).strip()
        paths = record_paths(record)
        for path in paths:
            if path in category_by_path:
                membership[path].add(legacy_id)
        primary = normalize_path(str(record.get("legacy_primary_section_path", "")))
        if primary in category_by_path:
            direct[primary].add(legacy_id)

        if str(record.get("transfer_status", "")) != "strict_mapped_evidence":
            continue
        product_id = str(record.get("one_c_external_id", "")).strip()
        targets = overrides.get(product_id) or {
            str(value).strip()
            for value in record.get("rb_category_external_ids", [])
            if str(value).strip().startswith("seo:")
        }
        if not targets:
            continue
        for path in paths:
            if path not in category_by_path:
                continue
            strict_members[path].add(legacy_id)
            for target in targets:
                strict_votes[path][target] += 1

    name_groups: dict[str, list[str]] = defaultdict(list)
    for path, category in category_by_path.items():
        name_groups[normalize_name(category["name"])].append(path)

    duplicate_targets: dict[str, str] = {}
    for normalized, paths in name_groups.items():
        if not normalized or len(paths) < 2:
            continue
        canonical_paths = [
            path for path in paths if not re.search(r"\d+$", path.rsplit("/", 1)[-1])
        ]
        for path in paths:
            if membership[path] or not re.search(r"\d+$", path.rsplit("/", 1)[-1]):
                continue
            candidates = [candidate for candidate in canonical_paths if candidate != path]
            if len(candidates) == 1:
                duplicate_targets[path] = candidates[0]

    rows: list[dict[str, str]] = []
    decisions: Counter[str] = Counter()
    for path in sorted(category_by_path, key=lambda value: (value.count("/"), value)):
        category = category_by_path[path]
        focus_count = len(membership[path])
        global_row = global_by_path.get(path, {})
        duplicate_group = normalize_name(category["name"])
        canonical_path = duplicate_targets.get(path, "")
        canonical_id = category_by_path.get(canonical_path, {}).get("external_id", "")

        if focus_count:
            decision = "focus_populated"
            reason = "Contains RB focus members; show only in the noindex preview pending semantic taxonomy review."
        elif canonical_id:
            decision = "empty_duplicate_candidate"
            reason = "Zero focus members and a numeric-suffix path duplicates one canonical normalized name; merge remains evidence-only."
        else:
            decision = "empty_in_focus_preview"
            reason = "Zero members in the 1,569-record focus; this does not prove the category is globally empty."

        votes = strict_votes[path]
        total_votes = sum(votes.values())
        top_target, top_votes = votes.most_common(1)[0] if votes else ("", 0)
        preliminary_target = (
            top_target
            if len(strict_members[path]) >= 3 and total_votes and top_votes / total_votes >= 0.8
            else ""
        )
        decisions[decision] += 1
        rows.append(
            {
                "legacy_external_id": category["external_id"].strip(),
                "legacy_path": path,
                "legacy_name": category["name"].strip(),
                "focus_membership_count": str(focus_count),
                "focus_direct_count": str(len(direct[path])),
                "global_direct_count": global_row.get("direct_product_count", ""),
                "global_aggregate_count": global_row.get("active_product_count", ""),
                "global_recommended_state": global_row.get("recommended_state", ""),
                "normalized_name_duplicate_group": duplicate_group if len(name_groups[duplicate_group]) > 1 else "",
                "canonical_category_external_id": canonical_id,
                "strict_product_count": str(len(strict_members[path])),
                "strict_target_votes": json.dumps(dict(sorted(votes.items())), ensure_ascii=False, separators=(",", ":")),
                "preliminary_seo_target": preliminary_target,
                "preview_decision": decision,
                "release_allowed": "false",
                "decision_reason": reason,
            }
        )

    summary = {
        "schema_version": 2,
        "categories_processed": len(rows),
        "snapshot_records": len(records),
        "visible_scope_records": sum(
            str(record.get("transfer_status", "")) in VISIBLE_STATUSES for record in records
        ),
        "strict_records": sum(
            str(record.get("transfer_status", "")) == "strict_mapped_evidence" for record in records
        ),
        "decisions": dict(sorted(decisions.items())),
        "release_allowed_rows": 0,
        "invariant": "Focus evidence never deletes, merges, publishes, redirects, or indexes a category automatically.",
    }
    return rows, summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--categories", type=Path, required=True)
    parser.add_argument("--transfer", type=Path, required=True)
    parser.add_argument("--global-evidence", type=Path)
    parser.add_argument("--override", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--expected-categories", type=int, default=219)
    parser.add_argument("--expected-records", type=int, default=1569)
    args = parser.parse_args()

    with args.categories.open(encoding="utf-8-sig", newline="") as handle:
        categories = list(csv.DictReader(handle))
    transfer = json.loads(args.transfer.read_text(encoding="utf-8-sig"))
    records = transfer.get("records") if isinstance(transfer, dict) else None
    if not isinstance(records, list):
        raise SystemExit("Transfer manifest must contain a records array.")
    if len(categories) != args.expected_categories:
        raise SystemExit(f"Expected {args.expected_categories} categories; received {len(categories)}.")
    if len(records) != args.expected_records:
        raise SystemExit(f"Expected {args.expected_records} records; received {len(records)}.")
    global_rows: list[dict[str, str]] = []
    if args.global_evidence:
        with args.global_evidence.open(encoding="utf-8-sig", newline="") as handle:
            global_rows = list(csv.DictReader(handle))

    rows, summary = build(categories, records, load_overrides(args.override), global_rows)
    source_paths = [args.categories, args.transfer]
    if args.global_evidence:
        source_paths.append(args.global_evidence)
    if args.override:
        source_paths.append(args.override)
    summary["sources"] = {
        str(path.as_posix()): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in source_paths
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=HEADER)
        writer.writeheader()
        writer.writerows(rows)
    args.summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
