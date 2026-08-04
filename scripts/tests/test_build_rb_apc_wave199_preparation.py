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


SCRIPT = Path(__file__).parents[1] / "build-rb-apc-wave199-preparation.py"
SPEC = importlib.util.spec_from_file_location("apc_wave199", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def row(external_id: str, name: str, **overrides: str) -> dict[str, str]:
    value = {
        "product_external_id": external_id,
        "name": name,
        "category_external_id": "seo:batteries-ups",
        "identity_ready": "false",
        "has_applied_description": "false",
        "description_source_tier": "",
        "description_manufacturer_primary": "false",
    }
    value.update(overrides)
    return value


def write(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def workspace_tmp() -> Path:
    path = SCRIPT.parents[1] / "docs" / "audits" / "generated" / f"test-apc-wave199-{uuid.uuid4().hex}"
    path.mkdir(parents=True)
    return path


def run_build(source: Path, output: Path, summary: Path, expected: int) -> dict[str, object]:
    return MODULE.build(
        source, output, summary, expected,
        readiness_snapshot_id="readiness@wave172-after",
        readiness_snapshot_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
    )


def test_selects_exact_cartridge_sybt_and_external_pack_tokens() -> None:
    rows = [
        row("bitrix:1", "APC Replacement Battery Cartridge APCRBC123"),
        row("bitrix:2", "Battery APC RBC7"),
        row("bitrix:3", "Battery APC SYBTU1-PLP"),
        row("bitrix:4", "External battery pack APC SRT192RMBP2"),
        row("bitrix:generic", "APC Smart-UPS 3000 VA"),
        row("bitrix:partial", "APC RBC123X"),
        row("1c:5", "APC RBC31"),
        row("bitrix:backed", "APC RBC32", has_applied_description="true"),
        row("bitrix:strict", "APC RBC33", identity_ready="true"),
        row("bitrix:wrong-category", "APC RBC34", category_external_id="seo:ups-systems"),
    ]
    tmp_path = workspace_tmp()
    try:
        source = tmp_path / "readiness.csv"
        write(source, rows)
        output, summary_path = tmp_path / "out.csv", tmp_path / "summary.json"
        summary = run_build(source, output, summary_path, 4)
        candidates = list(csv.DictReader(output.open(encoding="utf-8-sig")))
        assert [(item["external_id"], item["model_token"]) for item in candidates] == [
            ("bitrix:1", "APCRBC123"), ("bitrix:2", "RBC7"),
            ("bitrix:3", "SYBTU1-PLP"), ("bitrix:4", "SRT192RMBP2"),
        ]
        assert all(item["safe_to_apply"] == "false" for item in candidates)
        assert summary["excluded_counts"] == {
            "already_source_backed": 1,
            "already_strict_identity": 1,
            "generic_or_nonexact_apc_name": 2,
            "not_existing_bitrix_b2b_card": 1,
            "outside_b2b_battery_category": 1,
        }
        assert json.loads(summary_path.read_text(encoding="utf-8")) == summary
    finally:
        shutil.rmtree(tmp_path)


def test_source_tier_and_manufacturer_primary_also_exclude_source_backed_rows() -> None:
    rows = [
        row("bitrix:1", "APC RBC7", description_source_tier="manufacturer_primary"),
        row("bitrix:2", "APC RBC8", description_manufacturer_primary="true"),
        row("bitrix:3", "APC RBC9"),
    ]
    tmp_path = workspace_tmp()
    try:
        source = tmp_path / "readiness.csv"
        write(source, rows)
        summary = run_build(source, tmp_path / "out.csv", tmp_path / "summary.json", 1)
        assert summary["excluded_counts"] == {"already_source_backed": 2}
    finally:
        shutil.rmtree(tmp_path)


@pytest.mark.parametrize("field", ["identity_ready", "has_applied_description", "description_manufacturer_primary"])
def test_boolean_readiness_fields_fail_closed(field: str) -> None:
    tmp_path = workspace_tmp()
    try:
        source = tmp_path / "readiness.csv"
        write(source, [row("bitrix:1", "APC RBC7", **{field: "unknown"})])
        with pytest.raises(ValueError, match="must be explicitly true or false"):
            run_build(source, tmp_path / "out.csv", tmp_path / "summary.json", 1)
    finally:
        shutil.rmtree(tmp_path)


def test_pinned_snapshot_sha256_and_expected_count_fail_closed() -> None:
    tmp_path = workspace_tmp()
    try:
        source = tmp_path / "readiness.csv"
        write(source, [row("bitrix:1", "APC RBC7")])
        with pytest.raises(ValueError, match="selection mismatch"):
            run_build(source, tmp_path / "out.csv", tmp_path / "summary.json", 2)
        with pytest.raises(ValueError, match="SHA-256"):
            MODULE.build(
                source, tmp_path / "out.csv", tmp_path / "summary.json", 1,
                readiness_snapshot_id="readiness@wave172-after",
                readiness_snapshot_sha256="0" * 64,
            )
    finally:
        shutil.rmtree(tmp_path)
