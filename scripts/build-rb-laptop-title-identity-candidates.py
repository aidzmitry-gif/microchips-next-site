#!/usr/bin/env python3
"""Build a fail-closed identity-candidate registry from laptop battery titles.

Only facts literally present in a title are extracted.  The output is research
evidence: it never changes canonical identity, product attributes, publication,
SEO state, prices, media or duplicate decisions.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path


REQUIRED_COLUMNS = {
    "product_external_id",
    "name",
    "category_external_id",
    "readiness_class",
    "is_published",
}

BRAND_ALIASES: dict[str, tuple[str, ...]] = {
    "Lenovo": ("Lenovo", "ThinkPad",),
    "HP": ("Hewlett-Packard", "HP", "Compaq",),
    "ASUS": ("ASUS",),
    "Dell": ("Dell", "Alienware",),
    "Acer": ("Acer", "Packard Bell",),
    "Toshiba": ("Toshiba",),
    "Apple": ("Apple", "MacBook",),
    "MSI": ("MSI",),
    "Samsung": ("Samsung",),
    "Sony": ("Sony", "VAIO",),
    "Fujitsu": ("Fujitsu",),
    "Xiaomi": ("Xiaomi",),
    "LG": ("LG",),
    "Microsoft": ("Microsoft", "Surface",),
}

TITLE_PREFIX = re.compile(
    r"^\s*Аккумулятор(?:\s+\(батарея\))?\s+(.+?)\s+для\s+ноутбука\b",
    re.I,
)
PART_TOKEN = re.compile(
    r"(?<![A-Za-zА-Яа-яЁё0-9])([A-Z0-9][A-Z0-9._/+:-]{2,23})(?![A-Za-zА-Яа-яЁё0-9])",
    re.I,
)
VOLTAGE = re.compile(
    r"(?<!\d)(\d+(?:[.,]\d+)?)\s*(?:V|В|B)(?![A-Za-zА-Яа-яЁё])",
    re.I,
)
CAPACITY = re.compile(
    r"(?<!\d)(\d+(?:[.,]\d+)?)\s*(?:mAh|мА(?:·)?ч)(?![A-Za-zА-Яа-яЁё])",
    re.I,
)
ENERGY = re.compile(
    r"(?<!\d)(\d+(?:[.,]\d+)?)\s*(?:Wh|Whr|Втч|Vтч)(?![A-Za-zА-Яа-яЁё])",
    re.I,
)
PART_STOPWORDS = {
    "АККУМУЛЯТОР", "БАТАРЕЯ", "ДЛЯ", "НОУТБУКА", "OEM", "ORIGINAL",
}


def compact(value: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value or "")).strip()


def unique(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = value.replace(",", ".")
        key = normalized.casefold()
        if key not in seen:
            seen.add(key)
            result.append(normalized)
    return result


def normalize_part(value: str) -> str:
    return re.sub(r"[^A-Z0-9+]", "", unicodedata.normalize("NFKC", value).upper())


def extract_part_numbers(name: str) -> list[str]:
    match = TITLE_PREFIX.search(compact(name))
    if match is None:
        return []
    prefix = match.group(1).upper()
    candidates: list[str] = []
    for token in PART_TOKEN.findall(prefix):
        token = token.strip(".,;:")
        normalized = normalize_part(token)
        if normalized in PART_STOPWORDS or len(normalized) < 3:
            continue
        if not any(character.isdigit() for character in normalized):
            continue
        candidates.append(token)
    return unique(candidates)


def detect_brand(name: str) -> str:
    value = compact(name)
    matches: list[tuple[int, str]] = []
    for canonical, aliases in BRAND_ALIASES.items():
        for alias in aliases:
            if re.search(rf"(?<![\w]){re.escape(alias)}(?![\w])", value, re.I):
                matches.append((len(alias), canonical))
    if not matches:
        return ""
    matches.sort(reverse=True)
    return matches[0][1]


def extract_quality_marker(name: str) -> str:
    value = compact(name).casefold()
    if "low cost oem" in value:
        return "low_cost_oem"
    if "оригинал" in value:
        return "original"
    if re.search(r"(?<![\w])oem(?![\w])", value, re.I):
        return "oem"
    return "unspecified"


def extract_title_facts(name: str) -> dict[str, str]:
    value = compact(name)
    return {
        "voltage_v_candidates": "|".join(unique(VOLTAGE.findall(value))),
        "capacity_mah_candidates": "|".join(unique(CAPACITY.findall(value))),
        "energy_wh_candidates": "|".join(unique(ENERGY.findall(value))),
        "quality_marker": extract_quality_marker(value),
    }


def canonical_row_hash(row: dict[str, str]) -> str:
    payload = json.dumps(
        {
            "product_external_id": row["product_external_id"],
            "name": compact(row["name"]),
            "category_external_id": row["category_external_id"],
            "readiness_class": row["readiness_class"],
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_rows(path: Path) -> tuple[list[dict[str, str]], str]:
    source_bytes = path.read_bytes()
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"missing required columns: {', '.join(sorted(missing))}")
        rows = list(reader)
    external_ids = [row["product_external_id"].strip() for row in rows]
    if any(not value for value in external_ids):
        raise ValueError("blank product_external_id")
    if len(external_ids) != len(set(external_ids)):
        raise ValueError("duplicate product_external_id in readiness registry")
    return rows, hashlib.sha256(source_bytes).hexdigest()


def build(
    source: Path,
    output: Path,
    summary_output: Path,
    expected_input_records: int,
    expected_selected_records: int,
    category: str = "seo:replacement-laptops",
    readiness_class: str = "thin_unidentified",
) -> dict[str, object]:
    rows, source_sha256 = load_rows(source)
    if len(rows) != expected_input_records:
        raise ValueError(
            f"input record count mismatch: expected {expected_input_records}, got {len(rows)}"
        )

    selected = [
        row for row in rows
        if row["category_external_id"] == category
        and row["readiness_class"] == readiness_class
        and row["is_published"].strip().casefold() == "true"
    ]
    if len(selected) != expected_selected_records:
        raise ValueError(
            "selected record count mismatch: "
            f"expected {expected_selected_records}, got {len(selected)}"
        )

    candidates: list[dict[str, str]] = []
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in selected:
        parts = extract_part_numbers(row["name"])
        facts = extract_title_facts(row["name"])
        candidate = {
            "product_external_id": row["product_external_id"],
            "name": compact(row["name"]),
            "category_external_id": row["category_external_id"],
            "brand_candidate": detect_brand(row["name"]),
            "part_number_candidates": "|".join(parts),
            "primary_part_number_key": normalize_part(parts[0]) if parts else "",
            **facts,
            "candidate_scope": "title_only_unverified",
            "review_status": "needs_primary_source",
            "safe_to_apply": "false",
            "source_row_sha256": canonical_row_hash(row),
        }
        candidates.append(candidate)
        if candidate["primary_part_number_key"]:
            groups[candidate["primary_part_number_key"]].append(candidate)

    conflict_groups: set[str] = set()
    repeated_groups = {key: values for key, values in groups.items() if len(values) > 1}
    for key, values in repeated_groups.items():
        signatures = {
            (
                value["voltage_v_candidates"],
                value["capacity_mah_candidates"],
                value["energy_wh_candidates"],
                value["quality_marker"],
            )
            for value in values
        }
        if len(signatures) > 1:
            conflict_groups.add(key)

    for candidate in candidates:
        key = candidate["primary_part_number_key"]
        group_size = len(groups.get(key, [])) if key else 0
        candidate["primary_part_number_group_size"] = str(group_size)
        if not key:
            candidate["identity_risk"] = "missing_part_number"
        elif key in conflict_groups:
            candidate["identity_risk"] = "variant_or_fact_conflict_hold"
        elif group_size > 1:
            candidate["identity_risk"] = "repeated_part_number_needs_exact_source"
        elif "|" in candidate["part_number_candidates"]:
            candidate["identity_risk"] = "multiple_part_numbers_needs_exact_source"
        else:
            candidate["identity_risk"] = "single_candidate_needs_primary_source"

    candidates.sort(key=lambda item: (item["primary_part_number_key"], item["product_external_id"]))
    output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(candidates[0]) if candidates else []
    with output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(candidates)

    brand_counts = Counter(item["brand_candidate"] or "unmatched" for item in candidates)
    risk_counts = Counter(item["identity_risk"] for item in candidates)
    summary: dict[str, object] = {
        "source_path": str(source),
        "source_sha256": source_sha256,
        "input_records": len(rows),
        "selected_records": len(candidates),
        "category_external_id": category,
        "readiness_class": readiness_class,
        "records_with_part_number_candidate": sum(bool(item["primary_part_number_key"]) for item in candidates),
        "records_without_part_number_candidate": sum(not item["primary_part_number_key"] for item in candidates),
        "distinct_primary_part_number_groups": len(groups),
        "repeated_primary_part_number_groups": len(repeated_groups),
        "records_in_repeated_groups": sum(len(values) for values in repeated_groups.values()),
        "variant_or_fact_conflict_groups": len(conflict_groups),
        "records_with_voltage_candidate": sum(bool(item["voltage_v_candidates"]) for item in candidates),
        "records_with_capacity_candidate": sum(bool(item["capacity_mah_candidates"]) for item in candidates),
        "records_with_energy_candidate": sum(bool(item["energy_wh_candidates"]) for item in candidates),
        "brand_candidate_counts": dict(sorted(brand_counts.items())),
        "identity_risk_counts": dict(sorted(risk_counts.items())),
        "automatic_database_mutations": 0,
        "canonical_identity_changes": 0,
        "duplicate_merges": 0,
        "published_fact_changes": 0,
    }
    summary_output.parent.mkdir(parents=True, exist_ok=True)
    summary_output.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--expected-input-records", type=int, required=True)
    parser.add_argument("--expected-selected-records", type=int, required=True)
    parser.add_argument("--category", default="seo:replacement-laptops")
    parser.add_argument("--readiness-class", default="thin_unidentified")
    args = parser.parse_args()
    summary = build(
        args.input,
        args.output,
        args.summary,
        args.expected_input_records,
        args.expected_selected_records,
        args.category,
        args.readiness_class,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
