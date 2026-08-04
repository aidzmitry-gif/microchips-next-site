#!/usr/bin/env python3
"""Build the read-only, fail-closed Wave209-D identity/source-route triage.

No network access is used.  The only optional service call is a read-only
Docker PostgreSQL product listing used to record collisions in a local snapshot.
"""
from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import re
import subprocess
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "docs/audits/generated/rb-b2b-next-source-batch-wave208.csv"
REGISTRY = ROOT / "docs/audits/generated/full-catalog-canonical-registry.csv"
OUTPUT = ROOT / "docs/audits/generated/wave209d-identity-source-triage.csv"
SUMMARY = ROOT / "docs/audits/generated/wave209d-identity-source-triage.summary.json"
LIVE = ROOT / "docs/audits/generated/wave209d-live-identity-collisions.json"

TARGET = {
    "unresolved_industrial_cell": 54, "unresolved_other": 33,
    "unresolved_replacement": 1, "\u0412\u043e\u0441\u0442\u043e\u043a": 9, "Contact": 7,
    "General Security": 8, "Security Force": 5, "Alarm Force": 2, "Optimus": 1,
}
WAVE209_A = {"APC", "EnerSys", "Sonnenschein"}
WAVE209_B = {"Delta", "Fiamm", "Leoch"}
WAVE209_C = {"Panasonic", "Ventura", "Casil", "B.B. Battery", "Robiton", "CSB", "Yuasa", "WBR", "Sprinter"}
EXPECTED = 120
FIELDS = [
    "product_external_id", "name", "manufacturer_cluster", "family_cluster", "category_external_id",
    "exact_model_token", "product_pack_form", "normalized_identity_key", "likely_manufacturer_route",
    "route_partition", "scope_exclusion", "in_wave_identity_group_size", "in_wave_duplicate_external_ids",
    "full_registry_collision_count", "full_registry_collision_external_ids", "live_db_collision_count",
    "live_db_collision_external_ids", "live_current_manufacturer", "live_current_mpn", "hold_reason", "safe_to_apply",
]

def digest(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()
def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f: return list(csv.DictReader(f))
def norm(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "").upper()
    value = value.translate(str.maketrans("\u0410\u0412\u0415\u041a\u041c\u041d\u041e\u0420\u0421\u0422\u0423\u0425", "ABEKMHOPCTYX"))
    return re.sub(r"[^A-Z0-9]+", "", value)

def product_form(name: str) -> str:
    m = re.search(r"\(([^()]*)\)", name)
    return m.group(1).strip() if m else ""

def model_token(row: dict[str, str]) -> str:
    name, maker = row["name"], row["manufacturer_cluster"]
    if maker == "unresolved_industrial_cell":
        # Exact legacy designation is retained, including terminal P/PK variants.
        m = re.search(r"\b\d+\s*(?:KGL|KPH|KPL|KL|KH|KM)[-\s]*\d+(?:\s*(?:P|PK))?\b", name, re.I)
        return m.group(0).strip() if m else ""
    if maker == "unresolved_replacement":
        m = re.search(r"\bKiper\s+([^()]+?)(?:\s+\u0434\u043b\u044f\b|\s*\(|$)", name, re.I)
        return m.group(1).strip() if m else ""
    escaped = re.escape(maker)
    m = re.search(rf"\b{escaped}\s+(.+?)(?:\s*\(|$)", name, re.I)
    return m.group(1).strip() if m else ""

def route(row: dict[str, str], token: str) -> tuple[str, str, str]:
    maker = row["manufacturer_cluster"]
    if maker == "unresolved_industrial_cell":
        return ("hold", "manual_manufacturer_resolution_by_exact_legacy_cell_designation", "manufacturer_unresolved_legacy_industrial_cell")
    if maker == "unresolved_replacement":
        return ("hold", "device_oem_or_pack_assembler_confirmation_by_exact_model", "replacement_claim_not_verified_manufacturer_identity")
    if maker == "unresolved_other":
        return ("hold", "manual_manufacturer_resolution_before_source_research", "declared_manufacturer_absent_from_legacy_title")
    if maker == "\u0412\u043e\u0441\u0442\u043e\u043a":
        return ("hold", "vostok_pro_series_primary_catalogue_by_exact_model", "Cyrillic_TC_CX_CK_variant_requires_primary_confirmation")
    return ("hold", f"{norm(maker).lower()}_manufacturer_catalogue_by_exact_model", "claimed_brand_and_model_require_primary_source_confirmation")

def live_products() -> list[dict[str, str]]:
    php = "$r=app('db')->table('products')->select('external_id','name','manufacturer','mpn')->orderBy('external_id')->get();echo json_encode($r,JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES);"
    encoded = base64.b64encode(php.encode()).decode()
    proc = subprocess.run(["docker", "compose", "exec", "-T", "backend", "php", "artisan", "tinker", f"--execute=eval(base64_decode('{encoded}'));"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode or not proc.stdout.strip().startswith("["):
        raise SystemExit(f"read-only live DB query failed: {proc.stderr.strip() or proc.stdout.strip()}")
    return json.loads(proc.stdout.strip())

def main() -> None:
    ap = argparse.ArgumentParser(); ap.add_argument("--db-snapshot", type=Path); args = ap.parse_args()
    source = read_csv(INPUT)
    selected = [r for r in source if r["manufacturer_cluster"] in TARGET]
    ids = [r["product_external_id"] for r in selected]
    if len(selected) != EXPECTED or len(ids) != len(set(ids)) or Counter(r["manufacturer_cluster"] for r in selected) != Counter(TARGET):
        raise SystemExit("Wave209-D target union/count invariant failed")
    assigned = {"wave209a": {r["product_external_id"] for r in source if r["manufacturer_cluster"] in WAVE209_A}, "wave209b": {r["product_external_id"] for r in source if r["manufacturer_cluster"] in WAVE209_B}, "wave209c": {r["product_external_id"] for r in source if r["manufacturer_cluster"] in WAVE209_C}}
    overlaps = {wave: sorted(set(ids) & values) for wave, values in assigned.items()}
    if any(overlaps.values()): raise SystemExit(f"Wave209 A/B/C overlap: {overlaps}")
    db = json.loads(args.db_snapshot.read_text(encoding="utf-8")) if args.db_snapshot else live_products()
    db_by_id = {str(r["external_id"]): r for r in db}
    if len(db_by_id) != len(db): raise SystemExit("live DB repeats external_id")
    registry = read_csv(REGISTRY)
    prepared = []
    for row in selected:
        token = model_token(row); form = product_form(row["name"]); partition, source_route, scope = route(row, token)
        key = f"{norm(row['manufacturer_cluster'])}|{norm(token)}|{norm(form)}" if token else ""
        prepared.append({**row, "token": token, "form": form, "key": key, "partition": partition, "source_route": source_route, "scope": scope})
    sizes = Counter(r["key"] for r in prepared if r["key"])
    registry_by_key: dict[str, set[str]] = defaultdict(set)
    matcher = [(item, norm(item["token"]), norm(item["manufacturer_cluster"])) for item in prepared if item["key"]]
    for row in registry:
        normalized_name = norm(row["name"])
        for item, token_normalized, maker_normalized in matcher:
            if token_normalized in normalized_name and (maker_normalized in normalized_name or item["manufacturer_cluster"].startswith("unresolved")):
                registry_by_key[item["key"]].add(row["registry_id"])
    live_by_key: dict[str, set[str]] = defaultdict(set)
    for row in db:
        normalized_name = norm(str(row.get("name") or ""))
        for item, token_normalized, maker_normalized in matcher:
            if token_normalized in normalized_name and (maker_normalized in normalized_name or item["manufacturer_cluster"].startswith("unresolved")):
                live_by_key[item["key"]].add(str(row["external_id"]))
    output = []
    for item in prepared:
        external = item["product_external_id"]; current = db_by_id.get(external, {})
        in_wave = sorted(r["product_external_id"] for r in prepared if item["key"] and r["key"] == item["key"] and r["product_external_id"] != external)
        reg = sorted(x for x in registry_by_key[item["key"]] if x != external) if item["key"] else []
        live = sorted(x for x in live_by_key[item["key"]] if x != external) if item["key"] else []
        holds = [item["scope"]]
        if not item["token"]: holds.append("no_exact_model_token_in_legacy_title")
        if in_wave: holds.append("in_wave_identity_duplicate_or_variant")
        if reg: holds.append("full_registry_identity_collision")
        if live: holds.append("live_db_identity_collision")
        output.append({"product_external_id": external, "name": item["name"], "manufacturer_cluster": item["manufacturer_cluster"], "family_cluster": item["family_cluster"], "category_external_id": item["category_external_id"], "exact_model_token": item["token"], "product_pack_form": item["form"], "normalized_identity_key": item["key"], "likely_manufacturer_route": item["source_route"], "route_partition": item["partition"], "scope_exclusion": item["scope"], "in_wave_identity_group_size": str(sizes.get(item["key"], 0)), "in_wave_duplicate_external_ids": "|".join(in_wave), "full_registry_collision_count": str(len(reg)), "full_registry_collision_external_ids": "|".join(reg), "live_db_collision_count": str(len(live)), "live_db_collision_external_ids": "|".join(live), "live_current_manufacturer": str(current.get("manufacturer") or ""), "live_current_mpn": str(current.get("mpn") or ""), "hold_reason": "|".join(holds), "safe_to_apply": "false"})
    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n"); writer.writeheader(); writer.writerows(output)
    live_payload = {"schema_version": 1, "mode": "read_only", "database": "current Docker PostgreSQL", "candidate_rows_checked": len(output), "product_rows_checked": len(db), "query_rule": "exact normalized model token plus declared-brand token (unresolved cells: exact model token)", "collisions": [{"candidate_external_id": r["product_external_id"], "conflicting_external_ids": r["live_db_collision_external_ids"].split("|")} for r in output if r["live_db_collision_external_ids"]], "database_mutations": 0}
    LIVE.write_text(json.dumps(live_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = {"schema_version": 1, "wave": "wave209d", "input": {"path": INPUT.relative_to(ROOT).as_posix(), "sha256": digest(INPUT), "source_rows": len(source)}, "target_union": {"rows": len(output), "unique_external_ids": len(set(ids)), "manufacturer_counts": dict(sorted(Counter(r["manufacturer_cluster"] for r in output).items()))}, "wave209_assigned_overlap": {wave: {"rows": len(values), "overlap_rows": len(overlaps[wave]), "overlap_ids": overlaps[wave]} for wave, values in assigned.items()}, "full_registry": {"path": REGISTRY.relative_to(ROOT).as_posix(), "sha256": digest(REGISTRY), "rows": len(registry), "collision_candidates": sum(int(r["full_registry_collision_count"]) > 0 for r in output)}, "live_db": {"path": LIVE.relative_to(ROOT).as_posix(), "rows_checked": len(output), "collision_candidates": sum(int(r["live_db_collision_count"]) > 0 for r in output), "database_mutations": 0}, "in_wave_duplicate_candidates": sum(int(r["in_wave_identity_group_size"]) > 1 for r in output), "route_partition_counts": dict(sorted(Counter(r["route_partition"] for r in output).items())), "output": {"path": OUTPUT.relative_to(ROOT).as_posix(), "sha256": digest(OUTPUT), "rows": len(output)}, "automatic_web_requests": 0, "automatic_database_mutations": 0, "safe_to_apply_records": 0}
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"rows": len(output), "overlap": {k: len(v) for k,v in overlaps.items()}, "safe": 0}, ensure_ascii=False))
if __name__ == "__main__": main()
