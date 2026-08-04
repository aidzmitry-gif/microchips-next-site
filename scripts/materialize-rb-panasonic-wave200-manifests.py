#!/usr/bin/env python3
"""Materialize pinned Panasonic Wave200 model-core technical evidence only."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path


PDF_CONTRACTS = {
    "1ce9b9fa72a6263f34cf2390726ddb009759c04303c1d3f39bc981473af5f343": {
        "source_url": "https://energy.panasonic.com/dam/master/pdf/en/material/lithium/Introduction_of_coin_type_primary_lithium_batteries_EN.pdf",
        "pages": {"3", "4"},
    },
    "116c40368f6ee67f5c7842c3b6d3968089c5a979c40fcb0275b303f86f1705ca": {
        "source_url": "https://energy.panasonic.com/dam/master/pdf/en/material/lithium/Introduction_of_primary_lithium_batteries_cylindrical_type_CR_series_longlife_EN.pdf",
        "pages": {"6"},
    },
}
ATTACHED_SUFFIXES = {
    "BR-1/2AA": {"E2PN", "E5PN"},
    "BR-2/3A": {"E2SPN", "H", "N", "T2SPN", "Y4PN"},
    "BR-2/3AG": {"CT4A", "N"},
    "CR123A": {"PA/B", "PE/BN"},
    "CR2": {"PE/BN"},
}
LIVE_IDENTITY_HOLDS = {
    "bitrix:767": "live_catalogue_model_core_identity_blocker",
    "bitrix:768": "live_catalogue_model_core_identity_blocker",
    "bitrix:4004": "live_catalogue_model_core_identity_blocker",
    "bitrix:4005": "live_catalogue_model_core_identity_blocker",
    "bitrix:4013": "live_catalogue_transfer_status_hold_one_c_collision",
    "bitrix:4014": "live_catalogue_transfer_status_hold_one_c_collision",
    "bitrix:4021": "live_catalogue_product_missing",
    "bitrix:4022": "live_catalogue_model_core_identity_blocker",
    "bitrix:4023": "live_catalogue_model_core_identity_blocker",
    "bitrix:4024": "live_catalogue_model_core_identity_blocker",
    "bitrix:4025": "live_catalogue_model_core_identity_blocker",
    "bitrix:4045": "live_catalogue_transfer_status_hold_one_c_collision",
    "bitrix:4046": "live_catalogue_transfer_status_hold_one_c_collision",
    "bitrix:4047": "live_catalogue_transfer_status_hold_one_c_collision",
    "bitrix:4048": "live_catalogue_transfer_status_hold_one_c_collision",
    "bitrix:4075": "live_catalogue_model_core_identity_blocker",
    "bitrix:4140": "live_catalogue_model_core_identity_blocker",
    "bitrix:4142": "live_catalogue_model_core_identity_blocker",
}
TECHNOLOGIES = {
    "CR": "Литий-диоксид марганца",
    "BR": "Литий-поликарбонмонофторид",
}
SHA256 = re.compile(r"[0-9a-f]{64}")
HYPHENS = re.compile(r"[-‐‑‒–—\s]")
EVIDENCE_REQUIRED = {
    "product_external_id", "legacy_model_token", "legacy_pack_variant_key", "model_core",
    "match_kind", "manufacturer", "identity_scope", "evidence_scope", "technology",
    "voltage_v", "capacity_mah", "diameter_mm", "width_mm", "height_mm",
    "temperature_min_c", "temperature_max_c", "source_url", "source_snapshot_path",
    "source_snapshot_sha256", "source_page", "source_kind", "source_publisher",
    "manufacturer_primary", "price_or_stock_imported", "safe_to_apply",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require_pinned_file(path: Path, expected_sha256: str, label: str) -> str:
    expected = (expected_sha256 or "").strip().lower()
    if not path.is_file():
        raise ValueError(f"{label} must be an existing file")
    if SHA256.fullmatch(expected) is None:
        raise ValueError(f"expected {label} SHA-256 must be a 64-character hash")
    actual = sha(path)
    if actual != expected:
        raise ValueError(f"{label} SHA-256 mismatch")
    return actual


def load_csv(path: Path, required: set[str]) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError("missing required columns: " + ", ".join(sorted(missing)))
        return list(reader)


def normalize_model(value: str) -> str:
    return HYPHENS.sub("", (value or "").strip().upper())


def expected_match_kind(model_token: str, model_core: str) -> str | None:
    candidate = normalize_model(model_token)
    core = normalize_model(model_core)
    if candidate == core:
        return "exact_core"
    if candidate.startswith(core + "/"):
        return "slash_package_variant"
    if candidate.startswith(core) and candidate[len(core) :] in ATTACHED_SUFFIXES.get(model_core, set()):
        return "whitelisted_attached_suffix"
    return None


def positive_decimal(value: str, field: str, optional: bool = False) -> str:
    normalized = (value or "").strip()
    if optional and not normalized:
        return ""
    try:
        number = Decimal(normalized)
    except InvalidOperation as error:
        raise ValueError(f"{field} must be a positive decimal") from error
    if number <= 0:
        raise ValueError(f"{field} must be a positive decimal")
    return normalized


def nonnegative_int(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"evidence summary {field} must be a nonnegative integer")
    return value


def resolve_snapshot(value: str) -> Path:
    path = Path((value or "").strip())
    return path if path.is_absolute() else Path.cwd() / path


def build(
    candidates_path: Path,
    evidence_path: Path,
    holds_path: Path,
    evidence_summary_path: Path,
    descriptions_path: Path,
    materialization_summary_path: Path,
    expected_candidate_sha256: str,
    expected_evidence_sha256: str,
    expected_holds_sha256: str,
    expected_evidence_summary_sha256: str,
) -> dict[str, object]:
    candidate_sha256 = require_pinned_file(candidates_path, expected_candidate_sha256, "candidate")
    evidence_sha256 = require_pinned_file(evidence_path, expected_evidence_sha256, "evidence")
    holds_sha256 = require_pinned_file(holds_path, expected_holds_sha256, "holds")
    evidence_summary_sha256 = require_pinned_file(
        evidence_summary_path, expected_evidence_summary_sha256, "evidence summary"
    )
    candidates = load_csv(candidates_path, {
        "product_external_id", "manufacturer", "family", "model_token", "pack_variant_key", "safe_to_apply",
    })
    evidence = load_csv(evidence_path, EVIDENCE_REQUIRED)
    holds = load_csv(holds_path, {
        "product_external_id", "legacy_model_token", "legacy_pack_variant_key", "reason",
    })
    candidate_by_id = {row["product_external_id"]: row for row in candidates}
    evidence_by_id = {row["product_external_id"]: row for row in evidence}
    hold_by_id = {row["product_external_id"]: row for row in holds}
    if len(candidate_by_id) != len(candidates) or len(evidence_by_id) != len(evidence) or len(hold_by_id) != len(holds):
        raise ValueError("candidate, evidence, and hold external IDs must each be unique")
    if set(evidence_by_id) & set(hold_by_id):
        raise ValueError("evidence and holds must be disjoint")
    if set(evidence_by_id) | set(hold_by_id) != set(candidate_by_id):
        raise ValueError("evidence and holds do not completely partition candidates")
    if not set(LIVE_IDENTITY_HOLDS) <= set(hold_by_id):
        raise ValueError("pinned live identity holds are missing")

    try:
        evidence_summary = json.loads(evidence_summary_path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("evidence summary must be valid UTF-8 JSON") from error
    if not isinstance(evidence_summary, dict):
        raise ValueError("evidence summary must be a JSON object")
    if evidence_summary.get("candidate_sha256") != candidate_sha256:
        raise ValueError("evidence summary candidate SHA-256 mismatch")
    if evidence_summary.get("evidence_sha256") != evidence_sha256:
        raise ValueError("evidence summary evidence SHA-256 mismatch")
    if evidence_summary.get("holds_sha256") != holds_sha256:
        raise ValueError("evidence summary holds SHA-256 mismatch")
    expected_counts = {
        "candidate_records": len(candidates),
        "evidence_records": len(evidence),
        "hold_records": len(holds),
        "live_identity_hold_records": len(LIVE_IDENTITY_HOLDS),
        "unmatched_model_core_hold_records": len(holds) - len(LIVE_IDENTITY_HOLDS),
        "partition_records": len(candidates),
        "matched_model_core_records": len({normalize_model(row["model_core"]) for row in evidence}),
        "pinned_table_core_records": 51,
    }
    for field, expected in expected_counts.items():
        if nonnegative_int(evidence_summary.get(field), field) != expected:
            raise ValueError(f"evidence summary {field} mismatch")
    for field in (
        "price_or_stock_records", "image_records", "indexability_authorizations",
        "automatic_database_mutations", "safe_to_apply_records",
    ):
        if nonnegative_int(evidence_summary.get(field), field) != 0:
            raise ValueError(f"evidence summary {field} must be zero")
    source_contracts = evidence_summary.get("pdf_sources")
    if not isinstance(source_contracts, list) or len(source_contracts) != len(PDF_CONTRACTS):
        raise ValueError("evidence summary must pin both official PDF sources")
    seen_pdf_hashes: set[str] = set()
    for source in source_contracts:
        if not isinstance(source, dict):
            raise ValueError("invalid PDF source contract")
        source_sha = source.get("sha256")
        contract = PDF_CONTRACTS.get(source_sha)
        source_path = resolve_snapshot(str(source.get("path", "")))
        if contract is None or source.get("source_url") != contract["source_url"]:
            raise ValueError("unsupported PDF source URL or SHA-256")
        if not source_path.is_file() or sha(source_path) != source_sha:
            raise ValueError("PDF source SHA-256 mismatch")
        seen_pdf_hashes.add(source_sha)
    if seen_pdf_hashes != set(PDF_CONTRACTS):
        raise ValueError("evidence summary PDF source set mismatch")

    products: list[dict[str, object]] = []
    for external_id, hold in hold_by_id.items():
        candidate = candidate_by_id[external_id]
        expected_reason = LIVE_IDENTITY_HOLDS.get(
            external_id, "no_exact_model_core_in_pinned_official_tables"
        )
        if (
            hold["legacy_model_token"] != candidate["model_token"]
            or hold["legacy_pack_variant_key"] != candidate["pack_variant_key"]
            or hold["reason"] != expected_reason
        ):
            raise ValueError(f"hold does not match candidate {external_id}")

    for external_id, row in evidence_by_id.items():
        candidate = candidate_by_id[external_id]
        if candidate["manufacturer"] != "Panasonic" or candidate["family"] not in TECHNOLOGIES:
            raise ValueError(f"candidate is not Panasonic CR/BR: {external_id}")
        if candidate["safe_to_apply"].strip().lower() != "false":
            raise ValueError("candidate safe_to_apply must explicitly be false")
        if row["legacy_model_token"] != candidate["model_token"] or row["legacy_pack_variant_key"] != candidate["pack_variant_key"]:
            raise ValueError(f"evidence legacy identity mismatch for {external_id}")
        match_kind = expected_match_kind(row["legacy_model_token"], row["model_core"])
        if match_kind is None or row["match_kind"] != match_kind:
            raise ValueError(f"invalid model-core boundary for {external_id}")
        if (
            row["manufacturer"] != "Panasonic"
            or row["identity_scope"] != "model_core"
            or row["evidence_scope"] != "model_core"
            or row["technology"] != TECHNOLOGIES[candidate["family"]]
            or row["source_kind"] != "official_manufacturer_catalogue"
            or row["source_publisher"] != "Panasonic Energy Co., Ltd."
            or row["manufacturer_primary"].strip().lower() != "true"
        ):
            raise ValueError(f"unsupported evidence contract for {external_id}")
        if row["price_or_stock_imported"].strip().lower() != "false" or row["safe_to_apply"].strip().lower() != "false":
            raise ValueError("commercial or automatic apply authorization is forbidden")
        source_sha = row["source_snapshot_sha256"].strip().lower()
        contract = PDF_CONTRACTS.get(source_sha)
        snapshot = resolve_snapshot(row["source_snapshot_path"])
        if (
            contract is None
            or row["source_url"] != contract["source_url"]
            or row["source_page"] not in contract["pages"]
            or not snapshot.is_file()
            or sha(snapshot) != source_sha
        ):
            raise ValueError(f"unverified official PDF source for {external_id}")
        voltage = positive_decimal(row["voltage_v"], f"{external_id}.voltage_v")
        capacity = positive_decimal(row["capacity_mah"], f"{external_id}.capacity_mah")
        diameter = positive_decimal(row["diameter_mm"], f"{external_id}.diameter_mm")
        width = positive_decimal(row["width_mm"], f"{external_id}.width_mm", optional=True)
        height = positive_decimal(row["height_mm"], f"{external_id}.height_mm")
        try:
            minimum = int(row["temperature_min_c"])
            maximum = int(row["temperature_max_c"])
        except ValueError as error:
            raise ValueError(f"invalid temperature bounds for {external_id}") from error
        if minimum >= maximum:
            raise ValueError(f"invalid temperature bounds for {external_id}")
        attributes = {
            "Технология": row["technology"],
            "Номинальное напряжение": f"{voltage} В",
            "Номинальная ёмкость": f"{capacity} мА·ч",
            "Диаметр": f"{diameter} мм",
            "Высота": f"{height} мм",
            "Диапазон рабочих температур": f"{minimum}…{maximum} °C",
        }
        if width:
            attributes["Ширина"] = f"{width} мм"
        products.append({
            "external_id": external_id,
            "manufacturer": "Panasonic",
            "identity_scope": "model_core",
            "evidence_scope": "model_core",
            "model_core": row["model_core"],
            "technology": row["technology"],
            "technical_attributes": attributes,
            "source_url": row["source_url"],
            "source_kind": "official_manufacturer_catalogue",
            "source_tier": "manufacturer_primary",
            "source_publisher": "Panasonic Energy Co., Ltd.",
            "manufacturer_primary": True,
            "checked_at": "2026-07-29",
        })

    descriptions_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "purpose": "Wave 200 Panasonic model-core technical evidence only. Legacy package identity is preserved. No display name, MPN, price, stock, image, Offer, indexability or database mutation authorization.",
        "locale": "ru-BY",
        "products": products,
    }
    descriptions_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = {
        "candidate_path": str(candidates_path),
        "candidate_sha256": candidate_sha256,
        "evidence_path": str(evidence_path),
        "evidence_sha256": evidence_sha256,
        "holds_path": str(holds_path),
        "holds_sha256": holds_sha256,
        "evidence_summary_path": str(evidence_summary_path),
        "evidence_summary_sha256": evidence_summary_sha256,
        "candidate_records": len(candidates),
        "evidence_records": len(evidence),
        "hold_records": len(holds),
        "partition_records": len(evidence) + len(holds),
        "materialized_records": len(products),
        "description_manifest": str(descriptions_path),
        "description_sha256": sha(descriptions_path),
        "price_or_stock_records": 0,
        "image_records": 0,
        "indexability_authorizations": 0,
        "automatic_database_mutations": 0,
    }
    materialization_summary_path.parent.mkdir(parents=True, exist_ok=True)
    materialization_summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--holds", type=Path, required=True)
    parser.add_argument("--evidence-summary", type=Path, required=True)
    parser.add_argument("--descriptions", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--expected-candidate-sha256", required=True)
    parser.add_argument("--expected-evidence-sha256", required=True)
    parser.add_argument("--expected-holds-sha256", required=True)
    parser.add_argument("--expected-evidence-summary-sha256", required=True)
    args = parser.parse_args()
    print(json.dumps(build(
        args.candidates, args.evidence, args.holds, args.evidence_summary,
        args.descriptions, args.summary, args.expected_candidate_sha256,
        args.expected_evidence_sha256, args.expected_holds_sha256,
        args.expected_evidence_summary_sha256,
    ), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
