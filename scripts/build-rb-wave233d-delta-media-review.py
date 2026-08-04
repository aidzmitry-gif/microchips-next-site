#!/usr/bin/env python3
"""Build a fail-closed reviewed-media manifest for Wave233 Delta cards."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "docs/audits/generated"
IMP = ROOT / "docs/imports"
IDENTITY = IMP / "rb-delta-identity-stage-manifest-wave233a-2026-07-29.json"
EXPORT = GEN / "rb-wave233-exact-media-candidates.csv"
OCR_INPUT = GEN / "wave233-ocr-batches/wave227-ocr-input-001.csv"
OCR_REVIEW = GEN / "wave233-ocr-batches/wave227-ocr-review-001.csv"
SHEET_INDEX = GEN / "wave233-ocr-pass-sheets/index.json"
MANIFEST = IMP / "rb-reviewed-legacy-preview-media-wave233d-delta-2026-07-29.json"
LEDGER = GEN / "rb-wave233d-delta-media-review.csv"
SUMMARY = GEN / "rb-wave233d-delta-media-review.summary.json"
REPORT = ROOT / "docs/audits/2026-07-29-rb-wave233d-delta-media-review.md"

PINS = {
    IDENTITY: "407c187cbb53fd2193c96be18265f404cabdd1bb7ae086d4ecfe0619f05eab98",
    EXPORT: "753adf37f0b0ab45ea8f0bbe49ece64d97781292600fc95692ef8e3d16c059bf",
    OCR_INPUT: "3c80cec6aa8f67d7969d66eb9ec0829497f5b3d4b2b7845bb6ab3b261ed246f9",
    OCR_REVIEW: "70c922e651ba42c521d52a4aa761cda4c25feb3f13bc16f4d861f87a82a5e4ae",
    SHEET_INDEX: "80ff2c013e50561f97ddb48a83492f363003876695586f740c9ea1553f7fc7fc",
}
EXPECTED_HOLD = {"bitrix:2952": "DT 6033"}
LEDGER_FIELDS = [
    "external_id", "media_id", "expected_mpn", "asset_sha256", "decision",
    "reason", "ocr_tokens", "rights_basis", "identity_proof",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def build() -> dict[str, object]:
    for path, digest in PINS.items():
        require(sha256(path) == digest, f"Pinned Wave233-D input drift: {path.relative_to(ROOT)}")

    identity = json.loads(IDENTITY.read_text(encoding="utf-8-sig"))
    identities = {row["external_id"]: row for row in identity["products"]}
    require(len(identities) == 16, "Wave233-A exact Delta identity scope drift")
    require(all(row["manufacturer"] == "Delta" for row in identities.values()), "Non-Delta identity entered Wave233-D")

    exported = {row["external_id"]: row for row in read_csv(EXPORT) if row["external_id"] in identities}
    inputs = [row for row in read_csv(OCR_INPUT) if row["external_id"] in identities]
    reviews = read_csv(OCR_REVIEW)
    reviews_by_path = {str(Path(row["image_path"]).resolve()): row for row in reviews}
    require(len(exported) == len(inputs) == len(identities), "Wave233-D media/OCR coverage drift")

    sheet = json.loads(SHEET_INDEX.read_text(encoding="utf-8"))
    sheet_ids = {
        row["external_id"]
        for page in sheet["sheets"]
        for row in page["rows"]
    }

    ledger: list[dict[str, str]] = []
    images: list[dict[str, object]] = []
    for row in sorted(inputs, key=lambda item: item["external_id"]):
        external_id = row["external_id"]
        expected = identities[external_id]["mpn"]
        export = exported[external_id]
        image_path = Path(row["image_path"])
        review = reviews_by_path.get(str(image_path.resolve()))
        require(review is not None, f"Missing OCR verdict for {external_id}")
        require(row["expected_mpn"] == export["mpn"] == expected, f"Expected MPN drift for {external_id}")
        require(row["media_id"] == export["media_id"], f"Media ID drift for {external_id}")
        require(row["hash"] == export["content_sha256"] == sha256(image_path), f"Asset hash drift for {external_id}")
        is_pass = review["verdict"] == "PASS" and external_id in sheet_ids
        decision = "PASS" if is_pass else "HOLD"
        reason = "visible_complete_exact_mpn_on_company_owned_asset" if is_pass else review["hold_reason"]
        ledger.append({
            "external_id": external_id,
            "media_id": row["media_id"],
            "expected_mpn": expected,
            "asset_sha256": row["hash"],
            "decision": decision,
            "reason": reason,
            "ocr_tokens": review["ocr_normalized_tokens"],
            "rights_basis": "Company-owned Microchips legacy Bitrix upload backup.",
            "identity_proof": "Wave233-A SHA-pinned official Delta product page",
        })
        if is_pass:
            images.append({
                "external_id": external_id,
                "media_id": int(row["media_id"]),
                "content_sha256": row["hash"],
                "storage_path": export["storage_path"],
                "rights_basis": "Company-owned Microchips legacy Bitrix upload backup.",
                "identity_scope": "exact",
                "mpn": expected,
                "identity_evidence_level": "visible_exact_mpn",
                "visual_verification_note": "OCR and visual contact-sheet review: the complete visible Delta model matches SHA-pinned official manufacturer evidence.",
                "reviewed_at": "2026-07-29",
            })

    holds = {row["external_id"]: row["expected_mpn"] for row in ledger if row["decision"] == "HOLD"}
    require(len(images) == 15 and holds == EXPECTED_HOLD, "Wave233-D PASS/HOLD safety partition drift")
    require(len({row["media_id"] for row in images}) == 15, "Wave233-D repeats a media ID")
    require(len({row["content_sha256"] for row in images}) == 15, "Wave233-D repeats an image binary")

    with LEDGER.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=LEDGER_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(ledger)
    manifest = {
        "schema_version": 1,
        "purpose": "Promote only company-owned Delta legacy assets whose complete visible MPN matches pinned official manufacturer evidence.",
        "locale": "ru-BY",
        "images": images,
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = {
        "schema_version": 1,
        "wave": "wave233d_delta_exact_media",
        "inputs": {path.relative_to(ROOT).as_posix(): sha256(path) for path in PINS},
        "coverage": {"identity_rows": 16, "ocr_and_visual_pass": 15, "holds": 1},
        "manifest": {"path": MANIFEST.relative_to(ROOT).as_posix(), "sha256": sha256(MANIFEST), "rows": 15},
        "ledger": {"path": LEDGER.relative_to(ROOT).as_posix(), "sha256": sha256(LEDGER), "rows": 16},
        "safety": {"database_operations": 0, "apply_performed": False, "media_changes": 0, "price_or_stock_changes": 0},
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REPORT.write_text(
        "# Wave233-D: точные изображения Delta\n\n"
        "Проверены 16 карточек Delta, которым Wave233-A добавил идентичность по закреплённым официальным страницам производителя. "
        "Все файлы являются собственными изображениями из резервной копии Bitrix. OCR и контактные листы подтвердили полную модель на 15 изображениях. "
        "`bitrix:2952` / `DT 6033` оставлен HOLD: точная модель на изображении не доказана. "
        "Манифест содержит только 15 PASS; цена, наличие, публикация и SEO-индексация не меняются.\n",
        encoding="utf-8",
    )
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False))
