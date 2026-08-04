#!/usr/bin/env python3
"""Fail-closed evidence ledger for the five Wave213-C industrial-cell rows.

This batch deliberately records device/model designations, rather than turning
them into inferred OEM battery identities.  A valid OEM manifest cannot be
empty, so the Laravel command is invoked against the empty exact-safe manifest
only to capture its expected fail-closed rejection; --apply is never used.
"""
from __future__ import annotations

import base64
import csv
import hashlib
import json
import re
import subprocess
import unicodedata
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "docs/audits/generated/rb-b2b-next-source-batch-wave212.csv"
PROCESSED = ROOT / "docs/audits/generated/rb-b2b-processed-register-wave212.csv"
REGISTRY = ROOT / "docs/audits/generated/full-catalog-canonical-registry.csv"
OUTPUT = ROOT / "docs/audits/generated/rb-wave213c-industrial-cell-evidence.csv"
LIVE = ROOT / "docs/audits/generated/wave213c-industrial-live-identity-collisions.json"
DRY = ROOT / "docs/audits/generated/wave213c-industrial-laravel-dry-run.json"
SUMMARY = ROOT / "docs/audits/generated/rb-wave213c-industrial-cell-evidence.summary.json"
MANIFEST = ROOT / "docs/imports/rb-verified-oem-identities-wave213c-industrial-2026-07-29.json"
CHECKED_AT = "2026-07-29"

TARGETS = {
    "bitrix:11348": {
        "designation": "Flight 60 Internal; V60-19100-63",
        "manufacturer": "", "mpn": "V60-19100-63",
        "route": "Flight Medical first-party accessory/service document required",
        "source_url": "", "assertion": "",
        "reason": "device family and legacy token do not prove the replacement battery OEM or part number",
    },
    "bitrix:11349": {
        "designation": "Flight 60 Main; V60-19000-63",
        "manufacturer": "", "mpn": "V60-19000-63",
        "route": "Flight Medical first-party accessory/service document required",
        "source_url": "", "assertion": "",
        "reason": "device family and legacy token do not prove the replacement battery OEM or part number",
    },
    "bitrix:11351": {
        "designation": "Fluke Biomedical INCU II Incubator; 10200 mAh",
        "manufacturer": "", "mpn": "",
        "route": "Fluke Biomedical official accessory/service document required",
        "source_url": "https://www.flukebiomedical.com/products/incubator-radiant-warmer-analyzers/incu-ii-incubator-radiant-warmer-analyzer",
        "assertion": "official device page confirms the INCU II device only; it does not identify a replacement battery part",
        "reason": "capacity is not a unique MPN and the official device page contains no replacement battery identity",
    },
    "bitrix:11426": {
        "designation": "Marco KM500 (Nidek); MA-3010",
        "manufacturer": "", "mpn": "MA-3010",
        "route": "Marco/Nidek first-party accessory or service document required",
        "source_url": "", "assertion": "",
        "reason": "legacy parenthetical brand and token do not prove that MA-3010 is an OEM battery MPN",
    },
    "bitrix:1688": {
        "designation": "ЗАИТ НК-80 (без электролита)",
        "manufacturer": "", "mpn": "НК-80",
        "route": "ЗАИТ first-party catalogue/archive required; 1C match is supporting inventory evidence only",
        "source_url": "", "assertion": "1C match KA-00006874 names Аккумулятор НК-80 (без электролита), but is not a manufacturer-primary source",
        "reason": "no SHA-pinned official manufacturer source establishes the present product identity",
    },
}
FIELDS = [
    "batch", "product_external_id", "name", "exact_designation", "candidate_manufacturer", "candidate_mpn",
    "primary_manufacturer_source_route", "official_source_url", "official_source_assertion", "partition",
    "conflict_reason", "registry_exact_title_duplicates", "registry_designation_candidates",
    "live_db_collision_external_ids", "live_current_manufacturer", "live_current_mpn", "safe_to_apply",
]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


CONFUSABLES = str.maketrans({"А":"A", "В":"B", "Е":"E", "К":"K", "М":"M", "Н":"H", "О":"O", "Р":"P", "С":"C", "Т":"T", "У":"Y", "Х":"X"})
def norm(value: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "", unicodedata.normalize("NFKC", value or "").upper().translate(CONFUSABLES))


def live_products() -> list[dict]:
    php = "echo json_encode(app('db')->table('products')->select('external_id','name','sku','mpn','manufacturer','status')->orderBy('external_id')->get(),JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES);"
    encoded = base64.b64encode(php.encode()).decode()
    run = subprocess.run(["docker", "compose", "exec", "-T", "backend", "php", "artisan", "tinker", f"--execute=eval(base64_decode('{encoded}'));"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if run.returncode or not run.stdout.strip().startswith("["):
        raise SystemExit(f"read-only live DB query failed: {run.stderr.strip() or run.stdout.strip()}")
    return json.loads(run.stdout)


def main() -> None:
    source = read_csv(INPUT)
    targets = [row for row in source if row["manufacturer_cluster"] == "unresolved_industrial_cell"]
    ids = [row["product_external_id"] for row in targets]
    if len(targets) != 5 or set(ids) != set(TARGETS) or len(ids) != len(set(ids)):
        raise SystemExit(f"Wave213-C target drift: {ids}")
    if any(any(word in (row["name"] + row["category_external_id"]).casefold() for word in ("automotive", "electronics", "автомоб", "электрон")) for row in targets):
        raise SystemExit("automotive/electronics exclusion failed")
    wave213a = {row["product_external_id"] for row in source if row["manufacturer_cluster"] == "unresolved_replacement"}
    wave213b = {row["product_external_id"] for row in source if row["manufacturer_cluster"] == "unresolved_other" and row["category_external_id"] == "seo:power-systems"}
    wave213c = set(ids)
    if (len(wave213a), len(wave213b), len(wave213c)) != (274, 221, 5):
        raise SystemExit(f"Wave213 partition count drift: A={len(wave213a)} B={len(wave213b)} C={len(wave213c)}")
    if wave213a & wave213b or wave213a & wave213c or wave213b & wave213c or len(wave213a | wave213b | wave213c) != 500:
        raise SystemExit("Wave213 A/B/C union is not a disjoint 500-row partition")
    processed_ids = {row["product_external_id"] for row in read_csv(PROCESSED)}
    overlap = sorted(set(ids) & processed_ids)
    if overlap:
        raise SystemExit(f"processed2000 overlap: {overlap}")

    registry = read_csv(REGISTRY)
    by_title: dict[str, list[str]] = defaultdict(list)
    for row in registry:
        by_title[norm(row["name"])].append(row["registry_id"])
    live = live_products()
    live_by_id = {row["external_id"]: row for row in live}
    if set(ids) - set(live_by_id):
        raise SystemExit("candidate absent from live DB")

    evidence = []
    live_checks = []
    for row in targets:
        item = TARGETS[row["product_external_id"]]
        token = norm(item["mpn"])
        registry_candidates = sorted({other["registry_id"] for other in registry if token and token in norm(other["name"]) and other["registry_id"] != row["product_external_id"]})
        exact_duplicates = sorted(peer for peer in by_title[norm(row["name"])] if peer != row["product_external_id"])
        current = live_by_id[row["product_external_id"]]
        db_peers = sorted(other["external_id"] for other in live if other["external_id"] != row["product_external_id"] and token and token in {norm(str(other.get("sku") or "")), norm(str(other.get("mpn") or ""))})
        live_checks.append({"candidate_external_id": row["product_external_id"], "designation_token_normalized": token, "conflicting_external_ids": db_peers})
        evidence.append({
            "batch": "wave213c_industrial", "product_external_id": row["product_external_id"], "name": row["name"],
            "exact_designation": item["designation"], "candidate_manufacturer": item["manufacturer"], "candidate_mpn": item["mpn"],
            "primary_manufacturer_source_route": item["route"], "official_source_url": item["source_url"], "official_source_assertion": item["assertion"],
            "partition": "no_evidence", "conflict_reason": item["reason"],
            "registry_exact_title_duplicates": "|".join(exact_duplicates), "registry_designation_candidates": "|".join(registry_candidates),
            "live_db_collision_external_ids": "|".join(db_peers), "live_current_manufacturer": str(current.get("manufacturer") or ""),
            "live_current_mpn": str(current.get("mpn") or ""), "safe_to_apply": "false",
        })
    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n"); writer.writeheader(); writer.writerows(evidence)
    # Kept as a schema-valid provenance record.  It intentionally has no products.
    MANIFEST.write_text(json.dumps({"schema_version": 1, "site_key": "microchips-by", "products": []}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest_hash = sha(MANIFEST)
    # The Laravel command's non-empty-manifest contract makes a successful dry run impossible for zero exact-safe rows.
    # The backend image contains only the Laravel application, not repository
    # documentation. Copy this disposable, empty manifest to /tmp solely for
    # the command's dry validation; no --apply option is ever supplied.
    container_manifest = "/tmp/" + MANIFEST.name
    copied = subprocess.run(["docker", "compose", "cp", str(MANIFEST), "backend:" + container_manifest], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if copied.returncode:
        raise SystemExit(f"could not place disposable Laravel dry-run manifest: {copied.stderr.strip() or copied.stdout.strip()}")
    run = subprocess.run(["docker", "compose", "exec", "-T", "backend", "php", "artisan", "catalog:apply-verified-oem-identities", "microchips-by", container_manifest], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    dry = {"mode": "dry_run", "attempted_without_apply": True, "exit_code": run.returncode, "records": 0, "manifest_sha256": manifest_hash, "stdout": run.stdout.strip(), "stderr": run.stderr.strip(), "expected_fail_closed_reason": "Manifest requires a non-empty products list.", "database_mutations": 0, "commercial_fields_changed": 0, "publication_fields_changed": 0}
    if run.returncode == 0 or "non-empty products list" not in (run.stdout + run.stderr):
        raise SystemExit("Laravel empty-manifest dry-run did not fail closed as expected")
    LIVE.write_text(json.dumps({"schema_version": 1, "mode": "read_only", "database_mutations": 0, "candidate_rows_checked": 5, "checks": live_checks}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    DRY.write_text(json.dumps(dry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = {"schema_version": 1, "batch": "wave213c_industrial", "checked_at": CHECKED_AT, "input": {"path": str(INPUT.relative_to(ROOT)).replace("\\", "/"), "sha256": sha(INPUT), "rows": 5}, "wave213_partition": {"a_unresolved_replacement": len(wave213a), "b_unresolved_other_power_systems": len(wave213b), "c_unresolved_industrial_cell": len(wave213c), "disjoint_union_rows": len(wave213a | wave213b | wave213c), "pairwise_overlap_rows": 0}, "processed2000_overlap_ids": overlap, "scope_exclusion": {"automotive_rows": 0, "electronics_rows": 0}, "canonical_registry": {"path": str(REGISTRY.relative_to(ROOT)).replace("\\", "/"), "sha256": sha(REGISTRY), "rows": len(registry)}, "partition_counts": {"no_evidence": 5, "exact_safe": 0}, "manifest": {"path": str(MANIFEST.relative_to(ROOT)).replace("\\", "/"), "sha256": manifest_hash, "rows": 0}, "live_db": {"path": str(LIVE.relative_to(ROOT)).replace("\\", "/"), "database_mutations": 0}, "laravel_dry_run": {"path": str(DRY.relative_to(ROOT)).replace("\\", "/"), "exit_code": run.returncode, "database_mutations": 0}, "policy": {"official_evidence_if_available": True, "exact_safe_manifest_only": True, "database_apply": False}}
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"rows": 5, "exact_safe": 0, "laravel_exit": run.returncode, "database_mutations": 0}, ensure_ascii=False))


if __name__ == "__main__":
    main()
