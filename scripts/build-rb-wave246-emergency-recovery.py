#!/usr/bin/env python3
"""Rebuild fail-closed Wave246 recovery manifests from repository evidence only."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any


CATEGORY_SLUGS = {
    "seo:batteries-industrial": "catalog/industrial-batteries/batteries-industrial",
    "seo:batteries-traction": "catalog/industrial-batteries/batteries-traction",
    "seo:batteries-ups": "catalog/industrial-batteries/batteries-ups",
    "seo:chargers": "catalog/chargers",
    "seo:power-converters": "catalog/power-systems/power-converters",
    "seo:power-supplies": "catalog/power-systems/power-supplies",
    "seo:power-systems": "catalog/power-systems",
    "seo:primary-cells": "catalog/primary-cells",
    "seo:rechargeable-cells": "catalog/rechargeable-cells",
    "seo:replacement-batteries": "catalog/replacement-batteries",
    "seo:ups-systems": "catalog/power-systems/ups-systems",
}
SITE_KEY = "microchips-by"

MANUFACTURER_GLOBS = ("rb-manufacturer-product-candidates-*.json",)
DESCRIPTION_GLOBS = (
    "rb-source-backed-description*.json",
    "rb-manufacturer-evidence*.json",
)
PREVIEW_GLOBS = (
    "rb-source-verified-preview-*.json",
    "rb-bulk-source-backed-preview-*.json",
    "rb-reviewed-preview-*.json",
    "rb-model-core-preview-*.json",
)

# Four Wave246 rows require an explicit bridge from a historical preview category
# (or a duplicate hold) to the final pinned category. Every factual field below
# is checked against the named repository evidence before a row is emitted.
PREVIEW_RECOVERY_RULES: dict[str, dict[str, Any]] = {
    "КА-00005774": {
        "target_name": "APC Replacement Battery Cartridge APCRBC123",
        "manufacturer": "APC by Schneider Electric", "model_core": "APCRBC123",
        "category_external_id": "seo:batteries-ups",
        "preview_file": "rb-bulk-source-backed-preview-wave-133-2026-07-28.json",
        "old_category_slug": "catalog/rechargeable-cells",
        "description_file": "rb-source-backed-description-drafts-apc-bae-panasonic-wave-124-2026-07-28.json",
        "source_url": "https://www.apc.com/us/en/product/APCRBC123/apc-replacement-battery-cartridge-for-smartups-line-interactive-24v-7ah-leadacid-battery-2year-repair-or-replace-warranty/",
        "category_evidence": ("rb-site-category-move-confirmed-agm-wave146.csv", {
            "product_external_id": "КА-00005774", "from_category_external_id": "seo:rechargeable-cells", "to_category_external_id": "seo:batteries-ups",
        }),
    },
    "КА-00004972": {
        "target_name": "Аккумулятор Ventura HRL 12650W",
        "manufacturer": "Ventura", "model_core": "HRL 12650W",
        "category_external_id": "seo:batteries-ups",
        "preview_file": "rb-bulk-source-backed-preview-wave-133-2026-07-28.json",
        "old_category_slug": "catalog/rechargeable-cells",
        "description_file": "rb-source-backed-description-drafts-ventura-b-wave-128-2026-07-28.json",
        "source_url": "https://ventura-battery.ru/podderzhka/",
        "category_evidence": ("rb-site-category-move-confirmed-agm-wave146.csv", {
            "product_external_id": "КА-00004972", "from_category_external_id": "seo:rechargeable-cells", "to_category_external_id": "seo:batteries-ups",
        }),
    },
    "КА-00002676": {
        "target_name": "Адаптер/блок питания ROBITON B9-500 5,5x2, 1/12",
        "manufacturer": "Robiton", "model_core": "B9-500",
        "category_external_id": "seo:power-supplies",
        "preview_file": "rb-bulk-source-backed-preview-wave-133-2026-07-28.json",
        "old_category_slug": "catalog/chargers",
        "description_file": "rb-source-backed-description-drafts-robiton-wave-119-2026-07-28.json",
        "source_url": "https://www.robiton.ru/product/17518/",
        "category_evidence": ("rb-site-category-move-wave219c-robiton-adapter.csv", {
            "product_external_id": "КА-00002676", "from_category_external_id": "seo:chargers", "to_category_external_id": "seo:power-supplies",
        }),
    },
    "КА-00000471": {
        "target_name": "Аккумулятор CSB GP12170 B3",
        "manufacturer": "CSB", "model_core": "GP12170",
        "category_external_id": "seo:batteries-ups",
        "description_file": "rb-source-backed-description-drafts-csb-gp12170-wave-135-2026-07-28.json",
        "source_url": "https://csb-battery.com/wp-content/uploads/2026/03/CSB-Datasheet-GP12170-01312026.pdf",
        "product_slug": "csb-gp12170-b3",
        "duplicate_evidence": (
            ("rb-strict-duplicate-exclusion-csb-gp12170-wave-135.csv", {"product_external_id": "ФР-00001475", "reason": "exact_model_terminal_duplicate", "survivor_external_id": "КА-00000471"}),
            ("rb-strict-duplicate-exclusion-csb-wave-134.csv", {"product_external_id": "КА-00001065", "reason": "exact_model_terminal_duplicate", "survivor_external_id": "КА-00000471"}),
            ("rb-bulk-source-backed-preview-wave-133-2026-07-28-rejected.csv", {"external_id": "КА-00000471", "reason": "duplicate_current_brand_model_identity"}),
        ),
    },
}


class RecoveryError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_verified_price_ids(path: Path | None) -> set[str]:
    """Return only product IDs backed by the explicitly supplied price manifest."""
    if path is None:
        return set()
    expected = [
        "product_external_id", "source", "source_price", "currency", "observed_at",
        "source_reference", "source_external_id", "multiplier", "price_type",
    ]
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=";")
        if reader.fieldnames != expected:
            raise RecoveryError("verified price evidence header drifted")
        result: set[str] = set()
        for line, row in enumerate(reader, start=2):
            external_id = (row["product_external_id"] or "").strip()
            if (not external_id or external_id in result
                    or row["source"] not in {"legacy_site", "one_c_x2"}
                    or row["currency"] != "BYN"
                    or row["multiplier"] != ("2" if row["source"] == "one_c_x2" else "1")
                    or not row["observed_at"] or not row["source_reference"]
                    or not row["price_type"]):
                raise RecoveryError(f"invalid verified price evidence at line {line}")
            try:
                if float(row["source_price"].replace(",", ".")) <= 0:
                    raise ValueError
            except ValueError as error:
                raise RecoveryError(f"invalid verified price at line {line}") from error
            result.add(external_id)
    if not result:
        raise RecoveryError("verified price evidence is empty")
    return result


def authorize_verified_price(row: dict[str, Any], verified_price_ids: set[str]) -> dict[str, Any]:
    recovered = dict(row)
    if recovered.get("external_id") in verified_price_ids:
        recovered["allow_verified_price"] = True
    return recovered


def normalized(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = text.encode("ascii", "ignore").decode().casefold()
    return re.sub(r"[^a-z0-9]+", "", text)


def canonical(record: dict[str, Any]) -> str:
    return json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def read_target(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    required = {
        "product_external_id", "manufacturer", "mpn", "category_external_id",
        "has_applied_description",
    }
    missing = required.difference(rows[0] if rows else {})
    if missing:
        raise RecoveryError(f"target missing columns: {sorted(missing)}")
    ids = [row["product_external_id"].strip() for row in rows]
    duplicates = sorted(key for key, count in _counts(ids).items() if count > 1)
    if not all(ids) or duplicates:
        raise RecoveryError(f"target blank/duplicate identities: {duplicates}")
    return rows


def _counts(values: list[str]) -> dict[str, int]:
    result: dict[str, int] = defaultdict(int)
    for value in values:
        result[value] += 1
    return result


def discover(imports_dir: Path, globs: tuple[str, ...]) -> list[Path]:
    return sorted({path for pattern in globs for path in imports_dir.glob(pattern) if path.is_file()})


def products(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    records = payload.get("products", []) if isinstance(payload, dict) else []
    if not isinstance(records, list):
        raise RecoveryError(f"{path}: products is not a list")
    result = [record for record in records if isinstance(record, dict)]
    ids = [str(record.get("external_id") or "") for record in result]
    duplicates = sorted(key for key, count in _counts(ids).items() if key and count > 1)
    if duplicates:
        raise RecoveryError(f"{path}: duplicate identities {duplicates}")
    return result


def index_records(paths: list[Path]) -> dict[str, list[tuple[Path, dict[str, Any]]]]:
    index: dict[str, list[tuple[Path, dict[str, Any]]]] = defaultdict(list)
    for path in paths:
        for record in products(path):
            external_id = str(record.get("external_id") or "").strip()
            if external_id:
                index[external_id].append((path, record))
    return index


def exact_identity(target: dict[str, str], record: dict[str, Any]) -> bool:
    manufacturer = record.get("manufacturer")
    if target["manufacturer"] and manufacturer:
        if normalized(target["manufacturer"]) != normalized(manufacturer):
            return False
    target_mpn = normalized(target["mpn"])
    evidence_mpn = normalized(record.get("mpn") or record.get("model_core"))
    return not (target_mpn and evidence_mpn and target_mpn != evidence_mpn)


def source_rank(path: Path) -> tuple[int, str, int, str]:
    name = path.name
    if name.startswith("rb-source-backed-descriptions-"):
        kind = 5
    elif "stage-manifest" in name:
        kind = 4
    elif "stageable" in name:
        kind = 3
    elif "draft" in name:
        kind = 2
    elif "candidate" in name:
        kind = 1
    else:
        kind = 0
    date = max(re.findall(r"20\d{2}-\d{2}-\d{2}", name) or [""])
    wave = max([int(value) for value in re.findall(r"wave[-_ ]?(\d+)", name)] or [-1])
    return kind, date, wave, name


def select(records: list[tuple[Path, dict[str, Any]]]) -> tuple[Path, dict[str, Any]]:
    return max(records, key=lambda item: (source_rank(item[0]), canonical(item[1])))


def staging_description_record(record: dict[str, Any]) -> tuple[dict[str, Any], bool, bool]:
    """Remove only incomplete legacy provenance that the current policy rejects.

    Older accepted manifests used a free-text source_kind without the later
    source_tier contract.  Promoting that text to a tier would invent evidence;
    omitting the incomplete optional provenance keeps the original source URL,
    identity and technical facts while using the command's legacy path.
    """
    result = dict(record)
    has_kind = "source_kind" in result
    has_tier = "source_tier" in result
    if has_kind != has_tier:
        result.pop("source_kind", None)
        result.pop("source_tier", None)
        omitted_partial_provenance = True
    else:
        omitted_partial_provenance = False
    normalized_technology = False
    attributes = result.get("technical_attributes")
    technology = result.get("technology")
    if (isinstance(attributes, dict) and isinstance(attributes.get("Технология"), str)
            and attributes["Технология"].strip()
            and isinstance(technology, str) and technology.strip()
            and attributes["Технология"].strip() != technology.strip()):
        # Both strings come from the selected evidence record.  The dedicated
        # technical attribute is the command's canonical technology field.
        result["technology"] = attributes["Технология"].strip()
        normalized_technology = True
    return result, omitted_partial_provenance, normalized_technology


def conflict_entry(external_id: str, matches: list[tuple[Path, dict[str, Any]]],
                   chosen: tuple[Path, dict[str, Any]]) -> dict[str, Any] | None:
    distinct: dict[str, list[str]] = defaultdict(list)
    for path, record in matches:
        distinct[canonical(record)].append(path.name)
    if len(distinct) < 2:
        return None
    return {
        "external_id": external_id,
        "selected_source": chosen[0].name,
        "distinct_record_count": len(distinct),
        "candidate_sources": sorted({path.name for path, _ in matches}),
    }


def pin(paths: list[Path], base: Path) -> list[dict[str, str]]:
    return [
        {"path": path.relative_to(base).as_posix(), "sha256": sha256(path)}
        for path in sorted(set(paths))
    ]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")


def require_csv_evidence(path: Path, expected: dict[str, str]) -> None:
    if not path.is_file():
        raise RecoveryError(f"missing recovery evidence: {path}")
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not any(all(row.get(key) == value for key, value in expected.items()) for row in rows):
        raise RecoveryError(f"recovery evidence drift in {path.name}: {expected}")


def recover_preview_row(target: dict[str, str], imports_dir: Path,
                        preview_index: dict[str, list[tuple[Path, dict[str, Any]]]],
                        description_index: dict[str, list[tuple[Path, dict[str, Any]]]]) -> tuple[dict[str, Any], dict[str, Any], list[Path]] | None:
    external_id = target["product_external_id"]
    rule = PREVIEW_RECOVERY_RULES.get(external_id)
    if rule is None:
        return None
    for field, expected in (("name", rule["target_name"]), ("manufacturer", rule["manufacturer"]),
                            ("category_external_id", rule["category_external_id"])):
        if target[field] != expected:
            raise RecoveryError(f"final Wave246 target drift for {external_id}: {field}")
    expected_slug = CATEGORY_SLUGS[target["category_external_id"]]
    description_matches = [
        (path, row) for path, row in description_index.get(external_id, [])
        if path.name == rule["description_file"]
        and row.get("manufacturer") == rule["manufacturer"]
        and row.get("model_core") == rule["model_core"]
        and row.get("source_url") == rule["source_url"]
    ]
    if len(description_matches) != 1:
        raise RecoveryError(f"pinned recovery description missing or ambiguous for {external_id}")
    used_paths = [description_matches[0][0]]

    if rule.get("preview_file"):
        preview_matches = [
            (path, row) for path, row in preview_index.get(external_id, [])
            if path.name == rule["preview_file"]
            and row.get("manufacturer") == rule["manufacturer"]
            and row.get("identity_scope") == "model_core"
            and row.get("model_core") == rule["model_core"]
            and row.get("source_url") == rule["source_url"]
            and row.get("category_slug") == rule["old_category_slug"]
            and row.get("product_slug")
        ]
        if len(preview_matches) != 1:
            raise RecoveryError(f"pinned historical preview missing or ambiguous for {external_id}")
        row = dict(preview_matches[0][1])
        used_paths.append(preview_matches[0][0])
        category_file, category_expected = rule["category_evidence"]
        category_path = imports_dir / category_file
        require_csv_evidence(category_path, category_expected)
        used_paths.append(category_path)
        resolution = "reclassify_pinned_historical_preview_to_final_category"
    else:
        if preview_index.get(external_id):
            raise RecoveryError(f"unexpected historical preview appeared for duplicate survivor {external_id}")
        for evidence_file, expected in rule["duplicate_evidence"]:
            evidence_path = imports_dir / evidence_file
            require_csv_evidence(evidence_path, expected)
            used_paths.append(evidence_path)
        row = {
            "external_id": external_id,
            "manufacturer": rule["manufacturer"],
            "identity_scope": "model_core",
            "source_url": rule["source_url"],
            "category_slug": expected_slug,
            "product_slug": rule["product_slug"],
            "model_core": rule["model_core"],
        }
        resolution = "construct_from_pinned_description_after_exact_duplicate_survivor_resolution"
    row["category_slug"] = expected_slug
    row["replace_categories"] = True
    decision = {
        "external_id": external_id,
        "decision": "SAFE_EXACT_RECOVERY_PREVIEW",
        "resolution": resolution,
        "final_category_external_id": target["category_external_id"],
        "final_category_slug": expected_slug,
        "identity_scope": "model_core",
        "identity": rule["model_core"],
        "evidence_paths": sorted(path.name for path in set(used_paths)),
    }
    return row, decision, used_paths


def build(target_path: Path, imports_dir: Path, output_dir: Path, repo_root: Path,
          verified_price_evidence: Path | None = None) -> dict[str, Any]:
    targets = read_target(target_path)
    target_by_id = {row["product_external_id"]: row for row in targets}
    manufacturer_targets = [row for row in targets if row["product_external_id"].startswith("manufacturer:")]
    description_targets = [row for row in targets if row["has_applied_description"].casefold() == "true"]
    preview_targets = [row for row in targets if not row["product_external_id"].startswith("bitrix:")]

    manufacturer_paths = discover(imports_dir, MANUFACTURER_GLOBS)
    description_paths = discover(imports_dir, DESCRIPTION_GLOBS)
    preview_paths = discover(imports_dir, PREVIEW_GLOBS)
    manufacturer_index = index_records(manufacturer_paths)
    description_index = index_records(description_paths)
    preview_index = index_records(preview_paths)
    verified_price_ids = read_verified_price_ids(verified_price_evidence)

    manufacturer_output: list[dict[str, Any]] = []
    manufacturer_unresolved: list[str] = []
    seen_product_identities: set[tuple[str, str, str]] = set()
    for target in manufacturer_targets:
        matches = []
        for path, record in manufacturer_index.get(target["product_external_id"], []):
            if (record.get("manufacturer") == target["manufacturer"]
                    and record.get("mpn") == target["mpn"]
                    and record.get("category_external_id") == target["category_external_id"]):
                matches.append((path, record))
        if len(matches) != 1:
            manufacturer_unresolved.append(target["product_external_id"])
            continue
        path, record = matches[0]
        identity = (record["manufacturer"], record["mpn"], record["category_external_id"])
        if identity in seen_product_identities:
            raise RecoveryError(f"duplicate manufacturer/mpn/category identity: {identity}")
        seen_product_identities.add(identity)
        manufacturer_output.append(record)

    description_output: list[dict[str, Any]] = []
    description_unresolved: list[str] = []
    description_conflicts: list[dict[str, Any]] = []
    description_legacy_provenance_omissions: list[str] = []
    description_technology_normalizations: list[str] = []
    for target in description_targets:
        matches = [item for item in description_index.get(target["product_external_id"], [])
                   if item[1].get("source_url") and exact_identity(target, item[1])]
        if not matches:
            description_unresolved.append(target["product_external_id"])
            continue
        chosen = select(matches)
        staged_record, omitted_partial_provenance, normalized_technology = staging_description_record(chosen[1])
        description_output.append(staged_record)
        if omitted_partial_provenance:
            description_legacy_provenance_omissions.append(target["product_external_id"])
        if normalized_technology:
            description_technology_normalizations.append(target["product_external_id"])
        conflict = conflict_entry(target["product_external_id"], matches, chosen)
        if conflict:
            description_conflicts.append(conflict)
    description_by_id = {row["external_id"]: row for row in description_output}

    preview_output: list[dict[str, Any]] = []
    preview_unresolved: list[dict[str, Any]] = []
    preview_conflicts: list[dict[str, Any]] = []
    preview_recovery_resolutions: list[dict[str, Any]] = []
    preview_recovery_inputs: list[Path] = []
    for target in preview_targets:
        expected_slug = CATEGORY_SLUGS.get(target["category_external_id"])
        matches = [item for item in preview_index.get(target["product_external_id"], [])
                   if expected_slug and item[1].get("category_slug") == expected_slug
                   and item[1].get("product_slug") and exact_identity(target, item[1])]
        if not matches:
            recovered = recover_preview_row(target, imports_dir, preview_index, description_index)
            if recovered is not None:
                row, resolution, used_paths = recovered
                preview_output.append(authorize_verified_price(row, verified_price_ids))
                preview_recovery_resolutions.append(resolution)
                preview_recovery_inputs.extend(used_paths)
                continue
            preview_unresolved.append({
                "external_id": target["product_external_id"],
                "manufacturer": target["manufacturer"],
                "mpn": target["mpn"],
                "category_external_id": target["category_external_id"],
                "available_sources": sorted({path.name for path, _ in preview_index.get(target["product_external_id"], [])}),
            })
            continue
        chosen = select(matches)
        preview_output.append(authorize_verified_price(chosen[1], verified_price_ids))
        conflict = conflict_entry(target["product_external_id"], matches, chosen)
        if conflict:
            preview_conflicts.append(conflict)

    preview_source_realignments: list[str] = []
    preview_model_core_realignments: list[str] = []
    for index, row in enumerate(preview_output):
        external_id = row["external_id"]
        description = description_by_id.get(external_id)
        if description is None or not description.get("source_url"):
            raise RecoveryError(f"preview has no recovered applied-description source for {external_id}")
        if row.get("source_url") != description["source_url"]:
            preview_source_realignments.append(external_id)
            aligned = dict(row)
            aligned["source_url"] = description["source_url"]
            preview_output[index] = aligned
            row = aligned
        if description.get("identity_scope") == "exact":
            description_mpn = description.get("mpn")
            row_identity = row.get("mpn") if row.get("identity_scope", "exact") == "exact" else row.get("model_core")
            if not description_mpn or normalized(row_identity) != normalized(description_mpn):
                raise RecoveryError(f"preview exact identity drifted from applied description for {external_id}")
            if row.get("identity_scope") == "model_core":
                aligned = dict(row)
                aligned["identity_scope"] = "exact"
                aligned["mpn"] = description_mpn
                aligned.pop("model_core", None)
                preview_output[index] = aligned
        elif (description.get("identity_scope") == "model_core"
              and row.get("identity_scope") == "model_core"
              and normalized(row.get("model_core")) != normalized(description.get("model_core"))):
            aligned = dict(preview_output[index])
            aligned["model_core"] = description["model_core"]
            preview_output[index] = aligned
            preview_model_core_realignments.append(external_id)

    all_inputs = [target_path, *manufacturer_paths, *description_paths, *preview_paths, *preview_recovery_inputs]
    input_pins = pin(all_inputs, repo_root)
    preview_input_pins = pin(
        [*all_inputs, *([verified_price_evidence] if verified_price_evidence is not None else [])],
        repo_root,
    )
    manifest_common = {"schema_version": 1, "locale": "ru-BY", "input_pins": input_pins}
    write_json(output_dir / "rb-wave246-recovery-manufacturer-product-candidates.json", {
        **manifest_common,
        "site_key": SITE_KEY,
        "purpose": "Emergency recovery of exact final manufacturer products; no apply",
        "recovery_status": "blocked_unresolved" if manufacturer_unresolved else "ready",
        "unresolved": manufacturer_unresolved,
        "products": manufacturer_output,
    })
    write_json(output_dir / "rb-wave246-recovery-source-backed-descriptions.json", {
        **manifest_common,
        "purpose": "Emergency recovery of source-backed descriptions; no apply",
        "recovery_status": "blocked_unresolved" if description_unresolved else "ready",
        "selection_conflicts": description_conflicts,
        "legacy_partial_provenance_omissions": description_legacy_provenance_omissions,
        "technology_normalizations": description_technology_normalizations,
        "unresolved": description_unresolved,
        "products": description_output,
    })
    write_json(output_dir / "rb-wave246-recovery-preview-publication.json", {
        **manifest_common,
        "input_pins": preview_input_pins,
        "purpose": "Emergency recovery of final non-Bitrix preview publication records; no apply",
        "recovery_status": "blocked_unresolved" if preview_unresolved else "ready",
        "recovery_resolutions": preview_recovery_resolutions,
        "selection_conflicts": preview_conflicts,
        "unresolved": preview_unresolved,
        "products": preview_output,
    })
    summary = {
        "schema_version": 1,
        "status": "blocked_unresolved" if any((manufacturer_unresolved, description_unresolved, preview_unresolved)) else "ready",
        "target_path": target_path.relative_to(repo_root).as_posix(),
        "target_sha256": sha256(target_path),
        "target_rows": len(targets),
        "manufacturer": {"target": len(manufacturer_targets), "selected": len(manufacturer_output), "unresolved": manufacturer_unresolved},
        "descriptions": {
            "target": len(description_targets),
            "selected": len(description_output),
            "unresolved": description_unresolved,
            "conflict_count": len(description_conflicts),
            "legacy_partial_provenance_omission_count": len(description_legacy_provenance_omissions),
            "technology_normalization_count": len(description_technology_normalizations),
        },
        "preview_publication": {"target": len(preview_targets), "selected": len(preview_output), "unresolved": preview_unresolved, "conflict_count": len(preview_conflicts), "recovery_resolution_count": len(preview_recovery_resolutions), "recovery_resolutions": preview_recovery_resolutions, "verified_price_authorizations": sum(row.get("allow_verified_price") is True for row in preview_output), "applied_description_source_realignments": preview_source_realignments, "applied_description_model_core_realignments": preview_model_core_realignments},
        "input_pins": preview_input_pins,
        "output_hashes": {},
    }
    for name in (
        "rb-wave246-recovery-manufacturer-product-candidates.json",
        "rb-wave246-recovery-source-backed-descriptions.json",
        "rb-wave246-recovery-preview-publication.json",
    ):
        summary["output_hashes"][name] = sha256(output_dir / name)
    write_json(output_dir / "rb-wave246-recovery.summary.json", summary)
    if summary["status"] != "ready":
        raise RecoveryError(
            "unresolved target rows: "
            f"manufacturer={len(manufacturer_unresolved)}, "
            f"descriptions={len(description_unresolved)}, preview={len(preview_unresolved)}"
        )
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=Path, default=Path("docs/audits/generated/rb-full-content-readiness-wave246-after.csv"))
    parser.add_argument("--imports-dir", type=Path, default=Path("docs/imports"))
    parser.add_argument("--output-dir", type=Path, default=Path("docs/audits/generated"))
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--verified-price-evidence", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        summary = build(
            args.target.resolve(), args.imports_dir.resolve(), args.output_dir.resolve(),
            args.repo_root.resolve(),
            args.verified_price_evidence.resolve() if args.verified_price_evidence else None,
        )
    except RecoveryError as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
