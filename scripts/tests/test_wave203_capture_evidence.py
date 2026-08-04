from __future__ import annotations

import csv
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).parents[2]
SCRIPT = ROOT / "scripts/build-rb-wave203-capture-evidence.py"
INPUT = ROOT / "docs/audits/generated/wave203-industrial-unassigned-preparation.csv"
OUTPUT = ROOT / "docs/audits/generated/wave203-capture-evidence.csv"
SUMMARY = ROOT / "docs/audits/generated/wave203-capture-evidence-summary.json"
PRIOR = ROOT / "docs/imports/rb-source-backed-description-drafts-b2b-terminals-wave174-2026-07-29.json"

EXPECTED_BRANDS = {
    "Bluebird": 6,
    "Casio": 11,
    "CipherLab": 13,
    "Denso": 2,
    "Handheld": 3,
    "LXE": 10,
    "M3 Mobile": 5,
    "Opticon": 11,
    "Psion": 4,
    "TEKLOGIX": 3,
    "Unitech": 6,
}
OFFICIAL_HOSTS = {
    "www.casio-solutions.com",
    "support.casio.jp",
    "www.cipherlab.com",
    "www.denso-wave.com",
    "www.handheldgroup.com",
    "m3mobile.net",
    "www.m3mobile.net",
    "www.opticon.com",
    "www.ute.com",
}


def read_rows() -> list[dict[str, str]]:
    return list(csv.DictReader(OUTPUT.open(encoding="utf-8-sig", newline="")))


def test_builder_reproduces_complete_non_repeated_partition() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True, text=True)
    rows = read_rows()
    assert len(rows) == 74
    assert len({row["product_external_id"] for row in rows}) == 74
    assert Counter(row["brand_or_series"] for row in rows) == Counter(EXPECTED_BRANDS)
    prior_ids = {row["external_id"] for row in json.loads(PRIOR.read_text(encoding="utf-8-sig"))["products"]}
    assert not ({row["product_external_id"] for row in rows} & prior_ids)


def test_fail_closed_identity_and_primary_source_policy() -> None:
    rows = read_rows()
    assert {row["partition"] for row in rows} <= {"compatibility_only", "conflict", "no_evidence"}
    assert all(row["safe_to_apply"] == "false" for row in rows)
    assert all(not row["replacement_manufacturer"] and not row["replacement_mpn"] for row in rows)
    for row in rows:
        for url in filter(None, row["source_urls"].split("|")):
            parsed = urlparse(url)
            assert parsed.scheme == "https"
            assert parsed.hostname in OFFICIAL_HOSTS
        if row["partition"] == "compatibility_only":
            assert row["source_tier"] == "manufacturer_primary"
            assert row["source_urls"]
            assert "offered_pack" in row["unsupported_legacy_claims"]


def test_known_conflicts_and_summary_are_pinned() -> None:
    rows = {row["product_external_id"]: row for row in read_rows()}
    expected_conflicts = {
        "bitrix:12248",  # official NX8-1004 is 5200mAh, legacy claims 6800mAh
        "bitrix:12310",  # official SM20 standard is 4100mAh, legacy claims 4200mAh
        "bitrix:12311",  # official M3 SMART standard is 2200mAh, legacy claims 2000mAh
        "bitrix:12334",  # official H-27 is 2860mAh, legacy claims 3000mAh
        "bitrix:12340",  # official PX-35 pack is BTR0400, legacy uses another code
        "bitrix:12341",  # BTR0100 is officially tied to Opticon H-13, not PX001
        "bitrix:24019",  # BTR0100 is assigned to Denso without Denso pack evidence
    }
    assert all(rows[external_id]["partition"] == "conflict" for external_id in expected_conflicts)
    assert rows["bitrix:12179"]["partition"] == rows["bitrix:24023"]["partition"] == "conflict"
    assert rows["bitrix:12355"]["partition"] == rows["bitrix:24024"]["partition"] == "conflict"
    data = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert data["input"]["candidate_rows"] == data["output"]["rows"] == 74
    assert data["brand_counts"] == EXPECTED_BRANDS
    assert data["exact_safe_records"] == 0
    assert data["safe_to_apply_records"] == 0
    assert data["previously_processed_records"] == 0
    assert data["automatic_database_mutations"] == 0
