from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/build-rb-wave228b-delta-ventura-description-stage.py"
IMPORTS = ROOT / "docs/imports"
GEN = ROOT / "docs/audits/generated"
OUTPUTS = (
    IMPORTS / "rb-source-backed-description-stage-manifest-wave228b-2026-07-29.json",
    GEN / "rb-wave228b-delta-ventura-description-ledger.csv",
    GEN / "rb-wave228b-delta-ventura-description-holds.csv",
    GEN / "rb-wave228b-delta-ventura-description.summary.json",
    ROOT / "docs/audits/2026-07-29-rb-wave228b-delta-ventura-descriptions.md",
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_wave228b_is_deterministic_and_exact() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True)
    first = tuple(digest(path) for path in OUTPUTS)
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True)
    assert first == tuple(digest(path) for path in OUTPUTS)

    manifest = json.loads(OUTPUTS[0].read_text(encoding="utf-8"))
    ledger, holds = read_csv(OUTPUTS[1]), read_csv(OUTPUTS[2])
    summary = json.loads(OUTPUTS[3].read_text(encoding="utf-8"))
    assert len(manifest["products"]) == len(ledger) == 13
    assert holds == []
    assert {row["manufacturer"] for row in manifest["products"]} == {"Delta", "Ventura"}
    assert sum(row["manufacturer"] == "Delta" for row in manifest["products"]) == 8
    assert sum(row["manufacturer"] == "Ventura" for row in manifest["products"]) == 5
    assert all(row["identity_scope"] == "exact" and row["evidence_scope"] == "exact_model" for row in manifest["products"])
    assert manifest["application_contract"] == {"stage_only": True, "refresh_existing": True, "refresh_applied": True, "database_apply": False}
    assert all(row["safe_to_apply"] == "false" and row["refresh_existing"] == "true" and row["refresh_applied"] == "true" for row in ledger)
    assert summary["coverage"] == {"wave227_image_verified_no_description_targets": 13, "delta_targets": 8, "ventura_targets": 5, "staged": 13, "holds": 0}
    assert summary["safety"]["database_operations"] == 0 and summary["safety"]["apply_performed"] is False


def test_wave228b_preserves_official_ventura_not_title_rounded_values() -> None:
    manifest = json.loads(OUTPUTS[0].read_text(encoding="utf-8"))
    by_id = {row["external_id"]: row for row in manifest["products"]}
    assert by_id["bitrix:1609"]["technical_attributes"]["Номинальная ёмкость C20"] == "42 А·ч"
    assert by_id["bitrix:1643"]["technical_attributes"]["Номинальная ёмкость C20"] == "8,7 А·ч"
    assert by_id["bitrix:1624"]["technical_attributes"] == {"Номинальное напряжение": "12 В", "Мощность (15 мин до 1,6 В/эл)": "192 Вт/блок"}
