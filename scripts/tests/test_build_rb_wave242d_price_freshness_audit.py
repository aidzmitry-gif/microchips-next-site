from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/build-rb-wave242d-price-freshness-audit.py"
LEDGER = ROOT / "docs/audits/generated/rb-wave242d-price-freshness-ledger.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-wave242d-price-freshness.summary.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ledger_rows() -> list[dict[str, str]]:
    with LEDGER.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


@pytest.fixture(scope="module", autouse=True)
def build() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True, text=True)


def test_full_current_union_is_unique_and_source_backed() -> None:
    rows = ledger_rows()
    assert len(rows) == 1067
    assert len({row["product_external_id"] for row in rows}) == 1067
    assert len({row["source_reference"] for row in rows}) == 1067
    assert Counter(row["reconstruction_input"] for row in rows) == {
        "wave240_applied_manifest": 1065,
        "wave91_separate_exact_links": 2,
    }
    assert Counter(row["source"] for row in rows) == {"legacy_site": 1067}
    assert Counter(row["price_type"] for row in rows) == {
        "legacy_public_price_direct_bitrix": 1010,
        "legacy_public_price": 57,
    }


def test_freshness_and_commercial_policies_are_fail_closed() -> None:
    rows = ledger_rows()
    assert {row["observed_at"] for row in rows} == {"2026-06-23T00:00:00+03:00"}
    assert {row["age_days"] for row in rows} == {"36"}
    assert {row["age_bucket"] for row in rows} == {"31_60_stale_reconfirm"}
    assert {row["currency"] for row in rows} == {"BYN"}
    assert {row["availability_policy"] for row in rows} == {
        "ON_REQUEST_INDEPENDENT_OF_PRICE_DO_NOT_INFER_STOCK"
    }
    assert {row["offer_eligible"] for row in rows} == {"false"}


def test_receipt_integrity_and_safety_counters_are_zero() -> None:
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert summary["freshness"]["age_bucket_counts"] == {"31_60_stale_reconfirm": 1067}
    assert set(summary["integrity"].values()) == {0}
    assert summary["scope"]["receipt_current_numeric_prices"] == 1067
    assert summary["scope"]["receipt_published_numeric_prices"] == 1044
    assert set(summary["safety"].values()) == {0}
    assert summary["input_pins"]["scripts/audit-rb-price-truth.sql"] == (
        "3c294466b9d4f9ba0437ad1230e37213ad0ca4dc42d3e79bcb329edffdb82c36"
    )


def test_rebuild_is_deterministic() -> None:
    before = {path: sha256(path) for path in (LEDGER, SUMMARY)}
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True, text=True)
    after = {path: sha256(path) for path in (LEDGER, SUMMARY)}
    assert after == before
