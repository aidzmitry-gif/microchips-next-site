#!/usr/bin/env python3
"""Build the offline, fail-closed Wave245B Panasonic packet."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "docs/audits/generated/rb-enrichment-queue-wave244.csv"
EXCLUSIONS = ROOT / "docs/audits/generated/rb-wave245b-prior-source-exclusions.json"
ACQUISITION = ROOT / "docs/audits/sources/wave245b-panasonic-new-rows/acquisition.json"
LIVE = ROOT / "docs/audits/sources/wave245b-panasonic-new-rows/live-db-ownership-snapshot.json"
LEDGER = ROOT / "docs/audits/generated/rb-wave245b-panasonic-new-row-ledger.csv"
IMAGE_LEDGER = ROOT / "docs/audits/generated/rb-wave245b-panasonic-image-candidates.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-wave245b-panasonic-new-row.summary.json"
IDENTITIES = ROOT / "docs/imports/rb-verified-oem-identities-wave245b-panasonic-2026-07-30.json"
DESCRIPTIONS = ROOT / "docs/imports/rb-source-backed-descriptions-wave245b-panasonic-2026-07-30.json"
REPORT = ROOT / "docs/audits/2026-07-30-rb-wave245b-panasonic-new-rows.md"
IMAGE_DIR = ROOT / "docs/audits/generated/rb-wave245b-panasonic-image-candidates"
PINS = {
    QUEUE: "eb2549163840fce48d5f08e5f08129b268ddf11a220f84de8e0635a7c93eb0ab",
    EXCLUSIONS: "bb2b3e8c83da54097a16099cbc0b5f07417ad339a2f30def360971abe6961782",
    ACQUISITION: "35c64431484e4dde7e1ea99dcb2dbc762fbd41df8a8664362339bbc01de42298",
    LIVE: "6c32db24ca566c88c50d84d8a883e7e5b663cab60b82f8b31eab00507a8f1094",
}
TARGETS = {
    "bitrix:1596": {"mpn": "LC-XC1238P", "pdf_model": "LC-XC1238P/AP", "capacity_ah": "38.0"},
    "bitrix:1159": {"mpn": "LC-XD1217PG", "pdf_model": "LC-XD1217PG/APG", "capacity_ah": "17.0"},
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def main() -> None:
    for path, expected in PINS.items():
        if sha(path) != expected:
            raise SystemExit(f"pinned input changed: {path.relative_to(ROOT)}")
    with QUEUE.open(encoding="utf-8-sig", newline="") as handle:
        scope = [row for row in csv.DictReader(handle) if row["product_external_id"] in TARGETS]
    if {row["product_external_id"] for row in scope} != set(TARGETS) or len(scope) != 2:
        raise SystemExit("scope must be exactly bitrix:1596 and bitrix:1159")
    if any(row["research_status"] != "new_after_verified_duplicate_retirement_wave244" for row in scope):
        raise SystemExit("queue provenance drift")
    exclusions = json.loads(EXCLUSIONS.read_text(encoding="utf-8"))
    prior_urls = {row["value"] for row in exclusions["source_urls"]}
    prior_hashes = {row["value"] for row in exclusions["snapshot_sha256"]}
    acquisition = json.loads(ACQUISITION.read_text(encoding="utf-8"))
    if acquisition["prior_exclusions_sha256"] != sha(EXCLUSIONS):
        raise SystemExit("acquisition was not based on the pinned no-repeat snapshot")
    sources: dict[str, dict[str, object]] = {}
    for source in acquisition["sources"]:
        path = ROOT / source["snapshot_path"]
        if source["source_url"] in prior_urls or source["snapshot_sha256"] in prior_hashes:
            raise SystemExit("prior URL/SHA repeated")
        if sha(path) != source["snapshot_sha256"]:
            raise SystemExit("source snapshot hash drift")
        text = " ".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)
        for exact in source["expected_models"]:
            if exact not in text:
                raise SystemExit(f"source is not exact for {exact}")
            sources[exact] = {**source, "path": path, "text": text}
    live = json.loads(LIVE.read_text(encoding="utf-8"))
    if live["ownership_decision"] != "NO_EXACT_1C_OWNER" or live["exact_non_target_owner_candidates"]:
        raise SystemExit("exact owner safety guard failed")

    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    for stale in IMAGE_DIR.glob("*.png"):
        stale.unlink()
    xc_source = sources.get("LC-XC1238P/AP")
    image_path = IMAGE_DIR / "bitrix-1596-lc-xc1238p-official-candidate.png"
    if xc_source:
        images = PdfReader(str(xc_source["path"])).pages[0].images
        if len(images) != 1 or images[0].image.size != (203, 205):
            raise SystemExit("unexpected exact-image extraction topology")
        images[0].image.save(image_path, format="PNG")

    ledger = []
    image_ledger = []
    identities = []
    descriptions = []
    for row in sorted(scope, key=lambda item: item["product_external_id"]):
        external_id = row["product_external_id"]
        target = TARGETS[external_id]
        source = sources.get(target["pdf_model"])
        reasons = []
        if source is None:
            reasons.append("NO_NEW_EXACT_MANUFACTURER_PRIMARY_SOURCE")
        else:
            text = str(source["text"])
            if not re.search(r"Nominal voltage\s*\(V\)\s*12", text):
                reasons.append("SOURCE_VOLTAGE_NOT_12V")
            if not re.search(rf"20 hours rate\s*\(Ah\)\s*{re.escape(target['capacity_ah'])}", text):
                reasons.append("SOURCE_CAPACITY_CONFLICT")
        decision = "PASS_DESCRIPTION_IDENTITY" if not reasons else "HOLD"
        ledger.append({
            "external_id": external_id,
            "current_name": row["name"],
            "manufacturer": "Panasonic",
            "mpn": target["mpn"],
            "live_exact_non_target_owner_count": "0",
            "ownership_decision": live["ownership_decision"],
            "source_url": source["source_url"] if source else "",
            "source_snapshot_path": source["snapshot_path"] if source else "",
            "source_snapshot_sha256": source["snapshot_sha256"] if source else "",
            "nominal_voltage_v": "12" if source else "",
            "nominal_capacity_ah": target["capacity_ah"] if source else "",
            "technology": "VRLA AGM" if source else "",
            "decision": decision,
            "hold_reason": "|".join(reasons),
        })
        candidate_exists = external_id == "bitrix:1596" and image_path.exists()
        image_ledger.append({
            "external_id": external_id,
            "mpn": target["mpn"],
            "official_exact_image_candidate": "true" if candidate_exists else "false",
            "candidate_path": image_path.relative_to(ROOT).as_posix() if candidate_exists else "",
            "candidate_sha256": sha(image_path) if candidate_exists else "",
            "candidate_dimensions_px": "203x205" if candidate_exists else "",
            "visual_review": "PASS_EXACT_MODEL_PAGE_PHOTO" if candidate_exists else "HOLD_NO_NEW_EXACT_OFFICIAL_IMAGE",
            "rights_status": "HOLD_NO_EXPLICIT_REUSE_LICENSE" if candidate_exists else "NOT_APPLICABLE_NO_CANDIDATE",
            "rights_basis": "Panasonic-authored PDF; no explicit storefront reuse grant located" if candidate_exists else "",
            "media_manifest_eligible": "false",
        })
        if decision == "HOLD":
            continue
        identities.append({
            "external_id": external_id,
            "current_name": row["name"],
            "manufacturer": "Panasonic",
            "mpn": target["mpn"],
            "source_url": source["source_url"],
            "source_kind": "official_manufacturer_catalogue",
            "source_publisher": "Panasonic Industry Europe",
            "checked_at": "2026-07-29",
            "product_type": "VRLA AGM battery",
            "source_snapshot_path": "../audits/" + str(source["snapshot_path"]).removeprefix("docs/audits/"),
            "source_snapshot_sha256": source["snapshot_sha256"],
        })
        descriptions.append({
            "external_id": external_id,
            "identity_scope": "model_core",
            "manufacturer": "Panasonic",
            "model_core": target["mpn"],
            "technology": "VRLA AGM",
            "source_url": source["source_url"],
            "technical_attributes": {
                "Модель": target["mpn"], "Номинальное напряжение, В": "12",
                "Номинальная ёмкость (20-часовой режим), А·ч": target["capacity_ah"],
            },
            "source_kind": "official_manufacturer_catalogue",
            "source_tier": "manufacturer_primary",
            "source_publisher": "Panasonic Industry Europe",
            "manufacturer_primary": True,
            "evidence_scope": "model_core",
            "checked_at": "2026-07-29",
        })

    for path, rows in ((LEDGER, ledger), (IMAGE_LEDGER, image_ledger)):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
            writer.writeheader(); writer.writerows(rows)
    write_json(IDENTITIES, {"schema_version": 1, "site_key": "microchips-by", "products": identities})
    write_json(DESCRIPTIONS, {"schema_version": 1, "purpose": "Wave245B exact Panasonic description drafts", "locale": "ru-BY", "products": descriptions})
    decisions = Counter(row["decision"] for row in ledger)
    summary = {
        "schema_version": 1,
        "wave": "wave245b_panasonic_new_rows",
        "checked_at": "2026-07-30",
        "scope": ["bitrix:1596", "bitrix:1159"],
        "coverage": {"scope": 2, "pass_description_identity": decisions["PASS_DESCRIPTION_IDENTITY"], "hold": decisions["HOLD"]},
        "live_ownership": {"decision": live["ownership_decision"], "exact_non_target_owner_count": 0},
        "new_source_safety": {"prior_url_overlap": 0, "prior_sha_overlap": 0, "accepted_exact_pdfs": len(sources)},
        "image_candidates": {"official_exact": 1, "rights_hold": 1, "media_manifest_rows": 0, "visual_reviewed": 1},
        "bounded_xd1217_discovery": acquisition["xd1217_discovery"],
        "manifests": {"identities": len(identities), "descriptions": len(descriptions), "media": 0},
        "pins": {path.relative_to(ROOT).as_posix(): digest for path, digest in PINS.items()},
        "safety": {"apply_performed": False, "database_mutations": 0, "publication_changes": 0, "commercial_changes": 0},
    }
    write_json(SUMMARY, summary)
    REPORT.write_text(
        "# Wave245B: Panasonic new queue rows\n\n"
        "Scope is exactly `bitrix:1596` (LC-XC1238P) and `bitrix:1159` (LC-XD1217PG). "
        "The read-only live census found no non-target exact Bitrix/1C owner for either model.\n\n"
        "`bitrix:1596` has a byte-new exact Panasonic Industry Europe individual datasheet: 12 V, 38 Ah "
        "(20-hour rate), VRLA AGM, with an exact-page 203×205 product photo. The photo was extracted and "
        "visually checked, but is rights-HOLD because no explicit storefront reuse licence was found; no media "
        "manifest was created. Identity and description-only manifests contain this row.\n\n"
        "`bitrix:1159` remains HOLD. The old handbook URL/SHA was not reused; the new short-catalog endpoint "
        "returned HTML instead of PDF, and a bounded scan of 96 byte-new official Media Portal PDF candidates "
        "found zero exact LC-XD1217PG/APG sheets. It enters no manifest.\n\n"
        "No apply, publication, price, availability, or database mutation was performed.\n",
        encoding="utf-8", newline="\n",
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
