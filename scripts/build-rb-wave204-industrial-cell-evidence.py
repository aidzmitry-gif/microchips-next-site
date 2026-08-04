#!/usr/bin/env python3
"""Build fail-closed Wave204 evidence for legacy industrial traction cells."""

from __future__ import annotations

import csv
import hashlib
import html
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlparse

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "docs/audits/generated/wave203-industrial-unassigned-preparation.csv"
CANONICAL = ROOT / "docs/audits/generated/full-catalog-canonical-registry.csv"
REGISTRY = ROOT / "docs/audits/evidence/wave204-industrial-cell-official-source-evidence.json"
OUTPUT = ROOT / "docs/audits/generated/wave204-industrial-cell-evidence.csv"
SUMMARY = ROOT / "docs/audits/generated/wave204-industrial-cell-evidence-summary.json"
SNAPSHOT_INDEX = ROOT / "docs/audits/sources/wave204-industrial-cells/snapshot-index.json"
FAMILY = "legacy_industrial_traction_cells"
EXPECTED_ROWS = 34
ALLOWED_HOSTS = {"assets.danfoss.com", "gk-kaz.ru", "jsc-energiya.com", "www.niai.ru"}
ALLOWED_CLASSIFICATIONS = {"exact_safe", "conflict", "no_evidence"}
FIELDS = [
    "batch", "product_external_id", "name", "model_tokens", "partition",
    "source_tier", "source_publisher", "source_url", "source_assertion",
    "verified_model", "verified_chemistry", "verified_capacity_mah",
    "verified_voltage_v", "snapshot_path", "snapshot_sha256",
    "required_exact_tokens", "required_token_counts", "checked_source_ids",
    "unsupported_legacy_claims",
    "conflict_reason", "replacement_manufacturer", "replacement_mpn",
    "manufacturer_mpn_inference", "duplicate_cluster_ids", "related_variant_ids",
    "duplicate_decision",
    "safe_to_apply",
]

CONFUSABLES = str.maketrans({
    "А": "A", "В": "B", "Е": "E", "К": "K", "М": "M", "Н": "H",
    "О": "O", "Р": "P", "С": "C", "Т": "T", "У": "Y", "Х": "X",
})


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def normalized_identity(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).upper().translate(CONFUSABLES)
    return re.sub(r"[^0-9A-ZА-Я]+", "", value)


def extract_snapshot_text(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        return "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)
    raw = path.read_text(encoding="utf-8", errors="replace")
    return html.unescape(re.sub(r"<[^>]+>", " ", raw))


def validate_sources(data: dict) -> tuple[dict[str, dict], list[dict]]:
    sources: dict[str, dict] = {}
    index_rows: list[dict] = []
    for source in data.get("sources", []):
        source_id = source.get("source_id", "")
        if not source_id or source_id in sources:
            raise SystemExit(f"Invalid or duplicate source_id: {source_id}")
        parsed = urlparse(source.get("source_url", ""))
        if parsed.scheme != "https" or (parsed.hostname or "").lower() not in ALLOWED_HOSTS:
            raise SystemExit(f"Source is not an allow-listed primary HTTPS source: {source_id}")
        if source.get("source_tier") not in {
            "manufacturer_datasheet_primary", "manufacturer_catalogue_primary"
        }:
            raise SystemExit(f"Invalid primary source tier: {source_id}")
        path = ROOT / source.get("snapshot_path", "")
        if not path.is_file() or sha256(path) != source.get("snapshot_sha256"):
            raise SystemExit(f"Pinned snapshot missing or hash-mismatched: {source_id}")
        sources[source_id] = source
        index_rows.append({
            **source,
            "bytes": path.stat().st_size,
            "verified_sha256": sha256(path),
        })
    if not sources:
        raise SystemExit("No primary sources are pinned")
    return sources, index_rows


def expand_registry(data: dict, candidate_ids: set[str], sources: dict[str, dict]) -> dict[str, dict]:
    evidence: dict[str, dict] = {}
    for raw in data.get("evidence", []):
        record = dict(raw)
        external_id = record.get("product_external_id", "")
        if external_id in evidence or external_id not in candidate_ids:
            raise SystemExit(f"Invalid or duplicate evidence id: {external_id}")
        if record.get("classification") not in ALLOWED_CLASSIFICATIONS - {"no_evidence"}:
            raise SystemExit(f"Invalid sourced classification: {external_id}")
        if record.get("source_id") not in sources:
            raise SystemExit(f"Unknown source for {external_id}")
        evidence[external_id] = record

    for group in data.get("no_evidence_groups", []):
        checked = group.get("checked_source_ids", [])
        if any(source_id not in sources for source_id in checked):
            raise SystemExit("No-evidence group refers to an unknown source")
        for external_id in group.get("product_external_ids", []):
            if external_id in evidence or external_id not in candidate_ids:
                raise SystemExit(f"Invalid or duplicate no-evidence id: {external_id}")
            evidence[external_id] = {
                "product_external_id": external_id,
                "classification": "no_evidence",
                "checked_source_ids": checked,
                "unsupported_legacy_claims": group["unsupported_legacy_claims"],
                "conflict_reason": group["reason"],
            }

    if set(evidence) != candidate_ids:
        missing = sorted(candidate_ids - set(evidence))
        extra = sorted(set(evidence) - candidate_ids)
        raise SystemExit(f"Evidence coverage drifted; missing={missing}, extra={extra}")
    return evidence


def catalog_name_index() -> tuple[list[dict[str, str]], dict[str, list[str]]]:
    all_rows = read_csv(CANONICAL)
    by_name: dict[str, list[str]] = defaultdict(list)
    for row in all_rows:
        by_name[normalized_identity(row["name"])].append(row["registry_id"])
    return all_rows, by_name


def duplicate_map(candidates: list[dict[str, str]], by_name: dict[str, list[str]]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for row in candidates:
        external_id = row["product_external_id"]
        peers = sorted(item for item in by_name[normalized_identity(row["name"])] if item != external_id)
        result[external_id] = peers
    return result


def main() -> None:
    candidates = [row for row in read_csv(INPUT) if row["family"] == FAMILY]
    if len(candidates) != EXPECTED_ROWS or len({row["product_external_id"] for row in candidates}) != EXPECTED_ROWS:
        raise SystemExit("Wave204 family count or uniqueness drifted")

    data = json.loads(REGISTRY.read_text(encoding="utf-8-sig"))
    if data.get("schema_version") != 1 or data.get("scope", {}).get("expected_rows") != EXPECTED_ROWS:
        raise SystemExit("Wave204 evidence registry schema/scope drifted")
    sources, source_index = validate_sources(data)
    candidate_ids = {row["product_external_id"] for row in candidates}
    evidence = expand_registry(data, candidate_ids, sources)
    canonical_rows, names_index = catalog_name_index()
    canonical_by_id = {row["registry_id"]: row for row in canonical_rows}
    duplicates = duplicate_map(candidates, names_index)
    source_text_cache: dict[str, str] = {}
    output_rows: list[dict[str, str]] = []

    for candidate in candidates:
        external_id = candidate["product_external_id"]
        record = evidence[external_id]
        classification = record["classification"]
        source = sources.get(record.get("source_id", ""), {})
        exact = classification == "exact_safe"
        token_counts: dict[str, int] = {}
        exact_mpn_peers: list[str] = []
        related_variants = record.get("related_distinct_variants", [])

        if exact:
            required_fields = [
                "replacement_manufacturer", "replacement_mpn", "chemistry",
                "capacity_mah", "voltage_v", "required_exact_tokens",
            ]
            if record.get("identity_assertion") != "exact_oem_part" or any(not record.get(field) for field in required_fields):
                raise SystemExit(f"Exact row lacks a complete identity/specification proof: {external_id}")
            source_id = record["source_id"]
            if source_id not in source_text_cache:
                source_text_cache[source_id] = extract_snapshot_text(ROOT / source["snapshot_path"])
            source_text = source_text_cache[source_id]
            token_counts = {token: source_text.count(token) for token in record["required_exact_tokens"]}
            if not token_counts or any(count < 1 for count in token_counts.values()):
                raise SystemExit(f"Pinned exact tokens are incomplete for {external_id}: {token_counts}")
            if normalized_identity(record["replacement_mpn"]) not in normalized_identity(candidate["name"]):
                raise SystemExit(f"Exact MPN is not bounded by the legacy title: {external_id}")
            normalized_mpn = normalized_identity(record["replacement_mpn"])
            exact_mpn_peers = sorted(
                row["registry_id"] for row in canonical_rows
                if row["registry_id"] != external_id
                and normalized_mpn in normalized_identity(row["name"])
            )
            for related in related_variants:
                related_id = related.get("product_external_id", "")
                related_row = canonical_by_id.get(related_id)
                if not related_row or related_id in exact_mpn_peers or not related.get("reason"):
                    raise SystemExit(f"Invalid distinct-variant review for {external_id}: {related_id}")
                base_model = normalized_identity(record["replacement_mpn"].split()[0])
                if base_model not in normalized_identity(related_row["name"]):
                    raise SystemExit(f"Distinct variant does not share the model family: {related_id}")
        elif record.get("replacement_manufacturer") or record.get("replacement_mpn"):
            raise SystemExit(f"Unsafe row inferred an identity: {external_id}")

        peers = sorted(set(duplicates[external_id]) | set(exact_mpn_peers))
        checked_source_ids = record.get("checked_source_ids", [])
        output_rows.append({
            "batch": data["batch"],
            "product_external_id": external_id,
            "name": candidate["name"],
            "model_tokens": candidate["model_tokens_unverified"],
            "partition": classification,
            "source_tier": source.get("source_tier", "none"),
            "source_publisher": source.get("source_publisher", ""),
            "source_url": source.get("source_url", ""),
            "source_assertion": record.get("source_assertion", ""),
            "verified_model": record.get("replacement_mpn", "") if exact else "",
            "verified_chemistry": record.get("chemistry", "") if exact else "",
            "verified_capacity_mah": str(record.get("capacity_mah", "")) if exact else "",
            "verified_voltage_v": str(record.get("voltage_v", "")) if exact else "",
            "snapshot_path": source.get("snapshot_path", "") if source else "",
            "snapshot_sha256": source.get("snapshot_sha256", "") if source else "",
            "required_exact_tokens": "|".join(record.get("required_exact_tokens", [])) if exact else "",
            "required_token_counts": json.dumps(token_counts, ensure_ascii=False, sort_keys=True) if exact else "",
            "checked_source_ids": "|".join(checked_source_ids),
            "unsupported_legacy_claims": record["unsupported_legacy_claims"],
            "conflict_reason": record.get("conflict_reason", ""),
            "replacement_manufacturer": record.get("replacement_manufacturer", "") if exact else "",
            "replacement_mpn": record.get("replacement_mpn", "") if exact else "",
            "manufacturer_mpn_inference": "explicit_official_exact_part_only" if exact else "none",
            "duplicate_cluster_ids": "|".join(peers),
            "related_variant_ids": "|".join(item["product_external_id"] for item in related_variants),
            "duplicate_decision": "hold_duplicate_review" if peers else (
                "unique_exact_mpn_distinct_variant_reviewed" if related_variants else "unique_exact_title"
            ),
            "safe_to_apply": "true" if exact and not peers else "false",
        })

    exact_identity_keys = Counter(
        normalized_identity(row["replacement_manufacturer"] + row["replacement_mpn"])
        for row in output_rows if row["safe_to_apply"] == "true"
    )
    if any(count > 1 for count in exact_identity_keys.values()):
        raise SystemExit("Duplicate exact manufacturer/MPN identity detected")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(output_rows)

    snapshot_index = {
        "schema_version": 1,
        "batch": data["batch"],
        "created_at": "2026-07-29",
        "sources": source_index,
        "exact_token_evidence": [
            {
                "product_external_id": row["product_external_id"],
                "source_id": evidence[row["product_external_id"]]["source_id"],
                "required_exact_tokens": evidence[row["product_external_id"]]["required_exact_tokens"],
                "required_token_counts": json.loads(row["required_token_counts"]),
            }
            for row in output_rows if row["safe_to_apply"] == "true"
        ],
    }
    SNAPSHOT_INDEX.write_text(json.dumps(snapshot_index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    counts = Counter(row["partition"] for row in output_rows)
    safe_ids = sorted(row["product_external_id"] for row in output_rows if row["safe_to_apply"] == "true")
    duplicate_rows = [row for row in output_rows if row["duplicate_cluster_ids"]]
    summary = {
        "schema_version": 1,
        "site": "microchips-by",
        "batch": data["batch"],
        "created_at": "2026-07-29",
        "input": {"path": INPUT.relative_to(ROOT).as_posix(), "sha256": sha256(INPUT), "family": FAMILY, "rows": len(candidates)},
        "canonical_registry": {"path": CANONICAL.relative_to(ROOT).as_posix(), "sha256": sha256(CANONICAL)},
        "evidence_registry": {"path": REGISTRY.relative_to(ROOT).as_posix(), "sha256": sha256(REGISTRY)},
        "snapshot_index": {"path": SNAPSHOT_INDEX.relative_to(ROOT).as_posix(), "sha256": sha256(SNAPSHOT_INDEX), "sources": len(source_index)},
        "output": {"path": OUTPUT.relative_to(ROOT).as_posix(), "sha256": sha256(OUTPUT), "rows": len(output_rows)},
        "partition_counts": dict(sorted(counts.items())),
        "safe_to_apply": {"rows": len(safe_ids), "external_ids": safe_ids},
        "duplicates": {
            "normalized_exact_title_rows": len(duplicate_rows),
            "rows": [{"product_external_id": row["product_external_id"], "peer_ids": row["duplicate_cluster_ids"].split("|")} for row in duplicate_rows],
            "exact_manufacturer_mpn_collisions": 0,
            "distinct_variant_reviews": [
                {
                    "product_external_id": row["product_external_id"],
                    "related_variant_ids": row["related_variant_ids"].split("|"),
                    "decision": row["duplicate_decision"],
                }
                for row in output_rows if row["related_variant_ids"]
            ],
        },
        "policy": data["policy"],
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
