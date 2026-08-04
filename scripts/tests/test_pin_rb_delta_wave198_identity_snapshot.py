from __future__ import annotations

import csv
import importlib.util
import json
import shutil
import sys
import uuid
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "pin-rb-delta-wave198-identity-snapshot.py"
SPEC = importlib.util.spec_from_file_location("delta_pin", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC); assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE; SPEC.loader.exec_module(MODULE)


def write_csv(path: Path, status: str = "") -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["external_id", "identity_candidate_status"])
        writer.writeheader(); writer.writerow({"external_id": "bitrix:1", "identity_candidate_status": status})


def write_audit(path: Path, identity_rows: int = 0) -> None:
    path.write_text(json.dumps({"schema_version":1,"site_key":"microchips-by","source_run_id":763,"source_run_manifest_sha256":"a"*64,"candidate_scope_records":1,"identity_candidate_rows":identity_rows,"result":"verified_clear"}), encoding="utf-8")


def workspace_tmp() -> Path:
    path = SCRIPT.parents[1] / "docs" / "audits" / "generated" / f"test-delta-pin-{uuid.uuid4().hex}"
    path.mkdir(parents=True)
    return path


def test_pins_explicit_none() -> None:
    tmp_path = workspace_tmp()
    source, audit, output = tmp_path / "in.csv", tmp_path / "audit.json", tmp_path / "out.csv"
    try:
        write_csv(source); write_audit(audit)
        summary = MODULE.build(source, audit, output, 1)
        assert summary["explicit_none_records"] == 1
        assert next(csv.DictReader(output.open(encoding="utf-8-sig")))["identity_candidate_status"] == "none"
    finally:
        shutil.rmtree(tmp_path)


def test_refuses_nonzero_audit_or_existing_candidate() -> None:
    tmp_path = workspace_tmp()
    source, audit, output = tmp_path / "in.csv", tmp_path / "audit.json", tmp_path / "out.csv"
    try:
        write_csv(source, "pending"); write_audit(audit)
        with pytest.raises(ValueError, match="nonempty candidate"):
            MODULE.build(source, audit, output, 1)
        write_csv(source); write_audit(audit, identity_rows=1)
        with pytest.raises(ValueError, match="identity_candidate_rows"):
            MODULE.build(source, audit, output, 1)
    finally:
        shutil.rmtree(tmp_path)
