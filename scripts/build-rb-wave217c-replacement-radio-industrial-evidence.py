#!/usr/bin/env python3
"""Fail-closed Wave217-C evidence ledger for replacement, AT radio and cells.

Legacy compatibility/equipment wording is preserved as research context only.
It never becomes an asserted sellable OEM identity without a SHA-pinned
first-party source that proves the exact item.
"""
from __future__ import annotations

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
GEN = ROOT / "docs/audits/generated"
INPUT = GEN / "rb-b2b-next-source-batch-wave216.csv"
PROCESSED = GEN / "rb-b2b-processed-register-wave216.csv"
REGISTRY = GEN / "full-catalog-canonical-registry.csv"
OUTPUT = GEN / "rb-wave217c-replacement-radio-industrial-evidence.csv"
SUMMARY = GEN / "rb-wave217c-replacement-radio-industrial-evidence.summary.json"
LIVE = GEN / "wave217c-replacement-radio-industrial-live-identity-collisions.json"
DRY = GEN / "wave217c-replacement-radio-industrial-laravel-dry-run.json"
MANIFEST = ROOT / "docs/imports/rb-verified-oem-identities-wave217c-replacement-radio-industrial-2026-07-29.json"
REPORT = ROOT / "docs/audits/2026-07-29-rb-wave217c-replacement-radio-industrial-evidence.md"
CHECKED_AT = "2026-07-29"
INPUT_SHA256 = "1819df3c10c10f66e79811264f1f31164d83e17a68e0b3f833d89e1d50aab881"
FIELDS = [
    "batch", "product_external_id", "name", "category_external_id", "lane", "factual_product_type",
    "equipment_or_device_context", "title_brand_candidate", "title_series_or_model_candidate", "legacy_part_or_pack_ids",
    "technology", "capacity_ah", "voltage_v", "primary_source_route", "source_tier", "source_publisher",
    "source_url", "source_snapshot_path", "source_snapshot_sha256", "source_assertion", "partition", "hold_reason",
    "registry_exact_title_duplicates", "registry_candidate_identity_duplicates", "live_db_collision_external_ids",
    "live_current_manufacturer", "live_current_mpn", "safe_to_apply",
]
BRANDS = ("Hoppecke", "Midac", "Hawker", "Makita", "EnerSys", "NexSys", "AT", "ЗАИТ")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def norm(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "").upper()
    return re.sub(r"[^A-ZА-Я0-9]+", "", value)


def product_norm(value: str) -> str:
    return re.sub(r"[\W_]", "", (value or "").casefold(), flags=re.UNICODE)


def technical(name: str) -> tuple[str, str, str]:
    tech = re.search(r"\((AGM|GEL|Li-ion|NiCd|NiMH)(?:,|\))", name, re.I)
    capacity = re.search(r"\b(\d+(?:[.,]\d+)?)\s*(?:Ah|mAh)\b", name, re.I)
    voltage = re.search(r"\b(\d+(?:[.,]\d+)?)\s*V\b", name, re.I)
    return (tech.group(1) if tech else "", capacity.group(1).replace(",", ".") if capacity else "", voltage.group(1).replace(",", ".") if voltage else "")


def extraction(row: dict[str, str]) -> dict[str, str]:
    name, cluster = row["name"], row["manufacturer_cluster"]
    tech, capacity, voltage = technical(name)
    if cluster == "AT radio packs":
        token = re.search(r"\bAT\s+([^\s(]+)", name, re.I)
        model = token.group(1) if token else ""
        return {"lane": "at_radio_charger", "factual_product_type": "two_way_radio_battery_charger", "context": "AT radio station", "brand": "AT", "model": model, "ids": model, "tech": tech, "capacity": capacity, "voltage": voltage, "route": "AT manufacturer primary charger catalogue or exact labelled product document required"}
    if cluster == "unresolved_industrial_cell":
        token = re.search(r"\b(K(?:GL|PL)-\s*70\s*P)\b", name, re.I)
        model = re.sub(r"\s+", "", token.group(1)) if token else ""
        return {"lane": "industrial_cell", "factual_product_type": "industrial_nickel_cadmium_cell", "context": "industrial stationary cell", "brand": "ЗАИТ" if "ЗАИТ" in name else "", "model": model, "ids": model, "tech": "", "capacity": "70", "voltage": "", "route": "ЗАИТ manufacturer primary catalogue/archive with exact cell designation required"}
    # ``для`` marks equipment compatibility.  The text before it may describe
    # a family but does not by itself prove the SKU actually offered for sale.
    before, _, context = name.partition(" для ")
    title_brand = next((brand for brand in BRANDS if re.search(rf"\b{re.escape(brand)}\b", before, re.I)), "")
    series = re.sub(r"^Аккумулятор\s+", "", before, flags=re.I).strip()
    ids = "|".join(re.findall(r"\b(?:\d+NXS|\d+PzM|[A-Z]{2,}[A-Z0-9-]*\d[A-Z0-9-]*)\b", before, re.I))
    kind = "power_tool_battery_charger_kit" if "Makita" in name else "traction_battery"
    context = context or "industrial equipment"
    return {"lane": "replacement_context_hold", "factual_product_type": kind, "context": context, "brand": title_brand, "model": series, "ids": ids, "tech": tech, "capacity": capacity, "voltage": voltage, "route": f"{title_brand or 'manufacturer'} first-party exact traction/tool battery catalogue and part-number evidence required"}


def live_products() -> list[dict]:
    php = "echo json_encode(app('db')->table('products')->select('external_id','name','sku','mpn','manufacturer','sku_normalized','mpn_normalized')->orderBy('external_id')->get(),JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES);"
    encoded = base64.b64encode(php.encode()).decode()
    run = subprocess.run(["docker", "compose", "exec", "-T", "backend", "php", "artisan", "tinker", f"--execute=eval(base64_decode('{encoded}'));"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if run.returncode or not run.stdout.strip().startswith("["):
        raise SystemExit(f"read-only PostgreSQL query failed: {run.stderr.strip() or run.stdout.strip()}")
    rows = json.loads(run.stdout)
    if len({row["external_id"] for row in rows}) != len(rows):
        raise SystemExit("live PostgreSQL repeats external IDs")
    return rows


def main() -> None:
    source, processed, registry = read_csv(INPUT), read_csv(PROCESSED), read_csv(REGISTRY)
    if sha(INPUT) != INPUT_SHA256:
        raise SystemExit("Wave217-C input pin drift")
    lane_a = {row["product_external_id"] for row in source if row["manufacturer_cluster"] == "unresolved_other"}
    lane_b = {row["product_external_id"] for row in source if row["manufacturer_cluster"] in {"Robiton", "Panasonic", "EnerSys"}}
    targets = [row for row in source if row["manufacturer_cluster"] in {"unresolved_replacement", "AT radio packs", "unresolved_industrial_cell"}]
    ids = [row["product_external_id"] for row in targets]
    lane_c = set(ids)
    target_counts = Counter(row["manufacturer_cluster"] for row in targets)
    if target_counts != {"unresolved_replacement": 40, "AT radio packs": 6, "unresolved_industrial_cell": 3} or len(ids) != len(set(ids)):
        raise SystemExit(f"Wave217-C exact target drift: {target_counts}")
    if (len(lane_a), len(lane_b), len(lane_c)) != (395, 56, 49) or lane_a & lane_b or lane_a & lane_c or lane_b & lane_c or len(lane_a | lane_b | lane_c) != 500:
        raise SystemExit("Wave217 A/B/C partition is not a disjoint 500-row union")
    processed_overlap = sorted(lane_c & {row["product_external_id"] for row in processed})
    if processed_overlap:
        raise SystemExit(f"Wave217-C overlaps processed register: {processed_overlap[:5]}")
    forbidden = [row["product_external_id"] for row in targets if re.search(r"automotive|автомоб|electronics|электрон", " ".join(row.values()), re.I)]
    if forbidden:
        raise SystemExit(f"automotive/electronics scope breach: {forbidden}")
    live = live_products(); live_by_id = {row["external_id"]: row for row in live}
    if lane_c - set(live_by_id):
        raise SystemExit("Wave217-C candidate missing from live PostgreSQL")
    title_index = defaultdict(list)
    for row in registry:
        title_index[norm(row.get("name", ""))].append(row["registry_id"])
    live_identity = defaultdict(list)
    for row in live:
        for value in (row.get("sku_normalized") or row.get("sku") or "", row.get("mpn_normalized") or row.get("mpn") or ""):
            if (key := product_norm(str(value))):
                live_identity[key].append(row["external_id"])

    evidence, live_checks = [], []
    for row in targets:
        details = extraction(row); external_id, current = row["product_external_id"], live_by_id[row["product_external_id"]]
        # Only an explicit legacy identifier is a collision-search key.  A
        # generic compatibility title (for example, "battery for forklift")
        # would otherwise match much of the registry and turn a detector
        # artifact into a false collision claim.
        candidate_key = product_norm(details["ids"].split("|", 1)[0]) if details["ids"] else ""
        exact_title_dupes = sorted(peer for peer in title_index[norm(row["name"])] if peer != external_id)
        registry_peers = sorted(other["registry_id"] for other in registry if other["registry_id"] != external_id and candidate_key and candidate_key in product_norm(other.get("name", "")))
        live_peers = sorted(peer for peer in live_identity.get(candidate_key, []) if peer != external_id)
        reason = "compatibility_or_title_series_does_not_prove_exact_sellable_identity"
        if details["lane"] == "industrial_cell":
            reason = "legacy_cell_designation_without_pinned_manufacturer_primary_source"
        elif details["lane"] == "at_radio_charger":
            reason = "AT_radio_charger_title_requires_exact_primary_product_identity"
        evidence.append({
            "batch": "wave217c_replacement_radio_industrial", "product_external_id": external_id, "name": row["name"], "category_external_id": row["category_external_id"],
            "lane": details["lane"], "factual_product_type": details["factual_product_type"], "equipment_or_device_context": details["context"], "title_brand_candidate": details["brand"], "title_series_or_model_candidate": details["model"], "legacy_part_or_pack_ids": details["ids"], "technology": details["tech"], "capacity_ah": details["capacity"], "voltage_v": details["voltage"], "primary_source_route": details["route"],
            "source_tier": "", "source_publisher": "", "source_url": "", "source_snapshot_path": "", "source_snapshot_sha256": "", "source_assertion": "", "partition": "exact_source_hold", "hold_reason": reason,
            "registry_exact_title_duplicates": "|".join(exact_title_dupes), "registry_candidate_identity_duplicates": "|".join(registry_peers), "live_db_collision_external_ids": "|".join(live_peers), "live_current_manufacturer": str(current.get("manufacturer") or ""), "live_current_mpn": str(current.get("mpn") or ""), "safe_to_apply": "false",
        })
        live_checks.append({"candidate_external_id": external_id, "candidate_identity_normalized": candidate_key, "conflicting_external_ids": live_peers})
    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n"); writer.writeheader(); writer.writerows(evidence)
    MANIFEST.write_text(json.dumps({"schema_version": 1, "site_key": "microchips-by", "products": [], "policy": "Exact-safe only: no title/compatibility claim is a sellable identity."}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest_sha = sha(MANIFEST); container_manifest = "/tmp/" + MANIFEST.name
    copied = subprocess.run(["docker", "compose", "cp", str(MANIFEST), "backend:" + container_manifest], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if copied.returncode:
        raise SystemExit(f"could not place disposable dry-run manifest: {copied.stderr.strip() or copied.stdout.strip()}")
    run = subprocess.run(["docker", "compose", "exec", "-T", "backend", "php", "artisan", "catalog:apply-verified-oem-identities", "microchips-by", container_manifest], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    dry = {"mode": "dry_run", "attempted_without_apply": True, "apply_flag_used": False, "exit_code": run.returncode, "records": 0, "manifest_sha256": manifest_sha, "stdout": run.stdout.strip(), "stderr": run.stderr.strip(), "expected_fail_closed_reason": "Manifest requires a non-empty products list.", "database_mutations": 0, "commercial_fields_changed": 0, "publication_fields_changed": 0}
    if run.returncode == 0 or "non-empty products list" not in (run.stdout + run.stderr):
        raise SystemExit("Laravel empty exact-safe manifest did not fail closed")
    LIVE.write_text(json.dumps({"schema_version": 1, "mode": "read_only", "query_exit_code": 0, "candidate_rows_checked": len(evidence), "checks": live_checks, "database_mutations": 0}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    DRY.write_text(json.dumps(dry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = {"schema_version": 1, "batch": "wave217c_replacement_radio_industrial", "checked_at": CHECKED_AT,
        "input": {"path": INPUT.relative_to(ROOT).as_posix(), "sha256": sha(INPUT), "rows": 500},
        "wave217_partition": {"a_unresolved_other": len(lane_a), "b_claimed_manufacturer": len(lane_b), "c_replacement_radio_industrial": len(lane_c), "disjoint_union_rows": len(lane_a | lane_b | lane_c), "pairwise_overlap_rows": 0},
        "target": {"rows": len(evidence), "manufacturer_clusters": dict(sorted(target_counts.items())), "lane_counts": dict(sorted(Counter(row["lane"] for row in evidence).items()))}, "processed3000_overlap_ids": processed_overlap,
        "scope_exclusion": {"automotive_rows": 0, "electronics_rows": 0}, "canonical_registry": {"path": REGISTRY.relative_to(ROOT).as_posix(), "sha256": sha(REGISTRY), "rows": len(registry), "collision_rows": sum(bool(row["registry_exact_title_duplicates"] or row["registry_candidate_identity_duplicates"]) for row in evidence)},
        "live_db": {"path": LIVE.relative_to(ROOT).as_posix(), "rows_checked": len(evidence), "collision_rows": sum(bool(row["live_db_collision_external_ids"]) for row in evidence), "database_mutations": 0}, "partition_counts": dict(sorted(Counter(row["partition"] for row in evidence).items())), "manifest": {"path": MANIFEST.relative_to(ROOT).as_posix(), "sha256": manifest_sha, "rows": 0, "exact_safe_only": True}, "laravel_dry_run": {"path": DRY.relative_to(ROOT).as_posix(), "exit_code": run.returncode, "database_mutations": 0}, "safe_to_apply_records": 0, "database_mutations": 0}
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REPORT.write_text("# Wave217-C replacement, radio and industrial evidence\n\n"
                      "Wave217-C processes exactly 49 Wave216 B2B records: 40 unresolved replacement records, six AT radio-station chargers and three industrial cells. Tool, radio and industrial products remain in their B2B categories.\n\n"
                      "The ledger extracts equipment context, title brand/series candidates, legacy IDs and declared technical values, but compatibility language and title-only series are not treated as sellable OEM identities. No exact primary source was available in the pinned source set, so the exact-safe manifest is empty.\n\n"
                      "Canonical-registry and current PostgreSQL checks are read only. Laravel ran without `--apply` against the empty manifest and rejected it as required; database mutations are zero.\n", encoding="utf-8")
    print(json.dumps({"rows": len(evidence), "partitions": Counter(row["partition"] for row in evidence), "database_mutations": 0}, ensure_ascii=False, default=dict))


if __name__ == "__main__":
    main()
