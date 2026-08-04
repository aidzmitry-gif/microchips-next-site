from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/build-rb-wave202-strict-duplicate-manifest.py"
SOURCE = ROOT / "docs/audits/generated/rb-wave202-commercial-duplicate-guard.csv"
CHECKED_MANIFEST = ROOT / (
    "docs/imports/"
    "rb-reviewed-noindex-duplicates-motorola-symbol-wave202-2026-07-29.json"
)
CHECKED_SUMMARY = ROOT / (
    "docs/audits/generated/rb-wave202-strict-duplicate-manifest-summary.json"
)


def load_module():
    spec = importlib.util.spec_from_file_location("wave202_duplicate_manifest", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_checked_manifest_is_reproducible(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    summary = tmp_path / "summary.json"
    subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--source",
            str(SOURCE),
            "--manifest",
            str(manifest),
            "--summary",
            str(summary),
        ],
        cwd=ROOT,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    assert manifest.read_bytes() == CHECKED_MANIFEST.read_bytes()
    assert summary.read_bytes() == CHECKED_SUMMARY.read_bytes()


def test_manifest_contains_only_four_strict_motorola_symbol_pairs() -> None:
    manifest = json.loads(CHECKED_MANIFEST.read_text(encoding="utf-8"))
    rows = manifest["duplicates"]
    assert manifest["schema_version"] == 1
    assert manifest["site_key"] == "microchips-by"
    assert len(rows) == 4
    assert [row["survivor_external_id"] for row in rows] == [
        "bitrix:12130",
        "bitrix:12146",
        "bitrix:12139",
        "bitrix:12142",
    ]
    assert [row["duplicate_external_id"] for row in rows] == [
        "bitrix:24006",
        "bitrix:24007",
        "bitrix:24008",
        "bitrix:24009",
    ]
    assert len({row["survivor_external_id"] for row in rows}) == 4
    assert len({row["duplicate_external_id"] for row in rows}) == 4
    assert not ({row["survivor_external_id"] for row in rows} & {row["duplicate_external_id"] for row in rows})
    for row in rows:
        assert "Motorola" in row["survivor_name"]
        assert "Symbol" in row["duplicate_name"]
        assert row["availability"] == "on_request"
        assert row["category_external_ids"] == ["seo:batteries-industrial"]
        assert row["survivor_path"].endswith(row["survivor_external_id"].split(":", 1)[1])
        assert row["duplicate_path"].endswith(row["duplicate_external_id"].split(":", 1)[1])
        assert row["model_core"].lower() in row["survivor_name"].lower()
        assert row["model_core"].lower() in row["duplicate_name"].lower()
        assert row["voltage"] in row["survivor_name"]
        assert row["voltage"] in row["duplicate_name"]
        assert row["capacity"] in row["survivor_name"]
        assert row["capacity"] in row["duplicate_name"]


def test_builder_rejects_commercial_or_duplicate_guard_drift() -> None:
    module = load_module()
    plan = dict(module.PAIR_PLANS[0])
    row = module.read_rows(SOURCE)[plan["survivor_external_id"]]
    module.validate_source_row(row, plan)

    for field, value in (
        ("current_price", "1.00"),
        ("price_evidence_count", "1"),
        ("verified_published_media_count", "1"),
        ("offer_schema_present", "true"),
        ("strict_duplicate_group_size", "3"),
    ):
        drifted = dict(row)
        drifted[field] = value
        try:
            module.validate_source_row(drifted, plan)
        except ValueError:
            pass
        else:
            raise AssertionError(f"Builder accepted drift in {field}")
