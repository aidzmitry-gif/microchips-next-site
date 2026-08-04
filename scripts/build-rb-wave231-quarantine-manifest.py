#!/usr/bin/env python3
"""Build the exact-contract Wave231 media identity-mismatch quarantine manifest."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "docs/audits/generated"
AUDIT_A = GEN / "rb-wave231a-media-mpn-audit.csv"
AUDIT_B = GEN / "rb-wave231b-mnb-visible-media-mismatch-ledger.csv"
MEDIA_EXPORT = GEN / "rb-wave227-legacy-preview-candidates.csv"
CURRENT_DB = GEN / "rb-wave231-quarantine-current-db-readonly.json"
MANIFEST = ROOT / "docs/imports/rb-media-identity-mismatch-quarantine-wave231-2026-07-29.json"
SUMMARY = GEN / "rb-wave231-quarantine-manifest.summary.json"
REPORT = ROOT / "docs/audits/2026-07-29-rb-wave231-media-quarantine-manifest.md"

PINS = {
    AUDIT_A: "136716749a546c5eb04403c3b14ee11488b63eb308837d2a4556603d925678bb",
    AUDIT_B: "7c1df1857c9d889111e841f5896a2a1e4e9d29047101ea44416190c7102ed908",
    MEDIA_EXPORT: "34aa3a8d0743702a55e4a635d0b5d768f64b54874cfc42d6f7a7569a68600384",
    CURRENT_DB: "a46cf7cb819f6c05307ad0e53f9ff3c3ab07f0ff0de10cc6a84b4450fe1bbe9e",
}

WRONG = {
    "bitrix:2808": "A706/105", "bitrix:2909": "MM 250-12", "bitrix:3056": "MM 55-12",
    "bitrix:3099": "MR 80-12FT", "bitrix:3219": "MM 55-12",
}
TRUNCATED = {"bitrix:2831": "S 12/17 G5", "bitrix:3117": "S 12/6.6 S"}
EXPECTED_IDS = set(WRONG) | set(TRUNCATED)
ALLOWED_FIELDS = {"external_id", "media_id", "content_sha256", "storage_path", "rights_basis", "current_verification_status", "expected_catalogue_mpn", "observed_visible_mpn", "disposition", "reason", "reviewed_at", "reviewer", "review_evidence_path", "review_evidence_sha256"}
REVIEWER = "Codex Wave231 visual-review audit"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def normalized(value: str) -> str:
    return "".join(character for character in value.casefold() if character.isalnum())


def name_contains_model_core(name: str, model_core: str) -> bool:
    expected = normalized(model_core)
    tokens = [normalized(token) for token in re.findall(r"[^\W_]+", name, flags=re.UNICODE)]
    for start in range(len(tokens)):
        candidate = ""
        for token in tokens[start:]:
            candidate += token
            if candidate == expected:
                return True
            if len(candidate) >= len(expected):
                break
    return False


def audit_rows() -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for row in read_csv(AUDIT_A):
        result[row["product_external_id"]] = {"mpn": row["current_mpn"], "media_id": row["media_id"], "storage_path": row["media_storage_key"], "sha": row["media_sha256"], "visible": row["visible_label"], "classification": row["audit_classification"]}
    for row in read_csv(AUDIT_B):
        result[row["external_id"]] = {"mpn": row["expected_mpn"], "media_id": row["media_id"], "storage_path": row["media_storage_path"], "sha": row["media_sha256"], "visible": row["visible_mpn"], "classification": row["classification"]}
    require(set(result) >= EXPECTED_IDS, "Wave231 audit ledgers lack a reviewed mismatch")
    return result


def build() -> dict[str, object]:
    for path, expected in PINS.items():
        require(digest(path) == expected, f"pinned input drift: {path.relative_to(ROOT)}")
    audits = audit_rows()
    exports = {row["external_id"]: row for row in read_csv(MEDIA_EXPORT)}
    db = json.loads(CURRENT_DB.read_text(encoding="utf-8"))
    require(db["mode"] == "read_only" and db["database_mutations"] == 0, "current DB evidence is not read-only")
    current = {row["external_id"]: row for row in db["records"]}
    require(set(current) == EXPECTED_IDS and len(current) == 7, "current DB pin does not cover exactly seven rows")

    images = []
    for external_id in sorted(EXPECTED_IDS):
        audit, export, live = audits[external_id], exports.get(external_id), current[external_id]
        require(export is not None, f"missing generated media export: {external_id}")
        require(audit["mpn"] == live["mpn"] == export["mpn"], f"current MPN/media-export drift: {external_id}")
        require(int(audit["media_id"]) == live["media_id"] == int(export["media_id"]), f"media ID drift: {external_id}")
        require(audit["storage_path"] == live["storage_path"] == export["storage_path"], f"storage path drift: {external_id}")
        require(audit["sha"] == live["content_sha256"] == export["content_sha256"], f"content hash drift: {external_id}")
        require(live["kind"] == "image" and live["media_is_published"] is True and live["site_product_is_published"] is True, f"published image/current site-product drift: {external_id}")
        require(live["verification_status"] == "legacy_exact_preview" and live["rights_basis"].startswith("Company-owned Microchips"), f"current verification/rights drift: {external_id}")
        observed = WRONG.get(external_id) or TRUNCATED.get(external_id)
        require(normalized(observed) != normalized(live["mpn"]), f"visible label does not differ: {external_id}")
        if external_id in WRONG:
            disposition, reason = "quarantine_wrong_product_media", "Visible image MPN identifies a different product model; preserve the current catalogue MPN."
            review_path, review_sha = AUDIT_B.name if external_id != "bitrix:2808" else AUDIT_A.name, digest(AUDIT_B if external_id != "bitrix:2808" else AUDIT_A)
        else:
            disposition, reason = "hold_truncated_identity_preview", "Visible image MPN includes a suffix/detail omitted by the current catalogue MPN; retain as preview-only pending a separate identity correction."
            review_path, review_sha = AUDIT_A.name, digest(AUDIT_A)
            require(normalized(observed).startswith(normalized(live["mpn"])) and len(normalized(observed)) > len(normalized(live["mpn"])) and name_contains_model_core(live["name"], observed), f"strict truncated identity contract drift: {external_id}")
        images.append({"external_id": external_id, "media_id": live["media_id"], "content_sha256": live["content_sha256"], "storage_path": live["storage_path"], "rights_basis": live["rights_basis"], "current_verification_status": live["verification_status"], "expected_catalogue_mpn": live["mpn"], "observed_visible_mpn": observed, "disposition": disposition, "reason": reason, "reviewed_at": "2026-07-29", "reviewer": REVIEWER, "review_evidence_path": review_path, "review_evidence_sha256": review_sha})

    require(len(images) == 7 and {row["external_id"] for row in images} == EXPECTED_IDS, "manifest target set drift")
    require(all(set(row) == ALLOWED_FIELDS for row in images), "QuarantineIdentityMismatchMedia field contract drift")
    require(Counter(row["disposition"] for row in images) == Counter({"quarantine_wrong_product_media": 5, "hold_truncated_identity_preview": 2}), "disposition count drift")
    manifest = {"schema_version": 1, "locale": "ru-BY", "images": images}
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = {"schema_version": 1, "wave": "wave231_media_identity_mismatch_quarantine", "inputs": {path.relative_to(ROOT).as_posix(): digest(path) for path in PINS}, "coverage": {"reviewed_mismatches": 7, "quarantine_wrong_product_media": 5, "hold_truncated_identity_preview": 2, "published_legacy_preview_pins": 7}, "manifest": {"path": MANIFEST.relative_to(ROOT).as_posix(), "sha256": digest(MANIFEST), "rows": 7}, "command_contract": {"command": "media:quarantine-identity-mismatches microchips-by <manifest>", "dry_run_only": True, "apply_performed": False, "database_operations": 0}}
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REPORT.write_text("# Wave231: media identity-mismatch quarantine manifest\n\nThis deterministic manifest combines the two Wave231 audit ledgers, the frozen Wave227 media export, and a read-only current DB product/site-product/media snapshot. It pins exactly seven currently published `legacy_exact_preview` assets with company-owned rights.\n\nFive entries have visible labels for a different product and use `quarantine_wrong_product_media`: `bitrix:2808`, `bitrix:2909`, `bitrix:3056`, `bitrix:3099`, and `bitrix:3219`. Two entries have a visibly more specific identity than the current, truncated MPN and use `hold_truncated_identity_preview`: `bitrix:2831` and `bitrix:3117`. The builder proves for both holds that the normalized observed MPN strictly extends the current MPN and that it is present in the current product name.\n\nEvery row now carries the reviewer and a SHA-256-pinned audit-ledger basename. `QuarantineIdentityMismatchMedia` resolves review evidence beside the manifest at runtime. Therefore a Docker dry-run must copy the JSON manifest and the two source ledgers `rb-wave231a-media-mpn-audit.csv` and `rb-wave231b-mnb-visible-media-mismatch-ledger.csv` into the same container directory, retaining their exact basenames and bytes. This builder did not invoke the command, create an import run, apply any DB/media state, or publish changes.\n", encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False))
