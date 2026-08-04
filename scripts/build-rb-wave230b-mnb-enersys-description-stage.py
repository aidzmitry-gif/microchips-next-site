#!/usr/bin/env python3
"""Build the frozen Wave230-B MNB + EnerSys source-backed description stage."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "docs/audits/generated"
IMPORTS = ROOT / "docs/imports"
SOURCES = ROOT / "docs/audits/sources"

TARGETS = GEN / "rb-wave230-description-targets.csv"
VERIFIED_MEDIA = IMPORTS / "rb-reviewed-legacy-preview-media-wave229-2026-07-29.json"
MNB_INDEX = SOURCES / "wave206-panasonic-ventura-mnb/snapshot-index.json"
MNB_PDF = SOURCES / "wave206-panasonic-ventura-mnb/mnb-official-catalogue.pdf"
MNB_TEXT = SOURCES / "wave206-panasonic-ventura-mnb/mnb-official-catalogue.txt"
ENERSYS_EVIDENCE = GEN / "rb-wave209a-official-evidence.csv"
ENERSYS_REGISTRY = GEN / "rb-wave209a-official-source-registry.json"
ENERSYS_SERIES_EVIDENCE = GEN / "rb-wave215c-medical-ups-evidence.csv"
ENERSYS_SERIES_REGISTRY = SOURCES / "wave215c-medical-ups/source-registry.json"
ENERSYS_PDF = SOURCES / "wave209a/enersys-cyclon-selection-guide.pdf"

MANIFEST = IMPORTS / "rb-source-backed-description-stage-manifest-wave230b-2026-07-29.json"
LEDGER = GEN / "rb-wave230b-mnb-enersys-description-ledger.csv"
SUMMARY = GEN / "rb-wave230b-mnb-enersys-description.summary.json"
REPORT = ROOT / "docs/audits/2026-07-29-rb-wave230b-mnb-enersys-descriptions.md"

PINS = {
    TARGETS: "39bb2ca1d650997d78583ee7daa4589f124b5f3b9e18b0d9bd82e7b4dcab0bd2",
    VERIFIED_MEDIA: "99feaa5836d91da2e6c66ce8d808153a799dfe8e2b8cf8208479e8fada2d5ef4",
    MNB_INDEX: "705579d386df38e100fc430a52c1f834aece98742444e1ea4786205eff00828f",
    MNB_PDF: "85dac18f2953eeb29e306434b0af658a49f96afcc04d182ea2a2b8ef7b207859",
    MNB_TEXT: "c98577d15147e74b03ab645f1a926784d2dee2570e223a8a6c532b55b9e76372",
    ENERSYS_EVIDENCE: "5d093d66deddc3ad25858e918ccf1fa72a9087f78db42785632e8af5ffe62aa9",
    ENERSYS_REGISTRY: "bc34c9169aa88bec5771ef02722e01cd666b50e778bbe75fae2646b6ca380149",
    ENERSYS_SERIES_EVIDENCE: "0da04b2072b5ed54326d1c3ebe6683b787f7ed643444794cd9f95241bfc49ce6",
    ENERSYS_SERIES_REGISTRY: "2d5336ac0bd2a1901d1f8c49517a09794311ba54a9600896a3f106e533941eab",
    ENERSYS_PDF: "3c6ecbb7f5379fccd8c2f5e31b999ac6f4d62117377b56b5f1e9df578e8fec5f",
}

EXPECTED_IDS = {
    "MNB": {"bitrix:1433", "bitrix:2980", "bitrix:3097", "bitrix:3137", "bitrix:1434", "bitrix:1514", "bitrix:1562", "bitrix:2981", "bitrix:3035", "bitrix:3098", "bitrix:3138", "bitrix:3220", "bitrix:1518"},
    "EnerSys": {"bitrix:24568", "bitrix:24530", "bitrix:24571", "bitrix:24572", "bitrix:24574", "bitrix:24576", "bitrix:24559", "bitrix:24562", "bitrix:24584", "bitrix:24585", "bitrix:24517", "bitrix:24518"},
}
SERIES_CELLS = {"bitrix:24517": ("Cyclon BC Cell", "0820-0004"), "bitrix:24518": ("Cyclon E Cell", "0850-0004")}

PRODUCT_FIELDS = {"external_id", "identity_scope", "manufacturer", "model_core", "technology", "source_url", "technical_attributes", "source_kind", "source_tier", "source_publisher", "manufacturer_primary", "evidence_scope", "checked_at"}
LEDGER_FIELDS = ("external_id", "manufacturer", "current_name", "mpn", "identity_scope", "source_url", "source_snapshot_path", "source_snapshot_sha256", "source_assertion", "verified_media_id", "verified_media_sha256", "name_ends_with_mpn", "stage_status", "safe_to_apply")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=LEDGER_FIELDS, lineterminator="\n")
        writer.writeheader(); writer.writerows(rows)


def normal(value: str) -> str:
    """Compare catalogue OCR with title MPNs, including Cyrillic M OCR glyphs."""
    value = unicodedata.normalize("NFKC", value or "").upper().translate(str.maketrans({"М": "M", "Н": "H", "В": "B"}))
    return re.sub(r"[^A-Z0-9]+", "", value)


def name_ends_with_mpn(name: str, mpn: str) -> bool:
    """The strict Laravel-style condition: no technical suffix after the MPN."""
    return name.rstrip().casefold().endswith(mpn.casefold())


def mnb_technology(mpn: str) -> str:
    if mpn.startswith("MNG "):
        return "VRLA GEL"
    return "VRLA AGM"


def registered_source(index: dict, source_id: str) -> dict:
    source = next((item for item in index["sources"] if item["source_id"] == source_id), None)
    require(source is not None, f"source registry lacks {source_id}")
    return source


def build() -> dict[str, object]:
    for path, expected in PINS.items():
        require(digest(path) == expected, f"pinned input drift: {path.relative_to(ROOT)}")

    selected = [row for row in read_csv(TARGETS) if row["manufacturer"] in EXPECTED_IDS]
    counts = Counter(row["manufacturer"] for row in selected)
    require(counts == Counter({"MNB": 13, "EnerSys": 12}), f"frozen Wave230-B count drift: {dict(counts)}")
    require({maker: {row["product_external_id"] for row in selected if row["manufacturer"] == maker} for maker in EXPECTED_IDS} == EXPECTED_IDS, "frozen Wave230-B ID set drift")
    require(len(selected) == 25 == len({row["product_external_id"] for row in selected}), "Wave230-B target uniqueness drift")

    media = {row["external_id"]: row for row in json.loads(VERIFIED_MEDIA.read_text(encoding="utf-8-sig"))["images"]}
    for row in selected:
        image = media.get(row["product_external_id"])
        require(image is not None, f"verified-media lineage missing: {row['product_external_id']}")
        require(str(image["media_id"]) == row["media_id"] and image["content_sha256"] == row["media_sha256"], f"verified-media hash/id drift: {row['product_external_id']}")
        require(image["mpn"] == row["mpn"] and image["identity_scope"] == "exact" and row["identity_evidence_level"] == "visible_exact_mpn", f"verified-media identity lineage drift: {row['product_external_id']}")
        require(image.get("rights_basis", "").startswith("Company-owned Microchips"), f"unverified media rights lineage: {row['product_external_id']}")

    mnb_source = registered_source(json.loads(MNB_INDEX.read_text(encoding="utf-8")), "mnb_official_catalogue")
    require(mnb_source["snapshot_path"] == MNB_PDF.relative_to(ROOT).as_posix() and mnb_source["snapshot_sha256"] == digest(MNB_PDF), "MNB official registry/PDF drift")
    require(mnb_source["extracted_text_path"] == MNB_TEXT.relative_to(ROOT).as_posix() and mnb_source["extracted_text_sha256"] == digest(MNB_TEXT), "MNB official registry/text drift")
    mnb_text = normal(MNB_TEXT.read_text(encoding="utf-8"))

    enersys_registry = {row["filename"]: row for row in json.loads(ENERSYS_REGISTRY.read_text(encoding="utf-8"))}
    enersys_source = enersys_registry.get("enersys-cyclon-selection-guide.pdf")
    require(enersys_source is not None and enersys_source["sha256"] == digest(ENERSYS_PDF), "EnerSys official registry/PDF drift")
    series_registry = registered_source(json.loads(ENERSYS_SERIES_REGISTRY.read_text(encoding="utf-8")), "enersys-cyclon-selection-guide.pdf")
    require(series_registry["snapshot_sha256"] == digest(ENERSYS_PDF) and series_registry["source_url"] == enersys_source["source_url"], "EnerSys series registry drift")
    enersys_rows = {row["product_external_id"]: row for row in read_csv(ENERSYS_EVIDENCE)}
    series_rows = {row["product_external_id"]: row for row in read_csv(ENERSYS_SERIES_EVIDENCE)}
    enersys_text = normal("\n".join(page.extract_text() or "" for page in PdfReader(ENERSYS_PDF).pages))

    products: list[dict[str, object]] = []
    ledger: list[dict[str, str]] = []
    for row in selected:
        external_id, maker, mpn = row["product_external_id"], row["manufacturer"], row["mpn"]
        if maker == "MNB":
            require(normal(mpn) in mnb_text, f"MNB model absent from pinned official catalogue: {external_id}")
            source_url, source_path, source_sha = mnb_source["source_url"], mnb_source["snapshot_path"], mnb_source["snapshot_sha256"]
            technology, assertion = mnb_technology(mpn), "exact_model_token_in_wave206_mnb_official_catalogue"
        elif external_id in SERIES_CELLS:
            evidence = series_rows.get(external_id)
            series, part = SERIES_CELLS[external_id]
            require(evidence is not None and evidence["partition"] == "exact_safe" and evidence["enersys_exact_series"] == series and evidence["enersys_catalogue_part_number"] == part, f"EnerSys series evidence drift: {external_id}")
            require(normal(series.removeprefix("Cyclon ")) in enersys_text and normal(part) in enersys_text, f"EnerSys series token absent from pinned catalogue: {external_id}")
            source_url, source_path, source_sha = evidence["source_url"], evidence["source_snapshot_path"].replace("../", "docs/"), evidence["source_snapshot_sha256"]
            technology, assertion = "AGM", f"exact_series_and_catalogue_part_{part}_from_wave215c"
        else:
            evidence = enersys_rows.get(external_id)
            require(evidence is not None and evidence["partition"] == "exact_safe" and evidence["model_token"] == mpn and evidence["safe_to_apply"] == "true", f"EnerSys exact evidence drift: {external_id}")
            require(normal(mpn) in enersys_text, f"EnerSys MPN absent from pinned catalogue: {external_id}")
            source_url, source_path, source_sha = evidence["source_url"], evidence["source_snapshot_path"].replace("../", "docs/"), evidence["source_snapshot_sha256"]
            technology, assertion = "AGM", "exact_part_number_from_wave209a"
        require(source_sha == digest(ENERSYS_PDF if maker == "EnerSys" else MNB_PDF), f"source SHA drift: {external_id}")
        # Every frozen title has a suffix after the MPN, so model_core is the only safe contract.
        require(not name_ends_with_mpn(row["name"], mpn), f"unexpected exact-name candidate: {external_id}")
        product = {"external_id": external_id, "identity_scope": "model_core", "manufacturer": maker, "model_core": mpn, "technology": technology, "source_url": source_url, "technical_attributes": {"Технология": technology}, "source_kind": "official_manufacturer_catalogue", "source_tier": "manufacturer_primary", "source_publisher": "EnerSys" if maker == "EnerSys" else "MNB Battery", "manufacturer_primary": True, "evidence_scope": "model_core", "checked_at": "2026-07-29"}
        products.append(product)
        ledger.append({"external_id": external_id, "manufacturer": maker, "current_name": row["name"], "mpn": mpn, "identity_scope": "model_core", "source_url": source_url, "source_snapshot_path": source_path, "source_snapshot_sha256": source_sha, "source_assertion": assertion, "verified_media_id": row["media_id"], "verified_media_sha256": row["media_sha256"], "name_ends_with_mpn": "false", "stage_status": "STAGE", "safe_to_apply": "false"})

    require(len(products) == 25 and all(set(row) == PRODUCT_FIELDS for row in products), "manifest product contract drift")
    require(all(row["identity_scope"] == row["evidence_scope"] == "model_core" for row in products), "strict title-scope contract drift")
    manifest = {"schema_version": 1, "purpose": "Wave230-B frozen MNB (13) and EnerSys (12) manufacturer-primary description refresh stage only; exact scope is forbidden unless nameEndsWith MPN.", "locale": "ru-BY", "application_contract": {"stage_only": True, "refresh_existing": True, "refresh_applied": True, "database_apply": False}, "products": products}
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_csv(LEDGER, ledger)
    summary = {"schema_version": 1, "wave": "wave230b_mnb_enersys_description_stage", "inputs": {path.relative_to(ROOT).as_posix(): digest(path) for path in PINS}, "coverage": {"frozen_wave230_targets": 25, "mnb_targets": 13, "enersys_targets": 12, "verified_media_lineage": 25, "staged": 25, "holds": 0, "exact_scope": 0, "model_core_scope": 25}, "manifest": {"path": MANIFEST.relative_to(ROOT).as_posix(), "sha256": digest(MANIFEST), "rows": len(products)}, "ledger": {"path": LEDGER.relative_to(ROOT).as_posix(), "sha256": digest(LEDGER), "rows": len(ledger)}, "application_contract": manifest["application_contract"], "safety": {"database_operations": 0, "apply_performed": False, "price_changes": 0, "stock_changes": 0, "media_changes": 0, "publication_changes": 0, "url_changes": 0, "identity_changes": 0}}
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REPORT.write_text("# Wave230-B: MNB and EnerSys frozen description stage\n\nWave230-B uses exactly the frozen 25-row slice: MNB 13 and EnerSys 12. It reuses only SHA-pinned manufacturer-primary registries and snapshots already acquired in Wave206, Wave209A and Wave215C; no new source research was performed. Every target is cross-checked against the Wave229 reviewed-media manifest by external ID, media ID, media SHA-256, exact visible-MPN evidence, and company-owned rights basis.\n\nAll 25 current names contain a technical suffix after their model token. The strict `nameEndsWith MPN` condition is therefore false for every row, so the manifest uses bounded `model_core` evidence only; it makes no exact-MPN display-name claim. MNB catalogue OCR is normalized only for the Cyrillic `М` glyph in the `MM 33-12` table cell, while preserving the same hash-pinned catalogue source. The two Cyclon Cell titles reuse the prior source-proven series-to-catalogue-part mapping from Wave215C.\n\nThis is a stage-only `--refresh-existing --refresh-applied` contract. The builder did not run an importer, DB apply, publication, media, commercial, URL, or identity change.\n", encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False))
