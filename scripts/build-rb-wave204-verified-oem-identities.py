#!/usr/bin/env python3
"""Build the guarded combined Wave204 OEM identity manifest.

An evidence-exact first-party part is not automatically apply-eligible.  The
Laravel command deliberately requires both maker and exact MPN to already be
bounded in the current legacy name; this builder mirrors that gate and holds
everything else instead of weakening it.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
PREPARATION = ROOT / "docs/audits/generated/wave203-industrial-unassigned-preparation.csv"
OUTPUT = ROOT / "docs/imports/rb-verified-oem-identities-wave204-2026-07-29.json"
SUMMARY = ROOT / "docs/audits/generated/wave204-verified-oem-identities-summary.json"

ALLOWED_SOURCE_KINDS = {
    "official_manufacturer_catalogue",
    "official_manufacturer_accessory_catalogue",
    "official_manufacturer_product_page",
    "official_manufacturer_service_document",
}
ALLOWED_ATTACHED_SUFFIXES = {"cna", "cnr", "fl", "fle", "estd", "2pf", "3pf", "4pf"}
LOOKALIKE_MAP = str.maketrans({"а": "a", "с": "c", "е": "e", "о": "o", "р": "p", "х": "x"})


@dataclass(frozen=True)
class Partition:
    key: str
    family: str
    expected_rows: int
    evidence_path: Path
    registry_path: Path
    snapshot_index_path: Path
    builder_path: Path


PARTITIONS = (
    Partition(
        "radio", "radio_station_battery_packs", 41,
        ROOT / "docs/audits/generated/wave204-radio-evidence.csv",
        ROOT / "docs/audits/evidence/wave204-radio-official-source-evidence.json",
        ROOT / "docs/audits/sources/wave204-radio/snapshot-index.json",
        ROOT / "scripts/build-rb-wave204-radio-evidence.py",
    ),
    Partition(
        "industrial", "legacy_industrial_traction_cells", 34,
        ROOT / "docs/audits/generated/wave204-industrial-cell-evidence.csv",
        ROOT / "docs/audits/evidence/wave204-industrial-cell-official-source-evidence.json",
        ROOT / "docs/audits/sources/wave204-industrial-cells/snapshot-index.json",
        ROOT / "scripts/build-rb-wave204-industrial-cell-evidence.py",
    ),
    Partition(
        "remote", "industrial_remote_control_batteries", 31,
        ROOT / "docs/audits/generated/wave204-remote-control-evidence.csv",
        ROOT / "docs/audits/evidence/wave204-remote-control-official-source-evidence.json",
        ROOT / "docs/audits/sources/wave204-remote-control/snapshot-index.json",
        ROOT / "scripts/build-rb-wave204-remote-control-evidence.py",
    ),
)

SOURCE_KIND_BY_ID = {
    "alinco_handheld_accessories_2006": "official_manufacturer_accessory_catalogue",
    "danfoss-rct-rechargeable-batteries-2025": "official_manufacturer_service_document",
    "autec_mbm06mh_manual": "official_manufacturer_service_document",
    "autec_nc_mh0707l_manual": "official_manufacturer_service_document",
    "autec_official_battery_store": "official_manufacturer_product_page",
    "autec_official_lithium_store": "official_manufacturer_product_page",
    "elca_official_battery_store": "official_manufacturer_product_page",
    "hiab_red_parts_batteries": "official_manufacturer_product_page",
}

EXPECTED_EXACT_IDS = {
    "bitrix:2239",
    "bitrix:2394", "bitrix:2395", "bitrix:2396", "bitrix:2397",
    "bitrix:20045", "bitrix:20049", "bitrix:20050", "bitrix:20059",
    "bitrix:20060", "bitrix:20061", "bitrix:20071", "bitrix:20073", "bitrix:20075",
}
EXPECTED_APPLY_ELIGIBLE_IDS = {
    "bitrix:2394", "bitrix:2395", "bitrix:2396", "bitrix:2397",
    "bitrix:20045", "bitrix:20071", "bitrix:20073", "bitrix:20075",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def normalize(value: str) -> str:
    return "".join(character for character in value.strip().casefold() if character.isalnum())


def normalize_lookalikes(value: str) -> str:
    return normalize(value).translate(LOOKALIKE_MAP)


def normalized_tokens(value: str) -> list[str]:
    tokens: list[str] = []
    current: list[str] = []
    for character in value.casefold():
        if character.isalnum():
            current.append(character)
        elif current:
            tokens.append(normalize_lookalikes("".join(current)))
            current = []
    if current:
        tokens.append(normalize_lookalikes("".join(current)))
    return [token for token in tokens if token]


def name_contains(name: str, model_core: str) -> bool:
    """Mirror ModelCoreIdentityMatcher::nameContains without broad aliases."""
    normalized_core = normalize_lookalikes(model_core)
    if not normalized_core:
        return False
    tokens = normalized_tokens(name)
    for start in range(len(tokens)):
        candidate = ""
        for token in tokens[start:]:
            candidate += token
            if candidate == normalized_core:
                return True
            if candidate.startswith(normalized_core):
                return candidate[len(normalized_core):] in ALLOWED_ATTACHED_SUFFIXES
            if len(candidate) >= len(normalized_core):
                break
    return False


def normalized_snapshot_text(path: Path) -> str:
    if path.suffix.casefold() == ".pdf":
        text = "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)
    else:
        text = path.read_text(encoding="utf-8", errors="replace")
    return re.sub(r"\s+", " ", text).strip()


def validate_snapshot(path: Path, expected_sha256: str, required_tokens: tuple[str, ...]) -> None:
    resolved = path.resolve()
    if not resolved.is_relative_to(ROOT.resolve()) or not path.is_file():
        raise ValueError(f"Pinned snapshot missing or outside repository: {path}")
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256) or sha256(path) != expected_sha256:
        raise ValueError(f"Pinned snapshot SHA256 mismatch: {path.relative_to(ROOT).as_posix()}")
    text = normalized_snapshot_text(path).casefold()
    missing = [token for token in required_tokens if token.casefold() not in text]
    if missing:
        raise ValueError(f"Pinned snapshot lacks exact tokens for {path.name}: {', '.join(missing)}")


def registry_records(partition: Partition) -> tuple[dict[str, dict], dict[str, dict], str]:
    registry = json.loads(partition.registry_path.read_text(encoding="utf-8-sig"))
    index = json.loads(partition.snapshot_index_path.read_text(encoding="utf-8-sig"))
    evidence = {
        row["product_external_id"]: row
        for row in registry.get("evidence", [])
        if row.get("classification") == "exact_safe"
    }
    sources = {
        row["source_id"]: row
        for row in (registry.get("sources") or index.get("sources") or [])
    }
    checked_at = index.get("checked_at") or index.get("created_at") or registry.get("checked_at") or ""
    return evidence, sources, checked_at


def source_record(partition: Partition, source_id: str, registry_sources: dict[str, dict]) -> dict:
    index = json.loads(partition.snapshot_index_path.read_text(encoding="utf-8-sig"))
    indexed = {row["source_id"]: row for row in index.get("sources", [])}.get(source_id)
    registered = registry_sources.get(source_id)
    if indexed is None and registered is None:
        raise ValueError(f"{partition.key}: exact source {source_id} missing")
    if indexed is None:
        indexed = registered
    if registered is None:
        registered = indexed
    for field in ("source_url", "snapshot_path", "snapshot_sha256"):
        if indexed.get(field) != registered.get(field):
            raise ValueError(f"{partition.key}/{source_id}: source registry/index {field} drifted")
    return indexed


def validate_union() -> dict[str, dict[str, dict[str, str]]]:
    preparation = read_csv(PREPARATION)
    expected_union: set[str] = set()
    outputs: dict[str, dict[str, dict[str, str]]] = {}
    seen: set[str] = set()
    for partition in PARTITIONS:
        expected_ids = {
            row["product_external_id"] for row in preparation
            if row["family"] == partition.family and row["repeat_handling"] == "new"
        }
        rows = read_csv(partition.evidence_path)
        actual = {row["product_external_id"]: row for row in rows}
        if len(expected_ids) != partition.expected_rows or len(actual) != partition.expected_rows:
            raise ValueError(f"{partition.key}: partition count drifted from {partition.expected_rows}")
        if set(actual) != expected_ids:
            raise ValueError(f"{partition.key}: evidence output does not cover its exact input family")
        if seen & set(actual):
            raise ValueError("Wave204 partitions overlap")
        seen.update(actual)
        expected_union.update(expected_ids)
        outputs[partition.key] = actual
    if len(expected_union) != 106 or seen != expected_union:
        raise ValueError("Wave204 union is not the exact 41+34+31=106 rows")
    return outputs


def collect_exact(outputs: dict[str, dict[str, dict[str, str]]]) -> list[dict]:
    records: list[dict] = []
    for partition in PARTITIONS:
        exact_registry, registry_sources, default_checked_at = registry_records(partition)
        exact_rows = {
            external_id: row for external_id, row in outputs[partition.key].items()
            if row.get("partition") == "exact_safe" and row.get("safe_to_apply") == "true"
        }
        if set(exact_rows) != set(exact_registry):
            raise ValueError(f"{partition.key}: exact CSV and source registry sets drifted")
        for external_id, row in exact_rows.items():
            evidence = exact_registry[external_id]
            source_id = evidence["source_id"]
            source = source_record(partition, source_id, registry_sources)
            required_tokens = tuple(evidence.get("required_exact_tokens") or [])
            if not required_tokens:
                raise ValueError(f"{external_id}: exact evidence lacks required tokens")
            if row.get("replacement_manufacturer") != evidence.get("replacement_manufacturer") \
                    or row.get("replacement_mpn") != evidence.get("replacement_mpn"):
                raise ValueError(f"{external_id}: exact identity drifted between CSV and registry")
            if row.get("snapshot_path") != source.get("snapshot_path") \
                    or row.get("snapshot_sha256") != source.get("snapshot_sha256") \
                    or row.get("source_url") != source.get("source_url"):
                raise ValueError(f"{external_id}: exact snapshot/URL drifted")
            source_kind = SOURCE_KIND_BY_ID.get(source_id)
            if source_kind not in ALLOWED_SOURCE_KINDS:
                raise ValueError(f"{external_id}: uncontrolled source_kind")
            source_url = source["source_url"]
            parsed = urlparse(source_url)
            if parsed.scheme != "https" or not parsed.hostname:
                raise ValueError(f"{external_id}: official source must be HTTPS")
            checked_at = source.get("checked_at") or default_checked_at
            try:
                checked = date.fromisoformat(checked_at)
            except ValueError as error:
                raise ValueError(f"{external_id}: invalid checked_at") from error
            if checked > date.today():
                raise ValueError(f"{external_id}: checked_at is future")
            snapshot_repo_path = source["snapshot_path"]
            snapshot_path = ROOT / snapshot_repo_path
            validate_snapshot(snapshot_path, source["snapshot_sha256"], required_tokens)
            manufacturer = evidence["replacement_manufacturer"]
            mpn = evidence["replacement_mpn"]
            manufacturer_in_name = name_contains(row["name"], manufacturer)
            mpn_in_name = name_contains(row["name"], mpn)
            records.append({
                "partition": partition.key,
                "external_id": external_id,
                "current_name": row["name"],
                "manufacturer": manufacturer,
                "mpn": mpn,
                "product_type": "Battery pack",
                "source_url": source_url,
                "source_kind": source_kind,
                "source_publisher": source.get("publisher") or source.get("source_publisher") or evidence.get("source_publisher"),
                "checked_at": checked_at,
                "snapshot_repo_path": snapshot_repo_path,
                "snapshot_sha256": source["snapshot_sha256"],
                "required_exact_tokens": list(required_tokens),
                "manufacturer_in_current_name": manufacturer_in_name,
                "mpn_in_current_name": mpn_in_name,
                "apply_eligible": manufacturer_in_name and mpn_in_name,
            })
    ids = {record["external_id"] for record in records}
    if len(records) != 14 or ids != EXPECTED_EXACT_IDS:
        raise ValueError(f"Wave204 evidence-exact set drifted: {sorted(ids)}")
    return sorted(records, key=lambda record: int(record["external_id"].split(":", 1)[1]))


def manifest_row(record: dict, output_path: Path) -> dict[str, str]:
    snapshot = ROOT / record["snapshot_repo_path"]
    relative_snapshot = Path(os.path.relpath(snapshot, output_path.parent)).as_posix()
    if not relative_snapshot.startswith("../audits/sources/") or Path(relative_snapshot).is_absolute():
        raise ValueError(f"{record['external_id']}: snapshot path is not controlled and relative")
    return {
        "external_id": record["external_id"],
        "current_name": record["current_name"],
        "manufacturer": record["manufacturer"],
        "mpn": record["mpn"],
        "source_url": record["source_url"],
        "source_kind": record["source_kind"],
        "source_publisher": record["source_publisher"],
        "checked_at": record["checked_at"],
        "product_type": record["product_type"],
        "source_snapshot_path": relative_snapshot,
        "source_snapshot_sha256": record["snapshot_sha256"],
    }


def build(output_path: Path = OUTPUT, summary_path: Path = SUMMARY, rebuild_upstream: bool = True) -> dict:
    if rebuild_upstream:
        for partition in PARTITIONS:
            subprocess.run([sys.executable, str(partition.builder_path)], cwd=ROOT, check=True)
    outputs = validate_union()
    exact = collect_exact(outputs)
    apply_eligible = [record for record in exact if record["apply_eligible"]]
    held = [record for record in exact if not record["apply_eligible"]]
    eligible_ids = {record["external_id"] for record in apply_eligible}
    if eligible_ids != EXPECTED_APPLY_ELIGIBLE_IDS or len(held) != 6:
        raise ValueError(f"Wave204 nameContains eligibility drifted: {sorted(eligible_ids)}")
    normalized_mpns = [normalize(record["mpn"]) for record in apply_eligible]
    if len(set(normalized_mpns)) != len(normalized_mpns):
        raise ValueError("Apply-eligible manifest repeats a normalized MPN")

    manifest = {
        "schema_version": 1,
        "site_key": "microchips-by",
        "products": [manifest_row(record, output_path) for record in apply_eligible],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    hold_rows = [
        {
            "external_id": record["external_id"],
            "current_name": record["current_name"],
            "manufacturer": record["manufacturer"],
            "mpn": record["mpn"],
            "manufacturer_in_current_name": record["manufacturer_in_current_name"],
            "mpn_in_current_name": record["mpn_in_current_name"],
            "reason": "official_part_not_pinned_in_legacy_name",
        }
        for record in held
    ]
    summary = {
        "schema_version": 1,
        "site_key": "microchips-by",
        "created_at": "2026-07-29",
        "input_union": {
            "radio_rows": 41,
            "industrial_rows": 34,
            "remote_rows": 31,
            "union_rows": 106,
            "pairwise_overlap_rows": 0,
        },
        "evidence_exact": {
            "rows": len(exact),
            "external_ids": [record["external_id"] for record in exact],
        },
        "apply_eligible": {
            "rows": len(apply_eligible),
            "external_ids": [record["external_id"] for record in apply_eligible],
            "manifest_path": output_path.relative_to(ROOT).as_posix(),
            "manifest_sha256": sha256(output_path),
        },
        "holds": {
            "rows": len(hold_rows),
            "reason": "official_part_not_pinned_in_legacy_name",
            "products": hold_rows,
        },
        "source_validation": {
            "snapshots_sha256_verified": len(exact),
            "exact_token_sets_verified": len(exact),
            "controlled_source_kinds": sorted(ALLOWED_SOURCE_KINDS),
            "relative_manifest_snapshot_paths": len(apply_eligible),
        },
        "policy": {
            "laravel_name_contains_gate_weakened": False,
            "official_exact_is_not_automatically_apply_eligible": True,
            "database_mutations": 0,
        },
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"manifest": manifest, "summary": summary, "exact": exact}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--summary", type=Path, default=SUMMARY)
    parser.add_argument("--skip-upstream-build", action="store_true")
    args = parser.parse_args()
    result = build(args.output, args.summary, rebuild_upstream=not args.skip_upstream_build)
    print(json.dumps({
        "evidence_exact": len(result["exact"]),
        "apply_eligible": len(result["manifest"]["products"]),
        "holds": result["summary"]["holds"]["rows"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
