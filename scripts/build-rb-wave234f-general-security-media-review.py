#!/usr/bin/env python3
"""Build the visually reviewed General Security legacy-media manifest."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
IDENTITY = ROOT / "docs/imports/rb-verified-oem-identities-wave234c-general-security-2026-07-29.json"
EXPORT = ROOT / "docs/audits/generated/rb-wave234e-general-security-media-candidates.csv"
OCR_INPUTS = [ROOT / f"docs/audits/generated/rb-wave234e-ocr-ready/wave227-ocr-input-{n:03d}.csv" for n in (1, 2)]
OCR_REVIEWS = [ROOT / f"docs/audits/generated/rb-wave234e-ocr-ready/wave227-ocr-review-{n:03d}.csv" for n in (1, 2)]
SHEET_INDEXES = [
    ROOT / "docs/audits/generated/rb-wave234e-sheets/b1-pass/index.json",
    ROOT / "docs/audits/generated/rb-wave234e-sheets/b1-hold/index.json",
    ROOT / "docs/audits/generated/rb-wave234e-sheets/b2-pass/index.json",
    ROOT / "docs/audits/generated/rb-wave234e-sheets/b2-hold/index.json",
]
MANIFEST = ROOT / "docs/imports/rb-reviewed-legacy-preview-media-wave234f-general-security-2026-07-29.json"
LEDGER = ROOT / "docs/audits/generated/rb-wave234f-general-security-media-review.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-wave234f-general-security-media-review.summary.json"

PINS = {
    IDENTITY: "3cd236915ce0ed154ba145b8278b9fe59f9f567b50b5dff35270d1b6102b923e",
    EXPORT: "601d93a7797d963d03cb3db91226950dc44ccb7ba0fff2880584de5bf399f556",
    OCR_INPUTS[0]: "8f9f314ffc22dfddb072319c6a0e9e0facf14ec8dc7e3ee134571a0de528db9d",
    OCR_INPUTS[1]: "a0a20f399397a74f3151d3570bba72a78acc5813570cdaea987f8b0f55c579c7",
    OCR_REVIEWS[0]: "18e70c120f19e38d9e70716362dc7148dcddabfb685a4db3053f35e4661fcc2e",
    OCR_REVIEWS[1]: "ccce871d125039446b7829dd6be42f451f97c48c08c264ab0c4e0ca27ff9634f",
    SHEET_INDEXES[0]: "298c11a38b1ecc845d6610f3a9d9ff90360093b3bcbfceafb263a14743677095",
    SHEET_INDEXES[1]: "e3289d843f1c74a17f5c301c806ea72cdc3b5593d6e3c8119bd8f2424ad6a730",
    SHEET_INDEXES[2]: "8ac8cce8baeb689e6603085d951064ae2993bea822259b0adf3ea79961ed9090",
    SHEET_INDEXES[3]: "43507c1714b558fccd6dd88c91ccdc3397c6305def208d6f3cb6516d5ae848b6",
}
VISUAL_MISMATCHES = {
    "bitrix:3034": "expected GSL 40-12; visible label is GS 40-12",
    "bitrix:3135": "expected GSL 65-12; visible label is GS 65-12",
    "bitrix:3268": "expected GS 9-12; visible label is GSL 7.2-12",
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
        require(path.is_file() and sha256(path) == digest, f"Pinned Wave234-F input drift: {path.relative_to(ROOT)}")
    identities = {row["external_id"]: row for row in json.loads(IDENTITY.read_text(encoding="utf-8"))["products"]}
    exported = {row["external_id"]: row for row in read_csv(EXPORT)}
    inputs = [row for path in OCR_INPUTS for row in read_csv(path)]
    reviews = [row for path in OCR_REVIEWS for row in read_csv(path)]
    require(len(identities) == len(exported) == len(inputs) == len(reviews) == 29, "Wave234-F coverage drift")
    reviews_by_path = {str(Path(row["image_path"]).resolve()): row for row in reviews}
    sheet_ids = {
        row["external_id"]
        for path in SHEET_INDEXES
        for page in json.loads(path.read_text(encoding="utf-8"))["sheets"]
        for row in page["rows"]
    }
    require(sheet_ids == set(identities), "Visual contact-sheet coverage is incomplete")

    ledger = []
    images = []
    for row in sorted(inputs, key=lambda item: item["external_id"]):
        external_id = row["external_id"]
        identity, export = identities[external_id], exported[external_id]
        review = reviews_by_path.get(str(Path(row["image_path"]).resolve()))
        require(review is not None, f"Missing OCR review: {external_id}")
        require(row["expected_mpn"] == identity["mpn"] == export["mpn"], f"MPN drift: {external_id}")
        require(row["media_id"] == export["media_id"] and row["hash"] == export["content_sha256"], f"Media drift: {external_id}")
        mismatch = VISUAL_MISMATCHES.get(external_id)
        decision = "HOLD" if mismatch else "PASS"
        reason = mismatch or "complete exact model is visibly confirmed on the machine-vision contact sheet"
        ledger.append({
            "external_id": external_id, "media_id": row["media_id"], "expected_mpn": identity["mpn"],
            "asset_sha256": row["hash"], "ocr_verdict": review["verdict"],
            "visual_decision": decision, "reason": reason, "ocr_tokens": review["ocr_normalized_tokens"],
            "rights_basis": export["rights_basis"],
        })
        if decision == "PASS":
            images.append({
                "external_id": external_id, "media_id": int(row["media_id"]),
                "content_sha256": row["hash"], "storage_path": export["storage_path"],
                "rights_basis": export["rights_basis"], "identity_scope": "exact", "mpn": identity["mpn"],
                "identity_evidence_level": "visible_exact_mpn",
                "visual_verification_note": "Machine-vision contact-sheet review confirms the complete visible General Security model against pinned official catalogue evidence.",
                "reviewed_at": "2026-07-29",
            })
    require(len(images) == 26, f"Wave234-F PASS count drift: {len(images)}")
    require({row["external_id"] for row in ledger if row["visual_decision"] == "HOLD"} == set(VISUAL_MISMATCHES), "Visual HOLD set drift")
    require(len({row["media_id"] for row in images}) == len({row["content_sha256"] for row in images}) == 26, "PASS media IDs or binaries repeat")

    with LEDGER.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(ledger[0]), lineterminator="\n")
        writer.writeheader(); writer.writerows(ledger)
    manifest = {
        "schema_version": 1,
        "purpose": "Promote only company-owned General Security legacy assets whose complete visible model matches pinned official catalogue evidence.",
        "locale": "ru-BY", "images": images,
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = {
        "schema_version": 1, "wave": "wave234f_general_security_exact_media", "checked_at": "2026-07-29",
        "inputs": {path.relative_to(ROOT).as_posix(): digest for path, digest in PINS.items()},
        "coverage": {"identity_rows": 29, "ocr_pass": sum(row["ocr_verdict"] == "PASS" for row in ledger),
                     "visual_pass": 26, "visual_holds": 3},
        "visual_mismatches": VISUAL_MISMATCHES,
        "manifest": {"path": MANIFEST.relative_to(ROOT).as_posix(), "sha256": sha256(MANIFEST), "rows": len(images)},
        "ledger": {"path": LEDGER.relative_to(ROOT).as_posix(), "sha256": sha256(LEDGER), "rows": len(ledger)},
        "safety": {"database_operations": 0, "apply_performed": False, "media_changes": 0,
                   "price_or_stock_changes": 0, "publication_changes": 0},
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"rows": len(ledger), "pass": len(images), "hold": len(VISUAL_MISMATCHES)}))


if __name__ == "__main__":
    main()
