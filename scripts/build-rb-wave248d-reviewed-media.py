#!/usr/bin/env python3
"""Freeze Wave248D visual decisions and a two-row exact-media promotion manifest."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPORT = ROOT / "docs/audits/generated/rb-wave248d-legacy-media-candidates-2026-07-30.csv"
INDEX = ROOT / "docs/audits/generated/wave248d-ocr-batches/index.json"
BATCH_LEDGER = ROOT / "docs/audits/generated/wave248d-ocr-batches/wave227-ocr-batch-ledger.csv"
OCR_INPUT = ROOT / "docs/audits/generated/wave248d-ocr-batches/wave227-ocr-input-001.csv"
OCR_REVIEW = ROOT / "docs/audits/generated/wave248d-ocr-batches/wave227-ocr-review-001.csv"
ASSET_ROOT = ROOT / ".tmp/wave248d-assets"
MANIFEST = ROOT / "docs/imports/rb-reviewed-legacy-preview-media-wave248d-2026-07-30.json"
LEDGER = ROOT / "docs/audits/generated/rb-wave248d-reviewed-media-2026-07-30.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-wave248d-reviewed-media-2026-07-30.json"
REPORT = ROOT / "docs/audits/2026-07-30-rb-wave248d-reviewed-media.md"

PINS = {
    EXPORT: "d266b8984dab740eb9c0a6893546c3cb0096f1171b0a94f6e557203decb3264b",
    INDEX: "dea86403032fef43d156c22ae0696f964728d779eef74bafa3f929d5e9b107b8",
    BATCH_LEDGER: "9e1cf1fa4ed3ad2612d46dca19f568d062e84c2c54492f0e8ab582e5c95a23e1",
    OCR_INPUT: "c825454fc7add7419821281b338a9ab7c517b865796dd808591e4218638c625f",
    OCR_REVIEW: "5aaeee06529a02fe2bd5b597292c59c8b076df057841e7ba67fd6be01445c700",
}

VISUAL = {
    ("bitrix:20397", "10248"): (
        "HOLD",
        "exact_mpn_not_visibly_legible",
        "The image shows an open-frame power supply, but ELP-75-3.3 is not legible; the family form factor cannot prove the voltage variant.",
    ),
    ("bitrix:24373", "13917"): (
        "PASS",
        "visible_exact_mpn",
        "Manual machine-vision review confirmed the exact DCB145-6 marking on the battery label; the company-owned image is watermarked Microchips.",
    ),
    ("bitrix:24374", "13918"): (
        "PASS",
        "visible_exact_mpn",
        "Manual machine-vision review confirmed the exact DCB105-6 marking on the battery label; the company-owned image is watermarked Microchips.",
    ),
    ("bitrix:25120", "14409"): (
        "HOLD",
        "exact_mpn_not_visibly_legible",
        "The IPPON brand and enclosure are visible, but Back Verso 800 is not printed legibly and the manufacturer documents multiple appearance revisions.",
    ),
    ("bitrix:25135", "14421"): (
        "HOLD",
        "exact_mpn_not_visibly_legible",
        "The IPPON brand and UPS family form are visible, but Back Basic 1500 is not legible; adjacent power variants share the enclosure.",
    ),
    ("bitrix:25149", "14434"): (
        "HOLD",
        "exact_mpn_not_visibly_legible",
        "The IPPON brand and online-UPS form are visible, but Innova G2 2000L is not legible; appearance alone is not exact identity evidence.",
    ),
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def build() -> dict[str, object]:
    for path, expected in PINS.items():
        require(path.is_file() and digest(path) == expected, f"Wave248D evidence drift: {path.relative_to(ROOT)}")

    index = json.loads(INDEX.read_text(encoding="utf-8"))
    require(index["selected_rows"] == 6 and index["shared_asset_hash_holds"] == 28, "Wave248D scope drift")
    exports = {(row["external_id"], row["media_id"]): row for row in read_rows(EXPORT)}
    batch = read_rows(BATCH_LEDGER)
    inputs = {(row["external_id"], row["media_id"]): row for row in read_rows(OCR_INPUT)}
    reviews = {Path(row["image_path"]).name: row for row in read_rows(OCR_REVIEW)}
    require(len(exports) == len(batch) == 34 and len(inputs) == len(VISUAL) == 6, "Wave248D cardinality drift")

    decisions: list[dict[str, object]] = []
    promoted: list[dict[str, object]] = []
    for row in batch:
        key = (row["external_id"], row["media_id"])
        source = exports.get(key)
        require(source is not None, f"Missing exporter evidence for {key}")
        require(source["content_sha256"] == row["content_sha256"], f"Asset hash drift for {key}")
        asset = ASSET_ROOT / source["storage_path"]
        require(asset.is_file() and digest(asset) == source["content_sha256"], f"Materialized asset drift for {key}")
        require("company-owned" in source["rights_basis"].casefold(), f"Rights evidence drift for {key}")

        if row["status"] == "hold":
            require(row["reason"] == "shared_asset_hash_across_products", f"Unexpected batch HOLD for {key}")
            verdict = "HOLD"
            reason = "shared_asset_hash_across_products"
            note = "The same asset hash is assigned to multiple exact products; it cannot prove an individual SKU without a readable exact marking."
            ocr_verdict = "NOT_RUN_SHARED_HASH_HOLD"
        else:
            require(row["status"] == "selected" and key in VISUAL and key in inputs, f"Unexpected selected row {key}")
            verdict, reason, note = VISUAL[key]
            review = reviews.get(Path(inputs[key]["image_path"]).name)
            require(review is not None and review["verdict"] == "HOLD", f"OCR evidence drift for {key}")
            ocr_verdict = "HOLD"

        decision = {
            "external_id": row["external_id"],
            "media_id": int(row["media_id"]),
            "expected_exact": row["expected_exact"],
            "content_sha256": row["content_sha256"],
            "storage_path": source["storage_path"],
            "rights_basis": source["rights_basis"],
            "ocr_verdict": ocr_verdict,
            "visual_verdict": verdict,
            "disposition": reason,
            "visual_verification_note": note,
        }
        decisions.append(decision)
        if verdict == "PASS":
            require(source["identity_scope"] == "exact" and source["mpn"] == row["expected_exact"], f"Exact identity drift for {key}")
            promoted.append({
                "external_id": row["external_id"],
                "media_id": int(row["media_id"]),
                "content_sha256": row["content_sha256"],
                "storage_path": source["storage_path"],
                "rights_basis": source["rights_basis"],
                "identity_scope": "exact",
                "mpn": source["mpn"],
                "identity_evidence_level": "visible_exact_mpn",
                "visual_verification_note": note,
                "reviewed_at": "2026-07-30",
            })

    require(len(promoted) == 2, "Wave248D must promote exactly two visually exact Yuasa images")
    require({row["external_id"] for row in promoted} == {"bitrix:24373", "bitrix:24374"}, "Wave248D PASS set drift")
    require(len({row["content_sha256"] for row in decisions}) == 13, "Expected shared-asset hash structure drift")

    MANIFEST.write_text(json.dumps({
        "schema_version": 1,
        "purpose": "Promote only two company-owned Wave248D images with a visually readable exact Yuasa MPN.",
        "locale": "ru-BY",
        "images": promoted,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    fields = list(decisions[0])
    with LEDGER.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(decisions)
    summary = {
        "schema_version": 1,
        "wave": "wave248d",
        "reviewed": len(decisions),
        "shared_hash_holds": sum(row["disposition"] == "shared_asset_hash_across_products" for row in decisions),
        "selected_visual_reviews": len(VISUAL),
        "pass": len(promoted),
        "hold": len(decisions) - len(promoted),
        "manifest": str(MANIFEST.relative_to(ROOT)).replace("\\", "/"),
        "manifest_sha256": digest(MANIFEST),
        "ledger": str(LEDGER.relative_to(ROOT)).replace("\\", "/"),
        "ledger_sha256": digest(LEDGER),
        "database_apply": False,
        "publication_changes": 0,
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REPORT.write_text(
        "# Wave248D — проверка собственных изображений B2B-когорты\n\n"
        "Проверены 34 изображения из резервной копии Bitrix, принадлежащие Microchips. "
        "Двадцать восемь файлов оставлены HOLD, потому что один и тот же хэш назначен разным точным товарам. "
        "Из шести уникальных файлов два изображения Yuasa прошли ручную машинно-визуальную проверку: "
        "на этикетках читаются точные модели DCB145-6 и DCB105-6. Mean Well и три IPPON оставлены HOLD, "
        "поскольку точная модель не читается, а сходство корпуса не доказывает SKU.\n\n"
        "Итог: 2 PASS, 32 HOLD; удалённые изображения производителей не копировались; БД на этапе сборки не изменялась.\n",
        encoding="utf-8",
    )
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False))
