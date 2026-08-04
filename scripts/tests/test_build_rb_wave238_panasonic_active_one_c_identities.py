from __future__ import annotations

import csv
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/build-rb-wave238-panasonic-active-one-c-identities.py"
PDF = ROOT / "docs/audits/sources/panasonic-wave200/Introduction_coin_primary_lithium_EN.pdf"
MANIFEST = ROOT / "docs/imports/rb-verified-oem-identities-wave238-panasonic-active-1c-2026-07-29.json"
LEDGER = ROOT / "docs/audits/generated/rb-wave238-panasonic-active-one-c-identity-ledger.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-wave238-panasonic-active-one-c-identity.summary.json"
EXPECTED = {
    "КА-00003142": ("BR2032", 4),
    "ФР-00000639": ("CR2012", 3),
    "ФР-00001236": ("CR2450", 3),
}
EXPECTED_PDF_SHA256 = "1ce9b9fa72a6263f34cf2390726ddb009759c04303c1d3f39bc981473af5f343"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_builder() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True, text=True, encoding="utf-8")


def test_wave238_is_deterministic_and_exactly_bounded() -> None:
    run_builder()
    before = tuple(digest(path) for path in (MANIFEST, LEDGER, SUMMARY))
    run_builder()
    after = tuple(digest(path) for path in (MANIFEST, LEDGER, SUMMARY))
    assert before == after

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["target_kind"] == "active_1c"
    assert {item["external_id"]: item["mpn"] for item in manifest["products"]} == {
        external_id: mpn for external_id, (mpn, _page) in EXPECTED.items()
    }
    allowed_product_keys = {
        "external_id", "current_name", "manufacturer", "mpn", "source_url",
        "source_kind", "source_publisher", "checked_at", "product_type",
        "source_snapshot_path", "source_snapshot_sha256",
    }
    assert all(set(item) == allowed_product_keys for item in manifest["products"])
    assert all(item["source_kind"] == "official_manufacturer_catalogue" for item in manifest["products"])
    assert all(item["source_publisher"] == "Panasonic Energy Co., Ltd." for item in manifest["products"])

    assert digest(PDF) == EXPECTED_PDF_SHA256
    reader = PdfReader(str(PDF))
    ledger_by_id = {
        row["external_id"]: row
        for row in csv.DictReader(LEDGER.open(encoding="utf-8-sig", newline=""))
    }
    for item in manifest["products"]:
        evidence = ledger_by_id[item["external_id"]]
        text = reader.pages[int(evidence["source_page"]) - 1].extract_text() or ""
        pattern = re.compile(rf"(?<![A-Z0-9]){re.escape(item['mpn'])}(?![A-Z0-9])", re.I)
        assert len([line for line in text.splitlines() if pattern.search(line)]) == 1
        assert pattern.search(evidence["source_excerpt"])


def test_wave238_ledger_summary_and_offline_policy() -> None:
    run_builder()
    with LEDGER.open(encoding="utf-8-sig", newline="") as handle:
        ledger = list(csv.DictReader(handle))
    assert len(ledger) == 3
    assert {row["external_id"]: (row["mpn"], int(row["source_page"])) for row in ledger} == EXPECTED
    assert all(row["decision"] == "PASS" and row["safe_to_apply"] == "true" for row in ledger)

    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert summary["records"] == summary["pass_records"] == 3
    assert summary["hold_records"] == 0
    assert summary["policy"] == {"database_queries": 0, "network_requests": 0, "catalogue_mutations": 0}
    assert summary["manifest"]["sha256"] == digest(MANIFEST)
    assert summary["ledger"]["sha256"] == digest(LEDGER)

    source = SCRIPT.read_text(encoding="utf-8")
    assert "subprocess" not in source
    assert "import requests" not in source
    assert "from requests" not in source
    assert "docker" not in source.lower()
