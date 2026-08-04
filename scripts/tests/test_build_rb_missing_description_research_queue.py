from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "build-rb-missing-description-research-queue.py"


def write_input(path: Path) -> str:
    rows = [
        {
            "product_external_id": "bitrix:1",
            "name": "Аккумулятор для Datalogic Falcon X4 (BT-26) 5200mAh",
            "category_external_id": "seo:batteries-industrial",
            "manufacturer": "",
            "has_displayable_preview_image": "false",
            "readiness_class": "thin_unidentified",
        },
        {
            "product_external_id": "bitrix:2",
            "name": "Аккумулятор Robiton 18650 2600mAh",
            "category_external_id": "seo:rechargeable-cells",
            "manufacturer": "",
            "has_displayable_preview_image": "true",
            "readiness_class": "legacy_preview_only",
        },
        {
            "product_external_id": "bitrix:3",
            "name": "Аккумулятор CameronSino для Nikon MB-D12",
            "category_external_id": "seo:replacement-photo",
            "manufacturer": "",
            "has_displayable_preview_image": "true",
            "readiness_class": "legacy_preview_only",
        },
        {
            "product_external_id": "bitrix:4",
            "name": "Аккумулятор для Huawei MatePad 11",
            "category_external_id": "seo:replacement-mobile",
            "manufacturer": "",
            "has_displayable_preview_image": "true",
            "readiness_class": "legacy_preview_only",
        },
        {
            "product_external_id": "bitrix:5",
            "name": "Already described",
            "category_external_id": "seo:replacement-mobile",
            "manufacturer": "",
            "has_displayable_preview_image": "true",
            "readiness_class": "legacy_content_preview",
        },
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_builds_fail_closed_priority_queue(tmp_path: Path) -> None:
    source = tmp_path / "source.csv"
    output = tmp_path / "queue.csv"
    summary = tmp_path / "summary.json"
    digest = write_input(source)
    result = subprocess.run([
        sys.executable, str(SCRIPT), "--input", str(source), "--output", str(output),
        "--summary", str(summary), "--expected-records", "5", "--expected-missing", "4",
        "--expected-sha256", digest,
    ], check=False, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    rows = list(csv.DictReader(output.open(encoding="utf-8-sig", newline="")))
    assert [row["product_external_id"] for row in rows] == ["bitrix:1", "bitrix:2", "bitrix:3", "bitrix:4"]
    assert rows[0]["brand_candidate_unverified"] == "Datalogic"
    assert "BT-26" in rows[0]["model_candidates_unverified"]
    assert rows[2]["brand_candidate_unverified"] == "CameronSino"
    assert rows[2]["source_route"] == "replacement_brand_exact_model_catalog"
    assert rows[3]["brand_candidate_unverified"] == "Huawei"
    assert rows[3]["source_route"] == "device_oem_parts_or_service_document"
    assert all(row["safe_to_apply"] == "false" for row in rows)
    assert json.loads(summary.read_text(encoding="utf-8"))["automatic_database_mutations"] == 0


def test_rejects_hash_drift(tmp_path: Path) -> None:
    source = tmp_path / "source.csv"
    write_input(source)
    result = subprocess.run([
        sys.executable, str(SCRIPT), "--input", str(source), "--output", str(tmp_path / "queue.csv"),
        "--summary", str(tmp_path / "summary.json"), "--expected-records", "5",
        "--expected-missing", "4", "--expected-sha256", "0" * 64,
    ], check=False, capture_output=True, text=True)
    assert result.returncode != 0
    assert "SHA-256" in result.stderr
