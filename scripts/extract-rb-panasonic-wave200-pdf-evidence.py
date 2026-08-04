#!/usr/bin/env python3
"""Extract fail-closed Panasonic Wave200 model-core evidence from pinned PDFs.

The official tables describe battery model cores, not retail package variants.
Every matched candidate therefore keeps its legacy identity while inheriting
only the technical facts printed for an unambiguous model core.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pdfplumber


COIN_FILENAME = "Introduction_coin_primary_lithium_EN.pdf"
CYLINDRICAL_FILENAME = "Introduction_cylindrical_primary_lithium_EN.pdf"
PDF_SPECS = {
    COIN_FILENAME: {
        "sha256": "1ce9b9fa72a6263f34cf2390726ddb009759c04303c1d3f39bc981473af5f343",
        "source_url": "https://energy.panasonic.com/dam/master/pdf/en/material/lithium/Introduction_of_coin_type_primary_lithium_batteries_EN.pdf",
        "pages": {
            3: (
                "CR1025", "CR1216", "CR1220", "CR1616", "CR1620", "CR1632",
                "CR2012", "CR2016", "CR2025", "CR2032", "CR2330", "CR2354",
                "CR2412", "CR2450", "CR2477", "CR3032", "CR2032A", "CR2032B",
                "CR2050A", "CR2050B2", "CR2450B",
            ),
            4: (
                "BR1220", "BR1225", "BR1632", "BR2032", "BR2325", "BR2330",
                "BR3032", "BR1225A", "BR1632A", "BR2330A", "BR2477A",
            ),
        },
        "header": "Model No.",
        "columns": {"model": 2, "voltage": 3, "capacity": 4, "diameter": 6, "height": 7, "temperature": 9},
    },
    CYLINDRICAL_FILENAME: {
        "sha256": "116c40368f6ee67f5c7842c3b6d3968089c5a979c40fcb0275b303f86f1705ca",
        "source_url": "https://energy.panasonic.com/dam/master/pdf/en/material/lithium/Introduction_of_primary_lithium_batteries_cylindrical_type_CR_series_longlife_EN.pdf",
        "pages": {
            6: (
                "BR-1/2AA", "BR-2/3A", "BR-2/3AG", "BR-A", "BR-AG", "BR-C",
                "CR-2/3AU", "CR-2/3AZ", "CR-AAU", "CR-AG", "CR-AGZ", "CR-LAS",
                "CR-LAZ", "CR2U", "CR2Z", "2CR5", "CR-P2", "CR123A", "CR2",
            ),
        },
        "header": "Model",
        "columns": {"model": 2, "voltage": 3, "capacity": 4, "diameter": 6, "width": 7, "height": 8, "temperature": 10},
    },
}

# Attached suffixes are packaging/terminal variants explicitly observed in the
# Wave200 legacy identities. Arbitrary prefix matching is forbidden.
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

EVIDENCE_FIELDS = [
    "product_external_id", "legacy_model_token", "legacy_pack_variant_key", "model_core",
    "match_kind", "manufacturer", "identity_scope", "evidence_scope", "technology",
    "voltage_v", "capacity_mah", "diameter_mm", "width_mm", "height_mm",
    "temperature_min_c", "temperature_max_c", "source_url", "source_snapshot_path",
    "source_snapshot_sha256", "source_page", "source_kind", "source_publisher",
    "manufacturer_primary", "price_or_stock_imported", "safe_to_apply",
]
HOLD_FIELDS = ["product_external_id", "legacy_model_token", "legacy_pack_variant_key", "reason"]
HYPHENS = re.compile(r"[-‐‑‒–—\s]")
TEMPERATURE = re.compile(r"([+-]?\d+)\s*[～~]\s*\+?([+-]?\d+)")
SHA256 = re.compile(r"[0-9a-f]{64}")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize_model(value: str) -> str:
    return HYPHENS.sub("", (value or "").strip().upper())


def required_decimal(value: object, field: str) -> str:
    normalized = str(value or "").strip()
    try:
        number = Decimal(normalized)
    except InvalidOperation as error:
        raise ValueError(f"invalid {field}: {normalized!r}") from error
    if number <= 0:
        raise ValueError(f"invalid {field}: {normalized!r}")
    return normalized


def optional_decimal(value: object, field: str) -> str:
    normalized = str(value or "").strip()
    if normalized in {"", "-"}:
        return ""
    return required_decimal(normalized, field)


def temperature_bounds(value: object) -> tuple[str, str]:
    normalized = str(value or "").strip()
    match = TEMPERATURE.fullmatch(normalized)
    if match is None:
        raise ValueError(f"invalid operating temperature range: {normalized!r}")
    minimum, maximum = int(match.group(1)), int(match.group(2))
    if minimum >= maximum:
        raise ValueError(f"invalid operating temperature range: {normalized!r}")
    return str(minimum), str(maximum)


def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def load_csv(path: Path, required: set[str]) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError("missing required columns: " + ", ".join(sorted(missing)))
        return list(reader)


def table_after_header(page: object, expected_header: str) -> list[list[str | None]]:
    matches: list[list[list[str | None]]] = []
    for table in page.extract_tables():
        for index, row in enumerate(table):
            cells = [(cell or "").replace("\n", " ").strip() for cell in row]
            if expected_header in cells:
                matches.append(table[index + 1 :])
    if len(matches) != 1:
        raise ValueError(f"expected one {expected_header!r} table, found {len(matches)}")
    return matches[0]


def extract_pdf_rows(path: Path, spec: dict[str, object]) -> list[dict[str, str]]:
    if not path.is_file() or sha(path) != spec["sha256"]:
        raise ValueError(f"pinned PDF SHA-256 mismatch: {path.name}")
    rows: list[dict[str, str]] = []
    with pdfplumber.open(path) as pdf:
        for page_number, expected_models in spec["pages"].items():
            if page_number > len(pdf.pages):
                raise ValueError(f"missing pinned table page {page_number} in {path.name}")
            raw_rows = table_after_header(pdf.pages[page_number - 1], spec["header"])
            columns = spec["columns"]
            last_voltage = ""
            last_temperature = ""
            page_rows: list[dict[str, str]] = []
            for raw in raw_rows:
                model = (raw[columns["model"]] or "").replace("\n", "").strip()
                if not model:
                    continue
                voltage = (raw[columns["voltage"]] or "").strip() or last_voltage
                temperature = (raw[columns["temperature"]] or "").strip() or last_temperature
                last_voltage, last_temperature = voltage, temperature
                minimum, maximum = temperature_bounds(temperature)
                family = "BR" if normalize_model(model).startswith("BR") else "CR"
                page_rows.append({
                    "model_core": model,
                    "normalized_model_core": normalize_model(model),
                    "family": family,
                    "technology": "Литий-поликарбонмонофторид" if family == "BR" else "Литий-диоксид марганца",
                    "voltage_v": required_decimal(voltage, "nominal voltage"),
                    "capacity_mah": required_decimal(raw[columns["capacity"]], "nominal capacity"),
                    "diameter_mm": required_decimal(raw[columns["diameter"]], "diameter"),
                    "width_mm": optional_decimal(raw[columns["width"]], "width") if "width" in columns else "",
                    "height_mm": required_decimal(raw[columns["height"]], "height"),
                    "temperature_min_c": minimum,
                    "temperature_max_c": maximum,
                    "source_url": spec["source_url"],
                    "source_snapshot_path": str(path.resolve()),
                    "source_snapshot_sha256": spec["sha256"],
                    "source_page": str(page_number),
                })
            if tuple(row["model_core"] for row in page_rows) != tuple(expected_models):
                raise ValueError(f"pinned table model contract mismatch on {path.name} page {page_number}")
            rows.extend(page_rows)
    return rows


def build_core_index(table_rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    index: dict[str, dict[str, str]] = {}
    for row in table_rows:
        normalized = row["normalized_model_core"]
        if not normalized or normalized in index:
            raise ValueError(f"ambiguous normalized model core: {normalized!r}")
        index[normalized] = row
    return index


def match_model_core(model_token: str, core_index: dict[str, dict[str, str]]) -> tuple[dict[str, str], str] | None:
    candidate = normalize_model(model_token)
    matches: list[tuple[int, dict[str, str], str]] = []
    for normalized, row in core_index.items():
        if candidate == normalized:
            matches.append((len(normalized), row, "exact_core"))
        elif candidate.startswith(normalized + "/"):
            matches.append((len(normalized), row, "slash_package_variant"))
        elif candidate.startswith(normalized):
            suffix = candidate[len(normalized) :]
            if suffix in ATTACHED_SUFFIXES.get(row["model_core"], set()):
                matches.append((len(normalized), row, "whitelisted_attached_suffix"))
    if not matches:
        return None
    longest = max(length for length, _, _ in matches)
    winners = [(row, kind) for length, row, kind in matches if length == longest]
    if len(winners) != 1:
        raise ValueError(f"ambiguous model-core match for {model_token}")
    return winners[0]


def build(
    candidates_path: Path,
    coin_pdf: Path,
    cylindrical_pdf: Path,
    evidence_path: Path,
    holds_path: Path,
    summary_path: Path,
    expected_candidate_sha256: str,
) -> dict[str, object]:
    expected_candidate = (expected_candidate_sha256 or "").strip().lower()
    if SHA256.fullmatch(expected_candidate) is None or not candidates_path.is_file() or sha(candidates_path) != expected_candidate:
        raise ValueError("candidate SHA-256 mismatch")
    candidates = load_csv(candidates_path, {
        "product_external_id", "legacy_name", "manufacturer", "family", "model_token",
        "pack_variant_key", "safe_to_apply",
    })
    candidate_ids = [row["product_external_id"].strip() for row in candidates]
    if any(not value for value in candidate_ids) or len(set(candidate_ids)) != len(candidate_ids):
        raise ValueError("candidate external IDs must be nonempty and unique")
    if not set(LIVE_IDENTITY_HOLDS) <= set(candidate_ids):
        raise ValueError("pinned live identity holds are missing from candidates")
    for row in candidates:
        if row["manufacturer"] != "Panasonic" or row["family"] not in {"CR", "BR"}:
            raise ValueError("candidate must be a Panasonic CR/BR identity")
        if row["safe_to_apply"].strip().lower() != "false":
            raise ValueError("candidate safe_to_apply must explicitly be false")
        if not row["model_token"].strip() or not row["pack_variant_key"].strip():
            raise ValueError("candidate legacy identity must be complete")

    table_rows = extract_pdf_rows(coin_pdf, PDF_SPECS[COIN_FILENAME])
    table_rows += extract_pdf_rows(cylindrical_pdf, PDF_SPECS[CYLINDRICAL_FILENAME])
    core_index = build_core_index(table_rows)
    evidence: list[dict[str, str]] = []
    holds: list[dict[str, str]] = []
    matched_cores: set[str] = set()
    for candidate in candidates:
        live_hold_reason = LIVE_IDENTITY_HOLDS.get(candidate["product_external_id"])
        if live_hold_reason is not None:
            holds.append({
                "product_external_id": candidate["product_external_id"],
                "legacy_model_token": candidate["model_token"],
                "legacy_pack_variant_key": candidate["pack_variant_key"],
                "reason": live_hold_reason,
            })
            continue
        match = match_model_core(candidate["model_token"], core_index)
        if match is None:
            holds.append({
                "product_external_id": candidate["product_external_id"],
                "legacy_model_token": candidate["model_token"],
                "legacy_pack_variant_key": candidate["pack_variant_key"],
                "reason": "no_exact_model_core_in_pinned_official_tables",
            })
            continue
        table, match_kind = match
        if table["family"] != candidate["family"]:
            raise ValueError(f"family mismatch for {candidate['product_external_id']}")
        matched_cores.add(table["normalized_model_core"])
        evidence.append({
            "product_external_id": candidate["product_external_id"],
            "legacy_model_token": candidate["model_token"],
            "legacy_pack_variant_key": candidate["pack_variant_key"],
            "model_core": table["model_core"],
            "match_kind": match_kind,
            "manufacturer": "Panasonic",
            "identity_scope": "model_core",
            "evidence_scope": "model_core",
            "technology": table["technology"],
            "voltage_v": table["voltage_v"],
            "capacity_mah": table["capacity_mah"],
            "diameter_mm": table["diameter_mm"],
            "width_mm": table["width_mm"],
            "height_mm": table["height_mm"],
            "temperature_min_c": table["temperature_min_c"],
            "temperature_max_c": table["temperature_max_c"],
            "source_url": table["source_url"],
            "source_snapshot_path": table["source_snapshot_path"],
            "source_snapshot_sha256": table["source_snapshot_sha256"],
            "source_page": table["source_page"],
            "source_kind": "official_manufacturer_catalogue",
            "source_publisher": "Panasonic Energy Co., Ltd.",
            "manufacturer_primary": "true",
            "price_or_stock_imported": "false",
            "safe_to_apply": "false",
        })

    if len(evidence) + len(holds) != len(candidates):
        raise ValueError("evidence and holds do not completely partition candidates")
    write_csv(evidence_path, EVIDENCE_FIELDS, evidence)
    write_csv(holds_path, HOLD_FIELDS, holds)
    summary = {
        "wave": "wave200",
        "candidate_path": str(candidates_path),
        "candidate_sha256": sha(candidates_path),
        "candidate_records": len(candidates),
        "pdf_sources": [
            {"path": str(coin_pdf), "source_url": PDF_SPECS[COIN_FILENAME]["source_url"], "sha256": sha(coin_pdf)},
            {"path": str(cylindrical_pdf), "source_url": PDF_SPECS[CYLINDRICAL_FILENAME]["source_url"], "sha256": sha(cylindrical_pdf)},
        ],
        "pinned_table_core_records": len(table_rows),
        "matched_model_core_records": len(matched_cores),
        "evidence_records": len(evidence),
        "hold_records": len(holds),
        "live_identity_hold_records": sum(row["reason"].startswith("live_catalogue_") for row in holds),
        "unmatched_model_core_hold_records": sum(
            row["reason"] == "no_exact_model_core_in_pinned_official_tables" for row in holds
        ),
        "partition_records": len(evidence) + len(holds),
        "evidence_path": str(evidence_path),
        "evidence_sha256": sha(evidence_path),
        "holds_path": str(holds_path),
        "holds_sha256": sha(holds_path),
        "price_or_stock_records": 0,
        "image_records": 0,
        "indexability_authorizations": 0,
        "automatic_database_mutations": 0,
        "safe_to_apply_records": 0,
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--coin-pdf", type=Path, required=True)
    parser.add_argument("--cylindrical-pdf", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--holds", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--expected-candidate-sha256", required=True)
    args = parser.parse_args()
    print(json.dumps(build(
        args.candidates, args.coin_pdf, args.cylindrical_pdf, args.evidence,
        args.holds, args.summary, args.expected_candidate_sha256,
    ), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
