#!/usr/bin/env python3
"""Build the fail-closed Wave203 evidence partition left after POS and capture."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "docs/audits/generated/wave203-industrial-unassigned-preparation.csv"
REGISTRY = ROOT / "docs/audits/evidence/wave203-remaining-official-source-evidence.json"
SNAPSHOT_INDEX = ROOT / "docs/audits/sources/wave203-remaining/snapshot-index.json"
OUTPUT = ROOT / "docs/audits/generated/wave203-remaining-evidence.csv"
SUMMARY = ROOT / "docs/audits/generated/wave203-remaining-evidence-summary.json"

POS_BRANDS = {
    "VeriFone", "Ingenico", "Pax", "Castles", "Dejavoo", "FirstData",
    "Hypercom", "Newpos", "Sagem", "Sunmi", "Bitel",
}
CAPTURE_BRANDS = {
    "CipherLab", "Casio", "Opticon", "Unitech", "LXE", "Bluebird",
    "Denso", "Handheld", "M3 Mobile", "Psion", "TEKLOGIX",
}
OFFICIAL_HOST_SUFFIXES = (
    "cino.com.tw",
    "koamtac.com",
    "orderman.com",
    "urovo.com",
    "honeywell.com",
    "honeywellaidc.com",
    "keyence.co.jp",
    "leica-geosystems.com",
)
ALLOWED_CLASSIFICATIONS = {"exact_safe", "compatibility_only", "conflict", "no_evidence"}
ALLOWED_SOURCE_TIERS = {"manufacturer_primary", "manufacturer_service_primary"}
EXPECTED_RECOMMENDED = 143
EXPECTED_POS = 42
EXPECTED_CAPTURE = 74
EXPECTED_REMAINING = 27

FIELDS = [
    "batch", "product_external_id", "brand_or_series", "name", "model_tokens",
    "partition", "evidence_scope", "source_tier", "source_publisher",
    "source_url", "source_assertion", "verified_facts",
    "snapshot_path", "snapshot_sha256",
    "unsupported_legacy_claims", "conflict_reason", "replacement_manufacturer",
    "replacement_mpn", "manufacturer_mpn_inference", "repeat_handling",
    "safe_to_apply",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def is_official_https(url: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    return parsed.scheme == "https" and any(
        host == suffix or host.endswith("." + suffix)
        for suffix in OFFICIAL_HOST_SUFFIXES
    )


def validate_registry(data: dict, candidate_ids: set[str], snapshot_index: dict) -> dict[str, dict]:
    if data.get("schema_version") != 1:
        raise SystemExit("Evidence registry schema_version must be 1")
    records = data.get("evidence")
    if not isinstance(records, list):
        raise SystemExit("Evidence registry must contain an evidence list")

    snapshots = {source["source_id"]: source for source in snapshot_index.get("sources", [])}
    by_id: dict[str, dict] = {}
    for record in records:
        external_id = record.get("product_external_id", "")
        if external_id in by_id:
            raise SystemExit(f"Duplicate evidence record: {external_id}")
        if external_id not in candidate_ids:
            raise SystemExit(f"Evidence record is outside the remaining partition: {external_id}")
        if record.get("classification") not in ALLOWED_CLASSIFICATIONS - {"no_evidence"}:
            raise SystemExit(f"Invalid sourced classification for {external_id}")
        if record.get("source_tier") not in ALLOWED_SOURCE_TIERS:
            raise SystemExit(f"Non-primary source tier for {external_id}")
        if not is_official_https(record.get("source_url", "")):
            raise SystemExit(f"Non-official or non-HTTPS source for {external_id}")

        record = dict(record)
        exact = record["classification"] == "exact_safe"
        if exact:
            if record.get("identity_assertion") != "exact_oem_part":
                raise SystemExit(f"Exact identity lacks exact official part assertion: {external_id}")
            if not record.get("replacement_manufacturer") or not record.get("replacement_mpn"):
                raise SystemExit(f"Exact identity lacks manufacturer/MPN: {external_id}")
            snapshot = snapshots.get(record.get("source_id"))
            if not snapshot:
                record["_snapshot_hold_reason"] = "pinned snapshot index record is missing"
            elif snapshot.get("snapshot_path") != record.get("snapshot_path") or snapshot.get("snapshot_sha256") != record.get("snapshot_sha256"):
                record["_snapshot_hold_reason"] = "snapshot metadata drifted"
            else:
                snapshot_path = ROOT / record["snapshot_path"]
                if not snapshot_path.is_file() or sha256(snapshot_path) != record["snapshot_sha256"]:
                    record["_snapshot_hold_reason"] = "snapshot is missing or hash-mismatched"
                elif not all(snapshot.get("token_counts", {}).get(token, 0) > 0 for token in snapshot.get("required_exact_tokens", [])):
                    record["_snapshot_hold_reason"] = "snapshot token evidence is incomplete"
        elif any((record.get("replacement_manufacturer"), record.get("replacement_mpn"))):
            raise SystemExit(f"Compatibility/conflict row inferred identity: {external_id}")
        by_id[external_id] = record
    return by_id


def main() -> None:
    all_rows = read_csv(INPUT)
    recommended = [
        row for row in all_rows
        if row["recommended_wave"] == "wave203" and row["repeat_handling"] == "new"
    ]
    pos = [row for row in recommended if row["brand_or_series"] in POS_BRANDS]
    capture = [row for row in recommended if row["brand_or_series"] in CAPTURE_BRANDS]
    remaining = [
        row for row in recommended
        if row["brand_or_series"] not in POS_BRANDS | CAPTURE_BRANDS
    ]

    partitions = [
        {row["product_external_id"] for row in partition}
        for partition in (pos, capture, remaining)
    ]
    if [len(recommended), len(pos), len(capture), len(remaining)] != [
        EXPECTED_RECOMMENDED, EXPECTED_POS, EXPECTED_CAPTURE, EXPECTED_REMAINING
    ]:
        raise SystemExit("Wave203 partition counts drifted")
    if any(partitions[i] & partitions[j] for i in range(3) for j in range(i + 1, 3)):
        raise SystemExit("Wave203 partitions overlap")
    if set().union(*partitions) != {row["product_external_id"] for row in recommended}:
        raise SystemExit("Wave203 partitions do not cover every recommended row")

    registry_data = json.loads(REGISTRY.read_text(encoding="utf-8-sig"))
    snapshot_index = (
        json.loads(SNAPSHOT_INDEX.read_text(encoding="utf-8-sig"))
        if SNAPSHOT_INDEX.is_file()
        else {"schema_version": 1, "sources": []}
    )
    registry = validate_registry(registry_data, partitions[2], snapshot_index)
    evidence_rows = []
    for candidate in remaining:
        external_id = candidate["product_external_id"]
        source = registry.get(external_id)
        if source:
            snapshot_hold = source.get("_snapshot_hold_reason", "")
            classification = "no_evidence" if snapshot_hold else source["classification"]
            exact = classification == "exact_safe"
            evidence_rows.append({
                "batch": "wave203_remaining_mobile_computers_pos_data_capture",
                "product_external_id": external_id,
                "brand_or_series": candidate["brand_or_series"],
                "name": candidate["name"],
                "model_tokens": candidate["model_tokens_unverified"],
                "partition": classification,
                "evidence_scope": "exact_snapshot_validation_hold" if snapshot_hold else source["evidence_scope"],
                "source_tier": source["source_tier"],
                "source_publisher": source["source_publisher"],
                "source_url": source["source_url"],
                "source_assertion": source["source_assertion"],
                "verified_facts": source["verified_facts"],
                "snapshot_path": source.get("snapshot_path", ""),
                "snapshot_sha256": source.get("snapshot_sha256", ""),
                "unsupported_legacy_claims": source["unsupported_legacy_claims"],
                "conflict_reason": f"Pinned exact evidence held: {snapshot_hold}." if snapshot_hold else source["conflict_reason"],
                "replacement_manufacturer": source["replacement_manufacturer"] if exact else "",
                "replacement_mpn": source["replacement_mpn"] if exact else "",
                "manufacturer_mpn_inference": "explicit_official_exact_part_only" if exact else "none",
                "repeat_handling": "snapshot_validation_hold" if snapshot_hold else ("new_exact_source" if exact else "new_review"),
                "safe_to_apply": "true" if exact else "false",
            })
        else:
            evidence_rows.append({
                "batch": "wave203_remaining_mobile_computers_pos_data_capture",
                "product_external_id": external_id,
                "brand_or_series": candidate["brand_or_series"],
                "name": candidate["name"],
                "model_tokens": candidate["model_tokens_unverified"],
                "partition": "no_evidence",
                "evidence_scope": "none_for_exact_offered_pack",
                "source_tier": "none",
                "source_publisher": "",
                "source_url": "",
                "source_assertion": "",
                "verified_facts": "",
                "snapshot_path": "",
                "snapshot_sha256": "",
                "unsupported_legacy_claims": "replacement_pack_identity|legacy_capacity|legacy_compatibility",
                "conflict_reason": "No accessible primary manufacturer/service/accessory source tied the offered pack to an exact OEM part.",
                "replacement_manufacturer": "",
                "replacement_mpn": "",
                "manufacturer_mpn_inference": "none",
                "repeat_handling": "new_review",
                "safe_to_apply": "false",
            })

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(evidence_rows)

    counts = Counter(row["partition"] for row in evidence_rows)
    exact_ids = sorted(row["product_external_id"] for row in evidence_rows if row["safe_to_apply"] == "true")
    summary = {
        "schema_version": 1,
        "site": "microchips-by",
        "batch": "wave203_remaining_mobile_computers_pos_data_capture",
        "created_at": "2026-07-29",
        "input": {"path": INPUT.relative_to(ROOT).as_posix(), "sha256": sha256(INPUT), "recommended_rows": len(recommended)},
        "registry": {"path": REGISTRY.relative_to(ROOT).as_posix(), "sha256": sha256(REGISTRY), "pinned_records": len(registry)},
        "snapshot_index": {"path": SNAPSHOT_INDEX.relative_to(ROOT).as_posix(), "sha256": sha256(SNAPSHOT_INDEX), "sources": len(snapshot_index.get("sources", []))},
        "output": {"path": OUTPUT.relative_to(ROOT).as_posix(), "sha256": sha256(OUTPUT), "rows": len(evidence_rows)},
        "partition_counts": dict(sorted(counts.items())),
        "cross_partition_coverage": {
            "pos_rows": len(pos),
            "capture_rows": len(capture),
            "remaining_rows": len(remaining),
            "union_rows": len(set().union(*partitions)),
            "expected_rows": EXPECTED_RECOMMENDED,
            "pairwise_overlap_rows": 0,
            "uncovered_rows": 0,
        },
        "safe_to_apply": {"rows": len(exact_ids), "external_ids": exact_ids},
        "exact_snapshot_evidence": [
            {
                "product_external_id": row["product_external_id"],
                "snapshot_path": row["snapshot_path"],
                "snapshot_sha256": row["snapshot_sha256"],
            }
            for row in evidence_rows if row["safe_to_apply"] == "true"
        ],
        "snapshot_validation_holds": [
            row["product_external_id"]
            for row in evidence_rows if row["repeat_handling"] == "snapshot_validation_hold"
        ],
        "policy": {
            "manufacturer_service_accessory_sources_only": True,
            "device_compatibility_does_not_identify_aftermarket_pack": True,
            "exact_application_requires_pinned_explicit_official_part": True,
            "database_mutations": 0,
        },
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
