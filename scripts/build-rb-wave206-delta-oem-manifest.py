#!/usr/bin/env python3
"""Build the Wave206 Delta OEM identity manifest from exact-safe evidence.

The builder is intentionally narrower than the research registry. It emits
only literal current names, exact Delta model identifiers, and SHA-256 pinned
first-party product pages accepted by ``catalog:apply-verified-oem-identities``.
It never connects to or mutates the application database.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import unicodedata
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs/audits/generated/rb-delta-wave206-official-evidence.csv"
OUTPUT = ROOT / "docs/imports/rb-verified-oem-identities-wave206-delta-2026-07-29.json"
SUMMARY = ROOT / "docs/audits/generated/rb-verified-oem-identities-wave206-delta.summary.json"
SPLIT_DIR = ROOT / "docs/audits/generated/rb-wave206-delta-oem-candidates"
COLLISIONS = ROOT / "docs/audits/evidence/wave206-delta-current-db-collisions.json"
LARAVEL_DRY_RUN = ROOT / "docs/audits/evidence/wave206-delta-laravel-dry-run.json"
EXPECTED_EXACT = 27
EXPECTED_MANIFEST = 18
EXPECTED_COLLISIONS = 9


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalized(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", unicodedata.normalize("NFKC", value or "").casefold())


def build() -> dict:
    evidence_rows = read_csv(EVIDENCE)
    exact = [row for row in evidence_rows if row["partition"] == "exact_safe" and row["safe_to_apply"] == "true"]
    if len(exact) != EXPECTED_EXACT:
        raise SystemExit(f"Wave206 exact-safe partition drifted: expected {EXPECTED_EXACT}, got {len(exact)}")
    collision_evidence = json.loads(COLLISIONS.read_text(encoding="utf-8"))
    if (
        collision_evidence.get("schema_version") != 1
        or collision_evidence.get("site_key") != "microchips-by"
        or collision_evidence.get("normalization") != "ProductIdentity::normalize"
        or len(collision_evidence.get("collisions", [])) != EXPECTED_COLLISIONS
    ):
        raise SystemExit("Current-DB collision evidence contract drifted")
    collisions = {row["candidate_external_id"]: row for row in collision_evidence["collisions"]}
    if len(collisions) != EXPECTED_COLLISIONS:
        raise SystemExit("Current-DB collision evidence repeats a candidate external ID")
    exact_by_id = {row["product_external_id"]: row for row in exact}
    if set(collisions) - set(exact_by_id):
        raise SystemExit("Current-DB collision evidence includes a non-exact Wave206 candidate")
    for external_id, collision in collisions.items():
        if normalized(exact_by_id[external_id]["replacement_mpn"]) != collision["normalized_identifier"]:
            raise SystemExit(f"Current-DB collision fingerprint does not match exact evidence: {external_id}")

    products = []
    seen_ids: set[str] = set()
    seen_mpns: set[str] = set()
    for row in exact:
        external_id, name, mpn = row["product_external_id"], row["name"], row["replacement_mpn"]
        if external_id in collisions:
            continue
        if external_id in seen_ids or normalized(mpn) in seen_mpns:
            raise SystemExit(f"Duplicate external ID or normalized MPN: {external_id}")
        if row["replacement_manufacturer"] != "Delta" or not mpn:
            raise SystemExit(f"Exact row lacks literal Delta identity: {external_id}")
        if normalized("Delta") not in normalized(name) or normalized(mpn) not in normalized(name):
            raise SystemExit(f"Current name does not literally contain bounded identity tokens: {external_id}")
        snapshot = ROOT / row["snapshot_path"]
        if not snapshot.is_file() or sha256(snapshot) != row["snapshot_sha256"].casefold():
            raise SystemExit(f"Pinned source snapshot is missing or hash-mismatched: {external_id}")
        if not row["source_url"].startswith("https://") or "delta-batt.com" not in row["source_url"].casefold():
            raise SystemExit(f"Exact row is not a Delta first-party HTTPS source: {external_id}")
        seen_ids.add(external_id)
        seen_mpns.add(normalized(mpn))
        products.append({
            "external_id": external_id,
            "current_name": name,
            "manufacturer": "Delta",
            "mpn": mpn,
            "source_url": row["source_url"],
            "source_kind": "official_manufacturer_product_page",
            "source_publisher": row["source_publisher"],
            "checked_at": "2026-07-29",
            "product_type": "Stationary VRLA battery",
            "source_snapshot_path": "../" + row["snapshot_path"].removeprefix("docs/"),
            "source_snapshot_sha256": row["snapshot_sha256"].casefold(),
        })

    products.sort(key=lambda row: int(row["external_id"].split(":", 1)[1]))
    if len(products) != EXPECTED_MANIFEST:
        raise SystemExit(f"Current collision-filtered manifest drifted: expected {EXPECTED_MANIFEST}, got {len(products)}")
    manifest = {"schema_version": 1, "site_key": "microchips-by", "products": products}
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    SPLIT_DIR.mkdir(parents=True, exist_ok=True)
    for stale in SPLIT_DIR.glob("*.json"):
        stale.unlink()
    for row in products:
        path = SPLIT_DIR / f"{row['external_id'].replace(':', '-')}.json"
        path.write_text(json.dumps({"schema_version": 1, "site_key": "microchips-by", "products": [row]}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    dry_run = json.loads(LARAVEL_DRY_RUN.read_text(encoding="utf-8"))
    if (
        dry_run.get("site_key") != "microchips-by"
        or dry_run.get("mode") != "dry_run"
        or dry_run.get("records") != len(products)
        or dry_run.get("manifest_sha256") != sha256(OUTPUT)
        or dry_run.get("exit_code") != 0
        or dry_run.get("commercial_fields_changed") != 0
        or dry_run.get("publication_fields_changed") != 0
        or dry_run.get("database_mutations") != 0
    ):
        raise SystemExit("Pinned Laravel dry-run evidence is missing, stale, or unsafe")
    summary = {
        "schema_version": 1,
        "site_key": "microchips-by",
        "evidence": {"path": EVIDENCE.relative_to(ROOT).as_posix(), "sha256": sha256(EVIDENCE), "rows": len(evidence_rows)},
        "current_db_collision_evidence": {"path": COLLISIONS.relative_to(ROOT).as_posix(), "sha256": sha256(COLLISIONS), "rows": len(collisions), "candidate_external_ids": sorted(collisions)},
        "laravel_dry_run": {"path": LARAVEL_DRY_RUN.relative_to(ROOT).as_posix(), "sha256": sha256(LARAVEL_DRY_RUN), "records": dry_run["records"], "manifest_sha256": dry_run["manifest_sha256"], "exit_code": dry_run["exit_code"]},
        "manifest": {"path": OUTPUT.relative_to(ROOT).as_posix(), "sha256": sha256(OUTPUT), "rows": len(products)},
        "split_dry_run_manifests": {"path": SPLIT_DIR.relative_to(ROOT).as_posix(), "rows": len(list(SPLIT_DIR.glob('*.json')))},
        "holds": {"rows": len(evidence_rows) - len(products), "research_conflict": sum(row["partition"] == "conflict" for row in evidence_rows), "no_evidence": sum(row["partition"] == "no_evidence" for row in evidence_rows), "compatibility_only": sum(row["partition"] == "compatibility_only" for row in evidence_rows), "current_db_identity_collision": len(collisions)},
        "gate": {"literal_current_name": True, "first_party_snapshot_sha256": True, "allowed_source_kind": "official_manufacturer_product_page", "unique_normalized_mpn_within_manifest": True, "current_db_collision_evidence_applied": True, "database_mutations": 0},
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, indent=2))
