#!/usr/bin/env python3
"""Build official-source evidence and an exact-only identity manifest for Wave209-A."""
from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import re
import subprocess
import unicodedata
from urllib.parse import urlparse
from collections import Counter, defaultdict
from pathlib import Path

from pypdf import PdfReader


TARGETS = {"APC": 77, "EnerSys": 42, "Sonnenschein": 44}
EXPECTED_SOURCE_FILES = {
    "enersys-cyclon-selection-guide.pdf", "enersys-cyclon-us-selection-guide.pdf",
    "enersys-powersafe-v-range.pdf", "exide-sonnenschein-a400.pdf",
    "exide-sonnenschein-a500.pdf", "exide-sonnenschein-a600.pdf",
    "exide-sonnenschein-a600-solar.pdf", "exide-sonnenschein-a700.pdf",
    "exide-sonnenschein-solar-block.pdf",
}
# ModelCoreIdentityMatcher sees the APC prefix in an attached APCRBC token
# first, rejects its unapproved attached suffix, and does not advance to the
# later standalone "APC" token.  These are exact source identities but cannot
# pass Laravel's bounded-name contract, so they remain fail-closed.
LARAVEL_MATCHER_HOLDS = {"bitrix:23785", "bitrix:23786", "bitrix:23821"}
FIELDS = [
    "product_external_id", "manufacturer_cluster", "name", "model_token", "partition",
    "source_tier", "source_publisher", "source_url", "source_snapshot_path",
    "source_snapshot_sha256", "evidence_scope", "verified_facts", "conflict_reason",
    "full_registry_collision_count", "full_registry_collision_external_ids",
    "live_manufacturer", "live_mpn", "safe_to_apply",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "").upper()
    return re.sub(r"[^A-Z0-9]", "", value)


def legacy_capacity(name: str) -> float | None:
    match = re.search(r"(\d+(?:[.,]\d+)?)\s*AH\b", name, re.I)
    return float(match.group(1).replace(",", ".")) if match else None


def model_token(name: str, brand: str) -> str:
    upper = unicodedata.normalize("NFKC", name).upper()
    if brand == "APC":
        patterns = (
            r"\bAPCRBC\d+\b", r"\bRBC\d+\b", r"\bSYBT(?:5|U[12]-PLP)\b",
            r"\b(?:BR24BPG|SMX120BP|SMX120RMBP2U|SMX48RMBP2U|SRT192RMBP2?|SRT48(?:BP|RMBP)|SRT72(?:BP|RMBP)|SRT96(?:BP|RMBP)|SRV72RLBP-9A|SU24R2XLBP|SUA24XLBP|SUA48RMXLBP3U|SUA48XLBP|SUM48RMXLBP2U|SURT192RMXLBP2|SURT192XLBP|SURT48RMXLBP|SURT48XLBP|UXABP48|XBP48RM1U-LI)\b",
        )
        hits = [m.group(0) for pattern in patterns for m in re.finditer(pattern, upper)]
        hits = list(dict.fromkeys(hits))
        if len(hits) == 1:
            # APCRBC133 is a literal APC part number, not a decorative brand
            # prefix.  Keeping it also makes the bounded Laravel matcher and
            # the pinned Wave199 candidate identity agree.
            return hits[0]
        return ""
    if brand == "EnerSys":
        match = re.search(r"\b(?:\dX)?\d{4}-\d{4}[A-Z]?\b|\b12V70\b", upper)
        return match.group(0) if match else "DT CELL" if "CYCLON DT CELL" in upper else ""
    match = re.search(
        r"\b(?:A\d{3}/\d+(?:[.,]\d+)?(?:\s*(?:F10|G5|SR|FT|A|S|C))?|(?:SB|S)\s*12/\d+(?:\s*A)?)\b",
        upper,
    )
    return re.sub(r"\s+", " ", match.group(0)).strip() if match else ""


def query_products(root: Path) -> list[dict]:
    php = (
        "$r=app('db')->table('products')->select('external_id','name','sku','manufacturer','mpn','sku_normalized','mpn_normalized','status')"
        "->orderBy('external_id')->get();"
        "echo json_encode($r,JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES);"
    )
    encoded = base64.b64encode(php.encode()).decode()
    process = subprocess.run(
        ["docker", "compose", "exec", "-T", "backend", "php", "artisan", "tinker", f"--execute=eval(base64_decode('{encoded}'));"],
        cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )
    payload = process.stdout.strip()
    if process.returncode or not payload.startswith("["):
        raise SystemExit(f"live PostgreSQL query failed: {payload or process.stderr.strip()}")
    return json.loads(payload)


def canonical_claims(rows: list[dict[str, str]]) -> dict[tuple[str, str], list[str]]:
    """Index the complete immutable canonical registry by bounded brand/model identity."""
    claimed: dict[tuple[str, str], list[str]] = defaultdict(list)
    for row in rows:
        name = row.get("name") or ""
        for brand in TARGETS:
            if brand.upper() not in name.upper() and not (brand == "APC" and re.search(r"\bRBC\d+\b", name, re.I)):
                continue
            token = model_token(name, brand)
            if token:
                claimed[(brand.casefold(), normalize(token))].append(row["registry_id"])
    return claimed


def product_identity_normalize(value: str) -> str:
    """Match App\\Domain\\Imports\\ProductIdentity::normalize for MPNs."""
    return re.sub(r"[\W_]", "", (value or "").casefold(), flags=re.UNICODE)


def extract_pdf(path: Path) -> str:
    return "\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--source-batch", type=Path, required=True)
    parser.add_argument("--source-registry", type=Path, required=True)
    parser.add_argument("--apc-candidates", type=Path, required=True)
    parser.add_argument("--apc-evidence", type=Path, required=True)
    parser.add_argument("--apc-registry", type=Path, required=True)
    parser.add_argument("--canonical-registry", type=Path, required=True)
    parser.add_argument("--live-guard", type=Path, required=True)
    parser.add_argument("--dry-run", type=Path, required=True)
    parser.add_argument("--provisional", action="store_true", help="Build before the Laravel dry-run record exists.")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()

    selected = [row for row in read_csv(args.source_batch) if row["manufacturer_cluster"] in TARGETS]
    counts = Counter(row["manufacturer_cluster"] for row in selected)
    if counts != Counter(TARGETS) or len({row["product_external_id"] for row in selected}) != 163:
        raise SystemExit(f"Wave209-A union mismatch: {dict(counts)}")

    apc_candidates = read_csv(args.apc_candidates)
    apc_selected = {row["product_external_id"]: row for row in selected if row["manufacturer_cluster"] == "APC"}
    apc_candidate_by_id = {row["external_id"]: row for row in apc_candidates}
    if set(apc_candidate_by_id) != set(apc_selected):
        raise SystemExit("Wave209-A APC set differs from pinned Wave199")
    for external_id, candidate in apc_selected.items():
        pinned = apc_candidate_by_id[external_id]
        if pinned["name"] != candidate["name"] or pinned["model_token"] != model_token(candidate["name"], "APC"):
            raise SystemExit(f"Wave209-A APC name/model identity differs from pinned Wave199: {external_id}")
    if {row["external_id"] for row in apc_candidates} != {
        row["product_external_id"] for row in selected if row["manufacturer_cluster"] == "APC"
    }:
        raise SystemExit("Wave209-A APC set differs from pinned Wave199")
    apc_evidence = {row["external_id"]: row for row in read_csv(args.apc_evidence)}
    apc_registry = {row["external_id"]: row for row in read_csv(args.apc_registry)}

    source_registry = json.loads(args.source_registry.read_text(encoding="utf-8"))
    sources = {row["filename"]: row for row in source_registry}
    if set(sources) != EXPECTED_SOURCE_FILES or len(sources) != len(source_registry):
        raise SystemExit("Wave209-A primary source registry drifted")
    pdf_text = {}
    for filename, row in sources.items():
        host = urlparse(row["source_url"]).hostname or ""
        if not row["source_url"].startswith("https://") or host not in {"www.enersys.com", "www.exidegroup.com"}:
            raise SystemExit(f"non-primary Wave209-A source: {filename}")
        path = args.root / "docs" / row["snapshot_path"]
        if not path.is_file() or sha256(path) != row["sha256"]:
            raise SystemExit(f"source snapshot mismatch: {filename}")
        pdf_text[filename] = normalize(extract_pdf(path))

    canonical = read_csv(args.canonical_registry)
    registry_claimed = canonical_claims(canonical)
    database = query_products(args.root)
    db_by_id = {row["external_id"]: row for row in database}
    if len(db_by_id) != len(database):
        raise SystemExit("live product registry repeats external_id")
    output_rows = []
    manifest_rows = []
    for candidate in selected:
        external_id = candidate["product_external_id"]
        brand = candidate["manufacturer_cluster"]
        name = candidate["name"]
        token = model_token(name, brand)
        partition = "no_evidence"
        publisher = ""
        source_url = ""
        snapshot_path = ""
        snapshot_sha = ""
        evidence_scope = ""
        verified_facts = ""
        reason = "exact_model_absent_from_pinned_official_sources"

        if brand == "APC":
            evidence = apc_evidence.get(external_id)
            registry = apc_registry[external_id]
            if evidence:
                source_url = evidence["source_url"]
                snapshot = Path(evidence["source_snapshot_path"])
                if not snapshot.is_file() or sha256(snapshot) != evidence["source_sha256"]:
                    raise SystemExit(f"APC snapshot mismatch: {external_id}")
                snapshot_path = "../audits/sources/apc-wave199/" + snapshot.name
                snapshot_sha = evidence["source_sha256"]
                publisher = "APC by Schneider Electric"
                evidence_scope = "exact_official_product_page"
                verified_facts = "exact_model"
                legacy_ah = legacy_capacity(name)
                official_ah = float(evidence["capacity_ah"]) if evidence["capacity_ah"] else None
                if legacy_ah and official_ah and abs(legacy_ah - official_ah) > max(0.2, official_ah * 0.03):
                    partition = "conflict"
                    reason = f"legacy_capacity_{legacy_ah:g}Ah_conflicts_official_{official_ah:g}Ah"
                else:
                    partition = "exact_safe"
                    reason = ""
            else:
                source_url = registry["requested_url"]
                reason = registry["hold_reason"] or "official_page_has_no_exact_product_evidence"
                if registry["snapshot_path"]:
                    snapshot = Path(registry["snapshot_path"])
                    if not snapshot.is_file() or sha256(snapshot) != registry["source_sha256"]:
                        raise SystemExit(f"APC hold snapshot mismatch: {external_id}")
                    snapshot_path = "../audits/sources/apc-wave199/" + snapshot.name
                    snapshot_sha = registry["source_sha256"]
                    publisher = "APC by Schneider Electric"
        elif brand == "EnerSys":
            if token == "DT CELL":
                filename = "enersys-cyclon-selection-guide.pdf"
                partition = "compatibility"
                reason = "official_family_specs_do_not_prove_a_unique_saleable_part_number"
                evidence_scope = "official_family_model_only"
            elif token == "12V70":
                filename = "enersys-powersafe-v-range.pdf"
                partition = "exact_safe" if normalize(token) in pdf_text[filename] else "no_evidence"
                reason = "" if partition == "exact_safe" else reason
                evidence_scope = "exact_official_catalogue_model" if partition == "exact_safe" else ""
            else:
                filename = next((f for f in ("enersys-cyclon-selection-guide.pdf", "enersys-cyclon-us-selection-guide.pdf") if normalize(token) in pdf_text[f]), "enersys-cyclon-selection-guide.pdf")
                partition = "exact_safe" if normalize(token) in pdf_text[filename] else "no_evidence"
                reason = "" if partition == "exact_safe" else reason
                evidence_scope = "exact_official_catalogue_part_number" if partition == "exact_safe" else ""
            source = sources[filename]
            publisher = "EnerSys"
            source_url = source["source_url"]
            snapshot_path = "../audits/sources/wave209a/" + filename
            snapshot_sha = source["sha256"]
            verified_facts = "exact_part_number" if partition == "exact_safe" else "family_only" if partition == "compatibility" else ""
        else:
            upper = name.upper()
            if token.startswith("A4"):
                filename = "exide-sonnenschein-a400.pdf"
            elif token.startswith("A5"):
                filename = "exide-sonnenschein-a500.pdf"
            elif token.startswith("A7"):
                filename = "exide-sonnenschein-a700.pdf"
            elif token.startswith("SB") or token.startswith("S 12"):
                filename = "exide-sonnenschein-solar-block.pdf"
            elif "SOLAR" in upper:
                filename = "exide-sonnenschein-a600-solar.pdf"
            else:
                filename = "exide-sonnenschein-a600.pdf"
            present = bool(token and normalize(token) in pdf_text[filename])
            base_present = False
            if not present and "SOLAR" in upper:
                base = re.sub(r"\s+SOLAR\b", "", token, flags=re.I)
                base_present = bool(base and normalize(base) in pdf_text["exide-sonnenschein-a600.pdf"])
            partition = "exact_safe" if present else "compatibility" if base_present else "no_evidence"
            reason = "" if present else "official_standard_model_found_but_solar_variant_not_proven" if base_present else reason
            source = sources[filename]
            publisher = "Exide Technologies / Sonnenschein"
            source_url = source["source_url"]
            snapshot_path = "../audits/sources/wave209a/" + filename
            snapshot_sha = source["sha256"]
            evidence_scope = "exact_official_catalogue_model" if present else "official_base_model_only" if base_present else ""
            verified_facts = "exact_model|dryfit_gel_vrla" if present else "base_model" if base_present else ""

        collision_ids = sorted(value for value in registry_claimed.get((brand.casefold(), normalize(token)), []) if value != external_id) if token else []
        if collision_ids:
            partition = "conflict"
            reason = "full_registry_identity_collision"
        live = db_by_id.get(external_id)
        if live is None:
            raise SystemExit(f"candidate absent from live PostgreSQL: {external_id}")
        output_rows.append({
            "product_external_id": external_id, "manufacturer_cluster": brand, "name": name,
            "model_token": token, "partition": partition, "source_tier": "manufacturer_primary" if source_url else "",
            "source_publisher": publisher, "source_url": source_url,
            "source_snapshot_path": snapshot_path, "source_snapshot_sha256": snapshot_sha,
            "evidence_scope": evidence_scope, "verified_facts": verified_facts,
            "conflict_reason": reason, "full_registry_collision_count": len(collision_ids),
            "full_registry_collision_external_ids": "|".join(collision_ids),
            "live_manufacturer": str(live.get("manufacturer") or ""), "live_mpn": str(live.get("mpn") or ""),
            "safe_to_apply": "true" if partition == "exact_safe" else "false",
        })
        if partition == "exact_safe":
            manifest_rows.append({
                "external_id": external_id, "current_name": name, "manufacturer": brand,
                "mpn": token, "source_url": source_url,
                "source_kind": "official_manufacturer_product_page" if brand == "APC" else "official_manufacturer_catalogue",
                "source_publisher": publisher, "checked_at": "2026-07-29", "product_type": "Battery",
                "source_snapshot_path": snapshot_path, "source_snapshot_sha256": snapshot_sha,
            })

    # Laravel pins the current product name.  A legacy batch title that has
    # drifted in PostgreSQL must never be passed through merely because its
    # model token happens to be exact.
    for row in output_rows:
        live = db_by_id[row["product_external_id"]]
        if row["partition"] == "exact_safe" and str(live.get("name") or "") != row["name"]:
            row["partition"] = "conflict"
            row["conflict_reason"] = "live_current_name_drift"
            row["safe_to_apply"] = "false"
        if row["partition"] == "exact_safe" and row["product_external_id"] in LARAVEL_MATCHER_HOLDS:
            row["partition"] = "conflict"
            row["conflict_reason"] = "laravel_bounded_name_matcher_conflict"
            row["safe_to_apply"] = "false"

    # The canonical registry is a static broad collision guard.  This second
    # guard proves the same normalized MPN cannot collide with a *current*
    # product SKU or MPN just before the Laravel dry-run.
    pre_live_safe = [row for row in output_rows if row["partition"] == "exact_safe"]
    live_collisions = []
    for row in pre_live_safe:
        candidate_mpn = product_identity_normalize(row["model_token"])
        matches = []
        for live_row in database:
            if live_row["external_id"] == row["product_external_id"]:
                continue
            sku = str(live_row.get("sku_normalized") or product_identity_normalize(str(live_row.get("sku") or "")))
            mpn = str(live_row.get("mpn_normalized") or product_identity_normalize(str(live_row.get("mpn") or "")))
            if candidate_mpn and candidate_mpn in {sku, mpn}:
                matches.append(live_row["external_id"])
        if matches:
            row["partition"] = "conflict"
            row["conflict_reason"] = "live_product_identity_collision"
            row["safe_to_apply"] = "false"
            live_collisions.append({
                "candidate_external_id": row["product_external_id"],
                "candidate_mpn_normalized": candidate_mpn,
                "conflicting_external_ids": sorted(matches),
            })
    safe_ids = {row["product_external_id"] for row in output_rows if row["safe_to_apply"] == "true"}
    manifest_rows = [row for row in manifest_rows if row["external_id"] in safe_ids]
    normalized_manifest_mpns = [product_identity_normalize(row["mpn"]) for row in manifest_rows]
    if len(set(normalized_manifest_mpns)) != len(normalized_manifest_mpns):
        raise SystemExit("Wave209-A exact-safe manifest repeats a normalized MPN")

    live_guard = {
        "schema_version": 1,
        "site": "microchips-by",
        "checked_at": "2026-07-29",
        "database": "current Docker PostgreSQL",
        "normalizer": "App\\Domain\\Imports\\ProductIdentity::normalize",
        "query_rule": "candidate normalized MPN equals another product sku_normalized or mpn_normalized",
        "query_exit_code": 0,
        "candidate_rows_checked": len(pre_live_safe),
        "candidate_external_ids": [row["product_external_id"] for row in pre_live_safe],
        "candidate_mpn_normalized": [product_identity_normalize(row["model_token"]) for row in pre_live_safe],
        "collisions": live_collisions,
        "database_mutations": 0,
    }
    args.live_guard.parent.mkdir(parents=True, exist_ok=True)
    args.live_guard.write_text(json.dumps(live_guard, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader(); writer.writerows(output_rows)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps({"schema_version": 1, "site_key": "microchips-by", "products": manifest_rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    dry_run_verified = False
    if args.dry_run.is_file():
        dry_run = json.loads(args.dry_run.read_text(encoding="utf-8-sig"))
        dry_run_verified = (
            dry_run.get("mode") == "dry_run"
            and dry_run.get("exit_code") == 0
            and dry_run.get("records") == len(manifest_rows)
            and dry_run.get("manifest_sha256") == sha256(args.manifest)
            and dry_run.get("commercial_fields_changed") == 0
            and dry_run.get("publication_fields_changed") == 0
            and dry_run.get("database_mutations") == 0
        )
    if not args.provisional and not dry_run_verified:
        raise SystemExit("Wave209-A manifest lacks a matching successful Laravel dry-run record")

    partitions = Counter(row["partition"] for row in output_rows)
    summary = {
        "schema_version": 1, "wave": "wave209a", "candidate_records": len(output_rows),
        "brand_counts": dict(sorted(counts.items())), "partition_counts": dict(sorted(partitions.items())),
        "exact_safe_records": len(manifest_rows), "manifest_records": len(manifest_rows),
        "canonical_registry": {"path": str(args.canonical_registry).replace("\\", "/"), "sha256": sha256(args.canonical_registry), "records": len(canonical)},
        "full_registry_collision_candidates": sum(int(row["full_registry_collision_count"]) > 0 for row in output_rows),
        "live_collision_guard": {"path": str(args.live_guard).replace("\\", "/"), "sha256": sha256(args.live_guard), "candidate_rows_checked": len(pre_live_safe), "collision_rows": len(live_collisions)},
        "live_candidate_records": sum(row["product_external_id"] in db_by_id for row in output_rows),
        "live_manufacturer_records": sum(bool(row["live_manufacturer"]) for row in output_rows),
        "live_mpn_records": sum(bool(row["live_mpn"]) for row in output_rows),
        "source_batch_sha256": sha256(args.source_batch), "source_registry_sha256": sha256(args.source_registry),
        "apc_evidence_sha256": sha256(args.apc_evidence), "output_sha256": sha256(args.output),
        "manifest_sha256": sha256(args.manifest), "source_snapshot_records": len(source_registry) + sum(bool(row.get("source_snapshot_path")) for row in apc_evidence.values()),
        "apc_wave199_overlap": {"pinned_candidate_rows": len(apc_candidates), "wave209a_rows": len(apc_selected), "exact_external_id_name_model_match": True},
        "laravel_matcher_holds": {"rows": len(LARAVEL_MATCHER_HOLDS), "external_ids": sorted(LARAVEL_MATCHER_HOLDS)},
        "manifest": {"path": str(args.manifest).replace("\\", "/"), "sha256": sha256(args.manifest), "records": len(manifest_rows), "laravel_dry_run_verified": dry_run_verified},
        "laravel_dry_run": {"path": str(args.dry_run).replace("\\", "/"), "sha256": sha256(args.dry_run) if args.dry_run.is_file() else "", "verified": dry_run_verified},
        "policy": {"manufacturer_primary_sources_only": True, "full_registry_and_live_collision_guards": True, "database_mutations": 0},
        "automatic_database_mutations": 0, "safe_to_apply_records": len(manifest_rows),
    }
    args.summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
