#!/usr/bin/env python3
"""Build the fail-closed Wave232-F legacy-media review artifacts.

Official IPPON and EnerSys sources establish catalogue identity only.  The
promotion manifest may contain a row only when the company-owned local asset
itself visibly carries the complete expected MPN.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MEDIA_EXPORT = ROOT / "docs/audits/generated/rb-legacy-preview-candidates-wave232.csv"
OCR_INPUT = ROOT / ".tmp/wave232-ocr/wave227-ocr-input-002.csv"
OCR_REVIEW = ROOT / ".tmp/wave232-ocr/wave227-ocr-review-002.csv"
OCR_LEDGER = ROOT / ".tmp/wave232-ocr/wave227-ocr-batch-ledger.csv"
IPPON_IDENTITY = ROOT / "docs/imports/rb-source-verified-preview-ippon-ups-wave196-2026-07-29.json"
ENERSYS_IDENTITY = ROOT / "docs/imports/rb-verified-oem-identities-wave209a-2026-07-29.json"
ENERSYS_SNAPSHOT = ROOT / "docs/audits/sources/wave209a/enersys-powersafe-v-range.pdf"
ASSET_ROOT = ROOT / ".tmp/wave232-assets"
MANIFEST = ROOT / "docs/imports/rb-legacy-exact-preview-media-wave232f-2026-07-29.json"
LEDGER = ROOT / "docs/audits/generated/rb-wave232f-ippon-enersys-media-review.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-wave232f-ippon-enersys-media-review.summary.json"

REVIEWED_AT = "2026-07-29"
RIGHTS_BASIS = "Company-owned Microchips legacy Bitrix upload backup."
HOLD_REASON = "exact_bounded_expected_token_sequence_not_found"

PINS = {
    MEDIA_EXPORT: "63070e106c635821e1794b864b363d41180bbb74d6a08876191eb0e6acd6c4e7",
    OCR_INPUT: "8dba62e2c8926f419762ed5d089052d7fc77ce7f039f2a9b6fddac37bb32a7bb",
    OCR_REVIEW: "ea28fd2b98e7a6d3f7d4bef86c5e5b02b80b05ff66a97491f66765960ded5fd6",
    OCR_LEDGER: "593a787f9cf67bd92fba7d2f5b04f5c14cea2dc25b1bcaf2c95e18656ceeaf2f",
    IPPON_IDENTITY: "62877dd42866877686568c1dbe79dfc6052b99c0751a4559e82abff515565907",
    ENERSYS_IDENTITY: "ae1cced58e0b29937e0cbb0ee64e77447c7100d9051c26b61cc645c789070467",
    ENERSYS_SNAPSHOT: "bc2664996bb29496c4153bb041c0679296e6c8e1e74f833beceaeb9348c8ba00",
}

TARGETS = {
    "bitrix:25120": {
        "media_id": "1290", "mpn": "Back Verso 800", "manufacturer": "IPPON",
        "verdict": "HOLD", "observed_visible_marking": "IPPON brand only; exact model is not visibly legible",
        "disposition": "hold_no_exact_visible_mpn",
        "official_identity_url": "https://ippon.ru/catalog/item/ippon-800-751623/",
    },
    "bitrix:25135": {
        "media_id": "1302", "mpn": "Back Basic 1500", "manufacturer": "IPPON",
        "verdict": "HOLD", "observed_visible_marking": "IPPON brand only; exact model is not visibly legible",
        "disposition": "hold_no_exact_visible_mpn",
        "official_identity_url": "https://ippon.ru/catalog/item/ippon-1500-1108030/",
    },
    "bitrix:25149": {
        "media_id": "1315", "mpn": "Innova G2 2000L", "manufacturer": "IPPON",
        "verdict": "HOLD", "observed_visible_marking": "IPPON brand only; exact model is not visibly legible",
        "disposition": "hold_no_exact_visible_mpn",
        "official_identity_url": "https://ippon.ru/catalog/item/ippon-2000L-1511522/",
    },
    "bitrix:26048": {
        "media_id": "1566", "mpn": "12V70", "manufacturer": "EnerSys",
        "verdict": "PASS", "observed_visible_marking": "12V70",
        "disposition": "promote_visible_exact_mpn",
        "official_identity_url": "https://www.enersys.com/493bb4/globalassets/documents/product-documentation/powersafe/v-tt/emea/en-v-rs-013.pdf",
    },
}

LEDGER_FIELDS = (
    "external_id", "media_id", "expected_mpn", "manufacturer", "review_verdict",
    "observed_visible_marking", "disposition", "content_sha256", "storage_path",
    "rights_basis", "ocr_verdict", "ocr_hold_reason", "ocr_text_sha256",
    "official_identity_url", "official_identity_evidence", "visual_review",
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def exact_map(rows: list[dict[str, str]], label: str) -> dict[tuple[str, str], dict[str, str]]:
    result: dict[tuple[str, str], dict[str, str]] = {}
    for row in rows:
        key = (row["external_id"], row["media_id"])
        require(key not in result, f"duplicate {label}: {key}")
        result[key] = row
    return result


def ippon_identity_rows() -> dict[str, dict[str, object]]:
    payload = json.loads(IPPON_IDENTITY.read_text(encoding="utf-8"))
    return {str(row["external_id"]): row for row in payload["products"]}


def enersys_identity_rows() -> dict[str, dict[str, object]]:
    payload = json.loads(ENERSYS_IDENTITY.read_text(encoding="utf-8"))
    return {str(row["external_id"]): row for row in payload["products"]}


def build() -> dict[str, object]:
    for path, expected in PINS.items():
        require(digest(path) == expected, f"source evidence drift: {path.relative_to(ROOT)}")

    media = exact_map(read_csv(MEDIA_EXPORT), "media export")
    ocr_input = exact_map(read_csv(OCR_INPUT), "OCR input")
    review_by_path = {row["image_path"].replace("\\", "/").casefold(): row for row in read_csv(OCR_REVIEW)}
    ocr_ledger = exact_map(read_csv(OCR_LEDGER), "OCR ledger")
    ippon = ippon_identity_rows()
    enersys = enersys_identity_rows()

    images: list[dict[str, object]] = []
    ledger: list[dict[str, str]] = []
    for external_id, target in TARGETS.items():
        key = (external_id, target["media_id"])
        require(key in media and key in ocr_input and key in ocr_ledger, f"missing pinned OCR/media evidence: {key}")
        source = ocr_input[key]
        metadata = media[key]
        review = review_by_path.get(source["image_path"].replace("\\", "/").casefold())
        require(review is not None, f"OCR review missing: {key}")
        require(source["expected_mpn"] == metadata["mpn"] == target["mpn"], f"MPN drift: {key}")
        require(source["expected_model_core"] == source["manufacturer"] == "", f"non-exact OCR scope: {key}")
        require(metadata["identity_scope"] == "exact" and metadata["model_core"] == metadata["manufacturer"] == "", f"non-exact media scope: {key}")
        require(source["hash"] == metadata["content_sha256"] and len(source["hash"]) == 64, f"media hash drift: {key}")
        require(metadata["rights_basis"] == RIGHTS_BASIS, f"rights basis drift: {key}")
        asset = ASSET_ROOT / metadata["storage_path"]
        require(asset.is_file() and digest(asset) == source["hash"], f"local asset hash drift: {key}")
        require(review["expected_exact"] == target["mpn"] and review["verdict"] == "HOLD" and review["hold_reason"] == HOLD_REASON, f"OCR review drift: {key}")
        require(
            ocr_ledger[key]["status"] == "selected"
            and ocr_ledger[key]["reason"] == "exported_pinned_identity_and_materialized_hash_match",
            f"OCR ledger drift: {key}",
        )

        if target["manufacturer"] == "IPPON":
            evidence = ippon.get(external_id)
            require(evidence is not None, f"IPPON identity evidence missing: {external_id}")
            require(evidence["manufacturer"] == "IPPON" and evidence["identity_scope"] == "exact" and evidence["mpn"] == target["mpn"], f"IPPON identity drift: {external_id}")
            official_evidence = "official IPPON catalogue and current official product page prove identity only"
        else:
            evidence = enersys.get(external_id)
            require(evidence is not None, "EnerSys identity evidence missing")
            require(evidence["manufacturer"] == "EnerSys" and evidence["mpn"] == "12V70", "EnerSys identity drift")
            require(evidence["source_snapshot_sha256"] == PINS[ENERSYS_SNAPSHOT], "EnerSys snapshot pin drift")
            official_evidence = "official EnerSys PowerSafe V-TT datasheet contains exact 12V70 row; identity only"

        visual_review = (
            "Manual visual review: the complete printed label reads 12V70; official EnerSys evidence corroborates identity only."
            if target["verdict"] == "PASS"
            else "Manual visual review: the IPPON brand and chassis are visible, but no complete expected model marking is legible; official identity evidence cannot replace visible exact-MPN proof."
        )
        ledger.append({
            "external_id": external_id, "media_id": target["media_id"], "expected_mpn": target["mpn"],
            "manufacturer": target["manufacturer"], "review_verdict": target["verdict"],
            "observed_visible_marking": target["observed_visible_marking"], "disposition": target["disposition"],
            "content_sha256": source["hash"], "storage_path": metadata["storage_path"],
            "rights_basis": metadata["rights_basis"], "ocr_verdict": review["verdict"],
            "ocr_hold_reason": review["hold_reason"], "ocr_text_sha256": review["ocr_text_sha256"],
            "official_identity_url": target["official_identity_url"], "official_identity_evidence": official_evidence,
            "visual_review": visual_review,
        })
        if target["verdict"] == "PASS":
            images.append({
                "external_id": external_id, "media_id": int(target["media_id"]),
                "content_sha256": source["hash"], "storage_path": metadata["storage_path"],
                "rights_basis": metadata["rights_basis"], "identity_scope": "exact", "mpn": target["mpn"],
                "identity_evidence_level": "visible_exact_mpn", "visual_verification_note": visual_review,
                "reviewed_at": REVIEWED_AT,
            })

    require(len(ledger) == 4 and len(images) == 1, "review output cardinality drift")
    require(images[0]["external_id"] == "bitrix:26048", "only exact visible 12V70 may be promoted")
    payload = {"locale": "ru-BY", "images": images}
    MANIFEST.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    with LEDGER.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=LEDGER_FIELDS)
        writer.writeheader()
        writer.writerows(ledger)
    summary = {
        "schema_version": 1, "reviewed_rows": len(ledger), "promoted_images": len(images),
        "held_rows": [row["external_id"] for row in ledger if row["review_verdict"] == "HOLD"],
        "manifest": str(MANIFEST.relative_to(ROOT)).replace("\\", "/"), "manifest_sha256": digest(MANIFEST),
        "ledger": str(LEDGER.relative_to(ROOT)).replace("\\", "/"), "ledger_sha256": digest(LEDGER),
        "database_apply": False, "official_assets_used": False,
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=True))
