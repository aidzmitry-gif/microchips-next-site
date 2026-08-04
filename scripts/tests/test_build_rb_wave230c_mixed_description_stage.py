from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/build-rb-wave230c-mixed-description-stage.py"
MANIFEST = ROOT / "docs/imports/rb-source-backed-description-stage-manifest-wave230c-2026-07-29.json"
LEDGER = ROOT / "docs/audits/generated/rb-wave230c-mixed-description-ledger.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-wave230c-mixed-description.summary.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_wave230c_is_deterministic_and_preserves_the_frozen_28_target_scope() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True)
    first = {path: digest(path) for path in (MANIFEST, LEDGER, SUMMARY)}
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True)
    assert first == {path: digest(path) for path in first}
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert summary["frozen_denominator"] == 88
    assert summary["target_rows"] == 28
    assert summary["manufacturer_counts"] == {"Ventura": 7, "Casil": 5, "ROBITON": 5, "B.B. Battery": 4, "Delta": 3, "DELTA": 3, "Panasonic": 1}
    assert summary["verified_media_lineage"]["rows"] == 28
    assert summary["database_apply"] is False


def test_wave230c_uses_bounded_model_core_when_name_end_contract_fails() -> None:
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    products = payload["products"]
    assert len(products) == len({row["external_id"] for row in products}) == 28
    assert {row["identity_scope"] for row in products} == {"model_core"}
    assert all(row["evidence_scope"] == "model_core" and row["model_core"] for row in products)
    assert all("mpn" not in row and "display_name" not in row for row in products)
    assert all(row["source_url"].startswith("https://") and row["manufacturer_primary"] is True for row in products)
    assert json.loads(SUMMARY.read_text(encoding="utf-8"))["manifest_sha256"] == digest(MANIFEST)
    assert json.loads(SUMMARY.read_text(encoding="utf-8"))["ledger_sha256"] == digest(LEDGER)
