#!/usr/bin/env python3
"""Materialize the five fail-closed Wave206 B.B. Battery identity rows."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs/audits/generated/rb-wave206-fiamm-bb-csb-evidence.csv"
MANIFEST = ROOT / "docs/imports/rb-verified-oem-identities-wave206-bb-2026-07-29.json"
SUMMARY = ROOT / "docs/audits/generated/rb-verified-oem-identities-wave206-bb.summary.json"
EXPECTED_IDS = ["bitrix:1519", "bitrix:1526", "bitrix:1565", "bitrix:1587", "bitrix:1593"]
ALLOWED_SOURCE_KINDS = {"official_manufacturer_catalogue"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    os.replace(temporary, path)


def main() -> None:
    if not EVIDENCE.is_file():
        raise SystemExit("Run build-rb-wave206-fiamm-bb-csb-evidence.py first")
    safe = [row for row in read_csv(EVIDENCE) if row["safe_to_apply"] == "true"]
    ids = [row["product_external_id"] for row in safe]
    if ids != EXPECTED_IDS:
        raise SystemExit(f"Wave206 safe evidence drifted: {ids}")

    products = []
    seen_mpns = set()
    for row in safe:
        if row["manufacturer_cluster"] != "B.B. Battery" or row["partition"] != "exact":
            raise SystemExit(f"Unsafe evidence row entered manifest: {row['product_external_id']}")
        snapshot = ROOT / row["snapshot_path"]
        if not snapshot.is_file() or sha256(snapshot) != row["snapshot_sha256"]:
            raise SystemExit(f"Snapshot/hash mismatch: {row['product_external_id']}")
        mpn = row["replacement_mpn"]
        normalized_mpn = "".join(character.casefold() for character in mpn if character.isalnum())
        if not mpn or normalized_mpn in seen_mpns:
            raise SystemExit("Manifest would contain a blank or repeated normalized MPN")
        seen_mpns.add(normalized_mpn)
        relative_snapshot = Path(os.path.relpath(snapshot, MANIFEST.parent)).as_posix()
        source_kind = "official_manufacturer_catalogue"
        if source_kind not in ALLOWED_SOURCE_KINDS:
            raise SystemExit("Unsupported source kind")
        products.append({
            "external_id": row["product_external_id"],
            "current_name": row["name"],
            "manufacturer": "B.B. Battery",
            "mpn": mpn,
            "source_url": row["source_url"],
            "source_kind": source_kind,
            "source_publisher": "B.B. Battery Co., Ltd.",
            "checked_at": "2026-07-29",
            "product_type": "Valve-regulated lead-acid battery",
            "source_snapshot_path": relative_snapshot,
            "source_snapshot_sha256": row["snapshot_sha256"],
        })

    manifest = {"schema_version": 1, "site_key": "microchips-by", "products": products}
    atomic_json(MANIFEST, manifest)
    summary = {
        "schema_version": 1,
        "site": "microchips-by",
        "batch": "wave206_bb_verified_oem_identities",
        "created_at": "2026-07-29",
        "evidence": {"path": EVIDENCE.relative_to(ROOT).as_posix(), "sha256": sha256(EVIDENCE)},
        "manifest": {"path": MANIFEST.relative_to(ROOT).as_posix(), "sha256": sha256(MANIFEST), "rows": len(products)},
        "external_ids": [row["external_id"] for row in products],
        "held_exact_duplicate": ["bitrix:1590"],
        "policy": {
            "existing_laravel_contract_unchanged": True,
            "official_manufacturer_sources_only": True,
            "relative_snapshot_paths": True,
            "database_mutations": 0,
        },
    }
    atomic_json(SUMMARY, summary)


if __name__ == "__main__":
    main()
