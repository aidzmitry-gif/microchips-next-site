from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/build-rb-wave228c-bb-casil-cyclon-description-stage.py"
MANIFEST = ROOT / "docs/imports/rb-source-backed-description-stageable-wave228c-2026-07-29.json"
LEDGER = ROOT / "docs/audits/generated/rb-wave228c-bb-casil-cyclon-description-ledger.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-wave228c-bb-casil-cyclon-description.summary.json"
REPORT = ROOT / "docs/audits/2026-07-29-rb-wave228c-bb-casil-cyclon-description-stage.md"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_wave228c_manifest_is_deterministic_and_strictly_stageable() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True)
    first = {path: digest(path) for path in (MANIFEST, LEDGER, SUMMARY, REPORT)}
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True)
    assert first == {path: digest(path) for path in first}

    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    rows = payload["products"]
    assert payload["locale"] == "ru-BY"
    assert len(rows) == len({row["external_id"] for row in rows}) == 11
    assert len({row["model_core"].casefold() for row in rows}) == 11
    assert {row["manufacturer"] for row in rows} == {"B.B. Battery", "Casil", "EnerSys"}
    assert all(row["identity_scope"] == row["evidence_scope"] == "model_core" for row in rows)
    assert all(row["source_tier"] == "manufacturer_primary" and row["manufacturer_primary"] is True for row in rows)
    assert all(row["technical_attributes"] == {"Технология": row["technology"]} for row in rows)
    policy_fields = {"external_id", "identity_scope", "manufacturer", "model_core", "technology", "source_url", "technical_attributes", "source_kind", "source_tier", "source_publisher", "manufacturer_primary", "evidence_scope", "checked_at"}
    assert all(set(row) == policy_fields for row in rows)


def test_wave228c_ledger_retains_snapshot_pins_and_no_apply_claim() -> None:
    with LEDGER.open(encoding="utf-8-sig", newline="") as handle:
        ledger = list(csv.DictReader(handle))
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert len(ledger) == 11
    assert all(row["partition"] == "exact_official_source_model_core_stageable" and row["stageable"] == "true" for row in ledger)
    assert all(len(row["snapshot_sha256"]) == 64 and row["snapshot_path"].startswith("docs/audits/sources/") for row in ledger)
    assert summary["target_rows"] == 11
    assert summary["wave227_image_verified_no_description_denominator"] == 52
    assert summary["manufacturer_counts"] == {"B.B. Battery": 4, "Casil": 5, "EnerSys": 2}
    assert "--refresh-existing --refresh-applied" in summary["stage_command"]
    assert summary["manifest_sha256"] == digest(MANIFEST)
    assert summary["ledger_sha256"] == digest(LEDGER)
    assert summary["database_apply"] is False and summary["publication_changes"] == 0
