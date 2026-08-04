#!/usr/bin/env python3
"""Fail-closed local orchestration of the Wave222 enrichment backlog."""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "docs/audits/generated"
INPUT = GEN / "rb-enrichment-queue-wave222.csv"
WAVE220_REGISTER = GEN / "rb-b2b-processed-register-wave220.csv"
WAVE220_MANIFEST = ROOT / "docs/imports/rb-source-backed-description-drafts-wave220-2026-07-29.json"
WAVE220_RECEIPT = GEN / "wave220-description-enrichment-application-receipt.json"
QUEUE_A = GEN / "rb-enrichment-queue-wave223c-a-ups-industrial.csv"
QUEUE_B = GEN / "rb-enrichment-queue-wave223c-b-primary-rechargeable.csv"
QUEUE_C = GEN / "rb-enrichment-queue-wave223c-c-other-b2b.csv"
REMAINDER = GEN / "rb-enrichment-queue-wave223c-remainder.csv"
EXCLUSIONS = GEN / "rb-enrichment-queue-wave223c-exclusions.csv"
VERIFY = GEN / "rb-enrichment-queue-wave223c.verification.json"
REPORT = ROOT / "docs/audits/2026-07-29-rb-wave223c-enrichment-orchestration.md"

INPUT_SHA256 = "a9d937d6a78e198b8708756529b2e6e73fc8a9a2c67ca15c42759db557c9a8b0"
WAVE220_REGISTER_SHA256 = "76575950c6d5ceb4fbe7b7785961c57e7da488a569e62711d4799f594790ca29"
WAVE220_MANIFEST_SHA256 = "b351e9fdaafb52d5063fef219b11614615774e62713bca59ec60b97fe567db6f"
WAVE220_RECEIPT_SHA256 = "bf445745bd596059ce6fa60c1192b2513dd3a116b8cbdd858ed1ded237d1dd3a"
CAPACITY = 300

LANE_A = {"seo:batteries-ups", "seo:ups-systems", "seo:batteries-industrial"}
LANE_B = {"seo:primary-cells", "seo:rechargeable-cells"}
ALLOWED_B2B_CATEGORIES = LANE_A | LANE_B | {
    "seo:batteries-traction", "seo:power-supplies", "seo:power-converters", "seo:chargers", "seo:power-systems",
    "seo:replacement-home", "seo:replacement-laptops", "seo:replacement-photo",
}
EXPECTED_CATEGORY_COUNTS = {
    "seo:batteries-ups": 648, "seo:primary-cells": 360, "seo:batteries-industrial": 291,
    "seo:rechargeable-cells": 135, "seo:ups-systems": 38, "seo:power-supplies": 26,
    "seo:chargers": 22, "seo:batteries-traction": 18, "seo:replacement-laptops": 8,
    "seo:power-converters": 3, "seo:power-systems": 3, "seo:replacement-home": 1,
    "seo:replacement-photo": 1,
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_rows(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def validate_input() -> list[dict[str, str]]:
    rows = read_rows(INPUT)
    fields = ["priority", "product_external_id", "name", "sku", "mpn", "manufacturer", "category_external_id", "category_name", "has_applied_description", "has_verified_published_image", "completion_gap_count", "identity_fields_present", "is_published", "research_status"]
    ids = [row.get("product_external_id", "") for row in rows]
    if sha256(INPUT) != INPUT_SHA256 or len(rows) != 1554 or any(not value for value in ids) or len(ids) != len(set(ids)):
        raise SystemExit("Wave222 queue pin/count/uniqueness drift")
    if list(rows[0]) != fields or any(row.get("research_status") != "pending_official_source_research" for row in rows):
        raise SystemExit("Wave222 schema/research-status drift")
    priorities = [int(row["priority"]) for row in rows]
    if priorities != list(range(1, 1555)):
        raise SystemExit("Wave222 ordering is not the deterministic 1..1554 sequence")
    categories = Counter(row["category_external_id"] for row in rows)
    if categories != Counter(EXPECTED_CATEGORY_COUNTS) or set(categories) - ALLOWED_B2B_CATEGORIES:
        raise SystemExit("Wave222 contains excluded/unknown non-B2B categories")
    return rows


def exclusion_reasons(queue_ids: set[str]) -> dict[str, list[str]]:
    historical = read_rows(WAVE220_REGISTER)
    if sha256(WAVE220_REGISTER) != WAVE220_REGISTER_SHA256 or len(historical) != 3894:
        raise SystemExit("Wave220 historical identity register drift")
    historical_ids = {row["product_external_id"] for row in historical}
    if len(historical_ids) != 3894:
        raise SystemExit("Wave220 historical identity register repeats IDs")
    if sha256(WAVE220_MANIFEST) != WAVE220_MANIFEST_SHA256 or sha256(WAVE220_RECEIPT) != WAVE220_RECEIPT_SHA256:
        raise SystemExit("Wave220 applied-description evidence pin drift")
    manifest = json.loads(WAVE220_MANIFEST.read_text(encoding="utf-8"))
    applied_ids = {row["external_id"] for row in manifest.get("products", [])}
    receipt = json.loads(WAVE220_RECEIPT.read_text(encoding="utf-8"))
    if len(applied_ids) != 15 or len(manifest.get("products", [])) != 15 or receipt.get("application", {}).get("applied") != 15 or receipt.get("application", {}).get("status") != "completed":
        raise SystemExit("Wave220 applied15 contract drift")
    result: dict[str, list[str]] = {}
    for external_id in sorted(queue_ids & historical_ids):
        result.setdefault(external_id, []).append("historical_identity_research_wave220")
    for external_id in sorted(queue_ids & applied_ids):
        result.setdefault(external_id, []).append("wave220_applied_description")
    if len(queue_ids & historical_ids) != 596 or len(queue_ids & applied_ids) != 4 or any("wave220_applied_description" in reasons and "historical_identity_research_wave220" not in reasons for reasons in result.values()):
        raise SystemExit("Wave220 exclusion overlap drift")
    return result


def write_report(verification: dict[str, object]) -> None:
    REPORT.write_text(
        "# Wave223-C enrichment orchestration\n\n"
        "Wave223-C is a local planning artifact only. It validates the pinned 1,554-row Wave222 queue, then removes records already covered by the Wave220 historical identity-research ledger or the Wave220 applied-description batch. No source research, database access, staging, or application occurs.\n\n"
        "Three disjoint queues are ordered by the original deterministic Wave222 priority: A covers UPS and industrial batteries (max 300), B primary and rechargeable cells (max 300), and C the remaining approved B2B categories (max 300). Every eligible row not selected due to a lane cap is retained in the remainder register.\n\n"
        f"Eligible after exclusions: {verification['exclusions']['eligible_rows']}; planned A/B/C: {verification['lanes']['A']['rows']}/{verification['lanes']['B']['rows']}/{verification['lanes']['C']['rows']}; remainder: {verification['remainder']['rows']}.\n",
        encoding="utf-8",
    )


def main() -> None:
    source = validate_input()
    fields = list(source[0])
    source_ids = {row["product_external_id"] for row in source}
    reasons = exclusion_reasons(source_ids)
    excluded_ids = set(reasons)
    exclusions = [{"product_external_id": external_id, "exclusion_reasons": "|".join(reasons[external_id])} for external_id in sorted(reasons)]
    write_rows(EXCLUSIONS, ["product_external_id", "exclusion_reasons"], exclusions)
    eligible = [row for row in source if row["product_external_id"] not in excluded_ids]

    candidates = {
        "A": [row for row in eligible if row["category_external_id"] in LANE_A],
        "B": [row for row in eligible if row["category_external_id"] in LANE_B],
        "C": [row for row in eligible if row["category_external_id"] not in LANE_A | LANE_B],
    }
    selected = {lane: rows[:CAPACITY] for lane, rows in candidates.items()}
    remainder = sorted([
        {**row, "planned_lane": lane, "remainder_reason": "lane_capacity_reached"}
        for lane, rows in candidates.items()
        for row in rows[CAPACITY:]
    ], key=lambda row: int(row["priority"]))
    destinations = {"A": QUEUE_A, "B": QUEUE_B, "C": QUEUE_C}
    for lane, path in destinations.items():
        write_rows(path, fields, selected[lane])
    write_rows(REMAINDER, fields + ["planned_lane", "remainder_reason"], remainder)

    lane_ids = {lane: {row["product_external_id"] for row in rows} for lane, rows in selected.items()}
    remainder_ids = {row["product_external_id"] for row in remainder}
    if any(lane_ids[left] & lane_ids[right] for left in lane_ids for right in lane_ids if left < right) or any(remainder_ids & lane_ids[lane] for lane in lane_ids):
        raise SystemExit("Wave223-C queue overlap")
    if set().union(*lane_ids.values(), remainder_ids) != {row["product_external_id"] for row in eligible}:
        raise SystemExit("Wave223-C did not partition every eligible record")
    if any(len(rows) > CAPACITY for rows in selected.values()) or any(row["category_external_id"] not in ALLOWED_B2B_CATEGORIES for rows in selected.values() for row in rows):
        raise SystemExit("Wave223-C lane capacity/category breach")
    for rows in [*selected.values(), remainder]:
        priorities = [int(row["priority"]) for row in rows]
        if priorities != sorted(priorities):
            raise SystemExit("Wave223-C lane ordering drift")

    artifacts = (QUEUE_A, QUEUE_B, QUEUE_C, REMAINDER, EXCLUSIONS)
    first = {path.name: path.read_bytes() for path in artifacts}
    # A second pure rendering is intentionally byte-compared before publishing
    # the receipt; it does not contact a source or an application service.
    for lane, path in destinations.items(): write_rows(path, fields, selected[lane])
    write_rows(REMAINDER, fields + ["planned_lane", "remainder_reason"], remainder)
    write_rows(EXCLUSIONS, ["product_external_id", "exclusion_reasons"], exclusions)
    identical = {path.name: first[path.name] == path.read_bytes() for path in artifacts}
    if not all(identical.values()):
        raise SystemExit(f"Wave223-C non-deterministic output: {identical}")

    verification = {
        "schema_version": 1,
        "wave": "wave223c",
        "input": {"path": INPUT.relative_to(ROOT).as_posix(), "sha256": sha256(INPUT), "rows": len(source), "unique_ids": len(source_ids), "deterministic_priority_sequence": True, "allowed_b2b_categories": sorted(ALLOWED_B2B_CATEGORIES), "excluded_irrelevant_categories_present": []},
        "exclusions": {"wave220_historical_identity_research_input_overlap": 596, "wave220_applied15_input_overlap": 4, "rows": len(exclusions), "eligible_rows": len(eligible), "path": EXCLUSIONS.relative_to(ROOT).as_posix(), "sha256": sha256(EXCLUSIONS)},
        "lanes": {lane: {"path": destinations[lane].relative_to(ROOT).as_posix(), "rows": len(selected[lane]), "capacity": CAPACITY, "unique_ids": len(lane_ids[lane]), "category_counts": dict(sorted(Counter(row["category_external_id"] for row in selected[lane]).items())), "sha256": sha256(destinations[lane])} for lane in ("A", "B", "C")},
        "remainder": {"path": REMAINDER.relative_to(ROOT).as_posix(), "rows": len(remainder), "unique_ids": len(remainder_ids), "sha256": sha256(REMAINDER), "reason": "lane_capacity_reached"},
        "partition": {"input_ids": len(source_ids), "excluded_ids": len(excluded_ids), "eligible_ids": len(eligible), "selected_ids": sum(len(values) for values in lane_ids.values()), "remainder_ids": len(remainder_ids), "queue_overlap_ids": [], "remainder_overlap_ids": [], "unpartitioned_eligible_ids": []},
        "byte_identical_rerun": identical,
        "automatic_web_requests": 0,
        "automatic_database_queries": 0,
        "automatic_database_mutations": 0,
        "apply_performed": False,
    }
    VERIFY.write_text(json.dumps(verification, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_report(verification)
    print(json.dumps({"source": len(source), "excluded": len(exclusions), "eligible": len(eligible), "A": len(selected["A"]), "B": len(selected["B"]), "C": len(selected["C"]), "remainder": len(remainder), "rerun": all(identical.values())}))


if __name__ == "__main__":
    main()
