#!/usr/bin/env python3
"""Build the fail-closed Wave235 legacy-media review and promotion manifest."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPORT = ROOT / "docs/audits/generated/rb-wave235-media-candidates.csv"
BATCH_LEDGER = ROOT / "docs/audits/generated/rb-wave235-ocr/wave227-ocr-batch-ledger.csv"
OCR_INPUTS = [ROOT / f"docs/audits/generated/rb-wave235-ocr/wave227-ocr-input-{n:03d}.csv" for n in (1, 2)]
OCR_REVIEWS = [ROOT / f"docs/audits/generated/rb-wave235-ocr/wave227-ocr-review-{n:03d}.csv" for n in (1, 2)]
SHEET_INDEXES = [
    ROOT / "docs/audits/generated/rb-wave235-sheets/b1-hold/index.json",
    ROOT / "docs/audits/generated/rb-wave235-sheets/b2-hold/index.json",
]
MANIFEST = ROOT / "docs/imports/rb-reviewed-legacy-preview-media-wave235-2026-07-29.json"
LEDGER = ROOT / "docs/audits/generated/rb-wave235-reviewed-media.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-wave235-reviewed-media.summary.json"

PINS = {
    EXPORT: "4a6bb039f8463df1f2a6bda2b2cbcadb3af80f9e9f407ed449cb463774e834f0",
    BATCH_LEDGER: "ccae96b71109cb529aba0b7adb1a27918a8c75ec9d63cdeacc00691a32b332ce",
    OCR_INPUTS[0]: "fb40c76fca463a7e6a369ea50a0dece9d45aea109a7db2cb3e8a74c4563c3156",
    OCR_INPUTS[1]: "29a2daee3d78402c08f54456c3572e3cd3d59b62ce80ca338b1a927d8665d60a",
    OCR_REVIEWS[0]: "273226db3b87a32ec74fbaa8f9e066f9e63f626f54a711c44ef83046d2d57625",
    OCR_REVIEWS[1]: "5cf18e3341151aa23ca57f8677556f19075fc0a7ee1c2d57e24c5b162e4c01c4",
    SHEET_INDEXES[0]: "337490ac49646d8494acef22d665774a32161e537593f164b8f104a9acdb3f3f",
    SHEET_INDEXES[1]: "f3d505fa5727053ff7818752ac845c9a72864acfd0856971da3668abed9825d5",
}

# Every PASS below was inspected at original resolution. The complete expected
# MPN is visibly present on the pictured item; title or filename agreement is
# deliberately insufficient.
VISUAL_PASS = {
    "bitrix:11753": "Robiton LiFe18650 is visible on the cell label",
    "bitrix:1464": "MNB MM 120-12 is visible on the battery label",
    "bitrix:1493": "Ventura GP 12-12 is visible on the battery label",
    "bitrix:1526": "BB Battery BC17-12 is visible on the battery label",
    "bitrix:1561": "MNB MM 200-12 is visible on the battery label",
    "bitrix:1617": "BB Battery HR5.8-12 is visible on the battery label",
    "bitrix:24551": "EnerSys 0810-0008 is visible on the pack label",
    "bitrix:2952": "Delta DT 6033 is visible on the battery label",
    "bitrix:4776": "Dell Type J1KND is visible on the battery label",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> None:
    for path, digest in PINS.items():
        require(path.is_file() and sha256(path) == digest, f"Pinned Wave235 input drift: {path.relative_to(ROOT)}")

    exported = {row["external_id"]: row for row in read_csv(EXPORT)}
    batches = {row["external_id"]: row for row in read_csv(BATCH_LEDGER)}
    inputs = [row for path in OCR_INPUTS for row in read_csv(path)]
    reviews = [row for path in OCR_REVIEWS for row in read_csv(path)]
    require(len(exported) == len(batches) == 117, "Wave235 export/batch coverage drift")
    require(len(inputs) == len(reviews) == 70, "Wave235 selected OCR coverage drift")
    require(set(exported) == set(batches), "Wave235 batch ledger does not cover the export")

    inputs_by_id = {row["external_id"]: row for row in inputs}
    reviews_by_path = {str(Path(row["image_path"]).resolve()): row for row in reviews}
    selected_ids = {external_id for external_id, row in batches.items() if row["status"] == "selected"}
    shared_ids = {external_id for external_id, row in batches.items() if row["status"] == "hold"}
    require(len(selected_ids) == 70 and len(shared_ids) == 47, "Wave235 selected/shared partition drift")
    require(set(inputs_by_id) == selected_ids, "OCR inputs do not exactly cover selected binaries")
    require(set(VISUAL_PASS) <= selected_ids, "A visual PASS escaped the unique-binary review lane")

    sheet_ids = {
        row["external_id"]
        for path in SHEET_INDEXES
        for sheet in json.loads(path.read_text(encoding="utf-8"))["sheets"]
        for row in sheet["rows"]
    }
    require(sheet_ids == selected_ids, "Machine-vision sheet coverage is incomplete")

    ledger: list[dict[str, str]] = []
    images: list[dict[str, object]] = []
    for external_id in sorted(exported):
        export, batch = exported[external_id], batches[external_id]
        require(export["media_id"] == batch["media_id"], f"Media ID drift: {external_id}")
        require(export["content_sha256"] == batch["content_sha256"], f"Binary drift: {external_id}")
        require(export["mpn"] == batch["expected_exact"], f"MPN drift: {external_id}")
        require(export["identity_scope"] == batch["identity_scope"] == "exact", f"Non-exact identity: {external_id}")

        if external_id in shared_ids:
            decision = "HOLD"
            reason = "shared binary is assigned to multiple product identities"
            ocr_verdict = "NOT_RUN"
            ocr_tokens = ""
        else:
            ocr_input = inputs_by_id[external_id]
            review = reviews_by_path.get(str(Path(ocr_input["image_path"]).resolve()))
            require(review is not None, f"Missing OCR review: {external_id}")
            require(ocr_input["hash"] == export["content_sha256"], f"OCR hash drift: {external_id}")
            require(ocr_input["expected_mpn"] == export["mpn"], f"OCR MPN drift: {external_id}")
            decision = "PASS" if external_id in VISUAL_PASS else "HOLD"
            reason = VISUAL_PASS.get(external_id, "complete exact MPN is absent, ambiguous, or unreadable in visual review")
            ocr_verdict = review["verdict"]
            ocr_tokens = review["ocr_normalized_tokens"]

        ledger.append({
            "external_id": external_id,
            "media_id": export["media_id"],
            "expected_mpn": export["mpn"],
            "asset_sha256": export["content_sha256"],
            "batch_status": batch["status"],
            "ocr_verdict": ocr_verdict,
            "visual_decision": decision,
            "reason": reason,
            "ocr_tokens": ocr_tokens,
            "rights_basis": export["rights_basis"],
        })
        if decision == "PASS":
            images.append({
                "external_id": external_id,
                "media_id": int(export["media_id"]),
                "content_sha256": export["content_sha256"],
                "storage_path": export["storage_path"],
                "rights_basis": export["rights_basis"],
                "identity_scope": "exact",
                "mpn": export["mpn"],
                "identity_evidence_level": "visible_exact_mpn",
                "visual_verification_note": f"Original-resolution and contact-sheet review: {reason}.",
                "reviewed_at": "2026-07-29",
            })

    require(len(images) == 9, f"Wave235 PASS count drift: {len(images)}")
    require(len({row["media_id"] for row in images}) == len({row["content_sha256"] for row in images}) == 9,
            "PASS media IDs or binaries repeat")

    with LEDGER.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(ledger[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(ledger)
    manifest = {
        "schema_version": 1,
        "purpose": "Promote only company-owned legacy assets with a unique binary and a complete exact MPN visibly confirmed at original resolution.",
        "locale": "ru-BY",
        "images": images,
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = {
        "schema_version": 1,
        "wave": "wave235_unique_exact_legacy_media",
        "checked_at": "2026-07-29",
        "inputs": {path.relative_to(ROOT).as_posix(): digest for path, digest in PINS.items()},
        "coverage": {
            "exported": 117,
            "shared_binary_holds": 47,
            "unique_binary_reviewed": 70,
            "ocr_pass": sum(row["ocr_verdict"] == "PASS" for row in ledger),
            "visual_pass": 9,
            "visual_holds": 108,
        },
        "manifest": {"path": MANIFEST.relative_to(ROOT).as_posix(), "sha256": sha256(MANIFEST), "rows": len(images)},
        "ledger": {"path": LEDGER.relative_to(ROOT).as_posix(), "sha256": sha256(LEDGER), "rows": len(ledger)},
        "safety": {"database_operations": 0, "apply_performed": False, "media_changes": 0,
                   "price_or_stock_changes": 0, "publication_changes": 0},
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"rows": len(ledger), "pass": len(images), "hold": len(ledger) - len(images)}))


if __name__ == "__main__":
    main()
