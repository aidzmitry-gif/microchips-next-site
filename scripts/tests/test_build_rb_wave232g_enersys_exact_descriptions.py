from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/build-rb-wave232g-enersys-exact-descriptions.py"
MANIFEST = ROOT / "docs/imports/rb-source-backed-descriptions-wave232g-2026-07-29.json"
SUMMARY = ROOT / "docs/audits/generated/rb-wave232g-enersys-exact-descriptions.summary.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_wave232g_is_deterministic_and_commercially_inert() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True)
    first = (digest(MANIFEST), digest(SUMMARY))
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True)
    assert first == (digest(MANIFEST), digest(SUMMARY))

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert [row["external_id"] for row in manifest["products"]] == ["bitrix:24582", "bitrix:26048"]
    assert [row["identity_scope"] for row in manifest["products"]] == ["exact", "model_core"]
    assert manifest["products"][0]["mpn"] == "0859-0016"
    assert manifest["products"][1]["model_core"] == "12V70"
    assert all(row["source_tier"] == "manufacturer_primary" for row in manifest["products"])
    prohibited = {"price", "availability", "stock", "warranty", "is_published", "url", "image"}
    assert all(prohibited.isdisjoint(row) for row in manifest["products"])
    assert summary["commercial_fields"] == summary["publication_fields"] == summary["media_fields"] == 0
