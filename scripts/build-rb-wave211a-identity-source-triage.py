#!/usr/bin/env python3
"""Build Wave211-A's deterministic, read-only identity/source-route triage.

This script deliberately makes neither network nor database calls.  A missing
live-DB comparison is recorded as ``not_checked_db0`` rather than treated as a
negative collision result.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "docs/audits/generated"
INPUT = GEN / "rb-b2b-next-source-batch-wave210.csv"
PROCESSED = GEN / "rb-b2b-processed-register-wave210.csv"
REGISTRY = GEN / "full-catalog-canonical-registry.csv"
OUTPUT = GEN / "wave211a-identity-source-triage.csv"
SUMMARY = GEN / "wave211a-identity-source-triage.summary.json"
REPORT = ROOT / "docs/audits/2026-07-29-wave211a-identity-source-triage.md"

TARGET = {
    "unresolved_replacement": 104, "unresolved_other": 23,
    "unresolved_industrial_cell": 23, "Восток": 17,
    "General Security": 29, "Security Force": 8, "Alarm Force": 3,
    "Optimus": 6,
}
FIELDS = [
    "product_external_id", "name", "manufacturer_cluster", "family_cluster", "category_external_id",
    "exact_model_or_device", "product_pack_form", "normalized_identity_key", "scope", "source_route",
    "route_partition", "in_wave_identity_group_size", "in_wave_duplicate_external_ids",
    "full_registry_collision_count", "full_registry_collision_registry_ids", "live_db_collision_status",
    "live_db_collision_count", "live_db_collision_external_ids", "hold_reason", "safe_to_apply",
]

def sha(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()
def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f: return list(csv.DictReader(f))
def norm(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "").upper()
    value = value.translate(str.maketrans("АВЕКМНОРСТУХ", "ABEKMHOPCTYX"))
    return re.sub(r"[^A-Z0-9]+", "", value)
def form(name: str) -> str:
    groups = re.findall(r"\(([^()]*)\)", name)
    return next((x.strip() for x in groups if re.search(r"(?:AGM|\d+(?:[.,]\d+)?\s*(?:AH|MAH)|\d+(?:[.,]\d+)?\s*V)", x, re.I)), "")
def identity(row: dict[str, str]) -> str:
    name, maker = row["name"], row["manufacturer_cluster"]
    if maker == "unresolved_industrial_cell":
        m = re.search(r"\b(?:\d+\s*)?(?:KGL|KPH|KPL|KL|KH|KM)[-\s]*\d+(?:\s*(?:P|PK))?\b", name, re.I)
        return m.group(0).strip() if m else ""
    if maker == "unresolved_other":
        m = re.search(r"\bMarathon\s+([^()]+?)(?:\s*\(|$)", name, re.I)
        return m.group(1).strip() if m else ""
    if maker == "unresolved_replacement":
        m = re.search(r"\bдля\s+(.+?)(?:\s*\([^()]*\)|\s+\d+(?:[.,]\d+)?\s*(?:mAh|mah)|$)", name, re.I)
        return m.group(1).strip() if m else ""
    m = re.search(rf"\b{re.escape(maker)}\s+(.+?)(?:\s*\(|$)", name, re.I)
    return m.group(1).strip() if m else ""
def route(row: dict[str, str]) -> tuple[str, str, str]:
    maker, category = row["manufacturer_cluster"], row["category_external_id"]
    if category == "seo:replacement-medical":
        return ("hold", "device_oem_identity_and_medical_compatibility_evidence_by_exact_device", "medical_specialist_source_required")
    if maker == "unresolved_industrial_cell":
        return ("hold", "legacy_cell_manufacturer_and_exact_designation_confirmation", "manufacturer_unresolved_legacy_industrial_cell")
    if maker == "unresolved_other":
        return ("hold", "marathon_primary_catalogue_by_exact_model", "declared_manufacturer_absent_from_cluster")
    if maker == "Восток":
        return ("hold", "vostok_pro_primary_catalogue_by_exact_model", "cyrillic_tc_cx_ck_variant_requires_primary_confirmation")
    return ("hold", f"{norm(maker).lower()}_manufacturer_catalogue_by_exact_model", "claimed_brand_and_model_require_primary_confirmation")

def main() -> None:
    source, processed, registry = read_csv(INPUT), read_csv(PROCESSED), read_csv(REGISTRY)
    selected = [r for r in source if r["manufacturer_cluster"] in TARGET]
    ids = [r["product_external_id"] for r in selected]
    if len(selected) != 213 or len(ids) != len(set(ids)) or Counter(r["manufacturer_cluster"] for r in selected) != Counter(TARGET):
        raise SystemExit("Wave211-A target union/count invariant failed")
    processed_ids = {r["product_external_id"] for r in processed}
    overlap = sorted(set(ids) & processed_ids)
    if len(processed) != 1500 or overlap: raise SystemExit(f"processed-1500 overlap invariant failed: {overlap[:5]}")
    if any("automotive" in r["category_external_id"] or "electronics" in r["category_external_id"] for r in selected):
        raise SystemExit("automotive/electronics exclusion invariant failed")
    prepared = []
    for row in selected:
        token, pack = identity(row), form(row["name"])
        partition, source_route, scope = route(row)
        key = f"{norm(row['manufacturer_cluster'])}|{norm(token)}|{norm(pack)}" if token else ""
        prepared.append({**row, "token": token, "pack": pack, "key": key, "partition": partition, "source_route": source_route, "scope": scope})
    sizes = Counter(r["key"] for r in prepared if r["key"])
    registry_by_key: dict[str, set[str]] = defaultdict(set)
    for candidate in prepared:
        token = norm(candidate["token"])
        if not token: continue
        maker = norm(candidate["manufacturer_cluster"])
        for record in registry:
            title = norm(record.get("name", ""))
            if token in title and (maker in title or candidate["manufacturer_cluster"].startswith("unresolved")):
                registry_by_key[candidate["key"]].add(record["registry_id"])
    output = []
    for candidate in prepared:
        ext, key = candidate["product_external_id"], candidate["key"]
        same = sorted(r["product_external_id"] for r in prepared if key and r["key"] == key and r["product_external_id"] != ext)
        collisions = sorted(x for x in registry_by_key[key] if x != ext) if key else []
        holds = [candidate["scope"], "live_db_collision_not_checked_db0"]
        if not candidate["token"]: holds.append("no_exact_model_or_device_token_in_legacy_title")
        if same: holds.append("in_wave_identity_duplicate_or_variant")
        if collisions: holds.append("full_registry_identity_collision")
        output.append({"product_external_id": ext, "name": candidate["name"], "manufacturer_cluster": candidate["manufacturer_cluster"], "family_cluster": candidate["family_cluster"], "category_external_id": candidate["category_external_id"], "exact_model_or_device": candidate["token"], "product_pack_form": candidate["pack"], "normalized_identity_key": key, "scope": candidate["scope"], "source_route": candidate["source_route"], "route_partition": candidate["partition"], "in_wave_identity_group_size": str(sizes.get(key, 0)), "in_wave_duplicate_external_ids": "|".join(same), "full_registry_collision_count": str(len(collisions)), "full_registry_collision_registry_ids": "|".join(collisions), "live_db_collision_status": "not_checked_db0", "live_db_collision_count": "", "live_db_collision_external_ids": "", "hold_reason": "|".join(holds), "safe_to_apply": "false"})
    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n"); writer.writeheader(); writer.writerows(output)
    summary = {"schema_version": 1, "wave": "wave211a", "input": {"path": INPUT.relative_to(ROOT).as_posix(), "sha256": sha(INPUT), "rows": len(source)}, "target_union": {"rows": len(output), "unique_external_ids": len(set(ids)), "manufacturer_counts": dict(sorted(Counter(r["manufacturer_cluster"] for r in output).items()))}, "processed_register": {"path": PROCESSED.relative_to(ROOT).as_posix(), "rows": len(processed), "overlap_rows": len(overlap), "overlap_ids": overlap}, "scope_routes": {"automotive_rows": 0, "electronics_rows": 0, "medical_specialist_rows": sum(r["scope"] == "medical_specialist_source_required" for r in output), "other_b2b_rows": sum(r["scope"] != "medical_specialist_source_required" for r in output)}, "full_registry": {"path": REGISTRY.relative_to(ROOT).as_posix(), "sha256": sha(REGISTRY), "rows": len(registry), "collision_candidates": sum(int(r["full_registry_collision_count"]) > 0 for r in output)}, "live_db": {"status": "not_checked_db0", "database_queries": 0, "collision_candidates": None, "database_mutations": 0}, "in_wave_duplicate_candidates": sum(int(r["in_wave_identity_group_size"]) > 1 for r in output), "route_partition_counts": dict(sorted(Counter(r["route_partition"] for r in output).items())), "output": {"path": OUTPUT.relative_to(ROOT).as_posix(), "sha256": sha(OUTPUT), "rows": len(output)}, "automatic_web_requests": 0, "automatic_database_queries": 0, "automatic_database_mutations": 0, "safe_to_apply_records": 0}
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REPORT.write_text("# Wave211-A identity/source-route triage\n\nRead-only deterministic triage from Wave210's 500-row source batch. The exact target union is 213 B2B rows: 104 medical replacement batteries routed to exact device/OEM medical evidence and 109 other B2B holds. Medical products are not excluded from the catalogue. No web requests or database queries/mutations were made; live DB collision fields are explicitly `not_checked_db0`.\n\nThe triage uses model/device text plus pack form for in-wave duplicate groups and full canonical-registry collision candidates. It proves zero overlap with the 1,500-row processed register and zero automotive/electronics rows. Every record remains `safe_to_apply=false`.\n", encoding="utf-8")
    print(json.dumps({"rows": len(output), "processed_overlap": len(overlap), "safe": 0, "web": 0, "db": 0}, ensure_ascii=False))
if __name__ == "__main__": main()
