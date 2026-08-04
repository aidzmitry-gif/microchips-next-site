#!/usr/bin/env python3
"""Build the bounded fail-closed Wave207 evidence and OEM manifest."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "docs/audits/generated/rb-b2b-next-source-batch-wave205.csv"
REGISTRY = ROOT / "docs/audits/evidence/wave207-official-source-evidence.json"
SNAPSHOT_INDEX = ROOT / "docs/audits/sources/wave207-device-small/snapshot-index.json"
FULL_REGISTRY = ROOT / "docs/audits/generated/full-catalog-canonical-registry.csv"
OUTPUT = ROOT / "docs/audits/generated/rb-wave207-device-small-evidence.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-wave207-device-small-evidence.summary.json"
MANIFEST = ROOT / "docs/imports/rb-verified-oem-identities-wave207-device-small-2026-07-29.json"

EXPECTED = {
    "Icom": 12,
    "Vertex": 13,
    "Baofeng": 12,
    "Symbol": 1,
    "Yaesu": 1,
    "Casil": 11,
    "Robiton": 7,
    "Minamoto": 1,
}
EXPECTED_TOTAL = sum(EXPECTED.values())
WAVE206_GLOB = "rb-verified-oem-identities-wave206*.json"
ALLOWED_CLASSIFICATIONS = {"exact_safe", "compatibility_only", "conflict"}
OFFICIAL_HOSTS = {"icomjapan.com", "baofengradio.com"}

FIELDS = [
    "batch", "group", "product_external_id", "name", "partition",
    "evidence_scope", "source_publisher", "source_url", "source_assertion",
    "verified_facts", "snapshot_path", "snapshot_sha256",
    "unsupported_legacy_claims", "conflict_reason", "replacement_manufacturer",
    "replacement_mpn", "manufacturer_mpn_inference", "duplicate_review",
    "safe_to_apply",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def normalize(value: str) -> str:
    return re.sub(r"[^0-9a-zа-я]+", "", value.casefold().replace("ё", "е"))


def host_is_official(url: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").casefold()
    return parsed.scheme == "https" and any(host == item or host.endswith("." + item) for item in OFFICIAL_HOSTS)


def group_for(row: dict[str, str]) -> str | None:
    external_id = row["product_external_id"]
    name = row["name"]
    manufacturer = row["manufacturer_cluster"]
    if manufacturer == "Icom":
        return "Icom"
    if external_id in {f"bitrix:{value}" for value in range(2686, 2700)} and external_id != "bitrix:2693":
        return "Vertex"
    if external_id in {f"bitrix:{value}" for value in range(26294, 26306)}:
        return "Baofeng"
    if external_id == "bitrix:12172":
        return "Symbol"
    if external_id == "bitrix:2701":
        return "Yaesu"
    if manufacturer in {"Casil", "Robiton", "Minamoto"}:
        return manufacturer
    if "Vertex" in name and "Baofeng" in name:
        return None
    return None


def wave206_ids() -> set[str]:
    result: set[str] = set()
    for path in (ROOT / "docs/imports").glob(WAVE206_GLOB):
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        result.update(row["external_id"] for row in data.get("products", []))
    return result


def main() -> None:
    source_rows = read_csv(INPUT)
    selected: list[tuple[str, dict[str, str]]] = []
    for row in source_rows:
        group = group_for(row)
        if group is not None:
            selected.append((group, row))
    counts = Counter(group for group, _ in selected)
    if dict(counts) != EXPECTED or len(selected) != EXPECTED_TOTAL:
        raise SystemExit(f"Wave207 input drift: expected {EXPECTED}, got {dict(counts)}")
    ids = [row["product_external_id"] for _, row in selected]
    if len(ids) != len(set(ids)):
        raise SystemExit("Wave207 input repeats an external ID")
    overlap = sorted(set(ids) & wave206_ids())
    if overlap:
        raise SystemExit(f"Wave207 overlaps Wave206: {', '.join(overlap)}")

    snapshot_data = json.loads(SNAPSHOT_INDEX.read_text(encoding="utf-8-sig"))
    snapshots = {row["source_id"]: row for row in snapshot_data["sources"]}
    registry_data = json.loads(REGISTRY.read_text(encoding="utf-8-sig"))
    evidence = {}
    for record in registry_data["evidence"]:
        external_id = record["product_external_id"]
        if external_id in evidence or external_id not in set(ids):
            raise SystemExit(f"Invalid or duplicate evidence row: {external_id}")
        if record["classification"] not in ALLOWED_CLASSIFICATIONS:
            raise SystemExit(f"Invalid classification: {external_id}")
        source = snapshots.get(record["source_id"])
        if source is None or not host_is_official(source["source_url"]):
            raise SystemExit(f"Missing official source snapshot: {external_id}")
        path = ROOT / source["snapshot_path"]
        if not path.is_file() or sha256(path) != source["snapshot_sha256"]:
            raise SystemExit(f"Snapshot hash mismatch: {external_id}")
        if not all(source["token_counts"].get(token, 0) > 0 for token in source["required_tokens"]):
            raise SystemExit(f"Snapshot exact-token check failed: {external_id}")
        if record["classification"] != "exact_safe" and (
            record["replacement_manufacturer"] or record["replacement_mpn"]
        ):
            raise SystemExit(f"Non-exact row infers identity: {external_id}")
        record["_source"] = source
        evidence[external_id] = record

    full_rows = read_csv(FULL_REGISTRY)
    full_names: dict[str, list[str]] = {}
    for row in full_rows:
        full_names.setdefault(normalize(row["name"]), []).append(row["registry_id"])

    output_rows = []
    manifest_rows = []
    strict_duplicate_clusters: dict[str, list[str]] = {}
    for group, candidate in selected:
        external_id = candidate["product_external_id"]
        matching_ids = full_names.get(normalize(candidate["name"]), [])
        duplicate_ids = sorted(item for item in matching_ids if item != external_id)
        if duplicate_ids:
            strict_duplicate_clusters[external_id] = duplicate_ids
        record = evidence.get(external_id)
        if record is None:
            output_rows.append({
                "batch": "wave207_device_small",
                "group": group,
                "product_external_id": external_id,
                "name": candidate["name"],
                "partition": "no_evidence",
                "evidence_scope": "no_pinned_first_party_exact_pack_identity",
                "source_publisher": "",
                "source_url": "",
                "source_assertion": "",
                "verified_facts": "",
                "snapshot_path": "",
                "snapshot_sha256": "",
                "unsupported_legacy_claims": "manufacturer|stable_battery_mpn|chemistry|capacity|voltage|compatibility",
                "conflict_reason": "No pinned first-party source established the exact offered battery identity.",
                "replacement_manufacturer": "",
                "replacement_mpn": "",
                "manufacturer_mpn_inference": "none",
                "duplicate_review": "strict_duplicate_hold" if duplicate_ids else "no_strict_full_name_duplicate",
                "safe_to_apply": "false",
            })
            continue

        source = record["_source"]
        exact = record["classification"] == "exact_safe" and not duplicate_ids
        output_rows.append({
            "batch": "wave207_device_small",
            "group": group,
            "product_external_id": external_id,
            "name": candidate["name"],
            "partition": record["classification"] if not duplicate_ids else "duplicate_hold",
            "evidence_scope": "exact_oem_pack_identity" if exact else (
                "device_compatibility_only" if record["classification"] == "compatibility_only" else "official_conflict"
            ),
            "source_publisher": source["publisher"],
            "source_url": source["source_url"],
            "source_assertion": record["source_assertion"],
            "verified_facts": record["verified_facts"],
            "snapshot_path": source["snapshot_path"],
            "snapshot_sha256": source["snapshot_sha256"],
            "unsupported_legacy_claims": record["unsupported_legacy_claims"],
            "conflict_reason": record["conflict_reason"] or (
                "Strict full-name duplicate requires canonical-product review." if duplicate_ids else ""
            ),
            "replacement_manufacturer": record["replacement_manufacturer"] if exact else "",
            "replacement_mpn": record["replacement_mpn"] if exact else "",
            "manufacturer_mpn_inference": "explicit_first_party_oem_part" if exact else "none",
            "duplicate_review": "strict_duplicate_hold" if duplicate_ids else "no_strict_full_name_duplicate",
            "safe_to_apply": "true" if exact else "false",
        })
        if exact:
            manifest_rows.append({
                "external_id": external_id,
                "current_name": candidate["name"],
                "manufacturer": record["replacement_manufacturer"],
                "mpn": record["replacement_mpn"],
                "source_url": source["source_url"],
                "source_kind": "official_manufacturer_product_page",
                "source_publisher": source["publisher"],
                "checked_at": "2026-07-29",
                "product_type": "OEM two-way radio battery pack",
                "source_snapshot_path": "../audits/sources/wave207-device-small/" + Path(source["snapshot_path"]).name,
                "source_snapshot_sha256": source["snapshot_sha256"],
            })

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(output_rows)

    MANIFEST.write_text(
        json.dumps(
            {"schema_version": 1, "site_key": "microchips-by", "products": manifest_rows},
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    partition_counts = Counter(row["partition"] for row in output_rows)
    summary = {
        "schema_version": 1,
        "site": "microchips-by",
        "batch": "wave207_device_small",
        "checked_at": "2026-07-29",
        "input": {"path": INPUT.relative_to(ROOT).as_posix(), "sha256": sha256(INPUT), "rows": len(selected)},
        "group_counts": dict(counts),
        "partition_counts": dict(sorted(partition_counts.items())),
        "safe_to_apply": {
            "rows": len(manifest_rows),
            "external_ids": [row["external_id"] for row in manifest_rows],
        },
        "wave206_overlap_rows": 0,
        "strict_full_name_duplicates": strict_duplicate_clusters,
        "source_index": {
            "path": SNAPSHOT_INDEX.relative_to(ROOT).as_posix(),
            "sha256": sha256(SNAPSHOT_INDEX),
            "available": len(snapshot_data["sources"]),
            "unavailable": len(snapshot_data["unavailable"]),
        },
        "output": {"path": OUTPUT.relative_to(ROOT).as_posix(), "sha256": sha256(OUTPUT), "rows": len(output_rows)},
        "manifest": {"path": MANIFEST.relative_to(ROOT).as_posix(), "sha256": sha256(MANIFEST), "rows": len(manifest_rows)},
        "policy": {
            "compatibility_is_not_identity": True,
            "technical_conflict_blocks_identity_apply": True,
            "full_registry_strict_duplicate_hold": True,
            "database_mutations": 0,
        },
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"rows": len(output_rows), "partitions": dict(partition_counts), "manifest": len(manifest_rows)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
