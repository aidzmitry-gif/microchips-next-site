from __future__ import annotations

import csv
import importlib.util
import json
import shutil
import sys
import uuid
from pathlib import Path


ROOT = Path(__file__).parents[2]
SCRIPT = ROOT / "scripts/build-rb-wave203-industrial-preparation.py"
OUTPUT = ROOT / "docs/audits/generated/wave203-industrial-unassigned-preparation.csv"
SUMMARY = ROOT / "docs/audits/generated/wave203-industrial-unassigned-preparation-summary.json"
QUEUE = ROOT / "docs/audits/generated/rb-b2b-priority-queue-wave174.csv"
WAVE201 = ROOT / "docs/audits/generated/wave201-industrial-batch-candidates.csv"
PROCESSED = (
    ROOT
    / "docs/imports/rb-source-backed-description-drafts-b2b-terminals-wave174-2026-07-29.json"
)

SPEC = importlib.util.spec_from_file_location("wave203_preparation", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_checked_in_preparation_reconciles_and_has_no_prior_overlap() -> None:
    rows = read(OUTPUT)
    queue = read(QUEUE)
    prior = read(WAVE201)
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    queue_ids = {row["product_external_id"] for row in queue}
    prior_ids = {row["product_external_id"] for row in prior}
    output_ids = {row["product_external_id"] for row in rows}

    assert len(queue) == 500
    assert len(prior) == 249
    assert len(rows) == len(output_ids) == 251
    assert output_ids == queue_ids - prior_ids
    assert output_ids.isdisjoint(prior_ids)
    assert summary["family_counts"] == {
        "industrial_remote_control_batteries": 31,
        "legacy_industrial_traction_cells": 34,
        "mobile_computers_pos_data_capture": 145,
        "radio_station_battery_packs": 41,
    }
    assert summary["recommended_batch_records"] == 143
    assert summary["previously_processed_records"] == 2
    assert summary["previously_processed_product_external_ids"] == [
        "bitrix:12124",
        "bitrix:12247",
    ]
    assert summary["recommended_prior_id_overlap_records"] == 0
    assert summary["wave201_id_overlap_records"] == 0
    assert summary["automatic_database_mutations"] == 0
    assert summary["safe_to_apply_records"] == 0


def test_wave203_is_fail_closed_and_exactly_the_mobile_pos_family() -> None:
    rows = read(OUTPUT)
    recommended = [row for row in rows if row["recommended_wave"] == "wave203"]

    assert len(recommended) == 143
    assert {row["family"] for row in recommended} == {
        "mobile_computers_pos_data_capture"
    }
    assert all(row["research_cost_class"] == "low" for row in recommended)
    assert all(row["safe_to_apply"] == "false" for row in rows)
    assert all(row["required_gate"] for row in rows)
    assert all(row["brand_or_series"] for row in rows)
    assert all(row["model_tokens_unverified"] for row in recommended)
    assert not {
        row["product_external_id"] for row in recommended
    } & {"bitrix:12124", "bitrix:12247"}


def test_builder_is_reproducible() -> None:
    temp = ROOT / "docs/audits/generated" / f"test-wave203-{uuid.uuid4().hex}"
    temp.mkdir(parents=True)
    try:
        output = temp / "out.csv"
        summary_path = temp / "summary.json"
        built = MODULE.build(QUEUE, WAVE201, PROCESSED, output, summary_path)

        assert output.read_bytes() == OUTPUT.read_bytes()
        assert built == json.loads(summary_path.read_text(encoding="utf-8"))
    finally:
        shutil.rmtree(temp)
