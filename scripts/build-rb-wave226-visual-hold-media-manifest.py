#!/usr/bin/env python3
"""Build the frozen Wave226 visual-only promotion manifest for OCR-HOLD media."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MEDIA_EXPORT = ROOT / "docs/audits/generated/rb-wave225a-product-media-export.csv"
OCR_INPUT = ROOT / "docs/audits/generated/rb-wave225-ocr-input.csv"
OCR_REVIEW = ROOT / "docs/audits/generated/rb-wave225-ocr-review.csv"
CONTACT_INDEX = ROOT / ".tmp/wave225-hold-contact-sheets/index.json"
OUTPUT = ROOT / "docs/imports/rb-reviewed-legacy-preview-media-wave226-2026-07-29.json"
LEDGER = ROOT / "docs/audits/generated/rb-reviewed-legacy-preview-media-wave226.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-reviewed-legacy-preview-media-wave226.summary.json"

PINS = {
    MEDIA_EXPORT: "58671900c44a64f32419cc3bdf2cb6b020d2a7a41a3b7aec41a320614be59cbc",
    OCR_INPUT: "044931add3ce110f7de635dae9cd0d56f99405f877747fc4f50df55a5c8a564a",
    OCR_REVIEW: "4ca7b1cc13de475c9b3d0bb60389d3c77596a0f33e4e8f663f115a206193b3e9",
    CONTACT_INDEX: "f8a85173a430dc170016ecbf6a85ee9e526ef4f3c61f400e8ee6ad6edb21a563",
}

# Frozen manual visual-review allowlist.  OCR was intentionally retained as HOLD.
ALLOWLIST = (
    ("bitrix:4020", "2208", "BR1632A"),
    ("bitrix:4029", "2215", "BR2032"),
    ("bitrix:4030", "2216", "BR2032"),
    ("bitrix:4036", "2222", "BR2325"),
    ("bitrix:4052", "2234", "BR2477A"),
    ("bitrix:4054", "2236", "BR2477A"),
    ("bitrix:4066", "2248", "CR1025"),
    ("bitrix:4081", "2263", "CR1616"),
    ("bitrix:4084", "2266", "CR1620"),
    ("bitrix:4087", "2269", "CR1632"),
    ("bitrix:4090", "2272", "CR1632"),
    ("bitrix:4092", "2274", "CR2012"),
    ("bitrix:4095", "2277", "CR2016"),
    ("bitrix:4109", "2290", "CR2032"),
    ("bitrix:4115", "2296", "CR2032"),
    ("bitrix:4129", "2308", "CR2412"),
    ("bitrix:4131", "2310", "CR2450"),
    ("bitrix:4132", "2311", "CR2450"),
    ("bitrix:765", "1582", "BR-2/3A"),
    ("bitrix:766", "1583", "BR-2/3AG"),
)

# Explicitly retained outside the promotion set: its visible package marking is CR123,
# not the catalogue's CR2 identity expectation.
REJECTED_CONFLICTS = (
    {
        "external_id": "bitrix:4091",
        "media_id": "2273",
        "expected_exact": "CR2",
        "observed_visible_marking": "CR123",
        "disposition": "rejected_visible_marking_mismatch",
    },
)

HOLD_REASON = "exact_bounded_expected_token_sequence_not_found"
LEDGER_FIELDS = (
    "external_id",
    "media_id",
    "expected_exact",
    "identity_scope",
    "manufacturer",
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


def unique_map(rows: list[dict[str, str]], key_name: str, key) -> dict[object, dict[str, str]]:
    result: dict[object, dict[str, str]] = {}
    for row in rows:
        value = key(row)
        if value in result:
            raise SystemExit(f"duplicate {key_name}: {value}")
        result[value] = row
    return result


def path_key(value: str) -> str:
    return value.replace("\\", "/").casefold()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def build() -> dict[str, object]:
    for path, expected_digest in PINS.items():
        require(sha256(path) == expected_digest, f"review evidence drift: {path.relative_to(ROOT)}")
    require(len(ALLOWLIST) == 20 and len(set(ALLOWLIST)) == 20, "frozen allowlist drift")

    media_rows = read_rows(MEDIA_EXPORT)
    input_rows = read_rows(OCR_INPUT)
    review_rows = read_rows(OCR_REVIEW)
    require(len(media_rows) == len(input_rows) == len(review_rows) == 125, "source cardinality drift")
    media_by_key = unique_map(media_rows, "media key", lambda row: (row["external_id"], row["media_id"]))
    input_by_key = unique_map(input_rows, "OCR input key", lambda row: (row["external_id"], row["media_id"]))
    review_by_path = unique_map(review_rows, "OCR review path", lambda row: path_key(row["image_path"]))
    require(len(media_by_key) == len(input_by_key) == len(review_by_path) == 125, "source uniqueness drift")

    contact = json.loads(CONTACT_INDEX.read_text(encoding="utf-8"))
    require(contact.get("schema_version") == 1, "contact sheet schema drift")
    require(contact.get("selected_verdict") == "HOLD", "contact sheet verdict drift")
    require(contact.get("selected_rows") == 77, "contact sheet selection cardinality drift")
    contact_by_key: dict[tuple[str, str], tuple[dict[str, object], str]] = {}
    for sheet in contact.get("sheets", []):
        sheet_path = str(sheet.get("path", ""))
        require(bool(sheet_path), "contact sheet path missing")
        for row in sheet.get("rows", []):
            key = (str(row.get("external_id", "")), str(row.get("media_id", "")))
            require(key not in contact_by_key, f"duplicate contact-sheet key: {key}")
            contact_by_key[key] = (row, Path(sheet_path).name)

    selected_keys = {(external_id, media_id) for external_id, media_id, _ in ALLOWLIST}
    for conflict in REJECTED_CONFLICTS:
        key = (conflict["external_id"], conflict["media_id"])
        require(key not in selected_keys, f"rejected conflict included in allowlist: {key}")
        require(key in media_by_key and key in input_by_key and key in contact_by_key, f"rejected conflict evidence missing: {key}")
        require(input_by_key[key]["expected_model_core"].strip() == conflict["expected_exact"], f"rejected conflict identity drift: {key}")

    images: list[dict[str, object]] = []
    ledger: list[dict[str, str]] = []
    for external_id, media_id, expected_exact in ALLOWLIST:
        key = (external_id, media_id)
        require(key in media_by_key and key in input_by_key and key in contact_by_key, f"incomplete evidence: {key}")
        source = input_by_key[key]
        metadata = media_by_key[key]
        review = review_by_path.get(path_key(source["image_path"]))
        require(review is not None, f"OCR review missing: {key}")
        contact_row, contact_sheet = contact_by_key[key]

        require(source["expected_mpn"].strip() == "", f"unexpected exact MPN scope: {key}")
        require(source["expected_model_core"].strip() == expected_exact, f"model-core evidence drift: {key}")
        require(source["manufacturer"].strip() == "Panasonic", f"manufacturer evidence drift: {key}")
        require(source["hash"] == metadata["hash"] and len(source["hash"]) == 64, f"media hash drift: {key}")
        require(bool(metadata["storage_path"].strip()), f"storage path missing: {key}")
        require(bool(metadata["rights_basis"].strip()) and "company-owned" in metadata["rights_basis"].casefold(), f"rights basis missing: {key}")
        require(review["expected_exact"].strip() == expected_exact, f"OCR expected marking drift: {key}")
        require(review["verdict"].strip() == "HOLD", f"OCR must remain HOLD: {key}")
        require(review["hold_reason"].strip() == HOLD_REASON, f"OCR HOLD reason drift: {key}")
        require(bool(review["ocr_text_sha256"].strip()), f"OCR evidence hash missing: {key}")
        require(str(contact_row.get("expected_exact", "")).strip() == expected_exact, f"contact marking drift: {key}")
        require(path_key(str(contact_row.get("image_path", ""))) == path_key(source["image_path"]), f"contact image path drift: {key}")

        note = (
            "Manual machine-vision contact-sheet review confirmed the exact visible product "
            f"marking {expected_exact}; OCR remained HOLD and was not used as identity proof."
        )
        images.append({
            "external_id": external_id,
            "media_id": int(media_id),
            "content_sha256": source["hash"],
            "storage_path": metadata["storage_path"],
            "rights_basis": metadata["rights_basis"],
            "identity_scope": "model_core",
            "model_core": expected_exact,
            "manufacturer": source["manufacturer"],
            "identity_evidence_level": "visible_exact_model_core",
            "visual_verification_note": note,
            "reviewed_at": "2026-07-29",
        })
        ledger.append({
            "external_id": external_id,
            "media_id": media_id,
            "expected_exact": expected_exact,
            "identity_scope": "model_core",
            "manufacturer": source["manufacturer"],
            "content_sha256": source["hash"],
            "storage_path": metadata["storage_path"],
            "rights_basis": metadata["rights_basis"],
            "ocr_verdict": review["verdict"],
            "ocr_hold_reason": review["hold_reason"],
            "ocr_text_sha256": review["ocr_text_sha256"],
            "contact_sheet": contact_sheet,
            "visual_review": note,
        })

    require(len(images) == len({row["external_id"] for row in images}) == 20, "allowlist output cardinality drift")
    require(len({row["media_id"] for row in images}) == 20, "allowlist media uniqueness drift")
    payload = {
        "schema_version": 1,
        "purpose": "Promote only frozen Wave226 manually reviewed company-owned legacy preview media; all OCR evidence remains HOLD.",
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
        "manufacturer": "Panasonic",
        "allowlist_count": len(ALLOWLIST),
        "rejected_conflicts": list(REJECTED_CONFLICTS),
        "ocr_required_verdict": "HOLD",
        "media_export_sha256": PINS[MEDIA_EXPORT],
        "ocr_input_sha256": PINS[OCR_INPUT],
        "ocr_review_sha256": PINS[OCR_REVIEW],
        "contact_index_sha256": PINS[CONTACT_INDEX],
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
