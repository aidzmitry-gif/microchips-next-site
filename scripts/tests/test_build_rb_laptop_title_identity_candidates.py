import csv
import importlib.util
import json
import shutil
import sys
import uuid
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "build-rb-laptop-title-identity-candidates.py"
SPEC = importlib.util.spec_from_file_location("rb_laptop_title_identity", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def row(external_id: str, name: str, **overrides: str) -> dict[str, str]:
    value = {
        "product_external_id": external_id,
        "name": name,
        "category_external_id": "seo:replacement-laptops",
        "readiness_class": "thin_unidentified",
        "is_published": "true",
    }
    value.update(overrides)
    return value


def test_title_parser_keeps_only_explicit_candidates():
    name = (
        "Аккумулятор (батарея) 02P9KD, T0FWM для ноутбука Dell Alienware 13, "
        "14.4B, 51Vтч, 4400mAh (оригинал)"
    )
    assert MODULE.extract_part_numbers(name) == ["02P9KD", "T0FWM"]
    assert MODULE.detect_brand(name) == "Dell"
    assert MODULE.extract_title_facts(name) == {
        "voltage_v_candidates": "14.4",
        "capacity_mah_candidates": "4400",
        "energy_wh_candidates": "51",
        "quality_marker": "original",
    }


def test_same_part_number_with_different_facts_is_held():
    temp = SCRIPT.parent.parent / "docs" / "audits" / "generated" / f"test-laptop-{uuid.uuid4().hex}"
    temp.mkdir(parents=True)
    source = temp / "source.csv"
    output = temp / "candidates.csv"
    summary_path = temp / "summary.json"
    rows = [
        row("bitrix:1", "Аккумулятор (батарея) 04YRJH для ноутбука Dell N5110, 11.1V, 5200mAh (OEM)"),
        row("bitrix:2", "Аккумулятор (батарея) 04YRJH для ноутбука Dell N5110, 4400mAh (Low Cost OEM)"),
        row("bitrix:3", "Аккумулятор для ноутбука без артикула Lenovo Yoga"),
    ]
    with source.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    try:
        summary = MODULE.build(source, output, summary_path, 3, 3)
        assert summary["automatic_database_mutations"] == 0
        assert summary["variant_or_fact_conflict_groups"] == 1
        assert summary["records_without_part_number_candidate"] == 1
        candidates = list(csv.DictReader(output.open(encoding="utf-8-sig")))
        risks = {item["product_external_id"]: item["identity_risk"] for item in candidates}
        assert risks == {
            "bitrix:1": "variant_or_fact_conflict_hold",
            "bitrix:2": "variant_or_fact_conflict_hold",
            "bitrix:3": "missing_part_number",
        }
        assert all(item["safe_to_apply"] == "false" for item in candidates)
        assert json.loads(summary_path.read_text(encoding="utf-8"))["duplicate_merges"] == 0
    finally:
        shutil.rmtree(temp)


def test_count_and_duplicate_guards_fail_closed():
    tmp_path = SCRIPT.parent.parent / "docs" / "audits" / "generated" / f"test-laptop-guard-{uuid.uuid4().hex}"
    tmp_path.mkdir(parents=True)
    source = tmp_path / "source.csv"
    rows = [row("bitrix:1", "Аккумулятор (батарея) A32-K55 для ноутбука ASUS K55")]
    with source.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    try:
        try:
            MODULE.build(source, tmp_path / "out.csv", tmp_path / "summary.json", 2, 1)
            assert False, "input count mismatch must block"
        except ValueError as error:
            assert "input record count mismatch" in str(error)

        rows.append(rows[0].copy())
        with source.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        try:
            MODULE.build(source, tmp_path / "out.csv", tmp_path / "summary.json", 2, 2)
            assert False, "duplicate external IDs must block"
        except ValueError as error:
            assert "duplicate product_external_id" in str(error)
    finally:
        shutil.rmtree(tmp_path)
