#!/usr/bin/env python3
"""Build a deterministic no-repeat B2B source-enrichment batch.

The script plans research only. It never marks catalogue records safe to publish
and never mutates the application database.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


AUTOMOTIVE = re.compile(
    r"автомоб|авто[- ]?аккум|стартерн|мотоцикл|легков(?:ой|ых)|грузов(?:ой|ых)",
    re.IGNORECASE,
)
ELECTRONICS = re.compile(
    r"микросхем|транзистор|резистор|конденсатор|диод|тиристор|симистор|"
    r"микроконтроллер|полупроводник",
    re.IGNORECASE,
)

# Ordered: specific spellings must win over shorter aliases.
BRANDS: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (name, re.compile(pattern, re.IGNORECASE))
    for name, pattern in (
        ("Sonnenschein", r"\bSonnenschein\b"),
        ("Alarm Force", r"\bAlarm\s+Force\b"),
        ("General Security", r"\bGeneral\s+Security\b"),
        ("B.B. Battery", r"\bB\.?\s*B\.?\s+Battery\b|\bB\.B\.\b"),
        ("Panasonic", r"\bPanasonic\b"),
        ("Motorola", r"\bMotorola\b"),
        ("Symbol", r"\bSymbol\b"),
        ("Kenwood", r"\bKenwood\b"),
        ("EnerSys", r"\bEnerSys\b"),
        ("Ventura", r"\bVentura\b"),
        ("Leoch", r"\bLeoch\b"),
        ("Fiamm", r"\bFiamm\b"),
        ("Delta", r"\bDelta\b"),
        ("Yuasa", r"\bYuasa\b"),
        ("CSB", r"\bCSB\b"),
        ("APC", r"\bAPC\b"),
        ("MNB", r"\bMNB\b"),
        ("WBR", r"\bWBR\b"),
        ("Casil", r"\bCasil\b"),
        ("Security Force", r"\bSecurity\s+Force\b"),
        ("Sprinter", r"\bSprinter\b"),
        ("Robiton", r"\bRobiton\b"),
        ("Minamoto", r"\bMinamoto\b"),
        ("Baofeng", r"\bBaofeng\b"),
        ("Yaesu", r"\bYaesu\b"),
        ("AT radio packs", r"для\s+радиостанций\s+AT\b"),
        ("cash-register packs", r"для\s+кассов(?:ых|ого)\b"),
        ("Icom", r"\bIcom\b"),
        ("Vertex", r"\bVertex\b"),
        ("Vector", r"\bVector\b"),
        ("Optimus", r"\bOptimus\b"),
        ("Contact", r"\bContact\b"),
        ("Восток", r"\bВосток\b"),
    )
)

OFFICIAL_ROUTES = {
    "APC": ("apc_schneider_product_pages", "high"),
    "B.B. Battery": ("bb_battery_series_datasheets", "high"),
    "CSB": ("csb_battery_series_pages", "high"),
    "Casil": ("casil_series_datasheets", "medium"),
    "Delta": ("delta_battery_series_catalogues", "high"),
    "EnerSys": ("enersys_product_catalogues", "high"),
    "Fiamm": ("fiamm_energy_technology_datasheets", "high"),
    "Leoch": ("leoch_series_datasheets", "high"),
    "MNB": ("mnb_series_datasheets", "medium"),
    "Panasonic": ("panasonic_archived_datasheets", "medium"),
    "Sonnenschein": ("exide_sonnenschein_series_catalogues", "high"),
    "Sprinter": ("enersys_sprinter_catalogues", "high"),
    "Ventura": ("ventura_series_catalogues", "medium"),
    "WBR": ("wbr_series_datasheets", "medium"),
    "Yuasa": ("yuasa_series_datasheets", "high"),
    "Motorola": ("motorola_zebra_accessory_guides", "medium"),
    "Symbol": ("zebra_symbol_archived_accessory_guides", "medium"),
    "Kenwood": ("kenwood_accessory_guides", "medium"),
    "Icom": ("icom_accessory_guides", "medium"),
    "Vertex": ("vertex_standard_horizon_accessory_guides", "medium"),
    "Yaesu": ("yaesu_accessory_guides", "medium"),
    "Baofeng": ("baofeng_accessory_pages_compatibility_only", "medium"),
    "AT radio packs": ("at_supplier_catalogue_identity_first", "low"),
    "cash-register packs": ("assembly_configuration_source_required", "low"),
    "Minamoto": ("minamoto_series_datasheets", "medium"),
    "Robiton": ("robiton_product_pages", "medium"),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path: Path) -> list[dict[str, str]]:
    return list(csv.DictReader(path.read_text(encoding="utf-8-sig").splitlines()))


def load_priority_module(path: Path):
    spec = importlib.util.spec_from_file_location("rb_priority", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load priority module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def manufacturer(name: str) -> str:
    for canonical, pattern in BRANDS:
        if pattern.search(name):
            return canonical
    if re.search(r"\b(?:\d+)?(?:НК|КН|KL|KPL|KM|FL|KH|KPH|KGL)[А-ЯA-Z0-9-]*\b", name, re.I):
        return "unresolved_industrial_cell"
    if re.search(r"\bдля\b", name, re.I):
        return "unresolved_replacement"
    return "unresolved_other"


def family(name: str, brand: str) -> str:
    upper = name.upper().replace(",", ".")
    rules = {
        "APC": r"\bRBC\d+[A-Z-]*\b",
        "Delta": r"\b(?:DTM|HRL|HR|GX|GSC|CT|FT|DF|X-PERT|EPS)\s*[-]?[A-Z0-9.]+",
        "Fiamm": r"\b(?:FGH|FGL|FG|FIT|FLB|SLA|12FGL|12FGH)[A-Z0-9/-]*",
        "Sonnenschein": r"\b(?:DRYFIT\s+)?(?:SOLAR|A\d{3}|GF|GEL|SPORTLINE|PREVAILER)\b",
        "EnerSys": r"\b(?:POWERSAFE|DATASAFE|CYCLON|ODYSSEY|GENESIS|HAWKER)\b",
        "Sprinter": r"\bSPRINTER\b",
        "CSB": r"\b(?:GP|HRL|HR|TPL|EVX|XTV|UPS)\s*[-]?[A-Z0-9.]+",
        "Yuasa": r"\b(?:NP|NPL|SWL|RE|UXL|YPC|REC)\s*[-]?[A-Z0-9.]+",
        "Leoch": r"\b(?:DJM|DJW|LP|LHR|XP|PLH|FT|LPL)\s*[-]?[A-Z0-9.]+",
        "Panasonic": r"\b(?:LC|UP|HHR|CGR|NCR)[A-Z0-9-]+",
        "Motorola": r"\b(?:BTRY|PMNN|HNN|NNTN|RLN|JMNN|IXNN)[A-Z0-9-]+",
        "Kenwood": r"\b(?:KNB|KSC)[A-Z0-9-]+",
        "Icom": r"\b(?:BP|BC)[A-Z0-9-]+",
        "Vertex": r"\b(?:FNB|VAC)[A-Z0-9-]+",
        "Ventura": r"\b(?:GPL|GP|HRL|HR|FT|VG)(?=\s|-)\s*[-]?[A-Z0-9.]+",
        "MNB": r"\b(?:MS|MM|MNG|MR)\s*[-]?[A-Z0-9.]+",
        "Casil": r"\bCA(?=\s|-)\s*[-]?[A-Z0-9.]+",
        "B.B. Battery": r"\b(?:HRL|HR|BC|BPS)\s*[-]?[A-Z0-9.]+",
        "Robiton": r"\bVRLA[A-Z0-9.-]+",
        "Minamoto": r"\bMB[A-Z0-9.-]+",
        "Vector": r"\bBP-[A-Z0-9]+",
        "Baofeng": r"\b(?:BL|BF|UV|DM)-[A-Z0-9]+",
        "Yaesu": r"\bFNB-[A-Z0-9]+",
    }
    match = re.search(rules.get(brand, r"$^"), upper)
    if match:
        token = re.sub(r"\s+", "-", match.group(0))
        # Group individual model numbers into the source series where possible.
        return re.sub(r"(?<=[A-Z])[-]?\d.*$", "-series", token).lower()
    if brand == "unresolved_industrial_cell":
        match = re.search(r"\b(?:\d+)?(НК|КН|KL|KPL|KM|FL|KH|KPH|KGL)", upper, re.I)
        return f"industrial-cell-{match.group(1).lower()}" if match else "industrial-cell-other"
    if brand == "unresolved_replacement":
        return "device-replacement-unresolved"
    if brand == "AT radio packs":
        return "at-radio-pack-series"
    if brand == "cash-register packs":
        return "cash-register-pack-configurations"
    return "other-or-unresolved-series"


def cluster_role(brand: str) -> str:
    if brand in {"Motorola", "Symbol", "Kenwood", "Icom", "Vertex", "Yaesu", "Baofeng"}:
        return "device_oem_or_compatibility_family"
    if brand in {"AT radio packs", "cash-register packs"}:
        return "supplier_or_pack_configuration_family"
    if brand.startswith("unresolved_"):
        return "unresolved_identity"
    return "claimed_product_manufacturer"


def risk(row: dict[str, str], brand: str) -> str:
    missing = sum(
        (
            row.get("identity_ready", "").lower() != "true",
            row.get("has_applied_description", "").lower() != "true",
            int(row.get("technical_fact_count") or 0) == 0,
            row.get("has_displayable_preview_image", "").lower() != "true",
        )
    )
    if brand.startswith("unresolved_") or missing >= 3:
        return "high"
    if missing == 2:
        return "medium"
    return "low"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--readiness", type=Path, required=True)
    parser.add_argument("--processed", type=Path, required=True)
    parser.add_argument("--holds", type=Path, required=True)
    parser.add_argument("--priority-script", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--expected-readiness-sha256", required=True)
    parser.add_argument("--expected-processed-sha256", required=True)
    parser.add_argument("--expected-holds-sha256", required=True)
    parser.add_argument("--expected-readiness-records", type=int, required=True)
    parser.add_argument("--expected-processed-records", type=int, required=True)
    parser.add_argument("--limit", type=int, default=500)
    args = parser.parse_args()

    pinned = (
        (args.readiness, args.expected_readiness_sha256),
        (args.processed, args.expected_processed_sha256),
        (args.holds, args.expected_holds_sha256),
    )
    for path, expected in pinned:
        if sha256(path) != expected.lower():
            raise SystemExit(f"SHA-256 mismatch: {path}")

    source = rows(args.readiness)
    processed_rows = rows(args.processed)
    hold_rows = rows(args.holds)
    if len(source) != args.expected_readiness_records:
        raise SystemExit("unexpected readiness record count")
    if len(processed_rows) != args.expected_processed_records:
        raise SystemExit("unexpected processed record count")
    processed_ids = {row["product_external_id"] for row in processed_rows}
    hold_ids = {row["product_external_id"] for row in hold_rows}
    if len(processed_ids) != len(processed_rows):
        raise SystemExit("processed input repeats product_external_id")

    priority = load_priority_module(args.priority_script)
    candidates = []
    exclusions = Counter()
    for row in source:
        if row.get("category_external_id") not in priority.B2B_CATEGORY_PRIORITY:
            continue
        if row.get("readiness_class") == "strict_content_ready":
            continue
        external_id = row.get("product_external_id", "")
        if external_id in processed_ids:
            exclusions["already_processed"] += 1
            continue
        if external_id in hold_ids:
            exclusions["known_hold"] += 1
            continue
        if AUTOMOTIVE.search(row.get("name", "")):
            exclusions["automotive"] += 1
            continue
        if ELECTRONICS.search(row.get("name", "")):
            exclusions["electronics"] += 1
            continue
        score, reasons = priority.score(row)
        candidates.append((score, reasons, row))
    candidates.sort(key=lambda item: (-item[0], item[2]["product_external_id"]))
    selected = candidates[: args.limit]

    output_rows = []
    for score, reasons, row in selected:
        brand = manufacturer(row["name"])
        source_route, source_likelihood = OFFICIAL_ROUTES.get(
            brand, ("manual_manufacturer_resolution_before_research", "low")
        )
        output_rows.append(
            {
                "priority_score": score,
                "product_external_id": row["product_external_id"],
                "name": row["name"],
                "category_external_id": row["category_external_id"],
                "manufacturer_cluster": brand,
                "family_cluster": family(row["name"], brand),
                "cluster_role": cluster_role(brand),
                "official_source_route": source_route,
                "official_source_likelihood": source_likelihood,
                "source_coverage_limit": (
                    "compatibility_only_identity_and_specs_need_separate_battery_source"
                    if cluster_role(brand) == "device_oem_or_compatibility_family"
                    else "manufacturer_identity_specs_and_media_candidate"
                ),
                "media_route": "official_product_page_or_datasheet_then_rights_review",
                "thin_content_risk": risk(row, brand),
                "priority_reasons": "|".join(reasons),
                "safe_to_apply": "false",
            }
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    fields = list(output_rows[0]) if output_rows else []
    with args.output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(output_rows)

    clusters: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in output_rows:
        clusters[(row["manufacturer_cluster"], row["family_cluster"])].append(row)
    partition = [
        {
            "manufacturer_cluster": brand,
            "family_cluster": family_name,
            "records": len(cluster_rows),
            "official_source_route": cluster_rows[0]["official_source_route"],
            "official_source_likelihood": cluster_rows[0]["official_source_likelihood"],
            "cluster_role": cluster_rows[0]["cluster_role"],
            "thin_content_risk_counts": dict(
                sorted(Counter(row["thin_content_risk"] for row in cluster_rows).items())
            ),
        }
        for (brand, family_name), cluster_rows in clusters.items()
    ]
    partition.sort(key=lambda row: (-row["records"], row["manufacturer_cluster"], row["family_cluster"]))
    summary = {
        "readiness_sha256": sha256(args.readiness),
        "processed_sha256": sha256(args.processed),
        "holds_sha256": sha256(args.holds),
        "output_sha256": sha256(args.output),
        "source_records": len(source),
        "processed_records_excluded": exclusions["already_processed"],
        "known_holds_excluded": exclusions["known_hold"],
        "automotive_excluded": exclusions["automotive"],
        "electronics_excluded": exclusions["electronics"],
        "eligible_remaining": len(candidates),
        "selected_records": len(output_rows),
        "category_counts": dict(sorted(Counter(row["category_external_id"] for row in output_rows).items())),
        "manufacturer_counts": dict(sorted(Counter(row["manufacturer_cluster"] for row in output_rows).items())),
        "thin_content_risk_counts": dict(sorted(Counter(row["thin_content_risk"] for row in output_rows).items())),
        "partition_proposal": partition,
        "automatic_database_mutations": 0,
        "safe_to_apply_records": 0,
    }
    args.summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
