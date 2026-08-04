import csv
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/build-rb-wave241-source-backed-descriptions.py"
MANIFEST = ROOT / "docs/imports/rb-source-backed-descriptions-wave241-2026-07-29.json"
LEDGER = ROOT / "docs/audits/generated/rb-wave241-source-backed-descriptions-ledger.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-wave241-source-backed-descriptions.summary.json"
REPORT = ROOT / "docs/audits/2026-07-29-rb-wave241-source-backed-descriptions.md"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_builder() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True, text=True)


def read_ledger() -> list[dict[str, str]]:
    with LEDGER.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


@pytest.fixture(scope="module", autouse=True)
def build_artifacts_once() -> None:
    run_builder()


def test_wave241_is_deterministic_and_covers_all_44_rows():
    first = {path: digest(path) for path in (MANIFEST, LEDGER, SUMMARY, REPORT)}
    run_builder()
    assert first == {path: digest(path) for path in (MANIFEST, LEDGER, SUMMARY, REPORT)}
    ledger = read_ledger()
    assert len(ledger) == 44
    assert len({row["external_id"] for row in ledger}) == 44
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert summary["coverage"] == {"scope": 44, "pass": 44, "hold": 0}


def test_manifest_contains_only_passed_manufacturer_primary_model_core_facts():
    ledger = read_ledger()
    passed = {row["external_id"] for row in ledger if row["decision"] == "PASS"}
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    serialized = json.dumps(payload, ensure_ascii=False)
    assert "\ufffd" not in serialized
    assert not any(marker in serialized for marker in ("РњРѕ", "РўРёРї", "РЎ†РµРЅ"))
    assert {row["external_id"] for row in payload["products"]} == passed
    assert len(payload["products"]) == 44
    assert Counter(row["technology"] for row in payload["products"]) == {
        "VRLA AGM": 15,
        "GEL": 8,
        "VRLA GEL": 1,
        "AGM": 15,
        "lead-acid": 5,
    }
    for row in payload["products"]:
        assert row["identity_scope"] == row["evidence_scope"] == "model_core"
        assert row["source_tier"] == "manufacturer_primary"
        assert row["manufacturer_primary"] is True
        assert row["source_kind"] in {"official_manufacturer_catalogue", "official_manufacturer_product_page"}
        assert row["technical_attributes"]["Модель"] == row["model_core"]
        assert row["technical_attributes"]["Технология"] == row["technology"]
        assert not set(row) & {"price", "stock", "warranty", "publication", "media"}
        text = json.dumps(row["technical_attributes"], ensure_ascii=False).lower()
        assert not any(value in text for value in ("цена", "price", "налич", "stock", "гарант", "warranty"))


def test_generated_artifacts_are_clean_utf8_without_replacement_or_mojibake():
    mojibake_markers = (
        "\ufffd",
        "\u0420\u045a\u0420\u0455\u0420\u0491\u0420\u00b5\u0420\u00bb\u0421\u0452",
        "\u0420\u0452\u0420\u0451\u0420\u0457",
        "\u0421\u2020\u0420\u00b5\u0420\u0405\u0420\u00b0",
    )
    for path in (MANIFEST, LEDGER, SUMMARY, REPORT):
        raw = path.read_bytes()
        text = raw.decode("utf-8")
        assert not any(marker in text for marker in mojibake_markers), path


def test_all_source_and_registry_pins_are_revalidated_and_exact_models_are_present():
    for row in read_ledger():
        assert row["decision"] == "PASS"
        assert row["source_exact_model_present"] == "true"
        assert row["source_technology_present"] == "true"
        assert row["prior_description_manifest_hits"] == "0"
        assert digest(ROOT / row["identity_registry"]) == row["identity_registry_sha256"]
        assert digest(ROOT / row["source_snapshot_path"]) == row["source_snapshot_sha256"]


def test_no_repeat_audit_is_pinned_and_has_zero_scope_overlap():
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    audit = summary["no_repeat_audit"]
    assert audit["prior_description_manifest_count"] == 14
    assert audit["prior_description_product_rows"] == 337
    assert audit["scope_overlap"] == 0
    for path, expected in audit["pins"].items():
        assert digest(ROOT / path) == expected


def test_builder_has_no_network_or_database_side_effect_contract():
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert summary["safety"] == {
        "network_calls": 0,
        "database_operations": 0,
        "apply_performed": False,
        "commercial_changes": 0,
        "publication_changes": 0,
        "media_changes": 0,
    }
    source = SCRIPT.read_text(encoding="utf-8")
    assert "requests" not in source
    assert "urllib" not in source
    assert "artisan" not in source
