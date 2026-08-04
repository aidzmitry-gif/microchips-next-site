#!/usr/bin/env python3
"""Build fail-closed evidence for 31 industrial remote-control battery rows."""

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
FULL_CATALOG = ROOT / "docs/audits/generated/full-catalog-canonical-registry.csv"
REGISTRY = ROOT / "docs/audits/evidence/wave204-remote-control-official-source-evidence.json"
SNAPSHOT_INDEX = ROOT / "docs/audits/sources/wave204-remote-control/snapshot-index.json"
OUTPUT = ROOT / "docs/audits/generated/wave204-remote-control-evidence.csv"
SUMMARY = ROOT / "docs/audits/generated/wave204-remote-control-evidence-summary.json"

EXPECTED_ROWS = 31
FAMILY = "industrial_remote_control_batteries"
ALLOWED_CLASSIFICATIONS = {"exact_safe", "compatibility_only", "conflict"}
ALLOWED_TIERS = {"manufacturer_primary", "manufacturer_service_primary"}
OFFICIAL_SUFFIXES = ("autecsafety.com", "elcaradio.com", "hiab.com")

FIELDS = [
    "batch", "product_external_id", "brand_or_series", "name", "model_tokens",
    "partition", "evidence_scope", "source_tier", "source_publisher", "source_url",
    "source_assertion", "verified_facts", "snapshot_path", "snapshot_sha256",
    "unsupported_legacy_claims", "conflict_reason", "replacement_manufacturer",
    "replacement_mpn", "manufacturer_mpn_inference", "repeat_handling",
    "strict_duplicate_key", "strict_duplicate_group_size", "strict_duplicate_candidate",
    "strict_duplicate_members", "safe_to_apply",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def normalized_alnum(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def official_https(url: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    return parsed.scheme == "https" and any(
        host == suffix or host.endswith("." + suffix) for suffix in OFFICIAL_SUFFIXES
    )


def validate_registry(candidate_by_id: dict[str, dict[str, str]]) -> tuple[dict[str, dict], dict]:
    registry_data = json.loads(REGISTRY.read_text(encoding="utf-8-sig"))
    snapshot_index = json.loads(SNAPSHOT_INDEX.read_text(encoding="utf-8-sig"))
    if registry_data.get("schema_version") != 1 or snapshot_index.get("schema_version") != 1:
        raise SystemExit("Wave204 registry/index schema_version must be 1")
    snapshots = {record["source_id"]: record for record in snapshot_index.get("sources", [])}
    by_id: dict[str, dict] = {}
    for source in registry_data.get("evidence", []):
        external_id = source.get("product_external_id", "")
        if external_id not in candidate_by_id:
            raise SystemExit(f"Evidence outside remote-control partition: {external_id}")
        if external_id in by_id:
            raise SystemExit(f"Duplicate evidence row: {external_id}")
        if source.get("classification") not in ALLOWED_CLASSIFICATIONS:
            raise SystemExit(f"Invalid classification: {external_id}")
        if source.get("source_tier") not in ALLOWED_TIERS or not official_https(source.get("source_url", "")):
            raise SystemExit(f"Non-primary source: {external_id}")
        snapshot = snapshots.get(source.get("source_id"))
        if not snapshot:
            raise SystemExit(f"Missing pinned source: {external_id}")
        snapshot_path = ROOT / snapshot["snapshot_path"]
        if not snapshot_path.is_file() or sha256(snapshot_path) != snapshot["snapshot_sha256"]:
            raise SystemExit(f"Snapshot hash mismatch: {external_id}")
        required = source.get("required_exact_tokens", [])
        if not required or any(
            token not in snapshot.get("required_exact_tokens", [])
            or snapshot.get("token_counts", {}).get(token, 0) < 1
            for token in required
        ):
            raise SystemExit(f"Exact token evidence incomplete: {external_id}")
        source = dict(source)
        source["snapshot_path"] = snapshot["snapshot_path"]
        source["snapshot_sha256"] = snapshot["snapshot_sha256"]
        if source["classification"] == "exact_safe":
            if source.get("identity_assertion") != "exact_oem_part":
                raise SystemExit(f"Exact identity assertion missing: {external_id}")
            if not source.get("replacement_manufacturer") or not source.get("replacement_mpn"):
                raise SystemExit(f"Exact manufacturer/MPN missing: {external_id}")
            candidate_name = normalized_alnum(candidate_by_id[external_id]["name"])
            source_identity_tokens = {
                normalized_alnum(token) for token in required
            } | {
                normalized_alnum(token).removesuffix("battery") for token in required
            }
            if not any(token and token in candidate_name for token in source_identity_tokens):
                raise SystemExit(f"Pinned source lacks an exact legacy identity token: {external_id}")
        elif source.get("replacement_manufacturer") or source.get("replacement_mpn"):
            raise SystemExit(f"Unsafe evidence inferred identity: {external_id}")
        by_id[external_id] = source
    return by_id, snapshot_index


def chemistry(name: str) -> str:
    match = re.search(r"\b(?:Ni-?MH|Ni-?Cd|Li-?ion|Li-?Pol)\b", name, re.I)
    return re.sub(r"[^a-z0-9]+", "", match.group(0).casefold()) if match else ""


def capacity(name: str) -> str:
    match = re.search(r"\b(\d+)\s*mAh\b", name, re.I)
    return match.group(1) if match else ""


def identity_tokens(candidate: dict[str, str]) -> list[str]:
    result = []
    for token in candidate["model_tokens_unverified"].split("|"):
        token = token.strip()
        if re.search(r"[A-Za-z]", token) and not re.fullmatch(r"\d+\s*mAh", token, re.I):
            result.append(token.upper())
    return result


def strict_duplicate_metadata(candidates: list[dict[str, str]]) -> dict[str, dict[str, object]]:
    full = rows(FULL_CATALOG)
    result = {}
    for candidate in candidates:
        tokens = identity_tokens(candidate)
        chem = chemistry(candidate["name"])
        cap = capacity(candidate["name"])
        members: set[str] = set()
        keys = []
        if tokens and chem and cap:
            for token in tokens:
                pattern = re.compile(rf"(?<![A-Za-z0-9]){re.escape(token)}(?![A-Za-z0-9])", re.I)
                matches = {
                    row["registry_id"] for row in full
                    if pattern.search(row["name"])
                    and chemistry(row["name"]) == chem
                    and capacity(row["name"]) == cap
                }
                if len(matches) > 1:
                    members.update(matches)
                    keys.append(f"{token}|{chem}|{cap}")
        result[candidate["product_external_id"]] = {
            "key": ";".join(sorted(keys)),
            "size": len(members),
            "candidate": len(members) > 1,
            "members": ";".join(sorted(members)),
        }
    return result


def main() -> None:
    candidates = [row for row in rows(INPUT) if row["family"] == FAMILY]
    if len(candidates) != EXPECTED_ROWS:
        raise SystemExit(f"Expected {EXPECTED_ROWS} remote-control rows, got {len(candidates)}")
    by_candidate = {row["product_external_id"]: row for row in candidates}
    if len(by_candidate) != EXPECTED_ROWS:
        raise SystemExit("Remote-control product_external_id values are not unique")
    evidence, snapshot_index = validate_registry(by_candidate)
    duplicates = strict_duplicate_metadata(candidates)

    output_rows = []
    for candidate in candidates:
        external_id = candidate["product_external_id"]
        source = evidence.get(external_id)
        duplicate = duplicates[external_id]
        if source:
            exact = source["classification"] == "exact_safe"
            output = {
                "batch": "wave204_industrial_remote_control_batteries",
                "product_external_id": external_id,
                "brand_or_series": candidate["brand_or_series"],
                "name": candidate["name"],
                "model_tokens": candidate["model_tokens_unverified"],
                "partition": source["classification"],
                "evidence_scope": source["evidence_scope"],
                "source_tier": source["source_tier"],
                "source_publisher": source["source_publisher"],
                "source_url": source["source_url"],
                "source_assertion": source["source_assertion"],
                "verified_facts": source["verified_facts"],
                "snapshot_path": source["snapshot_path"],
                "snapshot_sha256": source["snapshot_sha256"],
                "unsupported_legacy_claims": source["unsupported_legacy_claims"],
                "conflict_reason": source["conflict_reason"],
                "replacement_manufacturer": source["replacement_manufacturer"] if exact else "",
                "replacement_mpn": source["replacement_mpn"] if exact else "",
                "manufacturer_mpn_inference": "explicit_official_exact_part_only" if exact else "none",
                "repeat_handling": "new_exact_source" if exact else "new_review",
                "safe_to_apply": "true" if exact else "false",
            }
        else:
            output = {
                "batch": "wave204_industrial_remote_control_batteries",
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
                "unsupported_legacy_claims": "replacement_pack_identity|legacy_chemistry|legacy_capacity",
                "conflict_reason": "No accessible primary OEM/service/accessory source tied the offered pack to an exact manufacturer part.",
                "replacement_manufacturer": "",
                "replacement_mpn": "",
                "manufacturer_mpn_inference": "none",
                "repeat_handling": "new_review",
                "safe_to_apply": "false",
            }
        output.update({
            "strict_duplicate_key": duplicate["key"],
            "strict_duplicate_group_size": str(duplicate["size"]),
            "strict_duplicate_candidate": str(duplicate["candidate"]).lower(),
            "strict_duplicate_members": duplicate["members"],
        })
        output_rows.append(output)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(output_rows)

    counts = Counter(row["partition"] for row in output_rows)
    exact = sorted(row["product_external_id"] for row in output_rows if row["safe_to_apply"] == "true")
    duplicate_ids = sorted(row["product_external_id"] for row in output_rows if row["strict_duplicate_candidate"] == "true")
    summary = {
        "schema_version": 1,
        "site": "microchips-by",
        "batch": "wave204_industrial_remote_control_batteries",
        "created_at": "2026-07-29",
        "input": {"path": INPUT.relative_to(ROOT).as_posix(), "sha256": sha256(INPUT), "family_rows": len(candidates)},
        "full_catalog": {"path": FULL_CATALOG.relative_to(ROOT).as_posix(), "sha256": sha256(FULL_CATALOG), "rows": len(rows(FULL_CATALOG))},
        "registry": {"path": REGISTRY.relative_to(ROOT).as_posix(), "sha256": sha256(REGISTRY), "sourced_records": len(evidence)},
        "snapshot_index": {"path": SNAPSHOT_INDEX.relative_to(ROOT).as_posix(), "sha256": sha256(SNAPSHOT_INDEX), "sources": len(snapshot_index["sources"])},
        "output": {"path": OUTPUT.relative_to(ROOT).as_posix(), "sha256": sha256(OUTPUT), "rows": len(output_rows)},
        "partition_counts": dict(sorted(counts.items())),
        "safe_to_apply": {"rows": len(exact), "external_ids": exact},
        "strict_duplicate_candidates": {"rows": len(duplicate_ids), "external_ids": duplicate_ids},
        "policy": {
            "manufacturer_service_accessory_sources_only": True,
            "device_compatibility_does_not_identify_aftermarket_pack": True,
            "exact_requires_pinned_snapshot_sha_and_exact_tokens": True,
            "technical_claims_outside_verified_facts_promoted": 0,
            "database_mutations": 0,
        },
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
