import csv
import hashlib
import importlib.util
import json
import shutil
import sys
import uuid
from pathlib import Path

import openpyxl


SCRIPT = Path(__file__).parents[1] / "build-lenovo-official-battery-evidence.py"
SPEC = importlib.util.spec_from_file_location("lenovo_official_evidence", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def candidate(external_id: str, part: str, voltage: str, wh: str) -> dict[str, str]:
    return {
        "product_external_id": external_id,
        "name": f"Аккумулятор (батарея) {part} для ноутбука Lenovo, {voltage}V, {wh}Wh",
        "brand_candidate": "Lenovo",
        "part_number_candidates": part,
        "primary_part_number_key": MODULE.normalize_part(part),
        "voltage_v_candidates": voltage,
        "capacity_mah_candidates": "3350",
        "energy_wh_candidates": wh,
        "identity_risk": "single_candidate_needs_primary_source",
        "safe_to_apply": "false",
    }


def create_workbook(path: Path) -> None:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "BatteryData"
    sheet.append([
        "ASSM PN", "FRU PN", "Battery Model", "WH Rating", "Weight (g)",
        "Li Content (g)", "Cell Voltage (VDC)", "Battery Voltage (VDC)",
        "Number of Cells", "BatterySupplier", "SDS File", "SDS Link",
        "UN38.3 File", "UN38.3 Link",
    ])
    sheet.append([
        "SB10F46440", "00HW002", "L15M4P23", 51, 270, 4.03, 3.8, 15.2,
        4, "LG", "SDS", "https://lenovo.example/sds", "UN", "https://lenovo.example/un",
    ])
    sheet.append([
        "SB10F46441", "00HW003", "L15M4P24", 50, 266, 3.95, 3.8, 15.2,
        4, "Simplo", "SDS2", "https://lenovo.example/sds2", "UN2", "https://lenovo.example/un2",
    ])
    workbook.save(path)


def test_exact_official_match_and_missing_are_staged_not_applied():
    temp = SCRIPT.parent.parent / "docs" / "audits" / "generated" / f"test-lenovo-{uuid.uuid4().hex}"
    temp.mkdir(parents=True)
    candidates = temp / "candidates.csv"
    official = temp / "official.xlsx"
    output = temp / "output.csv"
    summary_path = temp / "summary.json"
    rows = [candidate("bitrix:1", "00HW002", "15.2", "51"), candidate("bitrix:2", "00HW999", "11.1", "45")]
    with candidates.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    create_workbook(official)
    digest = hashlib.sha256(official.read_bytes()).hexdigest()

    try:
        summary = MODULE.build(candidates, official, output, summary_path, 2, 2, 2, digest)
        assert summary["official_match_status_counts"] == {
            "not_found_official_registry": 1,
            "official_exact_unique": 1,
        }
        evidence = list(csv.DictReader(output.open(encoding="utf-8-sig")))
        by_id = {row["product_external_id"]: row for row in evidence}
        assert by_id["bitrix:1"]["voltage_comparison"] == "match"
        assert by_id["bitrix:1"]["energy_comparison"] == "match"
        assert by_id["bitrix:1"]["official_energy_wh"] == "51"
        assert by_id["bitrix:1"]["safe_to_apply"] == "false"
        assert by_id["bitrix:1"]["compatibility_verified"] == "false"
        assert by_id["bitrix:2"]["review_status"] == "hold"
        assert json.loads(summary_path.read_text(encoding="utf-8"))["published_fact_changes"] == 0
    finally:
        shutil.rmtree(temp)


def test_hash_and_count_guards_fail_closed():
    temp = SCRIPT.parent.parent / "docs" / "audits" / "generated" / f"test-lenovo-guard-{uuid.uuid4().hex}"
    temp.mkdir(parents=True)
    candidates = temp / "candidates.csv"
    official = temp / "official.xlsx"
    rows = [candidate("bitrix:1", "00HW002", "15.2", "51")]
    with candidates.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    create_workbook(official)
    digest = hashlib.sha256(official.read_bytes()).hexdigest()
    try:
        for expected_rows, expected_hash, message in [
            (3, digest, "official row count mismatch"),
            (2, "0" * 64, "SHA-256 mismatch"),
        ]:
            try:
                MODULE.build(
                    candidates, official, temp / "out.csv", temp / "summary.json",
                    1, 1, expected_rows, expected_hash,
                )
                assert False, "guard must block"
            except ValueError as error:
                assert message in str(error)
    finally:
        shutil.rmtree(temp)
