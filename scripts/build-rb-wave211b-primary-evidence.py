#!/usr/bin/env python3
"""Build Wave211-B identity evidence from SHA-pinned manufacturer sources only.

This is deliberately a two-pass builder.  Run it with ``--provisional`` to
materialize the Delta acquisition list, acquire first-party pages, then build
the final manifest and Laravel dry-run.  The final run refuses an unmatched
dry-run receipt.  It never writes the application database.
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
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "docs/audits/generated"
INPUT = GEN / "rb-b2b-next-source-batch-wave210.csv"
REGISTRY = GEN / "full-catalog-canonical-registry.csv"
DELTA_EVIDENCE = GEN / "wave211b-delta-primary-evidence.csv"
DELTA_CANDIDATES = GEN / "wave211b-delta-primary-candidates.csv"
EXCLUSIONS = GEN / "wave211b-previous-evidence-and-scope-exclusions.csv"
LIVE = GEN / "wave211b-live-identity-collisions.json"
OUTPUT = GEN / "rb-wave211b-delta-fiamm-leoch-csb-evidence.csv"
SUMMARY = GEN / "rb-wave211b-delta-fiamm-leoch-csb-evidence.summary.json"
DRY_RUN = GEN / "wave211b-laravel-dry-run.json"
MANIFEST = ROOT / "docs/imports/rb-verified-oem-identities-wave211b-delta-2026-07-29.json"

EXPECTED = {"Delta": 66, "Fiamm": 43, "Leoch": 27, "CSB": 22}
CHECKED_AT = "2026-07-29"
DELTA_HOSTS = {"delta-batt.com", "www.delta-batt.com"}
FIELDS = [
    "batch", "product_external_id", "name", "manufacturer_cluster", "model_candidate",
    "partition", "source_tier", "source_publisher", "source_url", "source_assertion",
    "verified_facts", "snapshot_path", "snapshot_sha256", "conflict_reason",
    "duplicate_cluster_ids", "duplicate_decision", "safe_to_apply",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def norm(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", unicodedata.normalize("NFKC", value or "").upper())


def model_from_title(name: str, brand: str) -> str:
    match = re.search(rf"\b{re.escape(brand)}\b\s+(.+?)(?:\s*\(|$)", name, re.I)
    return match.group(1).strip() if match else ""


def title_capacity(name: str) -> str:
    match = re.search(r"\(AGM,\s*([0-9]+(?:[.,][0-9]+)?)Ah\)", name, re.I)
    return match.group(1).replace(",", ".") if match else ""


def is_out_of_scope(row: dict[str, str]) -> str:
    haystack = " ".join(row.get(key, "") for key in ("name", "category_key", "series_bucket"))
    if re.search(r"автомоб|starter|starting|cranking|мото", haystack, re.I):
        return "automotive_or_starter"
    # Cardioline/ECG are medical battery assemblies.  They remain catalogue
    # candidates and are held on a specialist/OEM device route below; only
    # actual electronic-component scope is excluded here.
    if re.search(r"электрон", haystack, re.I):
        return "electronics_component"
    return ""


def is_medical_oem_device_pack(row: dict[str, str]) -> bool:
    return bool(re.search(r"Cardioline|\bECG\b", row.get("name", ""), re.I))


def prior_evidence_ids() -> tuple[set[str], list[str]]:
    """Return every earlier generated evidence ID plus prior OEM manifests.

    The search intentionally does not use a hand-maintained wave list: a new
    prior evidence wave cannot silently become eligible for this batch.
    """
    found: set[str] = set()
    files: list[str] = []
    for path in sorted(GEN.glob("*evidence*.csv")):
        # Wave211-B's own prior provisional artefacts are not a previous
        # evidence wave.  Including them would make a second builder run
        # silently shrink the source set.
        if path == OUTPUT or path.name.startswith("wave211b-"):
            continue
        rows = read_csv(path)
        ids = {row.get("product_external_id") or row.get("external_id") or "" for row in rows}
        ids.discard("")
        if ids:
            found.update(ids)
            files.append(path.relative_to(ROOT).as_posix())
    for path in sorted((ROOT / "docs/imports").glob("rb-verified-oem-identities-wave*.json")):
        if path == MANIFEST:
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
            ids = {str(row.get("external_id") or "") for row in payload.get("products", [])}
        except (OSError, ValueError, AttributeError):
            continue
        ids.discard("")
        if ids:
            found.update(ids)
            files.append(path.relative_to(ROOT).as_posix())
    return found, files


def model_pattern(model: str) -> re.Pattern[str]:
    chars = [re.escape(char) for char in unicodedata.normalize("NFKC", model).upper() if char.isalnum()]
    return re.compile(r"(?<![A-Z0-9])" + r"[\s,._/-]*".join(chars) + r"(?![A-Z0-9])", re.I)


def official_delta_sources(eligible_ids: set[str]) -> dict[str, dict[str, str]]:
    if not DELTA_EVIDENCE.is_file():
        return {}
    sources: dict[str, dict[str, str]] = {}
    for row in read_csv(DELTA_EVIDENCE):
        external_id = row.get("external_id") or ""
        if external_id not in eligible_ids:
            raise SystemExit(f"Delta evidence has non-eligible ID: {external_id}")
        if external_id in sources:
            raise SystemExit(f"Delta evidence repeats ID: {external_id}")
        parsed = urlparse(row.get("source_url") or "")
        if parsed.scheme != "https" or (parsed.hostname or "").casefold() not in DELTA_HOSTS:
            raise SystemExit(f"Delta source is not an allowlisted manufacturer HTTPS URL: {external_id}")
        snapshot = ROOT / (row.get("source_snapshot_path") or "")
        if not snapshot.is_file() or sha256(snapshot) != row.get("source_sha256"):
            raise SystemExit(f"Delta source snapshot pin mismatch: {external_id}")
        if row.get("evidence_kind") != "exact_product_page" or row.get("publisher") != "DELTA Battery / ENERGON":
            raise SystemExit(f"Delta source is not an exact first-party product page: {external_id}")
        sources[external_id] = row
    return sources


def live_products() -> list[dict[str, str]]:
    php = (
        "$r=app('db')->table('products')->select('external_id','name','sku','manufacturer','mpn','sku_normalized','mpn_normalized','status')"
        "->orderBy('external_id')->get();echo json_encode($r,JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES);"
    )
    encoded = base64.b64encode(php.encode()).decode()
    proc = subprocess.run(
        ["docker", "compose", "exec", "-T", "backend", "php", "artisan", "tinker", f"--execute=eval(base64_decode('{encoded}'));"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )
    payload = proc.stdout.strip()
    if proc.returncode or not payload.startswith("["):
        raise SystemExit(f"read-only live PostgreSQL query failed: {payload or proc.stderr.strip()}")
    result = json.loads(payload)
    if len({row["external_id"] for row in result}) != len(result):
        raise SystemExit("live PostgreSQL repeats external_id")
    return result


def write_delta_candidates(rows: list[dict[str, str]]) -> None:
    # A product title that merely names a Delta-powered medical device must
    # not be guessed into the Delta stationary-battery product URL grammar.
    Delta = [row for row in rows if row["manufacturer_cluster"] == "Delta" and not is_medical_oem_device_pack(row)]
    fields = ["external_id", "model_candidate_unverified", "safe_to_apply"]
    with DELTA_CANDIDATES.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows({"external_id": row["product_external_id"], "model_candidate_unverified": model_from_title(row["name"], "Delta"), "safe_to_apply": "false"} for row in Delta)
    models = [model_from_title(row["name"], "Delta") for row in Delta]
    if not all(models) or len(models) != len(set(map(norm, models))):
        raise SystemExit("Wave211-B Delta acquisition candidates require unique exact title models")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provisional", action="store_true", help="Allow the acquisition phase before a matching Laravel receipt exists.")
    args = parser.parse_args()

    source = read_csv(INPUT)
    selected = [row for row in source if row.get("manufacturer_cluster") in EXPECTED]
    original_counts = Counter(row["manufacturer_cluster"] for row in selected)
    ids = [row["product_external_id"] for row in selected]
    if original_counts != Counter(EXPECTED) or len(selected) != 158 or len(ids) != len(set(ids)):
        raise SystemExit(f"Wave211-B source union drift: rows={len(selected)}, counts={dict(original_counts)}")

    previous, prior_files = prior_evidence_ids()
    exclusions = []
    eligible = []
    for row in selected:
        external_id = row["product_external_id"]
        if external_id in previous:
            exclusions.append({"product_external_id": external_id, "name": row["name"], "manufacturer_cluster": row["manufacturer_cluster"], "reason": "previous_evidence_wave"})
        elif reason := is_out_of_scope(row):
            exclusions.append({"product_external_id": external_id, "name": row["name"], "manufacturer_cluster": row["manufacturer_cluster"], "reason": reason})
        else:
            eligible.append(row)
    with EXCLUSIONS.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["product_external_id", "name", "manufacturer_cluster", "reason"], lineterminator="\n")
        writer.writeheader(); writer.writerows(exclusions)
    exclusion_ids = {row["product_external_id"] for row in exclusions}
    if any(row["product_external_id"] in previous for row in eligible) or len(exclusion_ids) != len(exclusions):
        raise SystemExit("Wave211-B no-repeat exclusion invariant failed")
    write_delta_candidates(eligible)

    delta_sources = official_delta_sources({row["product_external_id"] for row in eligible})
    registry = read_csv(REGISTRY)
    registry_peers: dict[str, list[str]] = {}
    exact_ids = set(delta_sources)
    for row in eligible:
        external_id = row["product_external_id"]
        if external_id not in exact_ids:
            continue
        model = model_from_title(row["name"], "Delta")
        pattern = model_pattern(model)
        registry_peers[external_id] = sorted({
            item["registry_id"] for item in registry
            if item["registry_id"] != external_id and re.search(r"\bDelta\b", item.get("name", ""), re.I) and pattern.search(item.get("name", "").upper())
        })

    products = live_products()
    live_by_id = {str(row["external_id"]): row for row in products}
    missing_or_renamed = [row["product_external_id"] for row in eligible if row["product_external_id"] not in live_by_id or str(live_by_id[row["product_external_id"]].get("name") or "") != row["name"]]
    if missing_or_renamed:
        raise SystemExit(f"Live candidate ID/name mismatch: {missing_or_renamed}")
    live_collisions: dict[str, list[str]] = defaultdict(list)
    for external_id, source_row in delta_sources.items():
        model = source_row["model"]
        needle = norm(model)
        pattern = model_pattern(model)
        for product in products:
            if product["external_id"] == external_id:
                continue
            sku = norm(str(product.get("sku_normalized") or product.get("sku") or ""))
            mpn = norm(str(product.get("mpn_normalized") or product.get("mpn") or ""))
            title_match = re.search(r"\bDelta\b", str(product.get("name") or ""), re.I) and bool(pattern.search(str(product.get("name") or "").upper()))
            if needle and (needle in {sku, mpn} or title_match):
                live_collisions[external_id].append(str(product["external_id"]))
    live_payload = {
        "schema_version": 1, "checked_at": CHECKED_AT, "mode": "read_only", "query_exit_code": 0,
        "database": "current Docker PostgreSQL", "normalizer": "App\\Domain\\Imports\\ProductIdentity::normalize",
        "query_rule": "candidate normalized MPN equals another product SKU/MPN or exact Delta title model",
        "candidate_rows_checked": len(delta_sources), "candidate_external_ids": sorted(delta_sources),
        "candidate_mpn_normalized": {external_id: norm(source["model"]) for external_id, source in sorted(delta_sources.items())},
        "collisions": [{"candidate_external_id": external_id, "conflicting_external_ids": sorted(set(peers))} for external_id, peers in sorted(live_collisions.items())],
        "database_mutations": 0,
    }
    LIVE.write_text(json.dumps(live_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    output = []
    for row in eligible:
        external_id, brand = row["product_external_id"], row["manufacturer_cluster"]
        model = model_from_title(row["name"], brand)
        partition, tier, publisher, url, assertion, facts, snap, digest, reason = (
            "no_evidence", "none", "", "", "", "", "", "", "No SHA-pinned manufacturer-primary exact-model source is available."
        )
        peers: list[str] = []
        if is_medical_oem_device_pack(row):
            reason = "Medical specialist/OEM device battery route required; no exact SHA-pinned manufacturer-primary pack identity evidence is available."
        elif brand == "Delta" and external_id in delta_sources:
            source_row = delta_sources[external_id]
            exact_model = source_row["model"]
            capacity_ok = title_capacity(row["name"]) == source_row["capacity_ah"]
            exact_model_ok = norm(model) == norm(exact_model)
            tier, publisher, url = "manufacturer_primary", source_row["publisher"], source_row["source_url"]
            assertion = "exact_model_in_pinned_first_party_product_page"
            facts = f"manufacturer=Delta|mpn={exact_model}|voltage_v={source_row['voltage_v']}|capacity_ah={source_row['capacity_ah']}"
            snap, digest = source_row["source_snapshot_path"], source_row["source_sha256"]
            peers = sorted(set(registry_peers.get(external_id, []) + live_collisions.get(external_id, [])))
            if not exact_model_ok or not capacity_ok:
                partition = "conflict"
                reason = f"Pinned manufacturer page is {exact_model} / {source_row['capacity_ah']}Ah; legacy title is {model} / {title_capacity(row['name']) or '?'}Ah."
            elif peers:
                partition = "conflict"
                reason = "Full registry or live PostgreSQL identity collision blocks apply."
            else:
                partition, reason = "exact", ""
        elif brand == "Fiamm":
            reason = "Pinned FIAMM material is distributor evidence, not manufacturer-primary; rejected for identity promotion."
        elif brand == "Leoch":
            reason = "No SHA-pinned Leoch manufacturer-primary exact-model page or catalogue is available."
        elif brand == "CSB":
            reason = "No SHA-pinned CSB manufacturer-primary exact-model page or catalogue is available."
        safe = partition == "exact"
        output.append({
            "batch": "wave211b_delta_fiamm_leoch_csb", "product_external_id": external_id, "name": row["name"],
            "manufacturer_cluster": brand, "model_candidate": model, "partition": partition, "source_tier": tier,
            "source_publisher": publisher, "source_url": url, "source_assertion": assertion, "verified_facts": facts,
            "snapshot_path": snap, "snapshot_sha256": digest, "conflict_reason": reason,
            "duplicate_cluster_ids": "|".join(peers), "duplicate_decision": "hold_registry_or_live_collision" if peers else "unique_exact_identity" if safe else "not_applicable",
            "safe_to_apply": "true" if safe else "false",
        })
    with OUTPUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader(); writer.writerows(output)
    manifest_rows = [{
        "external_id": row["product_external_id"], "current_name": row["name"], "manufacturer": "Delta", "mpn": row["model_candidate"],
        "source_url": row["source_url"], "source_kind": "official_manufacturer_product_page", "source_publisher": row["source_publisher"],
        "checked_at": CHECKED_AT, "product_type": "stationary sealed rechargeable battery",
        "source_snapshot_path": (Path("../audits") / Path(row["snapshot_path"]).relative_to("docs/audits")).as_posix(), "source_snapshot_sha256": row["snapshot_sha256"],
    } for row in output if row["safe_to_apply"] == "true"]
    MANIFEST.write_text(json.dumps({"schema_version": 1, "site_key": "microchips-by", "products": manifest_rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    dry_run_verified = False
    if DRY_RUN.is_file():
        dry = json.loads(DRY_RUN.read_text(encoding="utf-8-sig"))
        dry_run_verified = (dry.get("mode") == "dry_run" and dry.get("exit_code") == 0 and dry.get("records") == len(manifest_rows)
            and dry.get("manifest_sha256") == sha256(MANIFEST) and dry.get("commercial_fields_changed") == 0
            and dry.get("publication_fields_changed") == 0 and dry.get("database_mutations") == 0)
    if not args.provisional and (not manifest_rows or not dry_run_verified):
        raise SystemExit("Wave211-B requires a nonempty exact-safe manifest with a matching successful Laravel dry-run receipt")
    parts = Counter(row["partition"] for row in output)
    summary = {
        "schema_version": 1, "batch": "wave211b_delta_fiamm_leoch_csb", "checked_at": CHECKED_AT,
        "input": {"path": INPUT.relative_to(ROOT).as_posix(), "sha256": sha256(INPUT), "rows": len(selected), "manufacturer_counts": dict(sorted(original_counts.items()))},
        "previous_evidence_exclusion": {"files": prior_files, "rows": sum(item["reason"] == "previous_evidence_wave" for item in exclusions), "external_ids": sorted(item["product_external_id"] for item in exclusions if item["reason"] == "previous_evidence_wave")},
        "scope_exclusion": {"automotive_or_starter_rows": sum(item["reason"] == "automotive_or_starter" for item in exclusions), "electronics_component_rows": sum(item["reason"] == "electronics_component" for item in exclusions), "artifact": EXCLUSIONS.relative_to(ROOT).as_posix()},
        "medical_oem_device_holds": {"rows": sum(is_medical_oem_device_pack(row) for row in eligible), "external_ids": sorted(row["product_external_id"] for row in eligible if is_medical_oem_device_pack(row))},
        "eligible": {"rows": len(eligible), "manufacturer_counts": dict(sorted(Counter(row["manufacturer_cluster"] for row in eligible).items()))},
        "delta_acquisition_candidates": {"path": DELTA_CANDIDATES.relative_to(ROOT).as_posix(), "sha256": sha256(DELTA_CANDIDATES), "rows": sum(row["manufacturer_cluster"] == "Delta" and not is_medical_oem_device_pack(row) for row in eligible)},
        "canonical_registry": {"path": REGISTRY.relative_to(ROOT).as_posix(), "sha256": sha256(REGISTRY), "rows": len(registry)},
        "live_collision_guard": {"path": LIVE.relative_to(ROOT).as_posix(), "sha256": sha256(LIVE), "candidate_rows_checked": len(delta_sources), "collision_rows": len(live_payload["collisions"])},
        "output": {"path": OUTPUT.relative_to(ROOT).as_posix(), "sha256": sha256(OUTPUT), "rows": len(output)}, "partition_counts": dict(sorted(parts.items())),
        "safe_to_apply": {"rows": len(manifest_rows), "external_ids": [row["external_id"] for row in manifest_rows]},
        "manifest": {"path": MANIFEST.relative_to(ROOT).as_posix(), "sha256": sha256(MANIFEST), "rows": len(manifest_rows), "laravel_dry_run_verified": dry_run_verified},
        "laravel_dry_run": {"path": DRY_RUN.relative_to(ROOT).as_posix(), "sha256": sha256(DRY_RUN) if DRY_RUN.is_file() else "", "verified": dry_run_verified},
        "policy": {"manufacturer_primary_only_for_manifest": True, "official_distributor_rejected": True, "full_registry_and_live_collision_guards": True, "automotive_starter_electronics_excluded": True, "database_mutations": 0},
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"source_rows": len(selected), "eligible": len(eligible), "partitions": dict(parts), "manifest": len(manifest_rows), "dry_run_verified": dry_run_verified}, ensure_ascii=False))


if __name__ == "__main__":
    main()
