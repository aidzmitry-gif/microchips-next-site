#!/usr/bin/env python3
"""Materialize the strict Wave229-C visual-review promotion manifest.

All source images in this wave were OCR-HOLD.  Promotion is therefore limited
to the frozen manual-review allowlist below, whose exact expected MPN is visibly
legible on the image.  The rejected set remains in the ledger/summary so that a
future review cannot silently re-evaluate an already observed mismatch.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MEDIA_EXPORT = ROOT / "docs/audits/generated/rb-wave227-legacy-preview-candidates.csv"
OCR_INPUT = ROOT / "docs/audits/generated/wave227-ocr-batches/wave227-ocr-input-003.csv"
OCR_REVIEW = ROOT / "docs/audits/generated/wave227-ocr-batches/wave227-ocr-review-003.csv"
CONTACT_INDEX = ROOT / ".tmp/wave229-hold-003/index.json"
OUTPUT = ROOT / "docs/imports/rb-reviewed-legacy-preview-media-wave229c-2026-07-29.json"
LEDGER = ROOT / "docs/audits/generated/rb-reviewed-legacy-preview-media-wave229c.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-reviewed-legacy-preview-media-wave229c.summary.json"

PINS = {
    MEDIA_EXPORT: "34aa3a8d0743702a55e4a635d0b5d768f64b54874cfc42d6f7a7569a68600384",
    OCR_INPUT: "a624ca034a00f96a41f5be3f2cb3868dfe1387a8568576dceaab764f1c8aa26e",
    OCR_REVIEW: "09298f51e85de38904e9d917073365b5be7ed6ea3de559860b7bd3e03525d71e",
    CONTACT_INDEX: "b00567ed40710e4bf02769716dd79b1accafc69b9540da65c48daccd737e1d5c",
}

# Frozen after visual inspection of all 33 rows in wave229-hold-003/index.json.
# Tuples retain the contact-sheet order for reproducible output.
ALLOWLIST = (
    ("bitrix:2940", "698", "DTM 12032"),
    ("bitrix:2966", "718", "A412/32 F10"),
    ("bitrix:2969", "720", "S 12/32 G6"),
    ("bitrix:2980", "730", "MM 33-12"),
    ("bitrix:2981", "731", "MNG 33-12"),
    ("bitrix:3007", "752", "DTM 6045"),
    ("bitrix:3035", "770", "MNG 40-12"),
    ("bitrix:3039", "774", "A512/40 G6"),
    ("bitrix:3044", "779", "S 12/41 A"),
    ("bitrix:3082", "808", "A412/50 F10"),
    ("bitrix:3090", "815", "DTM 1255 L"),
    ("bitrix:3097", "819", "MM 55-12"),
    ("bitrix:3098", "820", "MNG 55-12"),
    ("bitrix:3117", "834", "S 12/6"),
    ("bitrix:3125", "840", "SB 12/60 A"),
    ("bitrix:3126", "841", "S 12/60 A"),
    ("bitrix:3137", "850", "MM 65-12"),
    ("bitrix:3138", "851", "MNG 65-12"),
    ("bitrix:3141", "854", "A412/65 F10"),
    ("bitrix:3143", "856", "A512/65 A"),
    ("bitrix:3220", "916", "MNG 75-12"),
    ("bitrix:3223", "919", "SB 12/75 A"),
    ("bitrix:3249", "939", "S 12/85 A"),
    ("bitrix:3284", "970", "A412/90 F10"),
    ("bitrix:3285", "971", "S 12/90 A"),
    ("bitrix:4778", "12137", "WDX0R"),
)

# Each selected image was reviewed; no generic product resemblance qualifies.
REJECTED = (
    {
        "external_id": "bitrix:3056",
        "media_id": "788",
        "expected_mpn": "MM 45-12",
        "observed_visible_marking": "MM55-12",
        "disposition": "rejected_visible_marking_mismatch",
    },
    {
        "external_id": "bitrix:3099",
        "media_id": "821",
        "expected_mpn": "MR 55-12FT",
        "observed_visible_marking": "MR 80-12FT",
        "disposition": "rejected_visible_marking_mismatch",
    },
    {
        "external_id": "bitrix:3219",
        "media_id": "915",
        "expected_mpn": "MM 75-12",
        "observed_visible_marking": "MM55-12",
        "disposition": "rejected_visible_marking_mismatch",
    },
    {
        "external_id": "bitrix:3222",
        "media_id": "918",
        "expected_mpn": "LC-P1275P",
        "observed_visible_marking": "not_visibly_legible",
        "disposition": "rejected_marking_not_visibly_legible",
    },
    {
        "external_id": "bitrix:4774",
        "media_id": "12133",
        "expected_mpn": "BQ350AA",
        "observed_visible_marking": "not_visibly_legible",
        "disposition": "rejected_marking_not_visibly_legible",
    },
    {
        "external_id": "bitrix:4776",
        "media_id": "12135",
        "expected_mpn": "J1KND",
        "observed_visible_marking": "not_visibly_legible",
        "disposition": "rejected_marking_not_visibly_legible",
    },
    {
        "external_id": "bitrix:4777",
        "media_id": "12136",
        "expected_mpn": "M5Y1K",
        "observed_visible_marking": "not_visibly_legible",
        "disposition": "rejected_marking_not_visibly_legible",
    },
)

HOLD_REASON = "exact_bounded_expected_token_sequence_not_found"
LEDGER_FIELDS = (
    "external_id",
    "media_id",
    "expected_mpn",
    "review_verdict",
    "observed_visible_marking",
    "disposition",
    "content_sha256",
    "storage_path",
    "rights_basis",
    "ocr_verdict",
    "ocr_hold_reason",
    "ocr_text_sha256",
    "contact_sheet",
    "visual_review",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def path_key(value: str) -> str:
    return value.replace("\\", "/").casefold()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def unique_map(rows: list[dict[str, str]], label: str, key) -> dict[object, dict[str, str]]:
    result: dict[object, dict[str, str]] = {}
    for row in rows:
        value = key(row)
        require(value not in result, f"duplicate {label}: {value}")
        result[value] = row
    return result


def build() -> dict[str, object]:
    for path, expected_digest in PINS.items():
        require(sha256(path) == expected_digest, f"review evidence drift: {path.relative_to(ROOT)}")

    selected = {(external_id, media_id): mpn for external_id, media_id, mpn in ALLOWLIST}
    rejected = {(row["external_id"], row["media_id"]): row for row in REJECTED}
    require(len(selected) == len(ALLOWLIST) == 26, "allowlist uniqueness/cardinality drift")
    require(len(rejected) == len(REJECTED) == 7, "rejected uniqueness/cardinality drift")
    require(not (set(selected) & set(rejected)), "review verdict overlap")

    media = unique_map(read_rows(MEDIA_EXPORT), "media external/media key", lambda row: (row["external_id"], row["media_id"]))
    inputs = read_rows(OCR_INPUT)
    reviews = read_rows(OCR_REVIEW)
    require(len(inputs) == len(reviews) == 57, "OCR source cardinality drift")
    input_by_key = unique_map(inputs, "OCR input external/media key", lambda row: (row["external_id"], row["media_id"]))
    review_by_path = unique_map(reviews, "OCR review image path", lambda row: path_key(row["image_path"]))

    contact = json.loads(CONTACT_INDEX.read_text(encoding="utf-8"))
    require(contact.get("schema_version") == 1, "contact schema drift")
    require(contact.get("ocr_input_rows") == 57, "contact input cardinality drift")
    require(contact.get("selected_verdict") == "HOLD", "contact verdict drift")
    require(contact.get("selected_rows") == 33, "contact selected cardinality drift")
    contact_by_key: dict[tuple[str, str], tuple[dict[str, object], str]] = {}
    for sheet in contact.get("sheets", []):
        sheet_name = Path(str(sheet.get("path", ""))).name
        require(bool(sheet_name), "contact sheet path missing")
        for row in sheet.get("rows", []):
            key = (str(row.get("external_id", "")), str(row.get("media_id", "")))
            require(key not in contact_by_key, f"duplicate contact key: {key}")
            contact_by_key[key] = (row, sheet_name)
    require(len(contact_by_key) == 33, "contact row cardinality drift")
    require(set(selected) | set(rejected) == set(contact_by_key), "every contact row needs exactly one review verdict")

    images: list[dict[str, object]] = []
    ledger: list[dict[str, str]] = []
    reviewed_by_key = {**selected, **{key: row["expected_mpn"] for key, row in rejected.items()}}
    for key, expected_mpn in reviewed_by_key.items():
        require(key in media and key in input_by_key and key in contact_by_key, f"incomplete evidence: {key}")
        source, metadata = input_by_key[key], media[key]
        review = review_by_path.get(path_key(source["image_path"]))
        require(review is not None, f"OCR review missing: {key}")
        contact_row, contact_sheet = contact_by_key[key]
        require(source["expected_mpn"].strip() == expected_mpn, f"input MPN drift: {key}")
        require(source["expected_model_core"].strip() == source["manufacturer"].strip() == "", f"exact identity scope drift: {key}")
        require(metadata["identity_scope"].strip() == "exact" and metadata["mpn"].strip() == expected_mpn, f"media identity drift: {key}")
        require(metadata["model_core"].strip() == metadata["manufacturer"].strip() == "", f"media exact fields drift: {key}")
        require(source["hash"] == metadata["content_sha256"] and len(source["hash"]) == 64, f"asset hash drift: {key}")
        require(bool(metadata["storage_path"].strip()), f"storage path missing: {key}")
        require("company-owned" in metadata["rights_basis"].casefold(), f"rights basis drift: {key}")
        require(review["expected_exact"].strip() == expected_mpn, f"OCR expected MPN drift: {key}")
        require(review["verdict"].strip() == "HOLD" and review["hold_reason"].strip() == HOLD_REASON, f"OCR HOLD evidence drift: {key}")
        require(bool(review["ocr_text_sha256"].strip()), f"OCR evidence hash missing: {key}")
        require(str(contact_row.get("expected_exact", "")).strip() == expected_mpn, f"contact MPN drift: {key}")
        require(path_key(str(contact_row.get("image_path", ""))) == path_key(source["image_path"]), f"contact image path drift: {key}")

        if key in rejected:
            item = rejected[key]
            ledger.append({
                "external_id": key[0], "media_id": key[1], "expected_mpn": expected_mpn,
                "review_verdict": "REJECT", "observed_visible_marking": item["observed_visible_marking"],
                "disposition": item["disposition"], "content_sha256": source["hash"],
                "storage_path": metadata["storage_path"], "rights_basis": metadata["rights_basis"],
                "ocr_verdict": "HOLD", "ocr_hold_reason": HOLD_REASON,
                "ocr_text_sha256": review["ocr_text_sha256"], "contact_sheet": contact_sheet,
                "visual_review": "No promotion: the expected exact MPN is not confirmed by the visible marking.",
            })
            continue

        note = (
            "Manual machine-vision contact-sheet review confirmed the exact visible MPN marking "
            f"{expected_mpn}; OCR remained HOLD and was not used as identity proof."
        )
        images.append({
            "external_id": key[0], "media_id": int(key[1]), "content_sha256": source["hash"],
            "storage_path": metadata["storage_path"], "rights_basis": metadata["rights_basis"],
            "identity_scope": "exact", "mpn": expected_mpn,
            "identity_evidence_level": "visible_exact_mpn", "visual_verification_note": note,
            "reviewed_at": "2026-07-29",
        })
        ledger.append({
            "external_id": key[0], "media_id": key[1], "expected_mpn": expected_mpn,
            "review_verdict": "PASS", "observed_visible_marking": expected_mpn,
            "disposition": "promote_visible_exact_mpn", "content_sha256": source["hash"],
            "storage_path": metadata["storage_path"], "rights_basis": metadata["rights_basis"],
            "ocr_verdict": "HOLD", "ocr_hold_reason": HOLD_REASON,
            "ocr_text_sha256": review["ocr_text_sha256"], "contact_sheet": contact_sheet,
            "visual_review": note,
        })

    require(len(images) == 26 and len(ledger) == 33, "review output cardinality drift")
    require(len({row["external_id"] for row in images}) == len(images), "promoted external_id uniqueness drift")
    require(len({row["media_id"] for row in images}) == len(images), "promoted media_id uniqueness drift")
    payload = {
        "schema_version": 1,
        "purpose": "Promote only frozen Wave229-C manually reviewed company-owned legacy preview media; all OCR evidence remains HOLD.",
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
        "reviewed_contact_rows": len(ledger), "promoted_images": len(images),
        "rejected_rows": list(REJECTED), "ocr_required_verdict": "HOLD",
        "media_export_sha256": PINS[MEDIA_EXPORT], "ocr_input_sha256": PINS[OCR_INPUT],
        "ocr_review_sha256": PINS[OCR_REVIEW], "contact_index_sha256": PINS[CONTACT_INDEX],
        "manifest": str(OUTPUT.relative_to(ROOT)).replace("\\", "/"), "manifest_sha256": sha256(OUTPUT),
        "ledger": str(LEDGER.relative_to(ROOT)).replace("\\", "/"), "ledger_sha256": sha256(LEDGER),
        "database_apply": False,
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False))
