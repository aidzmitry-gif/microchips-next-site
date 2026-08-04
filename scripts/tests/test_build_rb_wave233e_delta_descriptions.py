from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/build-rb-wave233e-delta-descriptions.py"
MANIFEST = ROOT / "docs/imports/rb-source-backed-descriptions-wave233e-delta-2026-07-29.json"
SUMMARY = ROOT / "docs/audits/generated/rb-wave233e-delta-descriptions.summary.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_wave233e_builds_16_exact_noncommercial_delta_descriptions() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True)
    first = (sha256(MANIFEST), sha256(SUMMARY))
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True)
    assert first == (sha256(MANIFEST), sha256(SUMMARY))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    rows = manifest["products"]
    assert len(rows) == len({row["external_id"] for row in rows}) == 16
    assert len({"".join(char for char in row["mpn"].upper() if char.isalnum()) for row in rows}) == 16
    assert all(row["manufacturer"] == "Delta" and row["identity_scope"] == "exact" for row in rows)
    assert all(row["manufacturer_primary"] is True and row["source_kind"] == "official_manufacturer_product_page" for row in rows)
    assert all({"Номинальное напряжение", "Номинальная ёмкость", "Технология"} <= set(row["technical_attributes"]) for row in rows)
    assert all(not ({"price", "availability", "stock", "warranty"} & set(row)) for row in rows)
    assert summary["rows"] == 16
    assert summary["commercial_fields"] == summary["publication_fields"] == summary["media_fields"] == 0
