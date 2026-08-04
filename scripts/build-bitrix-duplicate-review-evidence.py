#!/usr/bin/env python3
"""Build a complete, non-mutating review manifest for Bitrix/1C collisions.

`candidate_duplicate_group` means that several legacy rows point at one 1C
identity. It is not proof that those rows are duplicates. This builder covers
every group and member, separates strict matcher evidence from weak evidence,
and emits only review/hold decisions. It never emits merge or publication
instructions.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

GROUP_DECISIONS = {
    0: "mixed_mapping_collision_hold",
    1: "single_high_signal_review_queue",
}

QUEUE_HEADER = [
    "review_priority",
    "group_key",
    "one_c_external_id",
    "one_c_name",
    "legacy_element_id",
    "legacy_name",
    "legacy_url_candidate",
    "match_method",
    "match_score",
    "comparison_status",
    "legacy_text_sha256",
    "review_decision",
]


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def high_signal(match: dict[str, str], expected_one_c: str) -> bool:
    comparison = match.get("сравнение", match.get("comparison", "")).strip().casefold()
    return (
        match.get("1С-код", "").strip() == expected_one_c
        and match.get("brand_ok", "").strip().casefold() == "yes"
        and match.get("confidence", "").strip().replace(",", ".") == "0.95"
        and match.get("method", "").strip() == "sig+brand"
        and comparison == "agree"
    )


def build(
    transfer: dict[str, Any],
    matches: list[dict[str, str]],
    transfer_sha256: str,
    matches_sha256: str,
    source_import_run_id: int,
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    records = transfer.get("records")
    if not isinstance(records, list):
        raise ValueError("Transfer manifest must contain records.")
    candidates = [
        record for record in records
        if record.get("transfer_status") == "candidate_duplicate_group"
    ]
    match_by_legacy: dict[str, dict[str, str]] = {}
    for row in matches:
        legacy_id = row.get("Bitrix ID", "").strip()
        if not legacy_id:
            continue
        if legacy_id in match_by_legacy:
            raise ValueError(f"Duplicate matcher row for Bitrix ID {legacy_id}.")
        match_by_legacy[legacy_id] = row

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    seen_legacy: set[str] = set()
    for record in candidates:
        legacy_id = str(record.get("legacy_element_id", "")).strip()
        one_c_id = str(record.get("one_c_external_id", "")).strip()
        if not legacy_id or not legacy_id.isdigit() or legacy_id in seen_legacy:
            raise ValueError(f"Invalid or duplicate legacy ID {legacy_id!r}.")
        if not one_c_id:
            raise ValueError(f"Candidate {legacy_id} has no 1C external ID.")
        if legacy_id not in match_by_legacy:
            raise ValueError(f"Candidate {legacy_id} has no matcher evidence row.")
        seen_legacy.add(legacy_id)
        grouped[one_c_id].append(record)

    groups: list[dict[str, Any]] = []
    queue: list[dict[str, str]] = []
    group_counts: Counter[str] = Counter()
    member_counts: Counter[str] = Counter()

    for one_c_id in sorted(grouped):
        source_members = sorted(grouped[one_c_id], key=lambda row: int(row["legacy_element_id"]))
        strict_ids = {
            str(row["legacy_element_id"])
            for row in source_members
            if high_signal(match_by_legacy[str(row["legacy_element_id"])], one_c_id)
        }
        strict_count = len(strict_ids)
        group_decision = GROUP_DECISIONS.get(strict_count, "variant_or_collision_hold")
        group_counts[group_decision] += 1
        members: list[dict[str, Any]] = []

        for record in source_members:
            legacy_id = str(record["legacy_element_id"])
            match = match_by_legacy[legacy_id]
            is_strict = legacy_id in strict_ids
            if not is_strict:
                member_decision = "hold_insufficient_identity_evidence"
                retry_condition = "Obtain exact manufacturer/model evidence and verify all material facts."
            elif strict_count == 1:
                member_decision = "review_exact_identity_candidate"
                retry_condition = "Verify primary manufacturer identity evidence before any canonical link."
            else:
                member_decision = "hold_multiple_high_signal_candidates"
                retry_condition = "Resolve model, terminal, pack, origin and capacity variants with primary sources."
            member_counts[member_decision] += 1
            comparison = match.get("сравнение", match.get("comparison", "")).strip()
            member = {
                "legacy_element_id": legacy_id,
                "legacy_name": str(record.get("legacy_name", "")),
                "legacy_url_candidate": str(record.get("legacy_url_candidate", "")),
                "legacy_text_sha256": str(record.get("legacy_text_sha256", "")),
                "preview_picture_file_id": str(record.get("preview_picture_file_id", "")),
                "detail_picture_file_id": str(record.get("detail_picture_file_id", "")),
                "match_method": match.get("method", "").strip(),
                "match_score": match.get("confidence", "").strip(),
                "brand_ok": match.get("brand_ok", "").strip(),
                "comparison_status": comparison,
                "signature": match.get("signature", "").strip(),
                "member_decision": member_decision,
                "retry_condition": retry_condition,
                "create_product": False,
                "merge_product": False,
                "change_publication": False,
            }
            members.append(member)
            if member_decision == "review_exact_identity_candidate":
                queue.append({
                    "review_priority": "",
                    "group_key": f"one_c:{one_c_id}",
                    "one_c_external_id": one_c_id,
                    "one_c_name": str(record.get("one_c_name", "")),
                    "legacy_element_id": legacy_id,
                    "legacy_name": str(record.get("legacy_name", "")),
                    "legacy_url_candidate": str(record.get("legacy_url_candidate", "")),
                    "match_method": match.get("method", "").strip(),
                    "match_score": match.get("confidence", "").strip(),
                    "comparison_status": comparison,
                    "legacy_text_sha256": str(record.get("legacy_text_sha256", "")),
                    "review_decision": member_decision,
                })

        groups.append({
            "group_key": f"one_c:{one_c_id}",
            "one_c_external_id": one_c_id,
            "one_c_name": str(source_members[0].get("one_c_name", "")),
            "expected_member_count": len(members),
            "high_signal_member_count": strict_count,
            "group_decision": group_decision,
            "members": members,
        })

    queue.sort(key=lambda row: (row["one_c_external_id"], int(row["legacy_element_id"])))
    for index, row in enumerate(queue, 1):
        row["review_priority"] = str(index)

    manifest = {
        "schema_version": 1,
        "site_key": "microchips-by",
        "source_import_run_id": source_import_run_id,
        "source_manifest_sha256": transfer_sha256,
        "matcher_evidence_sha256": matches_sha256,
        "expected_groups": len(groups),
        "expected_members": len(candidates),
        "group_decision_counts": dict(sorted(group_counts.items())),
        "member_decision_counts": dict(sorted(member_counts.items())),
        "mutation_policy": {
            "create_products": False,
            "merge_products": False,
            "delete_products": False,
            "change_site_links": False,
            "create_families": False,
            "change_publication": False,
            "change_urls": False,
            "change_seo": False,
            "render_legacy_html": False,
        },
        "groups": groups,
    }
    return manifest, queue


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--transfer", type=Path, required=True)
    parser.add_argument("--matches", type=Path, required=True)
    parser.add_argument("--source-import-run-id", type=int, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--expected-groups", type=int, default=88)
    parser.add_argument("--expected-members", type=int, default=430)
    args = parser.parse_args()

    transfer = json.loads(args.transfer.read_text(encoding="utf-8-sig"))
    manifest, queue = build(
        transfer,
        read_csv(args.matches),
        file_hash(args.transfer),
        file_hash(args.matches),
        args.source_import_run_id,
    )
    if manifest["expected_groups"] != args.expected_groups:
        raise SystemExit(f"Expected {args.expected_groups} groups; received {manifest['expected_groups']}.")
    if manifest["expected_members"] != args.expected_members:
        raise SystemExit(f"Expected {args.expected_members} members; received {manifest['expected_members']}.")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with args.queue.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=QUEUE_HEADER)
        writer.writeheader()
        writer.writerows(queue)
    print(json.dumps({
        "groups": manifest["expected_groups"],
        "members": manifest["expected_members"],
        "group_decisions": manifest["group_decision_counts"],
        "member_decisions": manifest["member_decision_counts"],
        "review_queue": len(queue),
        "catalog_mutations": 0,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
