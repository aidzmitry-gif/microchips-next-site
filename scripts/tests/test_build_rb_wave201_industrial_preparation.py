from __future__ import annotations

import csv
import importlib.util
import shutil
import sys
import uuid
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "build-rb-wave201-industrial-preparation.py"
SPEC = importlib.util.spec_from_file_location("wave201", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def tmp() -> Path:
    path = SCRIPT.parents[1] / "docs" / "audits" / "generated" / f"test-wave201-{uuid.uuid4().hex}"
    path.mkdir(parents=True)
    return path


def write(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else ["external_id", "reason"])
        writer.writeheader(); writer.writerows(rows)


def test_builds_only_coherent_unexcluded_oem_batches() -> None:
    root = tmp()
    try:
        queue = root / "queue.csv"
        write(queue, [
            {"product_external_id": "bitrix:1", "name": "Battery Motorola MC55", "category_external_id": "seo:batteries-industrial", "safe_to_apply": "false"},
            {"product_external_id": "bitrix:2", "name": "Battery Honeywell CK65", "category_external_id": "seo:batteries-industrial", "safe_to_apply": "false"},
            {"product_external_id": "bitrix:3", "name": "Battery Datalogic Memor", "category_external_id": "seo:batteries-industrial", "safe_to_apply": "false"},
            {"product_external_id": "bitrix:4", "name": "Battery Intermec CK3", "category_external_id": "seo:batteries-industrial", "safe_to_apply": "false"},
            {"product_external_id": "bitrix:5", "name": "Battery CS-MC55BX for Motorola MC55", "category_external_id": "seo:batteries-industrial", "safe_to_apply": "false"},
        ])
        excluded = root / "exclusions.csv"; write(excluded, [{"external_id": "bitrix:2", "reason": "prior_hold"}])
        summary = MODULE.build(queue, excluded, root / "out.csv", root / "summary.json", expected_records=5)
        rows = list(csv.DictReader((root / "out.csv").open(encoding="utf-8-sig")))
        assert summary["recommended_batches"] == {
            "cameron_sino_exact_model": 1,
            "datalogic_data_capture": 1,
            "intermec_mobile_computers": 1,
            "zebra_legacy_mobile_computers": 1,
        }
        assert {row["product_external_id"] for row in rows} == {"bitrix:1", "bitrix:3", "bitrix:4", "bitrix:5"}
        assert all(row["safe_to_apply"] == "false" for row in rows)
        cameron_sino = next(row for row in rows if row["product_external_id"] == "bitrix:5")
        assert cameron_sino["batch"] == "cameron_sino_exact_model"
        assert cameron_sino["evidence_class"] == "replacement_pack_identity_and_specs"
        motorola = next(row for row in rows if row["product_external_id"] == "bitrix:1")
        assert motorola["evidence_class"] == "device_compatibility_context_only"
        assert "must not set" in motorola["evidence_boundary"]
    finally:
        shutil.rmtree(root)


def test_fails_closed_when_queue_is_not_safe_industrial_input() -> None:
    root = tmp()
    try:
        queue = root / "queue.csv"
        write(queue, [{"product_external_id": "bitrix:1", "name": "Battery Zebra", "category_external_id": "seo:replacement-mobile", "safe_to_apply": "true"}])
        excluded = root / "exclusions.csv"; write(excluded, [])
        try:
            MODULE.build(queue, excluded, root / "out.csv", root / "summary.json", expected_records=1)
        except ValueError as error:
            assert "industrial" in str(error)
        else:
            raise AssertionError("unsafe input was accepted")
    finally:
        shutil.rmtree(root)
