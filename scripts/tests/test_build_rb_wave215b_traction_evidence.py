from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/build-rb-wave215b-traction-evidence.py"
EVIDENCE = ROOT / "docs/audits/generated/rb-wave215b-traction-evidence.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-wave215b-traction-evidence.summary.json"
SOURCES = ROOT / "docs/audits/sources/wave215b-traction/source-registry.json"
MANIFEST = ROOT / "docs/imports/rb-verified-oem-identities-wave215b-traction-2026-07-29.json"
LIVE = ROOT / "docs/audits/generated/wave215b-traction-live-identity-collisions.json"
DRY = ROOT / "docs/audits/generated/wave215b-traction-laravel-dry-run.json"


def rows() -> list[dict[str, str]]:
    with EVIDENCE.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_wave215b_is_exact_target_and_deterministic() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True)
    before = (hashlib.sha256(EVIDENCE.read_bytes()).hexdigest(), hashlib.sha256(MANIFEST.read_bytes()).hexdigest())
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True)
    assert before == (hashlib.sha256(EVIDENCE.read_bytes()).hexdigest(), hashlib.sha256(MANIFEST.read_bytes()).hexdigest())
    assert Counter(row["manufacturer_cluster"] for row in rows()) == {"Minamoto": 5, "Sonnenschein": 15, "Yuasa": 2, "unresolved_other": 78, "unresolved_replacement": 15}
    assert len(rows()) == 115


def test_exact_safe_manifest_source_and_classification_guards() -> None:
    source = json.loads(SOURCES.read_text(encoding="utf-8"))["sources"][0]
    assert urlparse(source["source_url"]).scheme == "https"
    snapshot = ROOT / source["snapshot_path"]
    assert hashlib.sha256(snapshot.read_bytes()).hexdigest() == source["snapshot_sha256"]
    data = rows()
    assert Counter(row["partition"] for row in data) == {"exact_safe": 2, "hold_compatibility_context": 15, "hold_no_exact_primary_source": 98}
    assert all(row["product_class"] == "actual_battery" for row in data)
    assert all(row["safe_to_apply"] == "false" for row in data if row["partition"] != "exact_safe")
    assert {row["product_external_id"] for row in data if row["safe_to_apply"] == "true"} == {"bitrix:24373", "bitrix:24374"}
    assert {row["external_id"] for row in json.loads(MANIFEST.read_text(encoding="utf-8"))["products"]} == {"bitrix:24373", "bitrix:24374"}


def test_registry_live_scope_and_laravel_dry_run_guards() -> None:
    summary, live, dry = (json.loads(path.read_text(encoding="utf-8")) for path in (SUMMARY, LIVE, DRY))
    assert summary["scope_exclusion"] == {"automotive_starter_rows": 0, "electronic_component_rows": 0}
    assert summary["product_classification"] == {"actual_battery": 115, "accessory_or_device_only": 0, "compatibility_context_hold": 15}
    assert live["mode"] == "read_only" and live["database_mutations"] == 0 and live["collisions"] == []
    assert dry["mode"] == "dry_run" and dry["exit_code"] == 0 and dry["records"] == 2
    assert dry["manifest_sha256"] == hashlib.sha256(MANIFEST.read_bytes()).hexdigest()
    assert dry["commercial_fields_changed"] == dry["publication_fields_changed"] == dry["post_run_rows_with_manufacturer_or_mpn"] == dry["database_mutations"] == 0
