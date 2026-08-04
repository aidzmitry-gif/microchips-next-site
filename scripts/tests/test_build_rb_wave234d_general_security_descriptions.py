from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/build-rb-wave234d-general-security-descriptions.py"
OUTPUT = ROOT / "docs/imports/rb-source-backed-descriptions-wave234d-general-security-2026-07-29.json"
SUMMARY = ROOT / "docs/audits/generated/rb-wave234d-general-security-descriptions.summary.json"


def test_wave234d_descriptions_are_exact_deterministic_and_noncommercial() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True)
    first = hashlib.sha256(OUTPUT.read_bytes()).hexdigest()
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True)
    assert first == hashlib.sha256(OUTPUT.read_bytes()).hexdigest()
    data = json.loads(OUTPUT.read_text(encoding="utf-8"))
    assert len(data["products"]) == 28
    assert len({row["external_id"] for row in data["products"]}) == 28
    assert all(row["identity_scope"] == "exact" and row["manufacturer_primary"] is True for row in data["products"])
    assert all(set(row["technical_attributes"]) == {"Номинальное напряжение", "Номинальная ёмкость", "Габариты", "Масса", "Технология"} for row in data["products"])
    forbidden = {"price", "availability", "warranty", "published", "media"}
    assert not any(forbidden.intersection(row) for row in data["products"])
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert summary["output"]["rows"] == 28
    assert summary["excluded_nonterminal_mpn_external_ids"] == ["bitrix:2849"]
    assert summary["policy"]["commercial_mutations"] == 0
