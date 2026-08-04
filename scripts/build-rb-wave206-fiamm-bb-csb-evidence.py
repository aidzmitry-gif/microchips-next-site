#!/usr/bin/env python3
"""Build fail-closed Wave206 evidence for FIAMM, B.B. Battery and CSB rows."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "docs/audits/generated/rb-b2b-next-source-batch-wave205.csv"
CATALOG = ROOT / "docs/imports/site-catalog-full-products.csv"
COLLISIONS = ROOT / "docs/audits/evidence/wave206-fiamm-bb-csb-current-identity-collisions.json"
SOURCE_DIR = ROOT / "docs/audits/sources/wave206-fiamm-bb-csb"
OUTPUT = ROOT / "docs/audits/generated/rb-wave206-fiamm-bb-csb-evidence.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-wave206-fiamm-bb-csb-evidence.summary.json"

EXPECTED_BRANDS = {"Fiamm": 30, "B.B. Battery": 7, "CSB": 1}
FIELDS = [
    "product_external_id", "manufacturer_cluster", "name", "model_core",
    "partition", "source_tier", "source_url", "snapshot_path",
    "snapshot_sha256", "required_tokens", "verified_facts", "hold_reason",
    "replacement_manufacturer", "replacement_mpn", "safe_to_apply",
    "duplicate_review",
]

SOURCES = {
    "fiamm_fg": ("fiamm-fg-series-2026-07-29.html", "https://www.fiamm.ru/equipment/FG-series/", "official_distributor"),
    "fiamm_fit": ("fiamm-fit-2022.pdf", "https://www.fiamm.ru/data/Catalogue/2022/FIT_web.pdf", "official_distributor"),
    "fiamm_fgl": ("fiamm-fgl-series-2026-07-29.html", "https://www.fiamm.ru/equipment/FGL-series/", "official_distributor"),
    "fiamm_flb": ("fiamm-flb-series-2026-07-29.html", "https://www.fiamm.ru/equipment/FLB-series/", "official_distributor"),
    "fiamm_fgh": ("fiamm-fgh-series-2026-07-29.html", "https://www.fiamm.ru/equipment/FGH-series/", "official_distributor"),
    "fiamm_replacement": ("fiamm-replacement-table-2026-07-29.html", "https://www.fiamm.ru/services/faq/zaryadit-accumulyator.html", "official_distributor"),
    "bb_hr": ("bb-hr-series-2026-07-29.html", "https://www.bb-bat.com/en/HR.html", "manufacturer_primary"),
    "bb_bc": ("bb-bc-series-2026-07-29.html", "https://www.bb-bat.com/en/BC.html", "manufacturer_primary"),
    "bb_bps": ("bb-bps-series-2026-07-29.html", "https://www.bb-bat.com/en/BPS.html", "manufacturer_primary"),
    "bb_hrl": ("bb-hrl-series-2026-07-29.html", "https://www.bb-bat.com/en/HRL.html", "manufacturer_primary"),
    "csb_hrl": ("csb-hrl12390w-ra240531.pdf", "https://csb-battery.com/wp-content/uploads/2024/07/CSB-Datasheet-HRL12390W-%E2%80%93-053124.pdf", "manufacturer_primary"),
}


def d(partition: str, model: str, source: str | None, facts: str, hold: str = "", safe: bool = False, mpn: str = "", token: str = "") -> dict:
    return {"partition": partition, "model": model, "source": source, "facts": facts, "hold": hold, "safe": safe, "mpn": mpn, "token": token or model}


DECISIONS = {
    "bitrix:1405": d("exact", "FG10121", "fiamm_fg", "6 V; 1.2 Ah", "Distributor evidence cannot promote canonical manufacturer/MPN."),
    "bitrix:1406": d("exact", "FG20121", "fiamm_fg", "12 V; 1.2 Ah", "Distributor evidence cannot promote canonical manufacturer/MPN."),
    "bitrix:1407": d("exact", "FG20121A", "fiamm_fg", "12 V; 1.2 Ah", "Distributor evidence cannot promote canonical manufacturer/MPN."),
    "bitrix:1418": d("compatibility", "HRL12390W FR", "csb_hrl", "HRL12390W; 12 V; VRLA AGM", "Official datasheet names HRL12390W, not the offered FR-suffixed construction.", token="HRL12390W"),
    "bitrix:1425": d("compatibility", "12FIT100/19", "fiamm_replacement", "archival model token; 12 V; 100 Ah", "Replacement-table evidence is model-core only and distributor attributed."),
    "bitrix:1426": d("exact", "12FIT100/23", "fiamm_fit", "12 V; 100 Ah C10", "Distributor evidence cannot promote canonical manufacturer/MPN."),
    "bitrix:1427": d("conflict", "12FLB400P", "fiamm_flb", "12 V; current table 109 Ah", "Legacy name says 100 Ah; current official-distributor table says 109 Ah."),
    "bitrix:1431": d("compatibility", "FG2A007", "fiamm_replacement", "archival model token", "Only an archival replacement-table row was located."),
    "bitrix:1444": d("conflict", "12FLB450P", "fiamm_flb", "12 V; current table 124 Ah", "Legacy name says 115 Ah; current official-distributor table says 124 Ah."),
    "bitrix:1462": d("conflict", "12FGL80", "fiamm_fgl", "12 V; 80 Ah", "Legacy name says 120 Ah; current series table says 80 Ah."),
    "bitrix:1463": d("no_evidence", "FG2C00", None, "", "No exact token was found in the pinned current series or replacement snapshots."),
    "bitrix:1483": d("exact", "12FGH50", "fiamm_fgh", "12 V; 12 Ah", "Distributor evidence cannot promote canonical manufacturer/MPN."),
    "bitrix:1484": d("compatibility", "12FGHL48", "fiamm_replacement", "archival model token; 12 Ah", "Model appears only in the replacement table, not the current FGH series snapshot."),
    "bitrix:1485": d("exact", "FG11201", "fiamm_fg", "6 V; 12 Ah", "Distributor evidence cannot promote canonical manufacturer/MPN."),
    "bitrix:1486": d("exact", "FG11202", "fiamm_fg", "6 V; 12 Ah", "Distributor evidence cannot promote canonical manufacturer/MPN."),
    "bitrix:1487": d("exact", "FG21201", "fiamm_fg", "12 V; 12 Ah", "Distributor evidence cannot promote canonical manufacturer/MPN."),
    "bitrix:1488": d("exact", "FG21202", "fiamm_fg", "12 V; 12 Ah", "Distributor evidence cannot promote canonical manufacturer/MPN."),
    "bitrix:1494": d("compatibility", "12FIT130", "fiamm_replacement", "archival model token; 12 V; 130 Ah", "Replacement-table evidence is model-core only and distributor attributed."),
    "bitrix:1495": d("exact", "12FGL120", "fiamm_fgl", "12 V; 120 Ah", "Distributor evidence cannot promote canonical manufacturer/MPN."),
    "bitrix:1508": d("exact", "12FIT150", "fiamm_fit", "12 V; 150 Ah C10", "Distributor evidence cannot promote canonical manufacturer/MPN."),
    "bitrix:1509": d("exact", "12FLB540P", "fiamm_flb", "12 V; 150 Ah", "Distributor evidence cannot promote canonical manufacturer/MPN."),
    "bitrix:1510": d("exact", "12FGL150", "fiamm_fgl", "12 V; 150 Ah", "Distributor evidence cannot promote canonical manufacturer/MPN."),
    "bitrix:1511": d("compatibility", "4SLA150", "fiamm_replacement", "archival model token; 4 V; 150 Ah", "Only an archival replacement-table row was located."),
    "bitrix:1512": d("compatibility", "FG2F009", "fiamm_replacement", "archival model token; 12 V; 150 Ah", "Only an archival replacement-table row was located."),
    "bitrix:1519": d("exact", "HR15-12", "bb_hr", "12 V; 60 W high-power series", "", True, "HR15-12"),
    "bitrix:1521": d("compatibility", "6SLA160", "fiamm_replacement", "archival model token; 6 V; 160 Ah", "Only an archival replacement-table row was located."),
    "bitrix:1524": d("exact", "12FGL70", "fiamm_fgl", "12 V; 70 Ah", "Distributor evidence cannot promote canonical manufacturer/MPN."),
    "bitrix:1526": d("exact", "BC17-12", "bb_bc", "12 V; 17 Ah deep-cycle series", "", True, "BC17-12"),
    "bitrix:1528": d("compatibility", "FG21703", "fiamm_replacement", "archival model token; 12 V; 17 Ah", "Model is absent from the pinned current FG series snapshot."),
    "bitrix:1533": d("compatibility", "6SLA180", "fiamm_replacement", "archival model token; 6 V; 180 Ah", "Current SLA snapshot names 6SLA180L, not the unsuffixed offered model."),
    "bitrix:1541": d("exact", "12FGH65", "fiamm_fgh", "12 V; 18 Ah", "Distributor evidence cannot promote canonical manufacturer/MPN."),
    "bitrix:1542": d("exact", "FG21803", "fiamm_fg", "12 V; 18 Ah", "Distributor evidence cannot promote canonical manufacturer/MPN."),
    "bitrix:1546": d("exact", "FG20201", "fiamm_fg", "12 V; 2 Ah", "Distributor evidence cannot promote canonical manufacturer/MPN."),
    "bitrix:1565": d("exact", "HR22-12", "bb_hr", "12 V; 88 W high-power series", "", True, "HR22-12"),
    "bitrix:1587": d("exact", "HR4-12", "bb_hr", "12 V; 16 W high-power series", "", True, "HR4-12"),
    "bitrix:1590": d("exact", "HR33-12", "bb_hr", "12 V; 132 W high-power series", "", True, "HR33-12"),
    "bitrix:1593": d("exact", "BPS40-12", "bb_bps", "12 V; 40 Ah general-purpose series", "", True, "BPS40-12"),
    "bitrix:1594": d("compatibility", "HRL40-12", "bb_hrl", "12 V; 160 W; S/H/F variants", "Official series has S, H and F constructions; bare legacy model does not select one."),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def normalized(value: str) -> str:
    return re.sub(r"[^0-9a-z]+", "", value.casefold())


def source_text(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        return "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)
    return path.read_text(encoding="utf-8", errors="replace")


def main() -> None:
    all_rows = read_csv(INPUT)
    rows = [row for row in all_rows if row["manufacturer_cluster"] in EXPECTED_BRANDS]
    counts = Counter(row["manufacturer_cluster"] for row in rows)
    if dict(counts) != EXPECTED_BRANDS or len(rows) != 38:
        raise SystemExit(f"Wave206 target drifted: {dict(counts)}")
    ids = {row["product_external_id"] for row in rows}
    if ids != set(DECISIONS):
        raise SystemExit("Wave206 decision map does not exactly cover the 38-row target")

    source_cache: dict[str, tuple[Path, str, str]] = {}
    for key, (filename, _url, _tier) in SOURCES.items():
        path = SOURCE_DIR / filename
        if not path.is_file():
            raise SystemExit(f"Pinned snapshot missing: {path}")
        source_cache[key] = (path, sha256(path), source_text(path))

    catalog_keys: dict[tuple[str, str], list[str]] = defaultdict(list)
    for row in read_csv(CATALOG):
        manufacturer = normalized(row.get("manufacturer", ""))
        mpn = normalized(row.get("mpn", ""))
        if manufacturer and mpn:
            catalog_keys[(manufacturer, mpn)].append(row.get("id", ""))
    collision_data = json.loads(COLLISIONS.read_text(encoding="utf-8"))
    if collision_data.get("schema_version") != 1:
        raise SystemExit("Wave206 collision evidence schema drifted")
    current_collisions = {row["candidate_external_id"]: row for row in collision_data.get("collisions", [])}

    output_rows = []
    for row in rows:
        decision = DECISIONS[row["product_external_id"]]
        source_key = decision["source"]
        snapshot_path = snapshot_hash = source_url = source_tier = ""
        if source_key:
            path, snapshot_hash, text = source_cache[source_key]
            token = decision["token"]
            if normalized(token) not in normalized(text):
                raise SystemExit(f"Pinned source lacks required token {token}: {path}")
            snapshot_path = path.relative_to(ROOT).as_posix()
            _filename, source_url, source_tier = SOURCES[source_key]

        duplicate_ids = catalog_keys.get((normalized(row["manufacturer_cluster"]), normalized(decision["model"])), [])
        current_collision = current_collisions.get(row["product_external_id"])
        if current_collision:
            duplicate_review = "strict_duplicate_hold:" + current_collision["existing_external_id"]
        else:
            duplicate_review = "no_strict_duplicate" if len(duplicate_ids) <= 1 else "strict_duplicate_hold:" + "|".join(duplicate_ids)
        safe = bool(decision["safe"]) and duplicate_review == "no_strict_duplicate"
        hold_reason = decision["hold"]
        if duplicate_review.startswith("strict_duplicate_hold"):
            hold_reason = "Exact normalized manufacturer+MPN already belongs to another canonical product; do not create a duplicate identity."
        output_rows.append({
            "product_external_id": row["product_external_id"],
            "manufacturer_cluster": row["manufacturer_cluster"],
            "name": row["name"],
            "model_core": decision["model"],
            "partition": decision["partition"],
            "source_tier": source_tier or "none",
            "source_url": source_url,
            "snapshot_path": snapshot_path,
            "snapshot_sha256": snapshot_hash,
            "required_tokens": decision["token"] if source_key else "",
            "verified_facts": decision["facts"],
            "hold_reason": hold_reason if not safe else "",
            "replacement_manufacturer": "B.B. Battery" if safe else "",
            "replacement_mpn": decision["mpn"] if safe else "",
            "safe_to_apply": "true" if safe else "false",
            "duplicate_review": duplicate_review,
        })

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", dir=OUTPUT.parent, delete=False) as handle:
        output_tmp = Path(handle.name)
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(output_rows)
    os.replace(output_tmp, OUTPUT)

    partitions = Counter(row["partition"] for row in output_rows)
    safe_ids = [row["product_external_id"] for row in output_rows if row["safe_to_apply"] == "true"]
    source_index = {
        key: {
            "path": source_cache[key][0].relative_to(ROOT).as_posix(),
            "sha256": source_cache[key][1],
            "url": value[1],
            "tier": value[2],
        }
        for key, value in SOURCES.items()
    }
    summary = {
        "schema_version": 1,
        "site": "microchips-by",
        "batch": "wave206_fiamm_bb_csb",
        "created_at": "2026-07-29",
        "input": {"path": INPUT.relative_to(ROOT).as_posix(), "sha256": sha256(INPUT), "rows": len(rows)},
        "brand_counts": dict(sorted(counts.items())),
        "partition_counts": dict(sorted(partitions.items())),
        "safe_to_apply": {"rows": len(safe_ids), "external_ids": safe_ids},
        "strict_duplicates": {"clusters": sum(row["duplicate_review"].startswith("strict_duplicate") for row in output_rows)},
        "collision_evidence": {"path": COLLISIONS.relative_to(ROOT).as_posix(), "sha256": sha256(COLLISIONS)},
        "sources": source_index,
        "output": {"path": OUTPUT.relative_to(ROOT).as_posix(), "sha256": sha256(OUTPUT), "rows": len(output_rows)},
        "policy": {
            "exact_model_match_is_separate_from_apply_authority": True,
            "fiamm_official_distributor_does_not_promote_canonical_identity": True,
            "construction_suffixes_are_not_inferred": True,
            "price_stock_media_publication_mutations": 0,
            "database_mutations": 0,
        },
    }
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=SUMMARY.parent, delete=False) as handle:
        summary_tmp = Path(handle.name)
        handle.write(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    os.replace(summary_tmp, SUMMARY)


if __name__ == "__main__":
    main()
