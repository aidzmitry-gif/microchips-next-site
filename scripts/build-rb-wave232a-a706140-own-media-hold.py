"""Record the fail-closed local own-media search for Sonnenschein A706/140."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "docs/audits/generated/rb-wave231a-media-mpn-audit.csv"
VISUAL = ROOT / "docs/audits/generated/rb-wave229b-hold-002-visual-review.csv"
STAGING = ROOT / "docs/audits/generated/rb-bitrix-staging-media-wave141.csv"
FULL_INDEX = ROOT / "docs/audits/generated/bitrix-full-catalog-media-index.csv"
OFFICIAL = ROOT / "docs/audits/generated/rb-wave209a-official-evidence.csv"
REGISTRY = ROOT / "docs/audits/sources/wave211c-stationary/source-registry.json"
ASSET_ROOTS = [ROOT / ".tmp/wave227-assets", ROOT / ".tmp/rb-bitrix-staging-media-wave141"]
LEDGER = ROOT / "docs/audits/generated/rb-wave232a-a706140-own-media-search.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-wave232a-a706140-own-media-search.summary.json"
REPORT = ROOT / "docs/audits/2026-07-29-rb-wave232a-a706140-own-media-hold.md"


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalized(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def main() -> None:
    audit = {row["product_external_id"]: row for row in rows(AUDIT)}["bitrix:2808"]
    visual = {row["external_id"]: row for row in rows(VISUAL)}["bitrix:2808"]
    staging = {row["legacy_element_id"]: row for row in rows(STAGING)}["2808"]
    duplicate = next(row for row in rows(FULL_INDEX) if row["legacy_element_id"] == "28844")
    official = {row["product_external_id"]: row for row in rows(OFFICIAL)}["bitrix:2808"]
    registry = {row["source_id"]: row for row in json.loads(REGISTRY.read_text(encoding="utf-8"))["sources"]}
    source = registry["exide-sonnenschein-a700.pdf"]
    source_path = ROOT / source["snapshot_path"]

    if (
        audit["audit_classification"] != "wrong_image_keep_mpn"
        or audit["current_mpn"] != "A706/140"
        or audit["visible_label"] != "A706/105"
        or visual["verdict"] != "HOLD"
        or visual["reason"] != "visible_mpn_mismatch"
        or visual["expected_mpn"] != "A706/140"
        or visual["visible_mpn"] != "A706/105"
        or visual["promotion_eligible"] != "false"
        or staging["file_id"] != "80388"
        or staging["sha256"] != audit["media_sha256"]
        or duplicate["preview_picture_file_id"] != "96877"
        or duplicate["detail_picture_file_id"] != "96878"
        or official["model_token"] != "A706/140"
        or official["source_url"] != source["source_url"]
        or digest(source_path) != source["snapshot_sha256"]
    ):
        raise SystemExit("Wave232-A input pin drift")
    official_text = "\n".join(page.extract_text() or "" for page in PdfReader(source_path).pages)
    if normalized("A706/140") not in normalized(official_text):
        raise SystemExit("Pinned official A700 catalogue no longer proves A706/140")

    wrong_assets = [
        ASSET_ROOTS[0] / "legacy-staging/rb/bitrix-2808-80388.jpg",
        ASSET_ROOTS[1] / "bitrix-2808-80388.jpg",
    ]
    if any(not path.is_file() or digest(path) != audit["media_sha256"] for path in wrong_assets):
        raise SystemExit("Existing own-media copies do not match the quarantined pin")
    duplicate_assets = [path for root in ASSET_ROOTS for path in root.glob("**/*28844*")]
    if duplicate_assets:
        raise SystemExit("Unexpected extracted duplicate 28844 asset: manual visual review required")

    fieldnames = [
        "product_external_id", "expected_mpn", "own_media_search_result", "quarantined_media_id",
        "quarantined_asset_sha256", "visible_label", "staging_file_id", "duplicate_bitrix_element_id",
        "duplicate_preview_file_id", "duplicate_detail_file_id", "duplicate_asset_available",
        "official_candidate_source_url", "official_source_sha256", "official_model_proven", "rights_status", "next_action",
    ]
    ledger = [{
        "product_external_id": "bitrix:2808", "expected_mpn": "A706/140",
        "own_media_search_result": "HOLD_no_exact_company_owned_asset_found",
        "quarantined_media_id": audit["media_id"], "quarantined_asset_sha256": audit["media_sha256"],
        "visible_label": "A706/105", "staging_file_id": "80388", "duplicate_bitrix_element_id": "28844",
        "duplicate_preview_file_id": "96877", "duplicate_detail_file_id": "96878", "duplicate_asset_available": "false",
        "official_candidate_source_url": source["source_url"], "official_source_sha256": source["snapshot_sha256"],
        "official_model_proven": "true",
        "rights_status": "official manufacturer catalogue proves identity only; no image reuse licence or company-owned asset evidence established",
        "next_action": "HOLD: obtain a rights-cleared exact A706/140 image before any media import or promotion",
    }]
    with LEDGER.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(ledger)
    summary = {
        "wave": "wave232a", "product_external_id": "bitrix:2808", "result": "HOLD_no_exact_company_owned_asset_found",
        "local_search": {"current_db_a706140_products": 1, "current_db_media_rows": 1, "extracted_own_asset_copies": 2, "exact_matches": 0, "duplicate_bitrix_element": "28844", "duplicate_assets_available": 0},
        "official_candidate": {"url": source["source_url"], "snapshot_sha256": source["snapshot_sha256"], "model_token": "A706/140", "rights_status": ledger[0]["rights_status"]},
        "safety": {"media_import_manifest_created": False, "media_promotion_manifest_created": False, "database_operations": 0, "apply_performed": False, "commit_or_push": False},
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    REPORT.write_text(
        "# Wave232-A — A706/140 company-owned media search HOLD\n\n"
        "`bitrix:2808` remains HOLD. No deterministic legacy-image import or promotion manifest was created because no exact company-owned A706/140 image is available in the searched current DB/media rows or extracted Bitrix assets.\n\n"
        "## Local evidence\n\n"
        "- Live read-only DB search found one A706/140 product, `bitrix:2808`, with only media `586`; it is quarantined (`needs_review`, unpublished).\n"
        "- Both available company-owned extracted copies are file `80388`, SHA-256 `8a75d89f30e20d276b08d951318d6dec9d2791a1f923ff47202f93caffbb59fc`. Visual review and Wave231-A show label `A706/105`, not `A706/140`.\n"
        "- A full-catalog duplicate reference exists for Bitrix element `28844` (preview `96877`, detail `96878`), but it has no current Product/media row and no extracted own-media asset in the available Bitrix extraction roots. It cannot be promoted or imported.\n\n"
        "## Official candidate and rights\n\n"
        f"The pinned Exide Technologies A700 catalogue proves model `A706/140`: {source['source_url']} (SHA-256 `{source['snapshot_sha256']}`). It is an official identity source, not an established image-reuse licence. No official or third-party image may be acquired, copied, imported, or promoted without separate rights clearance.\n\n"
        "Next action: obtain a rights-cleared exact A706/140 image, then perform a new visual review and build a fresh import manifest.\n",
        encoding="utf-8", newline="\n",
    )
    print(f"wrote HOLD evidence: {LEDGER.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
