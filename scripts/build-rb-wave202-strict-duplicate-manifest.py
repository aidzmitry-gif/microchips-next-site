#!/usr/bin/env python3
"""Build the reviewed Wave 202 Motorola/Symbol noindex duplicate manifest."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


SITE_KEY = "microchips-by"
SOURCE_CSV = Path("docs/audits/generated/rb-wave202-commercial-duplicate-guard.csv")
EVIDENCE_CSV = Path(
    "docs/audits/generated/wave202-zebra-legacy-mobile-computers-evidence.csv"
)
MANIFEST_PATH = Path(
    "docs/imports/"
    "rb-reviewed-noindex-duplicates-motorola-symbol-wave202-2026-07-29.json"
)
SUMMARY_PATH = Path(
    "docs/audits/generated/rb-wave202-strict-duplicate-manifest-summary.json"
)
CATEGORY_IDS = ["seo:batteries-industrial"]

PAIR_PLANS = (
    {
        "survivor_external_id": "bitrix:12130",
        "duplicate_external_id": "bitrix:24006",
        "model_core": "BTRYMC30LA",
        "voltage": "3.7V",
        "capacity": "2740mAh",
    },
    {
        "survivor_external_id": "bitrix:12146",
        "duplicate_external_id": "bitrix:24007",
        "model_core": "BTRYMC30LA",
        "voltage": "3.7V",
        "capacity": "4800mAh",
    },
    {
        "survivor_external_id": "bitrix:12139",
        "duplicate_external_id": "bitrix:24008",
        "model_core": "BTRY-MC32-52MA-01",
        "voltage": "3.7V",
        "capacity": "5200mAh",
    },
    {
        "survivor_external_id": "bitrix:12142",
        "duplicate_external_id": "bitrix:24009",
        "model_core": "BTRY-MC55EAB00",
        "voltage": "3.7V",
        "capacity": "3600mAh",
    },
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=SOURCE_CSV)
    parser.add_argument("--evidence", type=Path, default=EVIDENCE_CSV)
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH)
    parser.add_argument("--summary", type=Path, default=SUMMARY_PATH)
    return parser.parse_args()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def read_rows(path: Path) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    by_external_id = {row["product_external_id"].strip(): row for row in rows}
    require(len(by_external_id) == len(rows), "Source repeats product_external_id")
    return by_external_id


def source_group_key(plan: dict[str, str]) -> str:
    return "|".join(
        (
            plan["model_core"].upper(),
            plan["voltage"].removesuffix("V"),
            plan["capacity"].removesuffix("mAh"),
        )
    )


def validate_source_row(row: dict[str, str], plan: dict[str, str]) -> None:
    external_id = row["product_external_id"].strip()
    require(row["batch"] == "zebra_legacy_mobile_computers", f"{external_id}: wrong batch")
    require(row["current_product"] == "true", f"{external_id}: product missing")
    require(row["current_product_status"] == "draft", f"{external_id}: status drift")
    require(row["rb_site_product"] == "true", f"{external_id}: RB product missing")
    require(row["rb_is_published"] == "true", f"{external_id}: unpublished")
    require(row["availability"] == "on_request", f"{external_id}: availability drift")
    require(row["current_price"] == "", f"{external_id}: price is present")
    require(row["currency"] == "", f"{external_id}: currency is present")
    require(row["price_evidence_count"] == "0", f"{external_id}: price evidence exists")
    require(
        row["current_price_evidence_count"] == "0",
        f"{external_id}: current price evidence exists",
    )
    require(row["verified_published_media_count"] == "0", f"{external_id}: verified media exists")
    require(row["offer_schema_present"] == "false", f"{external_id}: Offer schema exists")
    require(row["previously_processed"] == "false", f"{external_id}: already processed")
    require(row["strict_duplicate_candidate"] == "true", f"{external_id}: not a strict duplicate")
    require(row["strict_duplicate_group_size"] == "2", f"{external_id}: group is not a pair")
    require(
        row["strict_duplicate_group_key"].upper() == source_group_key(plan),
        f"{external_id}: strict duplicate key drift",
    )
    require(
        row["offer_claim_guard"] == "no_unsupported_commercial_claim",
        f"{external_id}: unsupported commercial claim",
    )


def validate_claim_evidence(
    survivor_evidence: dict[str, str], duplicate_evidence: dict[str, str], plan: dict[str, str]
) -> None:
    for row in (survivor_evidence, duplicate_evidence):
        external_id = row["product_external_id"]
        require(
            row["partition"] in {"conflict", "compatibility_only"},
            f"{external_id}: unexpected claim partition",
        )
        require(row["safe_to_apply"] == "false", f"{external_id}: claims unexpectedly safe")
        require(row["repeat_handling"] == "new_review", f"{external_id}: review state drift")
        require(
            row["explicit_legacy_part_tokens"].upper() == plan["model_core"].upper(),
            f"{external_id}: evidence part token drift",
        )
    require(
        survivor_evidence["partition"] == duplicate_evidence["partition"],
        "Pair has different adversarial partitions",
    )
    require(
        survivor_evidence["unsupported_legacy_claims"]
        == duplicate_evidence["unsupported_legacy_claims"],
        "Pair has different unsupported legacy claims",
    )


def build_pair(
    plan: dict[str, str],
    rows: dict[str, dict[str, str]],
    evidence_rows: dict[str, dict[str, str]],
) -> dict[str, object]:
    survivor = rows.get(plan["survivor_external_id"])
    duplicate = rows.get(plan["duplicate_external_id"])
    require(survivor is not None, f"Missing {plan['survivor_external_id']}")
    require(duplicate is not None, f"Missing {plan['duplicate_external_id']}")
    validate_source_row(survivor, plan)
    validate_source_row(duplicate, plan)
    survivor_evidence = evidence_rows.get(plan["survivor_external_id"])
    duplicate_evidence = evidence_rows.get(plan["duplicate_external_id"])
    require(survivor_evidence is not None, f"Missing evidence for {plan['survivor_external_id']}")
    require(duplicate_evidence is not None, f"Missing evidence for {plan['duplicate_external_id']}")
    validate_claim_evidence(survivor_evidence, duplicate_evidence, plan)

    survivor_name = survivor["legacy_name"].strip()
    duplicate_name = duplicate["legacy_name"].strip()
    require("Motorola" in survivor_name, f"{plan['survivor_external_id']}: survivor is not Motorola")
    require("Symbol" in duplicate_name, f"{plan['duplicate_external_id']}: duplicate is not Symbol")
    require(
        survivor_name.replace("Motorola", "Symbol") == duplicate_name,
        f"{plan['duplicate_external_id']}: pair differs beyond Motorola/Symbol alias",
    )

    survivor_number = plan["survivor_external_id"].split(":", 1)[1]
    duplicate_number = plan["duplicate_external_id"].split(":", 1)[1]
    return {
        "survivor_external_id": plan["survivor_external_id"],
        "duplicate_external_id": plan["duplicate_external_id"],
        "survivor_name": survivor_name,
        "duplicate_name": duplicate_name,
        "survivor_path": (
            "/catalog/industrial-batteries/batteries-industrial/"
            f"legacy-bitrix-{survivor_number}"
        ),
        "duplicate_path": (
            "/catalog/industrial-batteries/batteries-industrial/"
            f"legacy-bitrix-{duplicate_number}"
        ),
        "model_core": plan["model_core"],
        "voltage": plan["voltage"],
        "capacity": plan["capacity"],
        "availability": "on_request",
        "category_external_ids": CATEGORY_IDS,
        "decision_reason": (
            "The two legacy rows are identical after replacing Motorola with Symbol and "
            "share the same strict model/voltage/capacity group. This duplicate collapse "
            "does not verify or publish the disputed technical claims."
        ),
        "evidence_refs": [
            str(SOURCE_CSV).replace("\\", "/"),
            "docs/audits/generated/wave202-zebra-legacy-mobile-computers-evidence.csv",
            "docs/imports/rb-full-bitrix-staging-wave148-2026-07-28.json",
        ],
    }


def main() -> int:
    args = parse_args()
    source_rows = read_rows(args.source)
    evidence_rows = read_rows(args.evidence)
    duplicates = [
        build_pair(dict(plan), source_rows, evidence_rows) for plan in PAIR_PLANS
    ]
    source_display = (
        str(SOURCE_CSV).replace("\\", "/")
        if args.source.resolve() == SOURCE_CSV.resolve()
        else str(args.source).replace("\\", "/")
    )
    evidence_display = (
        str(EVIDENCE_CSV).replace("\\", "/")
        if args.evidence.resolve() == EVIDENCE_CSV.resolve()
        else str(args.evidence).replace("\\", "/")
    )
    selected_ids = {
        external_id
        for plan in PAIR_PLANS
        for external_id in (plan["survivor_external_id"], plan["duplicate_external_id"])
    }
    partitions = {
        partition: sum(
            evidence_rows[external_id]["partition"] == partition
            for external_id in selected_ids
        )
        for partition in ("conflict", "compatibility_only")
    }

    manifest = {
        "schema_version": 1,
        "site_key": SITE_KEY,
        "purpose": (
            "Collapse four strict Motorola/Symbol alias duplicate pairs while preserving "
            "the Motorola preview URL as survivor and creating permanent redirects."
        ),
        "duplicates": duplicates,
    }
    summary = {
        "schema_version": 1,
        "wave": "wave202",
        "site_key": SITE_KEY,
        "source": source_display,
        "claim_evidence_source": evidence_display,
        "source_candidate_records": len(source_rows),
        "strict_duplicate_groups": len(duplicates),
        "strict_duplicate_candidate_records": len(duplicates) * 2,
        "motorola_survivors": len(duplicates),
        "symbol_duplicates": len(duplicates),
        "no_price_records": len(duplicates) * 2,
        "no_price_evidence_records": len(duplicates) * 2,
        "no_verified_published_media_records": len(duplicates) * 2,
        "no_offer_schema_records": len(duplicates) * 2,
        "availability": "on_request",
        "claim_partition_counts": partitions,
        "technical_claims_promoted": 0,
        "database_verification": "required_by_command_dry_run",
        "automatic_database_mutations": 0,
    }

    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    args.summary.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
