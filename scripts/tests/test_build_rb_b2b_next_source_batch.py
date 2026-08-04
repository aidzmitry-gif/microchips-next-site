import csv
import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "build-rb-b2b-next-source-batch.py"
READINESS = ROOT / "docs" / "audits" / "generated" / "rb-full-content-readiness-wave172-after.csv"
PROCESSED = ROOT / "docs" / "audits" / "generated" / "rb-b2b-priority-queue-wave174.csv"
HOLDS = ROOT / "docs" / "audits" / "generated" / "rb-known-hold-products-wave172-cumulative.csv"
PRIORITY = ROOT / "scripts" / "build-rb-b2b-priority-queue.py"


def load_module():
    spec = importlib.util.spec_from_file_location("next_batch", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_manufacturer_and_family_inference_is_bounded():
    module = load_module()
    assert module.manufacturer("Аккумулятор APC RBC7 (AGM)") == "APC"
    assert module.family("Аккумулятор APC RBC7 (AGM)", "APC") == "rbc-series"
    assert module.family("Аккумулятор Ventura GPL 12-100", "Ventura") == "gpl-series"
    assert module.family("Аккумулятор Casil CA 1208", "Casil") == "ca-series"
    assert module.manufacturer("Аккумулятор для радиостанций AT 173-07") == "AT radio packs"
    assert module.manufacturer("Аккумулятор для радиостанций Baofeng UV-5R") == "Baofeng"
    assert module.cluster_role("Baofeng") == "device_oem_or_compatibility_family"
    assert module.manufacturer("Аккумулятор 5НК-125") == "unresolved_industrial_cell"
    assert module.manufacturer("Аккумулятор для неизвестного устройства") == "unresolved_replacement"


def test_real_batch_is_no_repeat_and_read_only():
    output = ROOT / "docs" / "audits" / "generated" / "test-wave205-next-source-batch.csv"
    summary = ROOT / "docs" / "audits" / "generated" / "test-wave205-next-source-summary.json"
    command = [
        sys.executable,
        str(SCRIPT),
        "--readiness", str(READINESS),
        "--processed", str(PROCESSED),
        "--holds", str(HOLDS),
        "--priority-script", str(PRIORITY),
        "--output", str(output),
        "--summary", str(summary),
        "--expected-readiness-sha256", "a9f683f30ee06adc5cad46a545a4266e74c5175c1244f5a3431b290dcdaa8493",
        "--expected-processed-sha256", "a4ed39b73d5f809d6d815cef68b6f31ad1704f4c0a6f8bedfdb550324a7fb7b7",
        "--expected-holds-sha256", "a01bc64f7c3aedf025e50b22de0988ff3221b6cf957c654ea7396268a954ab7f",
        "--expected-readiness-records", "16415",
        "--expected-processed-records", "500",
        "--limit", "500",
    ]
    try:
        subprocess.run(command, cwd=ROOT, check=True, capture_output=True, text=True)
        result = list(csv.DictReader(output.read_text(encoding="utf-8-sig").splitlines()))
        processed = {row["product_external_id"] for row in csv.DictReader(PROCESSED.read_text(encoding="utf-8-sig").splitlines())}
        report = json.loads(summary.read_text(encoding="utf-8"))

        assert len(result) == 500
        assert len({row["product_external_id"] for row in result}) == 500
        assert not ({row["product_external_id"] for row in result} & processed)
        assert all(row["safe_to_apply"] == "false" for row in result)
        assert all("автомоб" not in row["name"].lower() for row in result)
        assert report["automatic_database_mutations"] == 0
        assert report["safe_to_apply_records"] == 0
    finally:
        output.unlink(missing_ok=True)
        summary.unlink(missing_ok=True)
