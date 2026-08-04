#!/usr/bin/env python3
"""Materialize strict visual decisions for the Wave229 Batch-002 OCR holds."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HOLD_DIR = ROOT / ".tmp/wave229-hold-002"
INDEX = HOLD_DIR / "index.json"
OCR_INPUT = ROOT / "docs/audits/generated/wave227-ocr-batches/wave227-ocr-input-002.csv"
EXPORTER = ROOT / "docs/audits/generated/rb-wave227-legacy-preview-candidates.csv"
IMPORTS = ROOT / "docs/imports"
GEN = ROOT / "docs/audits/generated"

MANIFEST = IMPORTS / "rb-reviewed-legacy-preview-media-wave229b-2026-07-29.json"
LEDGER = GEN / "rb-wave229b-hold-002-visual-review.csv"
SUMMARY = GEN / "rb-wave229b-hold-002-visual-review.summary.json"
REPORT = ROOT / "docs/audits/2026-07-29-rb-wave229b-hold-002-visual-review.md"

PINS = {
    INDEX: "7f27bd1119bc8250102dbabb1b96084542c1631f9ed9b6f8795c5e60e9b79a42",
    OCR_INPUT: "41947f76b8a663ac609a71669838ecf11e184c24cf5df3e34a5a0c7cbdbd952e",
    EXPORTER: "34aa3a8d0743702a55e4a635d0b5d768f64b54874cfc42d6f7a7569a68600384",
}

# These are manual machine-vision decisions from all seven indexed contact
# sheets. An item is PASS only where its complete expected exact MPN is visibly
# legible on the pictured asset, not merely suggested by product shape or brand.
PASS_IDS = {
    "bitrix:20141", "bitrix:20142", "bitrix:20144", "bitrix:20146", "bitrix:20147", "bitrix:20150", "bitrix:20152", "bitrix:20153",
    "bitrix:24517", "bitrix:24518", "bitrix:24530", "bitrix:24559",
    "bitrix:24562", "bitrix:24568", "bitrix:24571", "bitrix:24572", "bitrix:24574", "bitrix:24576", "bitrix:24584", "bitrix:24585",
    "bitrix:2742", "bitrix:2743", "bitrix:2758", "bitrix:2767", "bitrix:2775", "bitrix:2794", "bitrix:2795", "bitrix:2800", "bitrix:2823",
    "bitrix:2837", "bitrix:2843", "bitrix:2894", "bitrix:2897", "bitrix:2898", "bitrix:2911", "bitrix:2932",
}
MISMATCHES = {
    "bitrix:2808": "A706/105",
    "bitrix:2831": "S12/17 G5",
    "bitrix:2909": "MM 250-12",
}

LEDGER_FIELDS = (
    "external_id", "media_id", "expected_mpn", "visible_mpn", "verdict", "reason", "content_sha256",
    "image_path", "contact_sheet", "review_note", "promotion_eligible",
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def build() -> dict[str, object]:
    for path, expected in PINS.items():
        require(digest(path) == expected, f"review evidence drift: {path.relative_to(ROOT)}")
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    require(index.get("selected_verdict") == "HOLD" and index.get("selected_rows") == 81, "Wave229 input scope drift")
    sheets = index.get("sheets", [])
    require(len(sheets) == 7 and sum(len(sheet.get("rows", [])) for sheet in sheets) == 81, "contact-sheet cardinality drift")

    inputs = {(row["external_id"], row["media_id"]): row for row in read_csv(OCR_INPUT)}
    require(len(inputs) == 100, "Wave227 input-002 cardinality drift")
    exporter = {(row["external_id"], row["media_id"]): row for row in read_csv(EXPORTER)}
    require(len(exporter) == 304, "Wave227 exporter cardinality drift")

    indexed: list[tuple[str, dict[str, str]]] = []
    for sheet in sheets:
        sheet_name = Path(str(sheet["path"])).name
        require((HOLD_DIR / sheet_name).is_file(), f"contact sheet absent: {sheet_name}")
        for row in sheet["rows"]:
            indexed.append((sheet_name, row))
    keys = [(row["external_id"], row["media_id"]) for _, row in indexed]
    require(len(keys) == len(set(keys)) == 81, "indexed key uniqueness drift")
    indexed_ids = {row["external_id"] for _, row in indexed}
    require(PASS_IDS.isdisjoint(MISMATCHES) and PASS_IDS | set(MISMATCHES) <= indexed_ids, "review decision scope drift")

    ledger: list[dict[str, str]] = []
    images: list[dict[str, object]] = []
    for sheet_name, indexed_row in indexed:
        key = (indexed_row["external_id"], indexed_row["media_id"])
        require(key in inputs and key in exporter, f"unmatched indexed row: {key}")
        source, candidate = inputs[key], exporter[key]
        expected = indexed_row["expected_exact"].strip()
        require(expected == source["expected_mpn"].strip() and source["expected_model_core"].strip() == "", f"expected MPN drift: {key}")
        require(candidate["identity_scope"] == "exact" and candidate["mpn"] == expected, f"exporter exact scope drift: {key}")
        image_path = Path(source["image_path"])
        require(image_path.is_file() and digest(image_path) == source["hash"], f"asset hash drift: {key}")
        require(candidate["content_sha256"] == source["hash"] and "company-owned" in candidate["rights_basis"].casefold(), f"candidate rights drift: {key}")

        if key[0] in PASS_IDS:
            verdict, visible, reason = "PASS", expected, "exact_expected_mpn_visibly_legible"
            note = f"Manual machine-vision review: exact visible MPN {expected} is legible on the asset."
            images.append({
                "external_id": key[0], "media_id": int(key[1]), "content_sha256": source["hash"],
                "storage_path": candidate["storage_path"], "rights_basis": candidate["rights_basis"],
                "identity_scope": "exact", "mpn": expected, "identity_evidence_level": "visible_exact_mpn",
                "visual_verification_note": note, "reviewed_at": "2026-07-29",
            })
        elif key[0] in MISMATCHES:
            verdict, visible, reason = "HOLD", MISMATCHES[key[0]], "visible_mpn_mismatch"
            note = f"Manual machine-vision review: visible MPN {visible} does not equal expected {expected}."
        else:
            verdict, visible, reason = "HOLD", "", "exact_mpn_not_visibly_legible_or_generic_asset"
            note = "Manual machine-vision review: exact expected MPN is not visibly legible; generic appearance is insufficient."
        ledger.append({
            "external_id": key[0], "media_id": key[1], "expected_mpn": expected, "visible_mpn": visible,
            "verdict": verdict, "reason": reason, "content_sha256": source["hash"], "image_path": source["image_path"],
            "contact_sheet": sheet_name, "review_note": note, "promotion_eligible": str(verdict == "PASS").lower(),
        })

    require(len(images) == 36, "frozen visual PASS cardinality drift")
    require(len(ledger) == 81 and sum(row["verdict"] == "HOLD" for row in ledger) == 45, "frozen visual HOLD cardinality drift")
    require(sum(row["reason"] == "visible_mpn_mismatch" for row in ledger) == 3, "frozen mismatch cardinality drift")
    require(len({row["external_id"] for row in images}) == len(images) == len({row["content_sha256"] for row in images}), "promotion uniqueness drift")

    manifest = {
        "schema_version": 1,
        "purpose": "Promote only Wave229-B visual PASS assets from Wave227 Batch-002 OCR holds.",
        "locale": "ru-BY",
        "images": images,
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with LEDGER.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=LEDGER_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(ledger)
    summary = {
        "schema_version": 1,
        "batch": "wave229b_hold_002_manual_machine_vision_review",
        "inputs": {path.relative_to(ROOT).as_posix(): digest(path) for path in PINS},
        "coverage": {"contact_sheets": 7, "ocr_hold_rows": 81, "visual_pass": 36, "visual_hold": 45, "visible_mpn_mismatches": 3},
        "mismatches": [{"external_id": row["external_id"], "expected_mpn": row["expected_mpn"], "visible_mpn": row["visible_mpn"]} for row in ledger if row["reason"] == "visible_mpn_mismatch"],
        "manifest": {"path": MANIFEST.relative_to(ROOT).as_posix(), "sha256": digest(MANIFEST), "rows": len(images)},
        "ledger": {"path": LEDGER.relative_to(ROOT).as_posix(), "sha256": digest(LEDGER), "rows": len(ledger)},
        "safety": {"database_operations": 0, "apply_performed": False, "media_promotion_performed": False, "commit_or_push": False},
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REPORT.write_text(
        "# Wave229-B: Batch-002 OCR-HOLD visual review\n\n"
        "All seven Wave229 contact sheets (81 Wave227 Batch-002 OCR-HOLD assets) were reviewed. A PASS is recorded only when the complete expected MPN is visibly legible on the pictured asset. This produced 36 PASS entries and 45 HOLD entries. Three HOLDs are positive mismatches: `bitrix:2808` expected `A706/140` but visibly reads `A706/105`; `bitrix:2831` expected `S 12/17` but visibly reads `S12/17 G5`; `bitrix:2909` expected `MNG 250-12` but visibly reads `MM 250-12`.\n\n"
        "The promotion manifest contains only the 36 exact visible-MPN PASS assets. Generic product shots and unreadable labels remain excluded. The builder SHA-pins the contact-sheet index, Batch-002 OCR input and frozen exporter, rechecks every local image hash, and verifies company-owned rights before writing output. No promotion, database apply, commit or push was performed.\n",
        encoding="utf-8",
    )
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False))
