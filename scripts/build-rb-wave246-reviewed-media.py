#!/usr/bin/env python3
"""Pin Wave246 machine-vision decisions and emit only exact visible-MPN media."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "docs/audits/generated/rb-wave246-new-media-review.csv"
LEDGER = ROOT / "docs/audits/generated/rb-reviewed-legacy-preview-media-wave246.csv"
MANIFEST = ROOT / "docs/imports/rb-reviewed-legacy-preview-media-wave246-2026-07-30.json"
SUMMARY = ROOT / "docs/audits/generated/rb-wave246-reviewed-media.summary.json"

PASS_NOTES = {
    "bitrix:1147": "Visible battery label reads Panasonic LC-P0612P.",
    "bitrix:1149": "Visible battery label reads Panasonic LC-R0612P.",
    "bitrix:1150": "Visible battery label reads Panasonic LC-R0612P1.",
    "bitrix:1585": "Visible battery label reads Panasonic LC-R063R4P.",
    "bitrix:3189": "Visible battery label reads Panasonic LC-R067R2P.",
    "bitrix:1161": "Visible battery label reads Panasonic LC-R122R2PG.",
    "bitrix:1586": "Visible battery label reads Panasonic LC-R123R4PG.",
    "bitrix:3191": "Visible battery label reads Panasonic LC-R127R2PG.",
    "bitrix:1151": "Visible battery label reads Panasonic LC-RA1212PG.",
    "bitrix:1569": "Visible battery label reads Panasonic LC-XC1222P.",
    "bitrix:3232": "Visible battery label reads Panasonic UP-VW0645P1.",
}
HOLD_NOTES = {
    "bitrix:3190": "Asset is blank white and contains no visible product identity.",
    "bitrix:1138": "Visible label reads LC-RA1212PG, not expected LC-RA1212PG1.",
    "bitrix:1580": "Expected LC-XC1228P is not fully legible at original resolution.",
    "bitrix:1596": "Expected LC-XC1238P is not fully legible at original resolution.",
    "bitrix:23844": "Visible APC label says generic RBC and does not show expected RBC109.",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    with INPUT.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    decisions = set(PASS_NOTES) | set(HOLD_NOTES)
    if len(rows) != 16 or {row["external_id"] for row in rows} != decisions:
        raise RuntimeError("Wave246 visual-decision coverage drift")
    ledger_rows = []
    images = []
    for row in rows:
        external_id = row["external_id"]
        expected = row["mpn"] or row["model_core"]
        passed = external_id in PASS_NOTES
        note = PASS_NOTES.get(external_id) or HOLD_NOTES[external_id]
        asset = Path(row["asset_path"])
        if not asset.is_file() or sha256(asset) != row["content_sha256"].lower():
            raise RuntimeError(f"Asset hash drift for {external_id}")
        ledger_rows.append({
            "external_id": external_id,
            "media_id": row["media_id"],
            "expected_mpn": expected,
            "content_sha256": row["content_sha256"].lower(),
            "storage_path": row["storage_path"],
            "rights_basis": row["rights_basis"],
            "visual_decision": "PASS_VISIBLE_EXACT_MPN" if passed else "HOLD",
            "reason": note,
        })
        if not passed:
            continue
        images.append({
            "external_id": external_id,
            "media_id": int(row["media_id"]),
            "content_sha256": row["content_sha256"].lower(),
            "storage_path": row["storage_path"],
            "rights_basis": row["rights_basis"],
            "identity_scope": "exact",
            "mpn": expected,
            "identity_evidence_level": "visible_exact_mpn",
            "visual_verification_note": f"Original-resolution machine-vision review: {note}",
            "reviewed_at": "2026-07-29",
        })
    with LEDGER.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(ledger_rows[0]))
        writer.writeheader()
        writer.writerows(ledger_rows)
    MANIFEST.write_text(json.dumps({
        "schema_version": 1,
        "purpose": "Promote only company-owned legacy assets with complete exact MPN visible at original resolution.",
        "locale": "ru-BY",
        "images": images,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    counts = Counter(row["visual_decision"] for row in ledger_rows)
    summary = {
        "schema_version": 1,
        "reviewed_rows": len(ledger_rows),
        "visual_pass": counts["PASS_VISIBLE_EXACT_MPN"],
        "visual_hold": counts["HOLD"],
        "manifest_rows": len(images),
        "ledger_sha256": sha256(LEDGER),
        "manifest_sha256": sha256(MANIFEST),
        "database_apply": False,
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
