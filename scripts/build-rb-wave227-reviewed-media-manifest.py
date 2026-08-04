#!/usr/bin/env python3
"""Materialize the frozen Wave227 OCR-PASS plus visual-review media manifest."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPORTER = ROOT / "docs/audits/generated/rb-wave227-legacy-preview-candidates.csv"
BATCHES = (
    (1, 100, 32),
    (2, 100, 19),
    (3, 57, 24),
)
INPUTS = {number: ROOT / f"docs/audits/generated/wave227-ocr-batches/wave227-ocr-input-{number:03}.csv" for number, _, _ in BATCHES}
REVIEWS = {number: ROOT / f"docs/audits/generated/wave227-ocr-batches/wave227-ocr-review-{number:03}.csv" for number, _, _ in BATCHES}
CONTACTS = {number: ROOT / f".tmp/wave227-pass-{number:03}/index.json" for number, _, _ in BATCHES}
OUTPUT = ROOT / "docs/imports/rb-reviewed-legacy-preview-media-wave227-2026-07-29.json"
LEDGER = ROOT / "docs/audits/generated/rb-reviewed-legacy-preview-media-wave227.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-reviewed-legacy-preview-media-wave227.summary.json"

PINS = {
    EXPORTER: "34aa3a8d0743702a55e4a635d0b5d768f64b54874cfc42d6f7a7569a68600384",
    INPUTS[1]: "059f61f2d6daf1f137ba6270123954960a4de41d4c15f03c23bcc7b2072f3658",
    INPUTS[2]: "41947f76b8a663ac609a71669838ecf11e184c24cf5df3e34a5a0c7cbdbd952e",
    INPUTS[3]: "a624ca034a00f96a41f5be3f2cb3868dfe1387a8568576dceaab764f1c8aa26e",
    REVIEWS[1]: "f627cff253e8a17c24f8a2522f05a6177d0e4cf390d0f7dd1a7dbc2a2f2af905",
    REVIEWS[2]: "0ab6f90c7959a0abd59069089cdd08613dae5012a72c8455207b3b26668892f0",
    REVIEWS[3]: "09298f51e85de38904e9d917073365b5be7ed6ea3de559860b7bd3e03525d71e",
    CONTACTS[1]: "484388478b22f7f0a744ebd8824692a9d6dfea8c185ac6f269c8d872c80df08d",
    CONTACTS[2]: "d8f397c2987adb7bfc3289b7ae7391cdf38835725d80d08706fc691e0abc086c",
    CONTACTS[3]: "1323423f23b8abc8dc833a598972bc809e8796024b564664d9af33362be16e53",
}
LEDGER_FIELDS = (
    "external_id", "media_id", "expected_mpn", "content_sha256", "storage_path", "rights_basis",
    "ocr_text_sha256", "ocr_verdict", "batch", "contact_sheet", "visual_review",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def path_key(value: str) -> str:
    return value.replace("\\", "/").casefold()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def unique_map(rows: list[dict[str, str]], key_name: str, key) -> dict[object, dict[str, str]]:
    result: dict[object, dict[str, str]] = {}
    for row in rows:
        value = key(row)
        require(value not in result, f"duplicate {key_name}: {value}")
        result[value] = row
    return result


def build() -> dict[str, object]:
    for path, expected_digest in PINS.items():
        require(sha256(path) == expected_digest, f"review evidence drift: {path.relative_to(ROOT)}")

    exporter_rows = read_csv(EXPORTER)
    exporter = unique_map(exporter_rows, "exporter external/media key", lambda row: (row["external_id"], row["media_id"]))
    require(len(exporter_rows) == len(exporter), "exporter external/media uniqueness drift")

    images: list[dict[str, object]] = []
    ledger: list[dict[str, str]] = []
    batch_summary: list[dict[str, object]] = []
    for number, expected_rows, expected_passes in BATCHES:
        inputs = read_csv(INPUTS[number])
        reviews = read_csv(REVIEWS[number])
        require(len(inputs) == len(reviews) == expected_rows, f"batch {number:03} cardinality drift")
        inputs_by_path = unique_map(inputs, f"batch {number:03} OCR input path", lambda row: path_key(row["image_path"]))
        reviews_by_path = unique_map(reviews, f"batch {number:03} OCR review path", lambda row: path_key(row["image_path"]))
        require(set(inputs_by_path) == set(reviews_by_path), f"batch {number:03} OCR input/review path drift")
        inputs_by_media = unique_map(inputs, f"batch {number:03} OCR input external/media key", lambda row: (row["external_id"], row["media_id"]))

        contact = json.loads(CONTACTS[number].read_text(encoding="utf-8"))
        require(contact.get("schema_version") == 1, f"batch {number:03} contact schema drift")
        require(contact.get("ocr_input_rows") == expected_rows, f"batch {number:03} contact input cardinality drift")
        require(contact.get("selected_verdict") == "PASS", f"batch {number:03} contact verdict drift")
        require(contact.get("selected_rows") == expected_passes, f"batch {number:03} contact PASS cardinality drift")
        contacts: dict[tuple[str, str], tuple[dict[str, object], str]] = {}
        for sheet in contact.get("sheets", []):
            sheet_name = Path(str(sheet.get("path", ""))).name
            require(bool(sheet_name), f"batch {number:03} contact sheet path missing")
            for row in sheet.get("rows", []):
                key = (str(row.get("external_id", "")), str(row.get("media_id", "")))
                require(key not in contacts, f"batch {number:03} duplicate contact key: {key}")
                contacts[key] = (row, sheet_name)
        require(len(contacts) == expected_passes, f"batch {number:03} contact-row cardinality drift")

        pass_rows = [review for review in reviews if review["verdict"].strip() == "PASS"]
        require(len(pass_rows) == expected_passes, f"batch {number:03} OCR PASS cardinality drift")
        for review in pass_rows:
            source = inputs_by_path[path_key(review["image_path"])]
            key = (source["external_id"], source["media_id"])
            require(key in exporter and key in contacts and key in inputs_by_media, f"batch {number:03} incomplete PASS evidence: {key}")
            candidate = exporter[key]
            contact_row, contact_sheet = contacts[key]
            expected_mpn = source["expected_mpn"].strip()
            require(expected_mpn != "" and source["expected_model_core"].strip() == "", f"batch {number:03} exact identity scope drift: {key}")
            require(candidate["identity_scope"].strip() == "exact", f"batch {number:03} exporter identity scope drift: {key}")
            require(candidate["mpn"].strip() == expected_mpn, f"batch {number:03} exporter MPN drift: {key}")
            require(candidate["model_core"].strip() == "" and candidate["manufacturer"].strip() == "", f"batch {number:03} exporter exact identity fields drift: {key}")
            require(candidate["content_sha256"].strip() == source["hash"].strip() and len(source["hash"].strip()) == 64, f"batch {number:03} asset hash drift: {key}")
            require(bool(candidate["storage_path"].strip()), f"batch {number:03} asset path missing: {key}")
            require(bool(candidate["rights_basis"].strip()) and "company-owned" in candidate["rights_basis"].casefold(), f"batch {number:03} rights basis drift: {key}")
            require(review["expected_exact"].strip() == expected_mpn and bool(review["ocr_text_sha256"].strip()), f"batch {number:03} OCR exact evidence drift: {key}")
            require(str(contact_row.get("expected_exact", "")).strip() == expected_mpn, f"batch {number:03} contact MPN drift: {key}")
            require(path_key(str(contact_row.get("image_path", ""))) == path_key(source["image_path"]), f"batch {number:03} contact image path drift: {key}")

            note = (
                "OCR PASS and manual machine-vision contact-sheet review confirmed the exact visible "
                f"MPN marking {expected_mpn}."
            )
            images.append({
                "external_id": source["external_id"],
                "media_id": int(source["media_id"]),
                "content_sha256": source["hash"],
                "storage_path": candidate["storage_path"],
                "rights_basis": candidate["rights_basis"],
                "identity_scope": "exact",
                "mpn": expected_mpn,
                "identity_evidence_level": "visible_exact_mpn",
                "visual_verification_note": note,
                "reviewed_at": "2026-07-29",
            })
            ledger.append({
                "external_id": source["external_id"],
                "media_id": source["media_id"],
                "expected_mpn": expected_mpn,
                "content_sha256": source["hash"],
                "storage_path": candidate["storage_path"],
                "rights_basis": candidate["rights_basis"],
                "ocr_text_sha256": review["ocr_text_sha256"],
                "ocr_verdict": "PASS",
                "batch": f"{number:03}",
                "contact_sheet": contact_sheet,
                "visual_review": note,
            })
        batch_summary.append({"batch": f"{number:03}", "input_rows": expected_rows, "pass_rows": expected_passes})

    require(len(images) == 75, "frozen Wave227 PASS set must contain exactly 75 rows")
    require(len({row["external_id"] for row in images}) == len(images), "Wave227 PASS external_id uniqueness drift")
    require(len({row["media_id"] for row in images}) == len(images), "Wave227 PASS media_id uniqueness drift")
    require(len({row["content_sha256"] for row in images}) == len(images), "Wave227 PASS asset-hash uniqueness drift")
    payload = {
        "schema_version": 1,
        "purpose": "Promote only frozen Wave227 OCR-PASS and manually visual-reviewed company-owned legacy preview media.",
        "locale": "ru-BY",
        "images": images,
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with LEDGER.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=LEDGER_FIELDS)
        writer.writeheader()
        writer.writerows(ledger)
    summary = {
        "schema_version": 1,
        "reviewed_images": len(images),
        "identity_scope": "exact",
        "ocr_required_verdict": "PASS",
        "exporter_sha256": PINS[EXPORTER],
        "input_sha256": {f"{number:03}": PINS[INPUTS[number]] for number, _, _ in BATCHES},
        "review_sha256": {f"{number:03}": PINS[REVIEWS[number]] for number, _, _ in BATCHES},
        "contact_index_sha256": {f"{number:03}": PINS[CONTACTS[number]] for number, _, _ in BATCHES},
        "batches": batch_summary,
        "manifest": str(OUTPUT.relative_to(ROOT)).replace("\\", "/"),
        "manifest_sha256": sha256(OUTPUT),
        "ledger": str(LEDGER.relative_to(ROOT)).replace("\\", "/"),
        "ledger_sha256": sha256(LEDGER),
        "database_apply": False,
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False))
