from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/verify-rb-wave208-priority-queue.py"
QUEUE = ROOT / "docs/audits/generated/rb-b2b-priority-queue-wave208.csv"
PROCESSED = ROOT / "docs/audits/generated/rb-b2b-processed-register-wave208.csv"
BUILDER_SUMMARY = ROOT / "docs/audits/generated/rb-b2b-priority-queue-wave208.summary.json"
VERIFY_SUMMARY = ROOT / "docs/audits/generated/rb-b2b-priority-queue-wave208.verification.json"


def load_module():
    spec = importlib.util.spec_from_file_location("wave208_verify", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_scope_patterns_detect_representative_out_of_scope_names() -> None:
    module = load_module()
    assert module.AUTOMOTIVE.search("Автомобильный стартерный аккумулятор")
    assert module.AUTOMOTIVE.search("Аккумулятор для мотоцикла")
    assert module.ELECTRONICS.search("Силовой транзистор")
    assert module.ELECTRONICS.search("Микросхема контроллера")
    assert not module.AUTOMOTIVE.search("Тяговый аккумулятор для погрузчика")
    assert not module.ELECTRONICS.search("Источник бесперебойного питания")


def test_real_wave208_queue_is_unique_disjoint_and_in_scope() -> None:
    module = load_module()
    queue = read_csv(QUEUE)
    processed = read_csv(PROCESSED)
    queue_ids = {row["product_external_id"] for row in queue}
    processed_ids = {row["product_external_id"] for row in processed}

    assert len(queue) == len(queue_ids) == 500
    assert len(processed) == len(processed_ids) == 1000
    assert queue_ids.isdisjoint(processed_ids)
    assert not [row for row in queue if module.AUTOMOTIVE.search(row["name"])]
    assert not [row for row in queue if module.ELECTRONICS.search(row["name"])]
    assert all(row["safe_to_apply"] == "false" for row in queue)


def test_verification_summary_pins_both_artifacts() -> None:
    summary = json.loads(VERIFY_SUMMARY.read_text(encoding="utf-8"))
    builder = json.loads(BUILDER_SUMMARY.read_text(encoding="utf-8"))

    assert summary["queue_records"] == 500
    assert summary["processed_records"] == 1000
    assert summary["processed_overlap_records"] == 0
    assert summary["automotive_records"] == 0
    assert summary["electronics_records"] == 0
    assert summary["safe_to_apply_records"] == 0
    assert summary["queue_sha256"] == sha(QUEUE) == builder["output_sha256"]
    assert summary["processed_sha256"] == sha(PROCESSED) == builder["processed_sha256"]
    assert summary["automatic_web_requests"] == 0
    assert summary["automatic_database_mutations"] == 0
