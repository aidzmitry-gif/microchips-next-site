#!/usr/bin/env python3
"""Materialize the frozen Wave225 OCR + visual review into a promotion manifest."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OCR_INPUT = ROOT / "docs/audits/generated/rb-wave225-ocr-input.csv"
OCR_REVIEW = ROOT / "docs/audits/generated/rb-wave225-ocr-review.csv"
MEDIA_EXPORT = ROOT / "docs/audits/generated/rb-wave225a-product-media-export.csv"
CONTACT_INDEX = ROOT / ".tmp/wave225-contact-sheets/index.json"
OUTPUT = ROOT / "docs/imports/rb-reviewed-legacy-preview-media-wave225-2026-07-29.json"
LEDGER = ROOT / "docs/audits/generated/rb-reviewed-legacy-preview-media-wave225.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-reviewed-legacy-preview-media-wave225.summary.json"

PINS = {
    OCR_INPUT: "044931add3ce110f7de635dae9cd0d56f99405f877747fc4f50df55a5c8a564a",
    OCR_REVIEW: "4ca7b1cc13de475c9b3d0bb60389d3c77596a0f33e4e8f663f115a206193b3e9",
    CONTACT_INDEX: "272779424eef9031b62725a047983da743c1ea3362fafd814f55bd60b7cd0fed",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def build() -> dict[str, object]:
    for path, expected in PINS.items():
        if sha256(path) != expected:
            raise SystemExit(f"review evidence drift: {path.relative_to(ROOT)}")

    inputs = rows(OCR_INPUT)
    reviews = rows(OCR_REVIEW)
    media = {(row["external_id"], row["media_id"]): row for row in rows(MEDIA_EXPORT)}
    if len(inputs) != 125 or len(reviews) != 125:
        raise SystemExit("OCR review cardinality drift")

    contact = json.loads(CONTACT_INDEX.read_text(encoding="utf-8"))
    sheet_by_key: dict[tuple[str, str], str] = {}
    for sheet in contact["sheets"]:
        for row in sheet["rows"]:
            key = (row["external_id"], row["media_id"])
            if key in sheet_by_key:
                raise SystemExit(f"duplicate contact-sheet key: {key}")
            sheet_by_key[key] = Path(sheet["path"]).name

    images: list[dict[str, object]] = []
    ledger: list[dict[str, str]] = []
    for source, review in zip(inputs, reviews, strict=True):
        if Path(source["image_path"]).resolve() != Path(review["image_path"]).resolve():
            raise SystemExit("OCR row order/path drift")
        if review["verdict"] != "PASS":
            continue

        key = (source["external_id"], source["media_id"])
        if key not in media or key not in sheet_by_key:
            raise SystemExit(f"reviewed media evidence is incomplete: {key}")
        metadata = media[key]
        expected_mpn = source["expected_mpn"].strip()
        expected_model = source["expected_model_core"].strip()
        if bool(expected_mpn) == bool(expected_model):
            raise SystemExit(f"identity scope drift: {key}")
        expected = expected_mpn or expected_model
        normalized_tokens = review["ocr_normalized_tokens"].upper().split()
        expected_tokens = expected.upper().replace("/", " ").replace("-", " ").split()
        if not expected_tokens or not all(token in normalized_tokens for token in expected_tokens):
            raise SystemExit(f"OCR PASS token evidence drift: {key}")

        scope = "exact" if expected_mpn else "model_core"
        note = (
            f"AI visual review of the frozen company-owned image on {sheet_by_key[key]} "
            f"confirms a Panasonic product image with the exact visible {expected} marking; "
            "the independent Windows OCR bounded-token check also passed."
        )
        row: dict[str, object] = {
            "external_id": source["external_id"],
            "media_id": int(source["media_id"]),
            "content_sha256": source["hash"],
            "storage_path": metadata["storage_path"],
            "rights_basis": metadata["rights_basis"],
            "identity_scope": scope,
            "identity_evidence_level": "visible_exact_mpn" if scope == "exact" else "visible_exact_model_core",
            "visual_verification_note": note,
            "reviewed_at": "2026-07-29",
        }
        if scope == "exact":
            row["mpn"] = expected_mpn
        else:
            row["model_core"] = expected_model
            row["manufacturer"] = source["manufacturer"]
        images.append(row)
        ledger.append({
            "external_id": source["external_id"],
            "media_id": source["media_id"],
            "identity_scope": scope,
            "expected_exact": expected,
            "content_sha256": source["hash"],
            "ocr_text_sha256": review["ocr_text_sha256"],
            "contact_sheet": sheet_by_key[key],
            "verdict": "PASS",
        })

    if len(images) != 48 or len({row["external_id"] for row in images}) != 48 or len({row["media_id"] for row in images}) != 48:
        raise SystemExit("frozen visual PASS set must contain exactly 48 unique rows")

    OUTPUT.write_text(json.dumps({
        "schema_version": 1,
        "purpose": "Promote only frozen Wave225 OCR-PASS, visually reviewed company-owned legacy preview media.",
        "locale": "ru-BY",
        "images": images,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with LEDGER.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(ledger[0]))
        writer.writeheader()
        writer.writerows(ledger)

    summary = {
        "schema_version": 1,
        "reviewed_images": len(images),
        "manufacturer": "Panasonic",
        "ocr_input_sha256": PINS[OCR_INPUT],
        "ocr_review_sha256": PINS[OCR_REVIEW],
        "contact_index_sha256": PINS[CONTACT_INDEX],
        "manifest": str(OUTPUT.relative_to(ROOT)).replace("\\", "/"),
        "manifest_sha256": sha256(OUTPUT),
        "database_apply": False,
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False))
