#!/usr/bin/env python3
"""Build the fail-closed Wave215-A power-system classification ledger.

The Wave214 source batch is immutable input.  This script does not acquire
pages: APC Wave199 evidence is permitted only if its external ID, current
title, and model all agree exactly.  Every other large family is retained as a
first-party research route, not silently promoted to an OEM identity.
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
INPUT = GEN / "rb-b2b-next-source-batch-wave214.csv"
PROCESSED = GEN / "rb-b2b-processed-register-wave214.csv"
REGISTRY = GEN / "full-catalog-canonical-registry.csv"
APC_CANDIDATES = GEN / "rb-apc-wave199-candidates.csv"
APC_EVIDENCE = GEN / "rb-apc-wave199-official-evidence.csv"
OUTPUT = GEN / "rb-wave215a-power-evidence.csv"
LIVE = GEN / "wave215a-power-live-identity-collisions.json"
DRY = GEN / "wave215a-power-laravel-dry-run.json"
SUMMARY = GEN / "rb-wave215a-power-evidence.summary.json"
MANIFEST = ROOT / "docs/imports/rb-verified-oem-identities-wave215a-power-2026-07-29.json"
REPORT = ROOT / "docs/audits/2026-07-29-rb-wave215a-power-systems.md"
CHECKED_AT = "2026-07-29"
INPUT_SHA256 = "add632ce13a89a0cd86ef166bc76dd6a924a21e730a3122b4ab4fa10b5ba8e4d"
APC_CANDIDATES_SHA256 = "48c443baaa19e9d65e8cc82c3f96bfd9fd8fa25c1ed02a9e620c0ffb1cf7d070"
APC_EVIDENCE_SHA256 = "a75307f6e1d4deedf4e834aa514c23c52cd7e1d2307c5a05e17a7eecdc96d8a9"

FIELDS = [
    "batch", "product_external_id", "name", "category_external_id", "source_cluster", "factual_type",
    "manufacturer_candidate", "manufacturer_status", "model_candidate", "model_status", "family_group",
    "family_status", "variant_group", "duplicate_group", "primary_manufacturer_source_route", "source_tier",
    "source_publisher", "source_url", "source_snapshot_path", "source_snapshot_sha256", "source_assertion",
    "partition", "conflict_reason", "batch_duplicate_external_ids", "batch_duplicate_identity_external_ids",
    "registry_exact_title_duplicates", "registry_model_candidate_external_ids", "live_db_collision_external_ids",
    "live_current_manufacturer", "live_current_mpn", "safe_to_apply",
]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


CONFUSABLES = str.maketrans({"А": "A", "В": "B", "Е": "E", "К": "K", "М": "M", "Н": "H", "О": "O", "Р": "P", "С": "C", "Т": "T", "У": "Y", "Х": "X"})


def norm(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "").upper().translate(CONFUSABLES)
    return re.sub(r"[^A-Z0-9]+", "", value)


def token_pattern(value: str) -> re.Pattern[str]:
    chars = [re.escape(c) for c in unicodedata.normalize("NFKC", value).upper() if c.isalnum() or c == "."]
    return re.compile(r"(?<![A-ZА-Я0-9])" + r"[\s_./-]*".join(chars) + r"(?![A-ZА-Я0-9])", re.I)


def factual_type(name: str) -> str:
    if re.match(r"^Источник бесперебойного питания\s+", name, re.I):
        return "ups_system"
    if re.match(r"^DC-DC\s+преобразователь\s+", name, re.I):
        return "dc_dc_power_converter"
    if re.match(r"^AC-DC\s+преобразователь\s+", name, re.I):
        return "ac_dc_power_supply"
    raise ValueError(f"unclassified power-system title: {name}")


def title_body(name: str) -> str:
    return re.sub(r"^(?:Источник бесперебойного питания|(?:AC|DC)-DC преобразователь)\s+", "", name, flags=re.I).strip()


BRANDS = (
    "Mean Well", "CrownMicro", "CyberPower", "Powercom", "EnerGenie", "ExeGate", "Hiden", "IPPON",
    "Eaton", "nJoy", "IНЭЛТ", "Kiper", "Kehua", "Энергия", "SVEN", "EKF", "FSP", "APC", "Ирбис",
)


def title_identity(name: str) -> tuple[str, str, str, str]:
    """Return candidate brand/model/family with the title asserted separately."""
    body = title_body(name)
    brand = next((candidate for candidate in BRANDS if body.casefold().startswith(candidate.casefold() + " ")), "")
    model = body[len(brand):].strip() if brand else body
    if not model:
        raise ValueError(f"empty title model: {name}")
    # A first model code is a useful family routing key, but never primary
    # manufacturer evidence.  APC's human-readable UPS series keeps enough
    # words to distinguish its principal product families.
    if brand == "APC":
        match = re.match(r"((?:Easy UPS(?: On-Line)?(?: [A-Z]+){0,2})|(?:Back UPS(?: Pro)?(?: [A-Z]+)?)|(?:Smart-?UPS(?: [A-Z]+){0,2}))(?:\s+\d|$)", model, re.I)
        family = match.group(1) if match else " ".join(model.split()[:3])
    else:
        words = model.split()
        first = re.sub(r"\d.*$", "", words[0]).rstrip("-_/.") or words[0]
        family = " ".join(words[:2]) if len(words) > 1 and re.search(r"[A-ZА-Я]\d", words[1], re.I) else first
    family = re.sub(r"\s+", " ", family).strip()
    return brand, model, family, ("title_label" if brand else "manufacturer_unresolved")


def route(brand: str, kind: str) -> str:
    if brand == "APC":
        return "pinned_APC_Wave199_primary_evidence_requires_exact_ID_name_model; otherwise_Schneider_APC_UPS_product_page_required"
    if brand == "Mean Well":
        return "Mean_Well_first_party_DDR_DCW_DCW_N_datasheet_batch_required"
    if brand:
        return f"{brand}_first_party_{'UPS' if kind == 'ups_system' else 'power_converter'}_family_batch_required"
    return "manufacturer_resolution_then_first_party_catalogue_required"


def live_products() -> list[dict]:
    php = "echo json_encode(app('db')->table('products')->select('external_id','name','sku','mpn','manufacturer','sku_normalized','mpn_normalized')->orderBy('external_id')->get(),JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES);"
    encoded = base64.b64encode(php.encode()).decode()
    run = subprocess.run(["docker", "compose", "exec", "-T", "backend", "php", "artisan", "tinker", f"--execute=eval(base64_decode('{encoded}'));"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if run.returncode or not run.stdout.strip().startswith("["):
        raise SystemExit(f"read-only live DB query failed: {run.stderr.strip() or run.stdout.strip()}")
    products = json.loads(run.stdout)
    if len(products) != len({row["external_id"] for row in products}):
        raise SystemExit("live DB repeats external IDs")
    return products


def write_report(evidence: list[dict[str, str]], apc_exact: int, dry: dict) -> None:
    types = Counter(row["factual_type"] for row in evidence)
    clusters = Counter(row["source_cluster"] for row in evidence)
    families = Counter(row["family_group"] for row in evidence)
    lines = [
        "# Wave215-A power systems", "",
        "Wave215-A classifies exactly 359 `seo:power-systems` records from the SHA-pinned Wave214 batch.",
        "It keeps power equipment distinct from batteries: all records are UPS systems or AC/DC/DC/DC power converters; none is an electronic component.", "",
        "## Scope and no-repeat guards", "",
        f"- Source clusters: {dict(sorted(clusters.items()))}",
        f"- Factual types: {dict(sorted(types.items()))}",
        "- Processed2500 and all prior Wave evidence IDs have zero overlap with this batch.",
        "- The full canonical registry, in-batch duplicate index, and read-only live-product identity check were run for every row.", "",
        "## Evidence policy", "",
        f"- Pinned APC Wave199 primary evidence exact matches: {apc_exact} of 36 APC UPS rows.",
        "- Wave199 is an APC replacement-battery-cartridge dataset, so its source bytes are not reused for a different APC ID, title, or title-derived UPS model.",
        "- Large unresolved UPS and converter families are routed to manufacturer-first-party batch research. Title labels remain candidates, not confirmed OEM identities.",
        "- The exact-safe manifest is empty; the Laravel command was executed without `--apply` and failed closed on its required non-empty product list.", "",
        "## Title-derived family routing", "",
        f"- Families: {dict(sorted(families.items()))}",
        "",
        f"Laravel dry-run exit: {dry['exit_code']} (expected fail-closed); database mutations: 0.",
    ]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    source = read_csv(INPUT)
    selected = [row for row in source if row["category_external_id"] == "seo:power-systems"]
    ids = [row["product_external_id"] for row in selected]
    expected_clusters = {"unresolved_other": 318, "APC": 36, "unresolved_industrial_cell": 5}
    if sha(INPUT) != INPUT_SHA256 or len(selected) != 359 or Counter(row["manufacturer_cluster"] for row in selected) != expected_clusters or len(ids) != len(set(ids)):
        raise SystemExit("Wave215-A input pin/scope/duplicate drift")
    processed_ids = {row["product_external_id"] for row in read_csv(PROCESSED)}
    processed_overlap = sorted(set(ids) & processed_ids)
    if processed_overlap:
        raise SystemExit(f"Wave215-A overlaps processed2500: {processed_overlap[:5]}")
    prior_paths = [path for path in GEN.glob("rb-wave*-evidence.csv") if path.name != OUTPUT.name]
    prior_ids = {row.get("product_external_id", "") for path in prior_paths for row in read_csv(path)}
    prior_overlap = sorted(set(ids) & prior_ids)
    if prior_overlap:
        raise SystemExit(f"Wave215-A overlaps prior evidence: {prior_overlap[:5]}")

    if sha(APC_CANDIDATES) != APC_CANDIDATES_SHA256 or sha(APC_EVIDENCE) != APC_EVIDENCE_SHA256:
        raise SystemExit("pinned APC Wave199 evidence drift")
    apc_candidates = {row["external_id"]: row for row in read_csv(APC_CANDIDATES)}
    apc_evidence = {row["external_id"]: row for row in read_csv(APC_EVIDENCE)}
    registry = read_csv(REGISTRY)
    registry_by_title: dict[str, list[str]] = defaultdict(list)
    registry_names: list[tuple[str, str]] = []
    for row in registry:
        registry_by_title[norm(row["name"])].append(row["registry_id"])
        registry_names.append((row["registry_id"], norm(row["name"])))
    live = live_products()
    live_by_id = {row["external_id"]: row for row in live}
    if set(ids) - set(live_by_id):
        raise SystemExit("Wave215-A candidate missing from live DB")
    # Build guards once.  The previous nested scans would re-normalize the
    # complete 26k-row live catalogue for every candidate.
    live_identity_index: dict[str, list[str]] = defaultdict(list)
    for row in live:
        for value in (str(row.get("sku_normalized") or row.get("sku") or ""), str(row.get("mpn_normalized") or row.get("mpn") or "")):
            if (key := norm(value)):
                live_identity_index[key].append(row["external_id"])

    prepared = []
    for row in selected:
        kind = factual_type(row["name"])
        brand, model, family, status = title_identity(row["name"])
        if row["manufacturer_cluster"] == "APC" and brand != "APC":
            raise SystemExit(f"APC title identity drift: {row['product_external_id']}")
        prepared.append({**row, "kind": kind, "brand": brand, "model": model, "family": family, "manufacturer_status": status})
    if Counter(item["kind"] for item in prepared) != {"ups_system": 314, "dc_dc_power_converter": 33, "ac_dc_power_supply": 12}:
        raise SystemExit("Wave215-A factual type count drift")
    if any(item["kind"] not in {"ups_system", "dc_dc_power_converter", "ac_dc_power_supply"} for item in prepared):
        raise SystemExit("battery/electronics category leak")

    identity_index: dict[str, list[str]] = defaultdict(list)
    for item in prepared:
        identity_index[f"{norm(item['brand'])}::{norm(item['model'])}"].append(item["product_external_id"])
    evidence, live_checks, apc_exact = [], [], 0
    for item in prepared:
        external_id, title, model, brand, family = item["product_external_id"], item["name"], item["model"], item["brand"], item["family"]
        exact_title_dupes = sorted(peer for peer in registry_by_title[norm(title)] if peer != external_id)
        model_peers = sorted({registry_id for registry_id, registry_name in registry_names if registry_id != external_id and norm(model) in registry_name})
        current = live_by_id[external_id]
        normalized_model = norm(model)
        live_peers = sorted(peer for peer in live_identity_index.get(normalized_model, []) if peer != external_id)
        exact_apc = False
        source = apc_evidence.get(external_id)
        candidate = apc_candidates.get(external_id)
        if brand == "APC" and source and candidate:
            exact_apc = candidate["name"] == title and norm(candidate["model_token"]) == normalized_model and source["model_token"] == candidate["model_token"]
        if exact_apc:
            # Kept for future proofing: no Wave215 row currently qualifies,
            # and a source record cannot bypass duplicate/live guards.
            apc_exact += 1
        identity_peers = sorted(peer for peer in identity_index[f"{norm(brand)}::{normalized_model}"] if peer != external_id)
        partition = "primary_source_batch_hold"
        reason = "title_derived_brand_model_family_requires_exact_first_party_product_evidence"
        if brand == "APC":
            reason = "pinned_Wave199_APC_evidence_has_no_exact_external_ID_name_model_match_for_this_UPS"
        elif not brand:
            reason = "manufacturer_unresolved; first_party_catalogue_required_before_identity_claim"
        evidence.append({
            "batch": "wave215a_power", "product_external_id": external_id, "name": title, "category_external_id": item["category_external_id"], "source_cluster": item["manufacturer_cluster"], "factual_type": item["kind"],
            "manufacturer_candidate": brand, "manufacturer_status": item["manufacturer_status"], "model_candidate": model, "model_status": "title_derived_not_primary_verified", "family_group": family, "family_status": "title_derived_batch_route", "variant_group": f"{brand or 'unresolved'}::{family}", "duplicate_group": f"{brand or 'unresolved'}::{normalized_model}",
            "primary_manufacturer_source_route": route(brand, item["kind"]), "source_tier": "pinned_primary_nonmatching" if brand == "APC" else "", "source_publisher": "APC by Schneider Electric" if brand == "APC" else "", "source_url": "" if not exact_apc else source["source_url"], "source_snapshot_path": "" if not exact_apc else source["source_snapshot_path"], "source_snapshot_sha256": "" if not exact_apc else source["source_sha256"], "source_assertion": "Wave199 primary evidence retained only as exact-match gate" if brand == "APC" else "",
            "partition": partition, "conflict_reason": reason, "batch_duplicate_external_ids": "", "batch_duplicate_identity_external_ids": "|".join(identity_peers), "registry_exact_title_duplicates": "|".join(exact_title_dupes), "registry_model_candidate_external_ids": "|".join(model_peers), "live_db_collision_external_ids": "|".join(live_peers), "live_current_manufacturer": str(current.get("manufacturer") or ""), "live_current_mpn": str(current.get("mpn") or ""), "safe_to_apply": "false",
        })
        live_checks.append({"candidate_external_id": external_id, "title_model_normalized": normalized_model, "conflicting_external_ids": live_peers})

    if apc_exact or any(row["safe_to_apply"] == "true" for row in evidence):
        raise SystemExit("Wave215-A exact APC policy unexpectedly admitted a record")
    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader(); writer.writerows(evidence)
    MANIFEST.write_text(json.dumps({"schema_version": 1, "site_key": "microchips-by", "products": []}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest_hash = sha(MANIFEST)
    container_manifest = "/tmp/" + MANIFEST.name
    copied = subprocess.run(["docker", "compose", "cp", str(MANIFEST), "backend:" + container_manifest], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if copied.returncode:
        raise SystemExit(f"could not place disposable Laravel dry-run manifest: {copied.stderr.strip() or copied.stdout.strip()}")
    run = subprocess.run(["docker", "compose", "exec", "-T", "backend", "php", "artisan", "catalog:apply-verified-oem-identities", "microchips-by", container_manifest], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    dry = {"mode": "dry_run", "attempted_without_apply": True, "apply_flag_used": False, "exit_code": run.returncode, "records": 0, "manifest_sha256": manifest_hash, "stdout": run.stdout.strip(), "stderr": run.stderr.strip(), "expected_fail_closed_reason": "Manifest requires a non-empty products list.", "database_mutations": 0, "commercial_fields_changed": 0, "publication_fields_changed": 0}
    if run.returncode == 0 or "non-empty products list" not in (run.stdout + run.stderr):
        raise SystemExit("Laravel empty-manifest dry-run did not fail closed as expected")
    LIVE.write_text(json.dumps({"schema_version": 1, "mode": "read_only", "query_exit_code": 0, "database_mutations": 0, "candidate_rows_checked": len(evidence), "checks": live_checks}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    DRY.write_text(json.dumps(dry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    partitions = Counter(row["partition"] for row in evidence)
    write_report(evidence, apc_exact, dry)
    SUMMARY.write_text(json.dumps({
        "schema_version": 1, "batch": "wave215a_power", "checked_at": CHECKED_AT,
        "input": {"path": INPUT.relative_to(ROOT).as_posix(), "sha256": sha(INPUT), "rows": len(evidence), "cluster_counts": dict(sorted(Counter(row["source_cluster"] for row in evidence).items()))},
        "scope": {"ups_system_rows": sum(row["factual_type"] == "ups_system" for row in evidence), "dc_dc_power_converter_rows": sum(row["factual_type"] == "dc_dc_power_converter" for row in evidence), "ac_dc_power_supply_rows": sum(row["factual_type"] == "ac_dc_power_supply" for row in evidence), "battery_rows": 0, "electronics_component_rows": 0, "processed2500_overlap_ids": processed_overlap, "prior_evidence_overlap_ids": prior_overlap},
        "apc_pinned_evidence": {"candidate_sha256": sha(APC_CANDIDATES), "evidence_sha256": sha(APC_EVIDENCE), "exact_ID_name_model_matches": apc_exact, "reused_source_records": 0},
        "canonical_registry": {"path": REGISTRY.relative_to(ROOT).as_posix(), "sha256": sha(REGISTRY), "rows": len(registry), "exact_title_collision_rows": sum(bool(row["registry_exact_title_duplicates"]) for row in evidence), "model_candidate_collision_rows": sum(bool(row["registry_model_candidate_external_ids"]) for row in evidence)},
        "live_collision_guard": {"path": LIVE.relative_to(ROOT).as_posix(), "database_mutations": 0, "collision_rows": sum(bool(row["live_db_collision_external_ids"]) for row in evidence)},
        "partition_counts": dict(sorted(partitions.items())), "manifest": {"path": MANIFEST.relative_to(ROOT).as_posix(), "sha256": manifest_hash, "rows": 0}, "laravel_dry_run": {"path": DRY.relative_to(ROOT).as_posix(), "exit_code": run.returncode, "database_mutations": 0},
        "policy": {"UPS_not_electronic_component": True, "battery_characteristics_attached_to_device": False, "APC_evidence_exact_ID_name_model_only": True, "unresolved_large_families_batch_route": True, "exact_safe_manifest_only": True, "database_apply": False},
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"rows": len(evidence), "partitions": dict(partitions), "apc_exact": apc_exact, "database_mutations": 0}, ensure_ascii=False))


if __name__ == "__main__":
    main()
