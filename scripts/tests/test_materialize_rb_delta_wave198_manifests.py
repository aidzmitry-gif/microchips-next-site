from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import shutil
import sys
import uuid
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "materialize-rb-delta-wave198-manifests.py"
SPEC = importlib.util.spec_from_file_location("delta_materialize", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC); assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE; SPEC.loader.exec_module(MODULE)


def workspace_tmp() -> Path:
    path = SCRIPT.parents[1] / "docs" / "audits" / "generated" / f"test-delta-materialize-{uuid.uuid4().hex}"
    path.mkdir(parents=True)
    return path


def fixture(root: Path, duplicate: bool = False) -> tuple[Path, Path]:
    evidence = root / "evidence.csv"
    rows = [{"external_id":"bitrix:1","model":"HR 12-4.5","source_url":"https://delta-batt.com/products/hr_12_4_5/","voltage_v":"12","capacity_ah":"4.5","publisher":"DELTA Battery / ENERGON"}]
    if duplicate:
        rows.append({**rows[0], "external_id":"bitrix:2"})
    with evidence.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    contract = root / "contract.json"
    contract.write_text(json.dumps({"official_evidence_sha256":hashlib.sha256(evidence.read_bytes()).hexdigest(),"official_exact_matches":len(rows)}), encoding="utf-8")
    return evidence, contract


def test_builds_exact_no_commercial_manifests() -> None:
    root = workspace_tmp()
    try:
        evidence, contract = fixture(root)
        descriptions, previews = root / "descriptions.json", root / "previews.json"
        summary = MODULE.build(evidence, contract, descriptions, previews)
        row = json.loads(descriptions.read_text(encoding="utf-8"))["products"][0]
        assert summary["records"] == 1 and summary["price_authorizations"] == 0
        assert row["identity_scope"] == "exact" and row["mpn"] == "HR 12-4.5"
        assert row["technical_attributes"]["Номинальная ёмкость"] == "4.5 А·ч"
    finally:
        shutil.rmtree(root)


def test_rejects_duplicate_slug() -> None:
    root = workspace_tmp()
    try:
        evidence, contract = fixture(root, duplicate=True)
        with pytest.raises(ValueError, match="slug"):
            MODULE.build(evidence, contract, root / "d.json", root / "p.json")
    finally:
        shutil.rmtree(root)


def test_excludes_a_pinned_existing_identity_hold() -> None:
    root = workspace_tmp()
    try:
        evidence, contract = fixture(root)
        holds = root / "holds.csv"
        with holds.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["external_id", "model", "existing_external_id", "reason"])
            writer.writeheader(); writer.writerow({"external_id":"bitrix:1","model":"HR 12-4.5","existing_external_id":"1c:1","reason":"existing_product_identity"})
        summary = MODULE.build(evidence, contract, root / "d.json", root / "p.json", holds)
        assert summary["records"] == 0 and summary["identity_holds"] == 1
    finally:
        shutil.rmtree(root)
