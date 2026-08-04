from __future__ import annotations

import csv
import importlib.util
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/build-rb-wave207-identity-triage.py"
SOURCE = ROOT / "docs/audits/generated/rb-b2b-next-source-batch-wave205.csv"
OUTPUT = ROOT / "docs/audits/generated/rb-wave207-identity-triage.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-wave207-identity-triage.summary.json"


def load_module():
    spec = importlib.util.spec_from_file_location("wave207_identity_triage", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_union_is_exact_and_does_not_repeat_wave206() -> None:
    module = load_module()
    candidates = module.candidate_union(SOURCE)
    previous = module.wave206_ids(module.WAVE206_FILES)
    ids = {row["product_external_id"] for row in candidates}

    assert len(candidates) == 153
    assert len(ids) == 153
    assert Counter(row["manufacturer_cluster"] for row in candidates) == Counter(
        module.TARGET_CLUSTERS
    )
    assert len(previous) == 185
    assert ids.isdisjoint(previous)


def test_at_identity_is_order_independent_and_configuration_exact() -> None:
    module = load_module()
    first = module.identify(
        "Аккумулятор для радиостанций AT 4018-12 (NiMH, 1200mAh, 7.5V)"
    )
    second = module.identify(
        "Аккумулятор AT 4018-12 для радиостанций (NiMH, 1200mAh, 7.5V)"
    )

    assert first["normalized_model"] == second["normalized_model"] == "401812"
    assert first["normalized_configuration"] == second["normalized_configuration"]
    assert first["identity_key"] == second["identity_key"]
    assert first["route_partition"] == "actionable_source_route"


def test_cash_register_requires_device_connector_or_form_factor() -> None:
    module = load_module()
    actionable = module.identify(
        "Аккумулятор для кассовых аппаратов (NiCd, 4.8V, 1800mAh, KET-2P)"
    )
    hold = module.identify(
        "Аккумулятор для кассовых аппаратов (NiCd, 7.2V, 700mAh)"
    )

    assert actionable["normalized_model"] == "KET2P"
    assert actionable["route_partition"] == "actionable_source_route"
    assert hold["normalized_model"] == ""
    assert hold["route_partition"] == "hold"
    assert hold["hold_reason"] == "no_exact_model_device_connector_or_form_factor"


def test_vector_and_dual_industrial_designations_remain_distinct() -> None:
    module = load_module()
    vector = module.identify(
        "Аккумулятор Vector BP-44 L для радиостанций (Li-ion, 1500mAh, 7.4V)"
    )
    industrial = module.identify(
        "Аккумулятор FL-350 II KP (ТНЖК-350-II П-У2) (NiFe, 350Ah)"
    )

    assert vector["normalized_model"] == "BP44L"
    assert vector["identity_signal"] == "exact_claimed_vector_model"
    assert industrial["normalized_model"] == "FL350IIKP|THЖK350IIПY2"
    assert industrial["identity_signal"] == "exact_dual_industrial_designation"


def test_generated_artifacts_are_conservative_and_complete() -> None:
    rows = read_csv(OUTPUT)
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    holds = {row["product_external_id"] for row in rows if row["route_partition"] == "hold"}

    assert len(rows) == 153
    assert holds == {"bitrix:25712", "bitrix:25713"}
    assert all(row["safe_to_apply"] == "false" for row in rows)
    assert all(row["wave206_overlap"] == "false" for row in rows)
    assert all(row["in_wave_duplicate_candidate"] == "false" for row in rows)
    assert sum(int(row["db_identity_collision_count"]) for row in rows) == 0
    assert summary["candidate_records"] == 153
    assert summary["route_partition_counts"] == {
        "actionable_source_route": 151,
        "hold": 2,
    }
    assert summary["db_candidate_records_present"] == 153
    assert summary["wave206_overlap_records"] == 0
    assert summary["automatic_web_requests"] == 0
    assert summary["automatic_database_mutations"] == 0
    assert summary["safe_to_apply_records"] == 0
