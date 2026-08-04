#!/usr/bin/env python3
"""Audit existing backup candidates for two quarantined MNB product images."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "docs/audits/generated"
SOURCES = ROOT / "docs/audits/sources/wave206-panasonic-ventura-mnb"
W231 = GEN / "rb-wave231b-mnb-visible-media-mismatch-ledger.csv"
MEDIA_INDEX = GEN / "bitrix-full-catalog-media-index.csv"
MATERIALIZED = GEN / "rb-bitrix-staging-media-wave141.csv"
CURRENT_DB = GEN / "rb-wave232b-mnb-media-current-db-readonly.json"
SOURCE_INDEX = SOURCES / "snapshot-index.json"
SOURCE_PDF = SOURCES / "mnb-official-catalogue.pdf"
SOURCE_TEXT = SOURCES / "mnb-official-catalogue.txt"
HOLDS = GEN / "rb-wave232b-mnb-media-replacement-holds.csv"
SUMMARY = GEN / "rb-wave232b-mnb-media-replacement-holds.summary.json"
REPORT = ROOT / "docs/audits/2026-07-29-rb-wave232b-mnb-media-replacement-holds.md"

PINS = {W231: "7c1df1857c9d889111e841f5896a2a1e4e9d29047101ea44416190c7102ed908", MEDIA_INDEX: "38f6431460f3f82661a17a0ef722d4c2f4f94b1c83662a23ce1af43f8537bac3", MATERIALIZED: "b594d2d73e181300260f16b8a23c29ca86afd37b47b3184255807b36462cef64", CURRENT_DB: "d40dceadba19c931e545f42599234a0ac3856b894b8988b4113277d17a9cadd0", SOURCE_INDEX: "705579d386df38e100fc430a52c1f834aece98742444e1ea4786205eff00828f", SOURCE_PDF: "85dac18f2953eeb29e306434b0af658a49f96afcc04d182ea2a2b8ef7b207859", SOURCE_TEXT: "c98577d15147e74b03ab645f1a926784d2dee2570e223a8a6c532b55b9e76372"}
TARGETS = {"bitrix:2909": {"mpn": "MNG 250-12", "wrong": "MM 250-12", "duplicate_id": "28752", "duplicate_file": "96694"}, "bitrix:3056": {"mpn": "MM 45-12", "wrong": "MM 55-12", "duplicate_id": "29629", "duplicate_file": "98450"}}
FIELDS = ("external_id", "expected_mpn", "visible_wrong_mpn", "current_media_id", "current_media_status", "current_media_published", "duplicate_bitrix_element_id", "duplicate_detail_file_id", "duplicate_backup_file_materialized", "exact_company_owned_candidate_found", "official_catalogue_url", "official_catalogue_sha256", "official_model_confirmed", "official_image_candidate_url", "official_image_rights_status", "hold_reason", "proposed_action")


def digest(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()
def require(value: bool, message: str) -> None:
    if not value: raise SystemExit(message)
def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle: return list(csv.DictReader(handle))
def write_csv(rows: list[dict[str, str]]) -> None:
    with HOLDS.open("w", encoding="utf-8-sig", newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=FIELDS,lineterminator="\n"); writer.writeheader(); writer.writerows(rows)


def build() -> dict[str, object]:
    for path, expected in PINS.items(): require(digest(path) == expected, f"pinned input drift: {path.relative_to(ROOT)}")
    review = {row["external_id"]: row for row in read_csv(W231)}
    media_index = {row["legacy_element_id"]: row for row in read_csv(MEDIA_INDEX)}
    materialized = {row["legacy_element_id"]: row for row in read_csv(MATERIALIZED)}
    live = {row["external_id"]: row for row in json.loads(CURRENT_DB.read_text(encoding="utf-8"))["records"]}
    index = json.loads(SOURCE_INDEX.read_text(encoding="utf-8")); source = next(row for row in index["sources"] if row["source_id"] == "mnb_official_catalogue")
    require(source["snapshot_sha256"] == digest(SOURCE_PDF) and source["extracted_text_sha256"] == digest(SOURCE_TEXT), "MNB official source drift")
    source_text = SOURCE_TEXT.read_text(encoding="utf-8")
    rows=[]
    for external_id, target in TARGETS.items():
        evidence, current = review[external_id], live[external_id]
        duplicate = media_index[target["duplicate_id"]]
        require(evidence["expected_mpn"] == current["mpn"] == target["mpn"] and evidence["visible_mpn"].replace(" ", "") == target["wrong"].replace(" ", ""), f"review/current identity drift: {external_id}")
        require(current["verification_status"] == "needs_review" and current["media_is_published"] is False, f"current quarantine drift: {external_id}")
        require(duplicate["detail_picture_file_id"] == target["duplicate_file"] and duplicate["has_media_reference"] == "true", f"duplicate Bitrix reference drift: {external_id}")
        require(target["mpn"] in source_text, f"MNB official catalogue lacks expected model: {external_id}")
        local_candidates=[]
        for directory in (ROOT / ".tmp/rb-bitrix-staging-media-wave141", ROOT / ".tmp/wave227-assets/legacy-staging/rb"):
            local_candidates.extend(directory.glob(f"bitrix-{target['duplicate_id']}-*"))
        require(not local_candidates, f"unreviewed duplicate backup asset became available: {external_id}")
        rows.append({"external_id": external_id, "expected_mpn": target["mpn"], "visible_wrong_mpn": target["wrong"], "current_media_id": str(current["media_id"]), "current_media_status": current["verification_status"], "current_media_published": str(current["media_is_published"]).lower(), "duplicate_bitrix_element_id": target["duplicate_id"], "duplicate_detail_file_id": target["duplicate_file"], "duplicate_backup_file_materialized": "false", "exact_company_owned_candidate_found": "false", "official_catalogue_url": source["source_url"], "official_catalogue_sha256": source["snapshot_sha256"], "official_model_confirmed": "true", "official_image_candidate_url": "", "official_image_rights_status": "no_standalone_official_image_or_reuse_rights_in_pinned_catalogue", "hold_reason": "no_locally_materialized_company_owned_duplicate_asset_for_visual_exact_mpn_review", "proposed_action": "HOLD: recover the referenced Bitrix backup file, then hash and visually verify its complete MPN before building an exact-media manifest."})
    require(len(rows)==2 and all(row["exact_company_owned_candidate_found"]=="false" for row in rows), "Wave232-B safe candidate scope drift")
    write_csv(rows)
    summary={"schema_version":1,"wave":"wave232b_mnb_exact_media_replacement_search","inputs":{path.relative_to(ROOT).as_posix():digest(path) for path in PINS},"coverage":{"targets":2,"exact_company_owned_candidates":0,"holds":2,"exact_media_manifest_emitted":False},"holds":{"path":HOLDS.relative_to(ROOT).as_posix(),"sha256":digest(HOLDS),"rows":2},"safety":{"database_operations":0,"apply_performed":False,"media_changes":0,"publication_changes":0}}
    SUMMARY.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    REPORT.write_text("# Wave232-B: MNB exact replacement-media search\n\nThe existing company-owned assets for `bitrix:2909` and `bitrix:3056` were already visually rejected and are now quarantined (`needs_review`, unpublished). Current DB product_media has no separate exact candidate. The Bitrix media index does contain same-name duplicate-element references: element `28752` / file `96694` for MNG 250-12 and element `29629` / file `98450` for MM 45-12. Neither referenced file is materialized in either available company-owned backup asset directory, so no image can be visually verified or safely promoted.\n\nThe pinned MNB official catalogue confirms both expected models, but exposes only a catalogue PDF and no standalone product-image URL or image reuse licence. It therefore supplies identity evidence, not media rights. Wave232-B emits HOLD evidence rather than an exact-media manifest. Recovering either original Bitrix file is the next step; it must be hash-pinned and visually checked for the full expected MPN before any new manifest. No DB, media, publication, or identity change was made.\n",encoding="utf-8")
    return summary


if __name__ == "__main__": print(json.dumps(build(),ensure_ascii=False))
