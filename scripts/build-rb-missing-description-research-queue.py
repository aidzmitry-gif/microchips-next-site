#!/usr/bin/env python3
"""Build a fail-closed research queue for RB cards with no usable text.

The output is planning evidence only. Brand/model tokens extracted from a
legacy title are candidates, never published facts.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path


MISSING_CLASSES = {"legacy_preview_only", "thin_unidentified"}
DEVICE_OEM_BRANDS = (
    "Datalogic", "Zebra", "Symbol", "Psion", "Garmin", "Panasonic",
    "Lenovo", "Asus", "Dell", "HP", "Samsung", "LG", "Sony", "MSI",
    "Logitech", "Dreame", "Huawei", "Xiaomi", "Meizu", "Nokia",
    "TP-LINK", "ZTE", "OnePlus", "Itel", "Apple", "Canon", "Nikon",
    "Pentax", "JVC", "MIO", "B.Braun", "Nintendo", "Amazon", "Prestigio",
    "Inova", "Velocitek", "Proline", "Stealth", "Subini", "Present",
    "Eplutos", "Explay", "Ritmix", "Highscreen", "Bluboo", "Elephone",
)
REPLACEMENT_BRANDS = (
    "Atlas Battery", "Robiton", "Energizer", "CameronSino", "Cameron Sino",
    "Delta", "Fiamm", "Ventura", "Saft", "Fanso", "Tekcell", "PKCELL",
    "Varta", "Maxell", "Omron", "Starnovo", "Энергия", "EURO", "W.E.P",
)
BRANDS = REPLACEMENT_BRANDS + DEVICE_OEM_BRANDS
MODEL_TOKEN = re.compile(r"(?<![\w])(?=[\w./-]{3,}\b)(?=[\w./-]*\d)[A-Za-zА-Яа-яЁё0-9][A-Za-zА-Яа-яЁё0-9./-]*")
UNIT_ONLY = re.compile(r"^\d+(?:[.,]\d+)?(?:mah|ah|wh|v|a|w|в|вт|ач|мач)$", re.I)


def bool_value(value: str) -> bool:
    return value.strip().lower() == "true"


def brand_candidate(row: dict[str, str]) -> str:
    explicit = row.get("manufacturer", "").strip()
    if explicit:
        return explicit
    name = row.get("name", "")
    for brand in BRANDS:
        if re.search(rf"(?<![\w]){re.escape(brand)}(?![\w])", name, re.I):
            return brand
    return ""


def model_candidates(name: str) -> list[str]:
    result: list[str] = []
    for token in MODEL_TOKEN.findall(name):
        normalized = token.strip(".,;:()[]{}")
        if not normalized or UNIT_ONLY.fullmatch(normalized):
            continue
        if normalized.lower() not in {item.lower() for item in result}:
            result.append(normalized)
    return result[:12]


def source_route(row: dict[str, str], brand: str) -> str:
    name = row.get("name", "")
    if any(re.search(rf"(?<![\w]){re.escape(candidate)}(?![\w])", name, re.I) for candidate in REPLACEMENT_BRANDS):
        return "replacement_brand_exact_model_catalog"
    if any(re.search(rf"(?<![\w]){re.escape(candidate)}(?![\w])", name, re.I) for candidate in DEVICE_OEM_BRANDS):
        return "device_oem_parts_or_service_document"
    if brand:
        return "manufacturer_exact_model_page_or_datasheet"
    return "exact_model_search_then_authorized_distributor_hold"


def priority(row: dict[str, str], brand: str, models: list[str]) -> int:
    score = 0
    if row.get("readiness_class") == "thin_unidentified":
        score += 40
    if not bool_value(row.get("has_displayable_preview_image", "")):
        score += 20
    if brand:
        score += 15
    if models:
        score += 15
    if row.get("category_external_id") == "seo:batteries-industrial":
        score += 10
    return score


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--expected-records", type=int, required=True)
    parser.add_argument("--expected-missing", type=int, required=True)
    parser.add_argument("--expected-sha256", required=True)
    args = parser.parse_args()

    raw = args.input.read_bytes()
    actual_hash = hashlib.sha256(raw).hexdigest()
    if actual_hash != args.expected_sha256.lower():
        raise SystemExit("input SHA-256 does not match the pinned value")
    rows = list(csv.DictReader(raw.decode("utf-8-sig").splitlines()))
    if len(rows) != args.expected_records:
        raise SystemExit(f"expected {args.expected_records} input rows, got {len(rows)}")

    selected = [row for row in rows if row.get("readiness_class") in MISSING_CLASSES]
    if len(selected) != args.expected_missing:
        raise SystemExit(f"expected {args.expected_missing} missing-text rows, got {len(selected)}")
    if len({row.get('product_external_id') for row in selected}) != len(selected):
        raise SystemExit("missing-text rows repeat product_external_id")

    output_rows = []
    for row in selected:
        brand = brand_candidate(row)
        models = model_candidates(row.get("name", ""))
        route = source_route(row, brand)
        has_image = bool_value(row.get("has_displayable_preview_image", ""))
        output_rows.append({
            "priority_score": priority(row, brand, models),
            "product_external_id": row.get("product_external_id", ""),
            "name": row.get("name", ""),
            "category_external_id": row.get("category_external_id", ""),
            "readiness_class": row.get("readiness_class", ""),
            "brand_candidate_unverified": brand,
            "model_candidates_unverified": "|".join(models),
            "has_company_owned_preview_image": str(has_image).lower(),
            "source_route": route,
            "required_evidence": "exact_product_identity|technical_datasheet|compatibility_scope|image_rights",
            "safe_to_apply": "false",
        })
    output_rows.sort(key=lambda row: (-int(row["priority_score"]), row["product_external_id"]))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(output_rows[0]))
        writer.writeheader()
        writer.writerows(output_rows)

    summary = {
        "source_path": str(args.input),
        "source_sha256": actual_hash,
        "source_records": len(rows),
        "research_records": len(output_rows),
        "readiness_class_counts": dict(sorted(Counter(row["readiness_class"] for row in output_rows).items())),
        "category_counts": dict(sorted(Counter(row["category_external_id"] for row in output_rows).items())),
        "source_route_counts": dict(sorted(Counter(row["source_route"] for row in output_rows).items())),
        "brand_candidates_present": sum(bool(row["brand_candidate_unverified"]) for row in output_rows),
        "model_candidates_present": sum(bool(row["model_candidates_unverified"]) for row in output_rows),
        "company_owned_preview_images_present": sum(row["has_company_owned_preview_image"] == "true" for row in output_rows),
        "automatic_database_mutations": 0,
        "safe_to_apply_records": 0,
    }
    args.summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
