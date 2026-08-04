import hashlib
import importlib.util
import json
import subprocess
import sys
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/build-rb-wave239-fiamm-exact-descriptions.py"
MANIFEST = ROOT / "docs/imports/rb-source-backed-descriptions-wave239-fiamm-2026-07-29.json"
LEDGER = ROOT / "docs/audits/generated/rb-wave239-fiamm-exact-description-ledger.json"
SUMMARY = ROOT / "docs/audits/generated/rb-wave239-fiamm-exact-description-summary.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_builder():
    spec = importlib.util.spec_from_file_location("wave239_builder", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def run_builder() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True, text=True)


def test_build_is_deterministic_and_scope_is_frozen():
    run_builder()
    first = {path: digest(path) for path in (MANIFEST, LEDGER, SUMMARY)}
    run_builder()
    assert first == {path: digest(path) for path in (MANIFEST, LEDGER, SUMMARY)}

    builder = load_builder()
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    actual = [(row["external_id"], row["mpn"]) for row in payload["products"]]
    assert actual == list(builder.FROZEN)
    assert len(actual) == len(set(actual)) == 29


def test_manifest_uses_only_exact_manufacturer_primary_evidence():
    run_builder()
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert payload["locale"] == "ru-BY"
    allowed = {
        "external_id", "identity_scope", "manufacturer", "mpn", "display_name", "technology",
        "source_url", "technical_attributes", "source_kind", "source_tier", "source_publisher",
        "manufacturer_primary", "evidence_scope", "checked_at",
    }
    for row in payload["products"]:
        assert set(row) == allowed
        assert row["identity_scope"] == "exact"
        assert row["manufacturer"] == "Fiamm"
        assert row["technology"] == "AGM"
        assert row["source_kind"] == "official_manufacturer_catalogue"
        assert row["source_tier"] == "manufacturer_primary"
        assert row["manufacturer_primary"] is True
        assert row["evidence_scope"] == "exact_model"
        assert row["source_url"].startswith("https://www.fiamm.ru/")
        assert row["checked_at"] == "2026-07-29"
        assert row["display_name"].startswith(f"Аккумулятор Fiamm {row['mpn']} (AGM, ")
        text = json.dumps(row, ensure_ascii=False).lower()
        assert not any(term in text for term in ("цена", "price", "налич", "stock", "гарант", "warranty"))


def test_ledger_pins_inputs_and_records_one_page_two_row_each():
    run_builder()
    builder = load_builder()
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    assert ledger["scope"] == {"frozen_pairs": 29, "pass": 29, "hold": 0}
    assert ledger["input_pins"]["identity_manifest"]["sha256"] == builder.INPUT_PINS["identity_manifest"]
    assert ledger["input_pins"]["queue"]["sha256"] == builder.INPUT_PINS["queue"]
    for key, source in builder.PDFS.items():
        pin = ledger["input_pins"]["pdfs"][key]
        assert pin["sha256"] == source["sha256"]
        assert digest(ROOT / pin["path"]) == source["sha256"]
    assert len(ledger["rows"]) == 29
    assert all(row["decision"] == "PASS" for row in ledger["rows"])
    assert all(row["source_page"] == 2 and row["exact_bounded_row_count"] == 1 for row in ledger["rows"])


def test_sensitive_table_values_and_horizontal_note_are_literal():
    run_builder()
    products = {
        row["external_id"]: row for row in json.loads(MANIFEST.read_text(encoding="utf-8"))["products"]
    }
    flb400 = products["bitrix:1427"]["technical_attributes"]
    assert flb400["Номинальная ёмкость (20 ч, 1,75 В/эл., 25 °C)"] == "109 А·ч"
    assert flb400["Номинальная мощность (15 мин, 1,67 В/эл., 25 °C)"] == "415 Вт/эл."
    assert products["bitrix:3010"]["technical_attributes"]["Тип выводов"] == "Faston 4.8"

    sla800 = products["bitrix:858"]
    assert sla800["display_name"] == "Аккумулятор Fiamm 2SLA800 (AGM, 820Ah)"
    assert sla800["technical_attributes"]["Номинальная ёмкость (10 ч, 1,80 В/эл., 20 °C)"] == "820 А·ч"
    assert sla800["technical_attributes"]["Габариты (Д × Ш × В)"] == "254 × 210 × 495 мм"
    assert products["bitrix:1462"]["technical_attributes"]["Номинальная ёмкость (20 ч, 1,75 В/эл., 25 °C)"] == "80 А·ч"
    assert products["bitrix:1462"]["technical_attributes"]["Габариты (Д × Ш × В)"] == "260 × 168 × 209 мм"
    assert products["bitrix:1704"]["technical_attributes"]["Номинальная ёмкость (10 ч, 1,80 В/эл., 20 °C)"] == "1500 А·ч"
    assert products["bitrix:1715"]["technical_attributes"]["Номинальная ёмкость (10 ч, 1,80 В/эл., 20 °C)"] == "2000 А·ч"
    assert products["bitrix:3079"]["technical_attributes"]["Номинальная ёмкость (10 ч, 1,80 В/эл., 20 °C)"] == "50 А·ч"

    builder = load_builder()
    assert builder.display_number(Decimal("820")) == "820"
    assert builder.display_number(Decimal("4.50")) == "4,5"

    horizontal = {
        external_id
        for external_id, row in products.items()
        if row["technical_attributes"].get("Монтаж") == "только горизонтальное положение"
    }
    assert horizontal == {"bitrix:858", "bitrix:1690", "bitrix:1704", "bitrix:1715"}


def test_summary_has_no_commercial_or_runtime_side_effect_facts():
    run_builder()
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert summary["frozen_scope_count"] == summary["pass_count"] == 29
    assert summary["hold_count"] == 0
    assert summary["manifest"]["sha256"] == digest(MANIFEST)
    assert summary["ledger"]["sha256"] == digest(LEDGER)
    for key in ("price_facts", "stock_facts", "warranty_facts", "database_calls", "network_calls"):
        assert summary[key] == 0
