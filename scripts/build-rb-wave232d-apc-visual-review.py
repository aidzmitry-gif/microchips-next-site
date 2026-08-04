"""Create a fail-closed APC visual-review manifest for the Wave232 OCR scope."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OCR_ROOT = ROOT / ".tmp/wave232-ocr"
INPUTS = [OCR_ROOT / "wave227-ocr-input-001.csv", OCR_ROOT / "wave227-ocr-input-002.csv"]
OCR_REVIEWS = [OCR_ROOT / "wave227-ocr-review-001.csv", OCR_ROOT / "wave227-ocr-review-002.csv"]
CANDIDATES = ROOT / "docs/audits/generated/rb-wave227-legacy-preview-candidates.csv"
VISUAL = ROOT / "docs/audits/generated/rb-wave229b-hold-002-visual-review.csv"
OFFICIAL = ROOT / "docs/audits/generated/rb-wave209a-official-evidence.csv"
MANIFEST = ROOT / "docs/imports/rb-apc-visual-review-wave232d-2026-07-29.json"
LEDGER = ROOT / "docs/audits/generated/rb-wave232d-apc-visual-review.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-wave232d-apc-visual-review.summary.json"
REPORT = ROOT / "docs/audits/2026-07-29-rb-wave232d-apc-visual-review.md"
RIGHTS = "Company-owned Microchips legacy Bitrix upload backup."


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalized(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def main() -> None:
    inputs = [row for path in INPUTS for row in rows(path)]
    official = {row["product_external_id"]: row for row in rows(OFFICIAL)}
    # APC is not populated in the manufacturer column of these OCR inputs.
    # The official APC/Schneider evidence set is the authoritative scope key.
    apc = [row for row in inputs if row["external_id"] in official and official[row["external_id"]]["manufacturer_cluster"] == "APC"]
    if len(apc) != 28 or len({row["external_id"] for row in apc}) != 28:
        raise SystemExit("Wave232-D APC scope must contain exactly 28 unique candidates")
    candidate = {row["external_id"]: row for row in rows(CANDIDATES)}
    visual = {row["external_id"]: row for row in rows(VISUAL)}
    ocr = {row["image_path"]: row for path in OCR_REVIEWS for row in rows(path)}

    ledger: list[dict[str, str]] = []
    reviewed: list[dict[str, object]] = []
    for row in apc:
        external_id = row["external_id"]
        expected = row["expected_mpn"]
        own = candidate.get(external_id)
        manual = visual.get(external_id)
        official_row = official[external_id]
        image = Path(row["image_path"])
        review = ocr.get(row["image_path"])
        source = (ROOT / "docs/imports" / official_row["source_snapshot_path"]).resolve()
        if (
            own is None or manual is None or review is None
            or own["media_id"] != row["media_id"]
            or own["content_sha256"] != row["hash"]
            or own["storage_path"] != "legacy-staging/rb/" + image.name
            or own["rights_basis"] != RIGHTS
            or manual["expected_mpn"] != expected
            or manual["verdict"] != "HOLD"
            or manual["reason"] != "exact_mpn_not_visibly_legible_or_generic_asset"
            or manual["promotion_eligible"] != "false"
            or review["verdict"] != "HOLD"
            or not image.is_file() or digest(image) != row["hash"]
            or official_row["model_token"] != expected
            or official_row["evidence_scope"] != "exact_official_product_page"
            or not official_row["source_url"].startswith("https://www.se.com/")
            or not source.is_file() or digest(source) != official_row["source_snapshot_sha256"]
            or normalized(expected) not in normalized(source.read_text(encoding="utf-8", errors="replace"))
        ):
            raise SystemExit(f"{external_id}: APC source, own-media, OCR or visual pin drift")
        disposition = "HOLD_exact_mpn_not_visibly_legible_or_generic_asset"
        note = "Visual review: APC branding/form factor is visible, but the exact expected MPN is not legible; generic appearance is insufficient."
        common = {
            "external_id": external_id,
            "media_id": int(row["media_id"]),
            "expected_mpn": expected,
            "content_sha256": row["hash"],
            "storage_path": own["storage_path"],
            "rights_basis": RIGHTS,
            "official_source_url": official_row["source_url"],
            "official_source_snapshot_sha256": official_row["source_snapshot_sha256"],
            "official_identity_status": "exact_model_proven",
            "ocr_verdict": "HOLD",
            "visual_verdict": "HOLD",
            "disposition": disposition,
            "visual_verification_note": note,
        }
        ledger.append({key: str(value) for key, value in common.items()})
        reviewed.append(common)

    fields = list(ledger[0])
    with LEDGER.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(ledger)
    manifest = {
        "schema_version": 1,
        "locale": "ru-BY",
        "reviewed_images": reviewed,
        "promotion_candidates": [],
        "policy": "Official APC/Schneider pages prove product identity only; they do not grant image copying rights. Promotion requires exact visible MPN evidence.",
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    summary = {
        "wave": "wave232d", "manufacturer": "APC", "candidate_rows": 28,
        "official_exact_identity_proven": 28, "company_owned_media_hash_pinned": 28,
        "ocr_hold": 28, "visual_hold": 28, "pass": 0, "promotion_candidates": 0,
        "safety": {"database_operations": 0, "image_copying_from_official_sources": 0, "import_or_promotion_manifest_for_command": False, "apply_performed": False, "commit_or_push": False},
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    REPORT.write_text(
        "# Wave232-D — APC local-media visual review\n\n"
        "Scope: exactly 28 APC candidates from Wave232 OCR inputs 001 and 002. Every row has an exact APC/Schneider official product-page identity pin and a company-owned Bitrix original, but all 28 remain HOLD.\n\n"
        "## Result\n\n"
        "- Exact official APC/Schneider identity evidence: 28/28.\n"
        "- Company-owned media SHA and path pins: 28/28.\n"
        "- OCR exact-label PASS: 0/28.\n"
        "- Manual visual exact-label PASS: 0/28.\n"
        "- Promotion candidates: 0.\n\n"
        "The originals visibly show APC branding and plausible battery-pack/cartridge form factors, but not a legible exact MPN; generic form is not enough to identify closely related APC models. Official Schneider Electric pages are recorded only as identity evidence and never as authority to copy an image. The review manifest is an audit artifact, not an application import/promotion manifest, because its `promotion_candidates` scope is empty. No database, media, or external source was modified.\n",
        encoding="utf-8", newline="\n",
    )
    print(f"wrote APC review: {len(reviewed)} HOLD, 0 PASS")


if __name__ == "__main__":
    main()
