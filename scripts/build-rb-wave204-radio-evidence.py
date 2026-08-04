#!/usr/bin/env python3
"""Build the fail-closed Wave204 radio-station battery-pack evidence registry."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "docs/audits/generated/wave203-industrial-unassigned-preparation.csv"
REGISTRY = ROOT / "docs/audits/evidence/wave204-radio-official-source-evidence.json"
SNAPSHOT_INDEX = ROOT / "docs/audits/sources/wave204-radio/snapshot-index.json"
OUTPUT = ROOT / "docs/audits/generated/wave204-radio-evidence.csv"
SUMMARY = ROOT / "docs/audits/generated/wave204-radio-evidence-summary.json"

EXPECTED_ROWS = 41
ALLOWED_CLASSIFICATIONS = {"exact_safe", "compatibility_only", "conflict"}
ALLOWED_SOURCE_TIERS = {"manufacturer_primary", "manufacturer_service_primary"}
OFFICIAL_HOST_SUFFIXES = ("alinco.com",)
LOOKALIKE_NOT_DUPLICATE = {"bitrix:2391", "bitrix:2395"}
PRIOR_EVIDENCE_PATTERNS = ("*wave200*evidence.csv", "*wave201*evidence.csv", "*wave202*evidence.csv", "*wave203*evidence.csv")

FIELDS = [
    "batch", "product_external_id", "brand_or_series", "name", "model_tokens",
    "partition", "evidence_scope", "source_tier", "source_publisher",
    "source_url", "source_assertion", "verified_facts", "snapshot_path",
    "snapshot_sha256", "unsupported_legacy_claims", "conflict_reason",
    "replacement_manufacturer", "replacement_mpn", "manufacturer_mpn_inference",
    "repeat_handling", "duplicate_review", "strict_duplicate_cluster",
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
        host == suffix or host.endswith("." + suffix) for suffix in OFFICIAL_HOST_SUFFIXES
    )


def prior_processed_ids() -> set[str]:
    ids: set[str] = set()
    seen_paths: set[Path] = set()
    for pattern in PRIOR_EVIDENCE_PATTERNS:
        for path in (ROOT / "docs/audits/generated").glob(pattern):
            if path in seen_paths:
                continue
            seen_paths.add(path)
            try:
                ids.update(row.get("product_external_id", "") for row in read_csv(path))
            except (UnicodeDecodeError, csv.Error):
                continue
    return ids - {""}


def normalized_name(value: str) -> str:
    return re.sub(r"[^0-9a-zа-я]+", "", value.casefold().replace("ё", "е"))


def validate_registry(data: dict, candidate_ids: set[str], snapshot_index: dict) -> dict[str, dict]:
    if data.get("schema_version") != 1:
        raise SystemExit("Evidence registry schema_version must be 1")
    records = data.get("evidence")
    if not isinstance(records, list):
        raise SystemExit("Evidence registry must contain an evidence list")
    snapshots = {source["source_id"]: source for source in snapshot_index.get("sources", [])}
    by_id: dict[str, dict] = {}
    for raw in records:
        record = dict(raw)
        external_id = record.get("product_external_id", "")
        if external_id in by_id:
            raise SystemExit(f"Duplicate evidence record: {external_id}")
        if external_id not in candidate_ids:
            raise SystemExit(f"Evidence record outside radio partition: {external_id}")
        if record.get("classification") not in ALLOWED_CLASSIFICATIONS:
            raise SystemExit(f"Invalid sourced classification: {external_id}")
        if record.get("source_tier") not in ALLOWED_SOURCE_TIERS:
            raise SystemExit(f"Non-primary source tier: {external_id}")
        if not is_official_https(record.get("source_url", "")):
            raise SystemExit(f"Non-official or non-HTTPS source: {external_id}")

        exact = record["classification"] == "exact_safe"
        if exact:
            if record.get("identity_assertion") != "exact_oem_part":
                raise SystemExit(f"Exact row lacks explicit OEM-part assertion: {external_id}")
            if not record.get("replacement_manufacturer") or not record.get("replacement_mpn"):
                raise SystemExit(f"Exact row lacks manufacturer/MPN: {external_id}")
            required = record.get("required_exact_tokens")
            snapshot = snapshots.get(record.get("source_id"))
            hold = ""
            if not isinstance(required, list) or len(required) < 2 or not all(required):
                hold = "record lacks exact token requirements"
            elif not snapshot:
                hold = "pinned snapshot index record is missing"
            else:
                path = ROOT / snapshot.get("snapshot_path", "")
                if not path.is_file() or sha256(path) != snapshot.get("snapshot_sha256"):
                    hold = "snapshot is missing or hash-mismatched"
                elif not all(snapshot.get("token_counts", {}).get(token, 0) > 0 for token in required):
                    hold = "snapshot lacks one or more row-exact tokens"
            record["_snapshot_hold_reason"] = hold
            if snapshot:
                record["_snapshot_path"] = snapshot.get("snapshot_path", "")
                record["_snapshot_sha256"] = snapshot.get("snapshot_sha256", "")
        elif any((record.get("replacement_manufacturer"), record.get("replacement_mpn"))):
            raise SystemExit(f"Unsafe row inferred manufacturer/MPN: {external_id}")
        by_id[external_id] = record
    return by_id


def main() -> None:
    candidates = [
        row for row in read_csv(INPUT)
        if row["family"] == "radio_station_battery_packs" and row["repeat_handling"] == "new"
    ]
    if len(candidates) != EXPECTED_ROWS:
        raise SystemExit(f"Radio partition drifted: expected {EXPECTED_ROWS}, got {len(candidates)}")
    candidate_ids = {row["product_external_id"] for row in candidates}
    if len(candidate_ids) != EXPECTED_ROWS:
        raise SystemExit("Radio partition contains duplicate external IDs")
    prior_overlap = sorted(candidate_ids & prior_processed_ids())
    if prior_overlap:
        raise SystemExit(f"Wave204 repeats prior evidence IDs: {', '.join(prior_overlap)}")

    normalized = Counter(normalized_name(row["name"]) for row in candidates)
    if any(count > 1 for count in normalized.values()):
        raise SystemExit("Strict duplicate full-name fingerprint found inside Wave204 input")

    registry_data = json.loads(REGISTRY.read_text(encoding="utf-8-sig"))
    snapshot_index = json.loads(SNAPSHOT_INDEX.read_text(encoding="utf-8-sig"))
    registry = validate_registry(registry_data, candidate_ids, snapshot_index)
    evidence_rows = []
    for candidate in candidates:
        external_id = candidate["product_external_id"]
        source = registry.get(external_id)
        duplicate_review = (
            "lookalike_variant_not_strict_duplicate"
            if external_id in LOOKALIKE_NOT_DUPLICATE else "no_strict_duplicate"
        )
        if source:
            snapshot_hold = source.get("_snapshot_hold_reason", "")
            partition = "no_evidence" if snapshot_hold else source["classification"]
            exact = partition == "exact_safe"
            evidence_rows.append({
                "batch": "wave204_radio_station_battery_packs",
                "product_external_id": external_id,
                "brand_or_series": candidate["brand_or_series"],
                "name": candidate["name"],
                "model_tokens": candidate["model_tokens_unverified"],
                "partition": partition,
                "evidence_scope": "exact_snapshot_validation_hold" if snapshot_hold else source["evidence_scope"],
                "source_tier": source["source_tier"],
                "source_publisher": source["source_publisher"],
                "source_url": source["source_url"],
                "source_assertion": source["source_assertion"],
                "verified_facts": source["verified_facts"],
                "snapshot_path": source.get("_snapshot_path", "") if exact else "",
                "snapshot_sha256": source.get("_snapshot_sha256", "") if exact else "",
                "unsupported_legacy_claims": source["unsupported_legacy_claims"],
                "conflict_reason": f"Pinned exact evidence held: {snapshot_hold}." if snapshot_hold else source["conflict_reason"],
                "replacement_manufacturer": source["replacement_manufacturer"] if exact else "",
                "replacement_mpn": source["replacement_mpn"] if exact else "",
                "manufacturer_mpn_inference": "explicit_official_exact_part_only" if exact else "none",
                "repeat_handling": "snapshot_validation_hold" if snapshot_hold else ("new_exact_source" if exact else "new_review"),
                "duplicate_review": duplicate_review,
                "strict_duplicate_cluster": "",
                "safe_to_apply": "true" if exact else "false",
            })
        else:
            evidence_rows.append({
                "batch": "wave204_radio_station_battery_packs",
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
                "unsupported_legacy_claims": "offered_pack_identity|chemistry|capacity|voltage|radio_compatibility",
                "conflict_reason": "No accessible primary manufacturer/service/accessory source tied the offered pack to an exact part.",
                "replacement_manufacturer": "",
                "replacement_mpn": "",
                "manufacturer_mpn_inference": "none",
                "repeat_handling": "new_review",
                "duplicate_review": duplicate_review,
                "strict_duplicate_cluster": "",
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
        "batch": "wave204_radio_station_battery_packs",
        "created_at": "2026-07-29",
        "input": {"path": INPUT.relative_to(ROOT).as_posix(), "sha256": sha256(INPUT), "rows": len(candidates)},
        "registry": {"path": REGISTRY.relative_to(ROOT).as_posix(), "sha256": sha256(REGISTRY), "pinned_records": len(registry)},
        "snapshot_index": {"path": SNAPSHOT_INDEX.relative_to(ROOT).as_posix(), "sha256": sha256(SNAPSHOT_INDEX), "sources": len(snapshot_index.get("sources", []))},
        "output": {"path": OUTPUT.relative_to(ROOT).as_posix(), "sha256": sha256(OUTPUT), "rows": len(evidence_rows)},
        "partition_counts": dict(sorted(counts.items())),
        "safe_to_apply": {"rows": len(exact_ids), "external_ids": exact_ids},
        "prior_evidence_overlap_rows": 0,
        "strict_duplicates": {"clusters": 0, "rows": 0},
        "lookalike_not_duplicate": {
            "pairs": [["bitrix:2391", "bitrix:2395"]],
            "reason": "Different offered manufacturers and capacities (Ajetrays 1650mAh versus Alinco 1500mAh); shared OEM reference token is insufficient for collapse.",
        },
        "policy": {
            "manufacturer_service_accessory_sources_only": True,
            "device_compatibility_does_not_identify_aftermarket_pack": True,
            "exact_requires_snapshot_sha_and_row_exact_tokens": True,
            "database_mutations": 0,
        },
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
