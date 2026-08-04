from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/build-rb-wave231-quarantine-manifest.py"
MANIFEST = ROOT / "docs/imports/rb-media-identity-mismatch-quarantine-wave231-2026-07-29.json"
SUMMARY = ROOT / "docs/audits/generated/rb-wave231-quarantine-manifest.summary.json"
REPORT = ROOT / "docs/audits/2026-07-29-rb-wave231-media-quarantine-manifest.md"
CURRENT_DB = ROOT / "docs/audits/generated/rb-wave231-quarantine-current-db-readonly.json"
ALLOWED = {"external_id", "media_id", "content_sha256", "storage_path", "rights_basis", "current_verification_status", "expected_catalogue_mpn", "observed_visible_mpn", "disposition", "reason", "reviewed_at", "reviewer", "review_evidence_path", "review_evidence_sha256"}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_wave231_manifest_is_deterministic_and_command_contract_shaped() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True)
    first = (digest(MANIFEST), digest(SUMMARY), digest(REPORT))
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True)
    assert first == (digest(MANIFEST), digest(SUMMARY), digest(REPORT))
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert payload["locale"] == "ru-BY" and len(payload["images"]) == 7
    assert all(set(row) == ALLOWED for row in payload["images"])
    assert Counter(row["disposition"] for row in payload["images"]) == Counter({"quarantine_wrong_product_media": 5, "hold_truncated_identity_preview": 2})
    assert all(row["current_verification_status"] == "legacy_exact_preview" and len(row["content_sha256"]) == 64 for row in payload["images"])
    assert all(Path(row["review_evidence_path"]).name == row["review_evidence_path"] and len(row["review_evidence_sha256"]) == 64 and row["reviewer"] for row in payload["images"])
    assert all(digest(ROOT / "docs/audits/generated" / row["review_evidence_path"]) == row["review_evidence_sha256"] for row in payload["images"])
    holds = [row for row in payload["images"] if row["disposition"] == "hold_truncated_identity_preview"]
    assert {row["external_id"] for row in holds} == {"bitrix:2831", "bitrix:3117"}
    assert all("rb-wave231a-media-mpn-audit.csv" == row["review_evidence_path"] for row in holds)
    names = {row["external_id"]: row.get("name", "") for row in json.loads(CURRENT_DB.read_text(encoding="utf-8"))["records"]}
    normalize = lambda value: "".join(character for character in value.casefold() if character.isalnum())
    assert all(normalize(row["observed_visible_mpn"]).startswith(normalize(row["expected_catalogue_mpn"])) and len(normalize(row["observed_visible_mpn"])) > len(normalize(row["expected_catalogue_mpn"])) and normalize(row["observed_visible_mpn"]) in normalize(names[row["external_id"]]) for row in holds)
    assert summary["command_contract"] == {"command": "media:quarantine-identity-mismatches microchips-by <manifest>", "dry_run_only": True, "apply_performed": False, "database_operations": 0}
