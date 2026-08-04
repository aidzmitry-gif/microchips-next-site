#!/usr/bin/env python3
"""Build the exact two-row source refresh stage after Wave231 MPN corrections."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import unicodedata
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "docs/audits/generated"
IMPORTS = ROOT / "docs/imports"
CORRECTIONS = IMPORTS / "rb-truncated-mpn-corrections-wave231b-2026-07-29.json"
EXTRACTION = IMPORTS / "rb-truncated-mpn-corrections-wave231b-2026-07-29.extraction.txt"
CURRENT_DB = GEN / "rb-wave231c-corrected-description-current-db-readonly.json"
SOURCE_REGISTRY = ROOT / "docs/audits/sources/wave211c-stationary/source-registry.json"
SOURCE_PDF = ROOT / "docs/audits/sources/wave209a/exide-sonnenschein-solar-block.pdf"
MANIFEST = IMPORTS / "rb-source-backed-description-stage-manifest-wave231c-2026-07-29.json"
LEDGER = GEN / "rb-wave231c-corrected-sonnenschein-description-ledger.csv"
SUMMARY = GEN / "rb-wave231c-corrected-sonnenschein-description.summary.json"
REPORT = ROOT / "docs/audits/2026-07-29-rb-wave231c-corrected-sonnenschein-descriptions.md"

PINS = {
    CORRECTIONS: "6ccb755b457cc1a232cebf7efab6f9303b252b746fc3214e7565959543e95e39",
    EXTRACTION: "64448fee7bdb38e81d08ab34e2f35dcb813daa36568744da911d051cdcddecbc",
    SOURCE_REGISTRY: "5cbb65a60a0038218f0504c57a44673dc0c220bc3614be61072726f18abede3c",
    SOURCE_PDF: "f065a4727d47d515d3bc9d8df09bbe4b8567ac53c7101806819287590ce80730",
    CURRENT_DB: "35cc69ad21f1edbafd696d84d30247e1480ee713c64a28c2cf60b30c3f465133",
}
EXPECTED = {"bitrix:2831": ("S 12/17 G5", "17 А·ч"), "bitrix:3117": ("S 12/6.6 S", "6,6 А·ч")}
PRODUCT_FIELDS = {"external_id", "identity_scope", "manufacturer", "model_core", "technology", "source_url", "technical_attributes", "source_kind", "source_tier", "source_publisher", "manufacturer_primary", "evidence_scope", "checked_at"}
LEDGER_FIELDS = ("external_id", "corrected_mpn", "current_draft_status", "source_url", "source_snapshot_path", "source_snapshot_sha256", "source_extraction_path", "source_extraction_sha256", "source_assertion", "identity_scope", "refresh_existing", "refresh_applied", "safe_to_apply")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def normal(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "").upper()
    return re.sub(r"[^A-Z0-9]", "", value)


def write_ledger(rows: list[dict[str, str]]) -> None:
    with LEDGER.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=LEDGER_FIELDS, lineterminator="\n")
        writer.writeheader(); writer.writerows(rows)


def build() -> dict[str, object]:
    for path, expected in PINS.items():
        require(digest(path) == expected, f"pinned input drift: {path.relative_to(ROOT)}")
    corrections = json.loads(CORRECTIONS.read_text(encoding="utf-8"))["corrections"]
    by_id = {row["external_id"]: row for row in corrections}
    require(set(by_id) == set(EXPECTED) and len(by_id) == 2, "corrected identity scope drift")
    live = json.loads(CURRENT_DB.read_text(encoding="utf-8"))
    require(live["mode"] == "read_only" and live["database_mutations"] == 0, "current DB evidence must be read-only")
    live_by_id = {row["external_id"]: row for row in live["records"]}
    require(set(live_by_id) == set(EXPECTED), "current DB target scope drift")
    registry = json.loads(SOURCE_REGISTRY.read_text(encoding="utf-8"))["sources"]
    source = next((row for row in registry if row["source_id"] == "exide-sonnenschein-solar-block.pdf"), None)
    require(source is not None and source["snapshot_path"] == SOURCE_PDF.relative_to(ROOT).as_posix() and source["snapshot_sha256"] == digest(SOURCE_PDF), "official Exide source registry drift")
    extraction = EXTRACTION.read_text(encoding="utf-8")
    products: list[dict[str, object]] = []
    ledger: list[dict[str, str]] = []
    for external_id, (corrected_mpn, capacity) in EXPECTED.items():
        correction, db = by_id[external_id], live_by_id[external_id]
        require(correction["corrected_mpn"] == corrected_mpn == db["mpn"], f"corrected MPN/live drift: {external_id}")
        require(correction["manufacturer"] == db["manufacturer"] == "Sonnenschein", f"manufacturer drift: {external_id}")
        require(db["draft_status"] == "legacy_preview_applied" and db["source_tier"] == "company_owned_legacy_preview", f"already source-backed or unsupported current draft: {external_id}")
        require(correction["source_url"] == source["source_url"] and correction["source_snapshot_sha256"] == source["snapshot_sha256"], f"correction source drift: {external_id}")
        require(correction["source_extraction_sha256"] == digest(EXTRACTION) and normal(corrected_mpn) in normal(extraction), f"corrected MPN absent from pinned Exide extraction: {external_id}")
        require(normal(correction["source_evidence_text"]) in normal(extraction), f"specific official catalogue row absent: {external_id}")
        product = {"external_id": external_id, "identity_scope": "model_core", "manufacturer": "Sonnenschein", "model_core": corrected_mpn, "technology": "GEL", "source_url": source["source_url"], "technical_attributes": {"Номинальное напряжение": "12 В", "Номинальная ёмкость C100": capacity}, "source_kind": "official_manufacturer_catalogue", "source_tier": "manufacturer_primary", "source_publisher": source["publisher"], "manufacturer_primary": True, "evidence_scope": "model_core", "checked_at": "2026-07-29"}
        products.append(product)
        ledger.append({"external_id": external_id, "corrected_mpn": corrected_mpn, "current_draft_status": db["draft_status"], "source_url": source["source_url"], "source_snapshot_path": source["snapshot_path"], "source_snapshot_sha256": source["snapshot_sha256"], "source_extraction_path": EXTRACTION.relative_to(ROOT).as_posix(), "source_extraction_sha256": digest(EXTRACTION), "source_assertion": "exact_corrected_mpn_and_catalogue_table_row", "identity_scope": "model_core", "refresh_existing": "true", "refresh_applied": "true", "safe_to_apply": "false"})
    require(all(set(row) == PRODUCT_FIELDS for row in products) and len(products) == 2, "StageSourceBackedDescriptionDrafts contract drift")
    manifest = {"schema_version": 1, "purpose": "Wave231-C exact two-row manufacturer-primary source refresh after corrected Sonnenschein MPNs; bounded model_core only.", "locale": "ru-BY", "application_contract": {"stage_only": True, "refresh_existing": True, "refresh_applied": True, "database_apply": False}, "products": products}
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_ledger(ledger)
    summary = {"schema_version": 1, "wave": "wave231c_corrected_sonnenschein_description_stage", "inputs": {path.relative_to(ROOT).as_posix(): digest(path) for path in PINS}, "coverage": {"corrected_products": 2, "source_backed_complete_before": 0, "legacy_preview_applied_before": 2, "staged": 2, "exact_scope": 0, "model_core_scope": 2}, "manifest": {"path": MANIFEST.relative_to(ROOT).as_posix(), "sha256": digest(MANIFEST), "rows": 2}, "ledger": {"path": LEDGER.relative_to(ROOT).as_posix(), "sha256": digest(LEDGER), "rows": 2}, "application_contract": manifest["application_contract"], "safety": {"database_operations": 0, "apply_performed": False, "publication_changes": 0, "commercial_changes": 0, "identity_changes": 0}}
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REPORT.write_text("# Wave231-C: corrected Sonnenschein source-backed description stage\n\nA read-only DB check found both corrected identities (`S 12/17 G5`, `S 12/6.6 S`) but only `legacy_preview_applied` description drafts, not manufacturer-primary source-backed content. Wave230 had explicitly held `bitrix:3117` before its identity correction; therefore this is not a duplicate source-backed stage.\n\nThe manifest contains exactly the two corrected products. It reuses the SHA-pinned Exide Sonnenschein SOLAR catalogue and its pinned extraction; each corrected full MPN and its table row are rechecked. The titles retain `для ИБП` after the model, so strict exact display-name scope is unavailable; the stage uses bounded manufacturer-primary `model_core` evidence only.\n\nThis is a `--refresh-existing --refresh-applied` stage contract for replacing the two legacy-preview-applied drafts after review. The builder did not invoke Laravel, create an import run, apply a DB change, publish content, alter media, or change product identity.\n", encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False))
