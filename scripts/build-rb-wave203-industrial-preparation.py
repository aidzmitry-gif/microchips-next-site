#!/usr/bin/env python3
"""Partition Wave201's untouched industrial tail and select Wave203.

This is intentionally a preparation-only step.  It neither researches the
web nor changes catalogue records.  The source of truth is the 500-row
Wave174 priority queue; every row already selected by Wave201 is excluded by
external id before the remaining records are classified.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path


REQUIRED_QUEUE = {
    "product_external_id",
    "name",
    "category_external_id",
    "safe_to_apply",
}
REQUIRED_PRIOR = {"product_external_id"}

MOBILE_BRANDS = (
    "Metrologic", "Bitel", "Ingenico", "VeriFone", "Casio", "Newpos",
    "CipherLab", "Psion", "Ascom", "Bluebird", "Castles", "Cino",
    "Unitech", "Denso", "FirstData", "Handheld", "Hypercom", "Koamtac",
    "LXE", "M3 Mobile", "NCR", "Newland", "Opticon", "Pax",
    "Point Mobile", "Proxibus", "Falcon", "Radiotec", "ICOM", "Sunmi",
    "TEKLOGIX", "Urovo", "Vocollect", "Dejavoo", "Proton", "Bearcat",
    "Sagem", "Panasonic", "Keyence", "Leica",
)
REMOTE_CONTROL_BRANDS = (
    "Itowa", "Autec", "ELCA", "HBC Radiomatic", "HIAB", "NBB",
    "Gross Funk", "Hetronic", "IKUSI", "Scanreco", "Schwing",
)


def read_rows(path: Path, required: set[str]) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{path}: missing columns: {', '.join(sorted(missing))}")
        return list(reader)


def read_processed_ids(path: Path) -> set[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    products = payload.get("products")
    if not isinstance(products, list):
        raise ValueError(f"{path}: products must be a list")
    ids = [row.get("external_id", "").strip() for row in products if isinstance(row, dict)]
    if len(ids) != len(products) or "" in ids or len(ids) != len(set(ids)):
        raise ValueError(f"{path}: processed external ids must be nonblank and unique")
    return set(ids)


def contains_brand(name: str, brands: tuple[str, ...]) -> str:
    for brand in brands:
        if re.search(rf"(?<![\w-]){re.escape(brand)}(?![\w-])", name, re.I):
            return brand
    return ""


def family_for(name: str) -> tuple[str, str, str, str]:
    if re.search(r"для\s+радиостанц", name, re.I):
        return (
            "radio_station_battery_packs",
            "radio communications",
            "model-family manufacturer documentation",
            "medium",
        )

    brand = contains_brand(name, REMOTE_CONTROL_BRANDS)
    if brand:
        return (
            "industrial_remote_control_batteries",
            brand,
            "industrial remote-control OEM documentation",
            "medium",
        )

    brand = contains_brand(name, MOBILE_BRANDS)
    if brand:
        return (
            "mobile_computers_pos_data_capture",
            brand,
            "OEM accessory and service documentation",
            "low",
        )

    if re.search(
        r"(?:FL-|ТНЖ|ВНЖ|НКГЦ|МГП|МГЦ|ЛИА|ВТ06К|Гарантия\s+14/24)",
        name,
        re.I,
    ):
        return (
            "legacy_industrial_traction_cells",
            "legacy industrial series",
            "manufacturer catalogue or normative technical documentation",
            "high",
        )

    raise ValueError(f"unclassified industrial candidate: {name}")


def model_tokens(name: str) -> str:
    tokens = re.findall(
        r"(?<![\w-])(?=[A-ZА-ЯЁ0-9-]*\d)[A-ZА-ЯЁ0-9][A-ZА-ЯЁ0-9_./-]{2,}(?![\w-])",
        name,
        re.I,
    )
    noise = {"MAH", "NIMH", "NICD", "LITHIUM", "LI-ION", "LI-POL"}
    unique: list[str] = []
    for token in tokens:
        token = token.strip(".,/()")
        if token.upper() in noise or re.fullmatch(r"\d+(?:[.,]\d+)?V", token, re.I):
            continue
        if token and token.casefold() not in {value.casefold() for value in unique}:
            unique.append(token)
    return "|".join(unique)


def build(
    queue_path: Path,
    wave201_path: Path,
    prior_processed_path: Path,
    output_path: Path,
    summary_path: Path,
    expected_queue_records: int = 500,
    expected_prior_records: int = 249,
) -> dict[str, object]:
    queue = read_rows(queue_path, REQUIRED_QUEUE)
    prior = read_rows(wave201_path, REQUIRED_PRIOR)
    processed_ids = read_processed_ids(prior_processed_path)
    if len(queue) != expected_queue_records:
        raise ValueError("priority queue record count mismatch")
    if len(prior) != expected_prior_records:
        raise ValueError("Wave201 selected record count mismatch")
    queue_ids = [row["product_external_id"].strip() for row in queue]
    prior_ids = [row["product_external_id"].strip() for row in prior]
    if "" in queue_ids or len(queue_ids) != len(set(queue_ids)):
        raise ValueError("priority queue external ids must be nonblank and unique")
    if "" in prior_ids or len(prior_ids) != len(set(prior_ids)):
        raise ValueError("Wave201 external ids must be nonblank and unique")
    if not set(prior_ids) <= set(queue_ids):
        raise ValueError("Wave201 contains ids outside the priority queue")
    if any(
        row["category_external_id"] != "seo:batteries-industrial"
        or row["safe_to_apply"].strip().casefold() != "false"
        for row in queue
    ):
        raise ValueError("priority queue must remain industrial and safe_to_apply=false")

    prior_set = set(prior_ids)
    untouched = [row for row in queue if row["product_external_id"] not in prior_set]
    output: list[dict[str, str]] = []
    for row in untouched:
        family, brand, source_route, cost = family_for(row["name"])
        repeat_handling = (
            "previously_processed" if row["product_external_id"] in processed_ids else "new"
        )
        output.append(
            {
                "recommended_wave": "wave203"
                if family == "mobile_computers_pos_data_capture"
                and repeat_handling == "new"
                else "backlog",
                "repeat_handling": repeat_handling,
                "family": family,
                "brand_or_series": brand,
                "product_external_id": row["product_external_id"],
                "name": row["name"],
                "model_tokens_unverified": model_tokens(row["name"]),
                "source_route": source_route,
                "research_cost_class": cost,
                "required_gate": (
                    "exact product identity and exact compatible battery variant; "
                    "OEM device compatibility alone must not identify an aftermarket pack"
                ),
                "safe_to_apply": "false",
            }
        )

    family_counts = Counter(row["family"] for row in output)
    recommended = [row for row in output if row["recommended_wave"] == "wave203"]
    if not 100 <= len(recommended) <= 250:
        raise ValueError("recommended Wave203 batch must contain 100-250 records")
    if any(row["product_external_id"] in prior_set for row in output):
        raise ValueError("prior-wave id leaked into Wave203 preparation")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(output[0])
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(output)

    recommended_brand_counts = Counter(row["brand_or_series"] for row in recommended)
    summary: dict[str, object] = {
        "queue_path": str(queue_path),
        "queue_sha256": hashlib.sha256(queue_path.read_bytes()).hexdigest(),
        "wave201_path": str(wave201_path),
        "wave201_sha256": hashlib.sha256(wave201_path.read_bytes()).hexdigest(),
        "prior_processed_path": str(prior_processed_path),
        "prior_processed_sha256": hashlib.sha256(
            prior_processed_path.read_bytes()
        ).hexdigest(),
        "queue_records": len(queue),
        "previously_selected_records": len(prior),
        "untouched_records": len(untouched),
        "family_counts": dict(sorted(family_counts.items())),
        "recommended_batch": "mobile_computers_pos_data_capture",
        "recommended_batch_records": len(recommended),
        "recommended_batch_brand_counts": dict(sorted(recommended_brand_counts.items())),
        "recommended_product_external_ids": [
            row["product_external_id"] for row in recommended
        ],
        "previously_processed_records": sum(
            row["repeat_handling"] == "previously_processed" for row in output
        ),
        "previously_processed_product_external_ids": sorted(
            row["product_external_id"]
            for row in output
            if row["repeat_handling"] == "previously_processed"
        ),
        "recommended_prior_id_overlap_records": sum(
            row["product_external_id"] in processed_ids for row in recommended
        ),
        "wave201_id_overlap_records": 0,
        "automatic_database_mutations": 0,
        "safe_to_apply_records": 0,
    }
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--wave201", type=Path, required=True)
    parser.add_argument("--prior-processed", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--expected-queue-records", type=int, default=500)
    parser.add_argument("--expected-prior-records", type=int, default=249)
    args = parser.parse_args()
    summary = build(
        args.queue,
        args.wave201,
        args.prior_processed,
        args.output,
        args.summary,
        args.expected_queue_records,
        args.expected_prior_records,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
