#!/usr/bin/env python3
"""Build the fail-closed Wave203 evidence ledger for legacy data-capture batteries."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "docs/audits/generated/wave203-industrial-unassigned-preparation.csv"
DEFAULT_OUTPUT = ROOT / "docs/audits/generated/wave203-capture-evidence.csv"
DEFAULT_SUMMARY = ROOT / "docs/audits/generated/wave203-capture-evidence-summary.json"
PRIOR_MANIFEST = ROOT / "docs/imports/rb-source-backed-description-drafts-b2b-terminals-wave174-2026-07-29.json"

TARGET_BRANDS = {
    "Bluebird",
    "Casio",
    "CipherLab",
    "Denso",
    "Handheld",
    "LXE",
    "M3 Mobile",
    "Opticon",
    "Psion",
    "TEKLOGIX",
    "Unitech",
}
EXPECTED_BRAND_COUNTS = {
    "Bluebird": 6,
    "Casio": 11,
    "CipherLab": 13,
    "Denso": 2,
    "Handheld": 3,
    "LXE": 10,
    "M3 Mobile": 5,
    "Opticon": 11,
    "Psion": 4,
    "TEKLOGIX": 3,
    "Unitech": 6,
}

CASIO_IT9000 = "https://www.casio-solutions.com/global/downloads/euro/technical-specification_it9000.pdf"
CASIO_ITG400 = "https://support.casio.jp/storage/pdf/010/IT-G400_JA_Web_201102.pdf"
CIPHERLAB_CP60 = "https://www.cipherlab.com/files/CipherLab_CP60_Mobile_Computer_EN_Brochure.pdf"
HANDHELD_X8 = "https://www.handheldgroup.com/globalassets/downloads/product-information/brochures-and-manuals/nautiz/nautiz-x8-manual.pdf"
M3_SM20 = "https://m3mobile.net/eng/business/detail.html?bid=22&bid_2=23&id=32"
M3_SMART = "https://www.m3mobile.net/upload/download/M3SMART_PR_EN_Ver.1.0.pdf"
OPTICON_H13 = "https://www.opticon.com/support/LEGACY/H-13/H-13%20Quick%20Start%20Guide.pdf"
OPTICON_H27 = "https://www.opticon.com/support/LEGACY/H-27/H-27%20Leaflet.pdf"
OPTICON_PX35 = "https://www.opticon.com/support/LEGACY/PX-35/PX-35%20Quick%20Start%20Guide.pdf"
UNITECH_HT682 = "https://www.ute.com/en/products/detail/HT682"
UNITECH_PA550 = "https://www.ute.com/jp/products/detail/PA550"
UNITECH_PA700 = "https://www.ute.com/jp/products/detail/PA700"
DENSO_BHT500 = "https://www.denso-wave.com/en/adcd/download/category/manual/bht_bht/BHT-500-Guide.html"

FIELDNAMES = [
    "brand_or_series",
    "product_external_id",
    "name",
    "model_tokens_unverified",
    "partition",
    "evidence_scope",
    "source_tier",
    "source_urls",
    "verified_facts",
    "unsupported_legacy_claims",
    "conflict_reason",
    "replacement_manufacturer",
    "replacement_mpn",
    "repeat_handling",
    "safe_to_apply",
]

TOKEN_RE = re.compile(
    r"(?i)(?<![A-Z0-9])(?:HA-[A-Z0-9-]+|BA-[A-Z0-9-]+|BAT-[A-Z0-9_]+|"
    r"BTR\d+|NX\d+-\d+|SM\d+-[A-Z0-9-]+|\d{4}-\d{6,7}[A-Z]?|"
    r"\d{7}|A\d{10}|MX\d+[A-Z0-9-]*BATT)(?![A-Z0-9])"
)

# Manufacturer documents below define OEM accessories or device battery variants.  They
# do not prove that an offered legacy replacement pack was manufactured by that OEM.
OVERRIDES: dict[str, dict[str, str]] = {
    "bitrix:12143": {
        "partition": "compatibility_only",
        "scope": "official_oem_part_context_only",
        "urls": CASIO_IT9000,
        "facts": "HA-G20BAT is a Casio 7.4V 2000mAh battery pack used by an official Casio terminal family",
        "unsupported": "offered_pack_manufacturer;offered_pack_identity;DT-X30_exact_compatibility",
    },
    "bitrix:12200": {
        "partition": "compatibility_only",
        "scope": "official_oem_part_and_device_context_only",
        "urls": CASIO_ITG400,
        "facts": "HA-R21LBAT is the Casio IT-G400 high-capacity 3.85V 5800mAh battery pack",
        "unsupported": "offered_pack_manufacturer;offered_pack_identity",
    },
    "bitrix:12214": {
        "partition": "compatibility_only",
        "scope": "official_device_battery_variant_only",
        "urls": CIPHERLAB_CP60,
        "facts": "CipherLab CP60 supports a rechargeable 3.7V 4400mAh extended battery variant",
        "unsupported": "offered_pack_manufacturer;offered_pack_mpn",
    },
    "bitrix:12284": {
        "partition": "compatibility_only",
        "scope": "official_device_battery_variant_only",
        "urls": UNITECH_HT682,
        "facts": "Unitech HT682 has a 3.7V 2200mAh standard battery; official P/N 1400-900001G",
        "unsupported": "offered_pack_manufacturer;offered_pack_mpn;PA690_scope",
    },
    "bitrix:12285": {
        "partition": "compatibility_only",
        "scope": "official_device_accessory_context_only",
        "urls": UNITECH_PA550,
        "facts": "Unitech lists spare battery P/N 1400-900008G for PA550",
        "unsupported": "legacy_capacity=2200mAh;offered_pack_manufacturer;offered_pack_mpn",
    },
    "bitrix:12286": {
        "partition": "compatibility_only",
        "scope": "official_device_accessory_context_only",
        "urls": UNITECH_PA700,
        "facts": "Unitech lists spare battery P/N 1400-900023G for PA700",
        "unsupported": "legacy_capacity=3000mAh;PA720_scope;offered_pack_manufacturer;offered_pack_mpn",
    },
    "bitrix:12334": {
        "partition": "conflict",
        "scope": "official_device_capacity_conflict",
        "urls": OPTICON_H27,
        "facts": "Opticon specifies the H-27 battery as 3.7V 2860mAh",
        "unsupported": "legacy_capacity=3000mAh;offered_pack_identity",
        "reason": "legacy 3000mAh conflicts with the official H-27 2860mAh specification",
    },
    "bitrix:12340": {
        "partition": "conflict",
        "scope": "official_oem_part_conflict",
        "urls": OPTICON_PX35,
        "facts": "Opticon identifies BTR0400 as the dedicated PX-35 rechargeable battery",
        "unsupported": "legacy_part=1400-203047G;legacy_capacity=1800mAh",
        "reason": "legacy part 1400-203047G conflicts with official PX-35 part BTR0400",
    },
    "bitrix:12341": {
        "partition": "conflict",
        "scope": "official_oem_part_device_conflict",
        "urls": OPTICON_H13,
        "facts": "Opticon identifies BTR0100 as the H-13 battery pack",
        "unsupported": "legacy_device=PX001;legacy_capacity=1100mAh",
        "reason": "official BTR0100 evidence is tied to H-13, not PX001",
    },
    "bitrix:24019": {
        "partition": "conflict",
        "scope": "cross_manufacturer_part_conflict",
        "urls": f"{OPTICON_H13}|{DENSO_BHT500}",
        "facts": "Opticon identifies BTR0100 as H-13 battery; Denso documents BHT-500 as its own terminal family",
        "unsupported": "legacy_part=BTR0100;legacy_capacity=1100mAh;Denso_BHT500_battery_identity",
        "reason": "legacy assigns Opticon part BTR0100 to a Denso BHT-500 product without Denso battery evidence",
    },
    "bitrix:12248": {
        "partition": "conflict",
        "scope": "official_exact_part_capacity_conflict",
        "urls": HANDHELD_X8,
        "facts": "Handheld defines NX8-1004 as the Nautiz X8 3.7V 5200mAh standard battery",
        "unsupported": "legacy_capacity=6800mAh",
        "reason": "legacy 6800mAh conflicts with official NX8-1004 capacity 5200mAh",
    },
    "bitrix:12310": {
        "partition": "conflict",
        "scope": "official_device_capacity_conflict",
        "urls": M3_SM20,
        "facts": "M3 Mobile specifies the SM20 standard battery as 3.8V 4100mAh",
        "unsupported": "legacy_part=SM20-BATT-S41;legacy_capacity=4200mAh",
        "reason": "legacy 4200mAh conflicts with current official SM20 standard capacity 4100mAh",
    },
    "bitrix:12311": {
        "partition": "conflict",
        "scope": "official_device_capacity_conflict",
        "urls": M3_SMART,
        "facts": "M3 Mobile specifies the M3 SMART standard battery as 3.7V 2200mAh",
        "unsupported": "legacy_capacity=2000mAh",
        "reason": "legacy 2000mAh conflicts with official M3 SMART standard capacity 2200mAh",
    },
}

CROSS_RECORD_CONFLICTS = {
    "bitrix:12179": "same legacy OEM token 1030070 also appears on bitrix:24023 under TEKLOGIX",
    "bitrix:24023": "same legacy OEM token 1030070 also appears on bitrix:12179 under Psion",
    "bitrix:12355": "same legacy device/capacity claim also appears on bitrix:24024 under TEKLOGIX",
    "bitrix:24024": "same legacy device/capacity claim also appears on bitrix:12355 under Psion",
    "bitrix:12190": "same legacy token NX5-2004 also appears on bitrix:24064 under Handheld",
    "bitrix:24064": "same legacy token NX5-2004 also appears on bitrix:12190 under Bluebird",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def extract_tokens(value: str) -> str:
    return ";".join(sorted({match.group(0).upper() for match in TOKEN_RE.finditer(value)}))


def classify(candidate: dict[str, str]) -> dict[str, str]:
    external_id = candidate["product_external_id"]
    row = {
        "brand_or_series": candidate["brand_or_series"],
        "product_external_id": external_id,
        "name": candidate["name"],
        "model_tokens_unverified": extract_tokens(candidate["name"]),
        "partition": "no_evidence",
        "evidence_scope": "none_for_exact_offered_pack",
        "source_tier": "none",
        "source_urls": "",
        "verified_facts": "",
        "unsupported_legacy_claims": "all_identity_capacity_voltage_and_compatibility_claims",
        "conflict_reason": "no pinned primary source identifies the exact offered replacement pack",
        "replacement_manufacturer": "",
        "replacement_mpn": "",
        "repeat_handling": "new_review",
        "safe_to_apply": "false",
    }
    override = OVERRIDES.get(external_id)
    if override:
        row.update(
            partition=override["partition"],
            evidence_scope=override["scope"],
            source_tier="manufacturer_primary",
            source_urls=override["urls"],
            verified_facts=override["facts"],
            unsupported_legacy_claims=override["unsupported"],
            conflict_reason=override.get("reason", "OEM device/accessory context does not identify the offered replacement pack"),
        )
    elif external_id in CROSS_RECORD_CONFLICTS:
        row.update(
            partition="conflict",
            evidence_scope="legacy_cross_record_identity_collision",
            source_tier="internal_legacy_collision",
            unsupported_legacy_claims="replacement_pack_identity;manufacturer;mpn",
            conflict_reason=CROSS_RECORD_CONFLICTS[external_id],
        )
    return row


def build(input_path: Path, output_path: Path, summary_path: Path) -> dict[str, object]:
    with input_path.open(encoding="utf-8-sig", newline="") as handle:
        input_rows = list(csv.DictReader(handle))
    candidates = [
        row
        for row in input_rows
        if row["recommended_wave"] == "wave203"
        and row["repeat_handling"] == "new"
        and row["brand_or_series"] in TARGET_BRANDS
    ]
    brand_counts = Counter(row["brand_or_series"] for row in candidates)
    if dict(sorted(brand_counts.items())) != EXPECTED_BRAND_COUNTS:
        raise ValueError(f"Wave203 capture partition drift: {dict(sorted(brand_counts.items()))}")
    if len(candidates) != 74 or len({row["product_external_id"] for row in candidates}) != 74:
        raise ValueError("Wave203 capture partition must contain 74 unique candidates")

    prior = json.loads(PRIOR_MANIFEST.read_text(encoding="utf-8-sig"))
    prior_ids = {row["external_id"] for row in prior["products"]}
    repeated = sorted({row["product_external_id"] for row in candidates} & prior_ids)
    if repeated:
        raise ValueError(f"Previously processed IDs leaked into Wave203 capture partition: {repeated}")

    rows = [classify(candidate) for candidate in candidates]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    partition_counts = Counter(row["partition"] for row in rows)
    official_sources = sorted(
        {
            url
            for row in rows
            for url in row["source_urls"].split("|")
            if url
        }
    )
    summary: dict[str, object] = {
        "schema_version": 1,
        "site": "microchips-by",
        "batch": "wave203_capture_legacy",
        "created_at": "2026-07-29",
        "input": {
            "path": input_path.relative_to(ROOT).as_posix(),
            "sha256": sha256(input_path),
            "candidate_rows": len(candidates),
        },
        "output": {
            "path": output_path.relative_to(ROOT).as_posix(),
            "sha256": sha256(output_path),
            "rows": len(rows),
        },
        "brand_counts": dict(sorted(brand_counts.items())),
        "partition_counts": dict(sorted(partition_counts.items())),
        "exact_safe_records": 0,
        "safe_to_apply_records": 0,
        "previously_processed_records": 0,
        "automatic_database_mutations": 0,
        "official_sources": official_sources,
        "policy": {
            "device_compatibility_is_not_offered_pack_identity": True,
            "oem_part_used_as_cross_reference_is_not_replacement_manufacturer_evidence": True,
            "unsupported_legacy_specs_are_not_promoted": True,
            "cross_record_collisions_are_held_for_deduplication": True,
        },
        "notes": [
            "All 74 candidates are read-only evidence rows; no database writes are performed.",
            "Official sources are pinned only where they establish a device, OEM accessory or an explicit conflict.",
            "No row proves the manufacturer and MPN of the exact offered replacement pack, so exact apply is zero.",
        ],
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    args = parser.parse_args()
    result = build(args.input, args.output, args.summary)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
