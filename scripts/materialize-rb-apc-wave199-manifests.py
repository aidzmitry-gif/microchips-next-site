#!/usr/bin/env python3
"""Materialize exact APC description and image-review manifests.

The description manifest still has to pass Laravel's live identity/lineage
dry-run. Official image URLs remain review-only and are never published here.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlsplit


SHA256 = re.compile(r"[0-9a-f]{64}", re.I)
MODEL_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]{1,63}")
PRODUCT_PATH = re.compile(r"/[A-Za-z]{2}/[A-Za-z]{2}/product/([^/]+)(?:/[^/?#]+)?/?")
NUMBER = re.compile(r"\d+(?:\.\d+)?")
TECHNOLOGY_NAMES = {
    "VRLA lead-acid": "VRLA",
    "lead-acid": "Свинцово-кислотная",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require_pinned_file(path: Path, expected_sha256: str, label: str) -> str:
    if not path.is_file():
        raise ValueError(f"{label} must be an existing file")
    expected = (expected_sha256 or "").strip().casefold()
    if SHA256.fullmatch(expected) is None:
        raise ValueError(f"expected {label} SHA-256 must be a 64-character hash")
    actual = sha(path)
    if actual != expected:
        raise ValueError(f"{label} SHA-256 mismatch")
    return actual


def load(path: Path, required: set[str]) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError("missing required columns: " + ", ".join(sorted(missing)))
        return list(reader)


def exact_false(value: str, field: str) -> None:
    if (value or "").strip().casefold() != "false":
        raise ValueError(f"{field} must explicitly be false")


def exact_product_url(value: str, model_token: str) -> bool:
    parsed = urlsplit((value or "").strip())
    match = PRODUCT_PATH.fullmatch(parsed.path)
    return bool(
        parsed.scheme == "https"
        and parsed.netloc.casefold() == "www.se.com"
        and not parsed.query
        and not parsed.fragment
        and match
        and match.group(1).casefold() == model_token.casefold()
    )


def strict_optional_number(value: str, field: str) -> str:
    normalized = (value or "").strip()
    if not normalized:
        return ""
    if NUMBER.fullmatch(normalized) is None or float(normalized) <= 0:
        raise ValueError(f"{field} must be a positive decimal number or blank")
    return normalized


def nonnegative_int(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"evidence summary {field} must be a nonnegative integer")
    return value


def build(
    candidates_path: Path,
    evidence_path: Path,
    holds_path: Path,
    evidence_summary_path: Path,
    descriptions_path: Path,
    images_path: Path,
    summary_path: Path,
    expected_candidate_sha256: str,
    expected_evidence_sha256: str,
    expected_holds_sha256: str,
    expected_evidence_summary_sha256: str,
) -> dict[str, object]:
    candidate_sha256 = require_pinned_file(candidates_path, expected_candidate_sha256, "candidate")
    evidence_sha256 = require_pinned_file(evidence_path, expected_evidence_sha256, "evidence")
    holds_sha256 = require_pinned_file(holds_path, expected_holds_sha256, "identity holds")
    evidence_summary_sha256 = require_pinned_file(
        evidence_summary_path, expected_evidence_summary_sha256, "evidence summary"
    )
    candidates = load(candidates_path, {"external_id", "model_token", "safe_to_apply"})
    evidence = load(evidence_path, {
        "external_id", "model_token", "source_url", "source_snapshot_path", "source_sha256",
        "product_type", "technology", "voltage_v", "capacity_ah",
        "capacity_vah", "image_url_candidate", "image_safe_to_publish",
        "price_or_stock_imported", "publisher", "evidence_kind", "safe_to_apply",
    })
    candidate_by_id = {row["external_id"]: row for row in candidates}
    if len(candidate_by_id) != len(candidates):
        raise ValueError("candidate external_id must be unique")
    model_keys = [re.sub(r"[^a-z0-9]", "", row["model_token"].casefold()) for row in candidates]
    if any(MODEL_TOKEN.fullmatch(row["model_token"]) is None for row in candidates):
        raise ValueError("candidate model_token must be an exact APC SKU token")
    if len(set(model_keys)) != len(model_keys):
        raise ValueError("candidate model_token must be unique after identity normalization")
    holds = load(holds_path, {"external_id", "model_token", "reason"})
    hold_by_id = {row["external_id"]: row for row in holds}
    if len(hold_by_id) != len(holds) or any(not row["reason"].strip() for row in holds):
        raise ValueError("identity holds must be unique and have a reason")
    for external_id, hold in hold_by_id.items():
        candidate = candidate_by_id.get(external_id)
        if candidate is None or candidate["model_token"] != hold["model_token"]:
            raise ValueError(f"identity hold does not match candidate {external_id}")

    try:
        evidence_summary = json.loads(evidence_summary_path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("evidence summary must be valid UTF-8 JSON") from error
    if not isinstance(evidence_summary, dict):
        raise ValueError("evidence summary must be a JSON object")
    rejected_counts = evidence_summary.get("rejected_counts")
    if not isinstance(rejected_counts, dict) or any(not isinstance(key, str) or not key for key in rejected_counts):
        raise ValueError("evidence summary rejected_counts must be a named count map")
    rejected_records = sum(
        nonnegative_int(value, f"rejected_counts.{key}") for key, value in rejected_counts.items()
    )
    candidate_records = nonnegative_int(evidence_summary.get("candidate_records"), "candidate_records")
    registry_records = nonnegative_int(evidence_summary.get("registry_records"), "registry_records")
    exact_evidence_records = nonnegative_int(
        evidence_summary.get("exact_evidence_records"), "exact_evidence_records"
    )
    technical_fact_records = nonnegative_int(
        evidence_summary.get("technical_fact_records"), "technical_fact_records"
    )
    image_candidate_records = nonnegative_int(
        evidence_summary.get("image_candidates_not_publishable"),
        "image_candidates_not_publishable",
    )
    if SHA256.fullmatch(str(evidence_summary.get("registry_sha256", ""))) is None:
        raise ValueError("evidence summary registry_sha256 must be a 64-character hash")
    if evidence_summary.get("candidate_sha256") != candidate_sha256:
        raise ValueError("evidence summary candidate SHA-256 mismatch")
    if evidence_summary.get("output_sha256") != evidence_sha256:
        raise ValueError("evidence summary output SHA-256 mismatch")
    if candidate_records != len(candidates) or registry_records != candidate_records:
        raise ValueError("evidence summary candidate/registry count mismatch")
    if exact_evidence_records != len(evidence):
        raise ValueError("evidence summary exact evidence count mismatch")
    actual_technical_fact_records = sum(
        bool(
            row["voltage_v"].strip()
            or row["capacity_ah"].strip()
            or row["capacity_vah"].strip()
        )
        for row in evidence
    )
    if technical_fact_records != actual_technical_fact_records:
        raise ValueError("evidence summary technical fact count mismatch")
    actual_image_candidate_records = sum(bool(row["image_url_candidate"].strip()) for row in evidence)
    if image_candidate_records != actual_image_candidate_records:
        raise ValueError("evidence summary image candidate count mismatch")
    if candidate_records != exact_evidence_records + rejected_records:
        raise ValueError("evidence summary does not completely partition all candidates")
    for field in ("price_or_stock_records", "automatic_database_mutations", "safe_to_apply_records"):
        if nonnegative_int(evidence_summary.get(field), field) != 0:
            raise ValueError(f"evidence summary {field} must be zero")

    manifests: list[dict[str, object]] = []
    image_rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in evidence:
        external_id = row["external_id"]
        candidate = candidate_by_id.get(external_id)
        if candidate is None or candidate["model_token"] != row["model_token"]:
            raise ValueError(f"evidence identity does not match candidate {external_id}")
        if external_id in seen:
            raise ValueError(f"evidence repeats external_id {external_id}")
        seen.add(external_id)
        exact_false(candidate["safe_to_apply"], "candidate.safe_to_apply")
        exact_false(row["safe_to_apply"], "evidence.safe_to_apply")
        exact_false(row["image_safe_to_publish"], "image_safe_to_publish")
        exact_false(row["price_or_stock_imported"], "price_or_stock_imported")
        if row["publisher"] != "APC by Schneider Electric" or row["evidence_kind"] != "exact_product_jsonld":
            raise ValueError("unsupported APC publisher/evidence kind")
        if not exact_product_url(row["source_url"], row["model_token"]):
            raise ValueError(f"evidence source URL is not an exact www.se.com product URL for {external_id}")
        source_sha256 = (row["source_sha256"] or "").strip().casefold()
        if SHA256.fullmatch(source_sha256) is None:
            raise ValueError("evidence source_sha256 must be a 64-character hash")
        snapshot = Path(row["source_snapshot_path"].strip())
        if not snapshot.is_absolute():
            snapshot = evidence_path.parent / snapshot
        if not snapshot.is_file() or sha(snapshot) != source_sha256:
            raise ValueError(f"evidence source snapshot SHA-256 mismatch for {external_id}")
        if row["technology"] not in TECHNOLOGY_NAMES:
            raise ValueError(f"unsupported battery technology for {external_id}")
        voltage_v = strict_optional_number(row["voltage_v"], f"{external_id}.voltage_v")
        capacity_ah = strict_optional_number(row["capacity_ah"], f"{external_id}.capacity_ah")
        capacity_vah = strict_optional_number(row["capacity_vah"], f"{external_id}.capacity_vah")
        hold = hold_by_id.get(external_id)
        if hold is not None:
            if hold["model_token"] != row["model_token"]:
                raise ValueError(f"hold model does not match {external_id}")
            continue

        sku = row["model_token"]
        type_names = {
            "replacement_battery_cartridge": "Сменный аккумуляторный картридж",
            "external_battery_pack": "Внешний батарейный блок",
            "battery_module": "Аккумуляторный модуль",
            "battery_product": "Аккумуляторное изделие",
        }
        if row["product_type"] not in type_names:
            raise ValueError(f"unsupported product type for {external_id}")
        technology = TECHNOLOGY_NAMES[row["technology"]]
        attributes = {
            "Тип изделия": type_names[row["product_type"]],
            "Технология": technology,
        }
        if voltage_v:
            attributes["Номинальное напряжение"] = f'{voltage_v} В'
        if capacity_ah:
            attributes["Номинальная ёмкость"] = f'{capacity_ah} А·ч'
        if capacity_vah:
            attributes["Энергия батарейного блока"] = f'{capacity_vah} ВА·ч'
        manifests.append({
            "external_id": external_id,
            "identity_scope": "exact",
            "manufacturer": "APC",
            "mpn": sku,
            "display_name": f'{type_names[row["product_type"]]} APC {sku}',
            "technology": technology,
            "source_url": row["source_url"],
            "technical_attributes": attributes,
            "source_kind": "official_manufacturer_catalogue",
            "source_tier": "manufacturer_primary",
            "source_publisher": "APC by Schneider Electric",
            "manufacturer_primary": True,
            "evidence_scope": "exact_model",
            "checked_at": "2026-07-29",
        })
        if row["image_url_candidate"]:
            image_rows.append({
                "external_id": external_id,
                "model_token": sku,
                "source_page_url": row["source_url"],
                "source_asset_url": row["image_url_candidate"],
                "source_page_sha256": row["source_sha256"],
                "required_review": "download_hash|exact_sku_visual_or_unique_catalog_identity|rights_basis|dimensions|mime",
                "safe_to_publish": "false",
            })

    descriptions_path.parent.mkdir(parents=True, exist_ok=True)
    description_manifest = {
        "schema_version": 1,
        "purpose": "Wave 199 exact first-party APC enrichment. No RB price, stock, Offer, image publication or indexability authorization.",
        "locale": "ru-BY",
        "products": manifests,
    }
    descriptions_path.write_text(json.dumps(description_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    image_fields = [
        "external_id", "model_token", "source_page_url", "source_asset_url",
        "source_page_sha256", "required_review", "safe_to_publish",
    ]
    with images_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=image_fields)
        writer.writeheader(); writer.writerows(image_rows)
    summary = {
        "candidate_path": str(candidates_path), "candidate_sha256": candidate_sha256,
        "evidence_path": str(evidence_path), "evidence_sha256": evidence_sha256,
        "evidence_summary_path": str(evidence_summary_path),
        "evidence_summary_sha256": evidence_summary_sha256,
        "partition_candidate_records": candidate_records,
        "partition_evidence_records": exact_evidence_records,
        "partition_rejected_records": rejected_records,
        "identity_holds_path": str(holds_path), "identity_holds_sha256": holds_sha256,
        "identity_holds": len(holds),
        "description_manifest": str(descriptions_path), "description_sha256": sha(descriptions_path),
        "description_records": len(manifests),
        "image_review_manifest": str(images_path), "image_review_sha256": sha(images_path),
        "image_review_records": len(image_rows), "publishable_image_records": 0,
        "price_or_stock_records": 0, "automatic_database_mutations": 0,
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--identity-holds", type=Path, required=True)
    parser.add_argument("--evidence-summary", type=Path, required=True)
    parser.add_argument("--descriptions", type=Path, required=True)
    parser.add_argument("--images", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--expected-candidate-sha256", required=True)
    parser.add_argument("--expected-evidence-sha256", required=True)
    parser.add_argument("--expected-identity-holds-sha256", required=True)
    parser.add_argument("--expected-evidence-summary-sha256", required=True)
    args = parser.parse_args()
    print(json.dumps(build(
        args.candidates, args.evidence, args.identity_holds, args.evidence_summary,
        args.descriptions, args.images, args.summary, args.expected_candidate_sha256,
        args.expected_evidence_sha256, args.expected_identity_holds_sha256,
        args.expected_evidence_summary_sha256,
    ), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
