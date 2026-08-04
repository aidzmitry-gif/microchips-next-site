import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_BUILDER = ROOT / "scripts/build-rb-wave206-fiamm-bb-csb-evidence.py"
BUILDER = ROOT / "scripts/build-rb-wave206-bb-verified-oem-identities.py"
EVIDENCE = ROOT / "docs/audits/generated/rb-wave206-fiamm-bb-csb-evidence.csv"
MANIFEST = ROOT / "docs/imports/rb-verified-oem-identities-wave206-bb-2026-07-29.json"
SUMMARY = ROOT / "docs/audits/generated/rb-verified-oem-identities-wave206-bb.summary.json"
EXPECTED_IDS = ["bitrix:1519", "bitrix:1526", "bitrix:1565", "bitrix:1587", "bitrix:1593"]


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    subprocess.run([sys.executable, str(EVIDENCE_BUILDER)], cwd=ROOT, check=True)
    subprocess.run([sys.executable, str(BUILDER)], cwd=ROOT, check=True)
    return json.loads(MANIFEST.read_text(encoding="utf-8")), json.loads(SUMMARY.read_text(encoding="utf-8"))


def test_manifest_contains_exactly_the_five_safe_output_rows():
    manifest, summary = build()
    with EVIDENCE.open(encoding="utf-8", newline="") as handle:
        evidence = list(csv.DictReader(handle))
    safe_ids = [row["product_external_id"] for row in evidence if row["safe_to_apply"] == "true"]
    manifest_ids = [row["external_id"] for row in manifest["products"]]
    assert safe_ids == manifest_ids == EXPECTED_IDS
    assert summary["external_ids"] == manifest_ids
    assert summary["manifest"] == {
        "path": "docs/imports/rb-verified-oem-identities-wave206-bb-2026-07-29.json",
        "sha256": sha256(MANIFEST),
        "rows": 5,
    }
    assert "bitrix:1590" not in manifest_ids


def test_rows_match_laravel_contract_and_pinned_snapshots():
    manifest, _ = build()
    assert manifest["schema_version"] == 1
    assert manifest["site_key"] == "microchips-by"
    normalized_mpns = set()
    for row in manifest["products"]:
        assert set(row) == {
            "external_id", "current_name", "manufacturer", "mpn", "source_url",
            "source_kind", "source_publisher", "checked_at", "product_type",
            "source_snapshot_path", "source_snapshot_sha256",
        }
        assert row["source_kind"] == "official_manufacturer_catalogue"
        assert row["source_url"].startswith("https://www.bb-bat.com/")
        assert not Path(row["source_snapshot_path"]).is_absolute()
        snapshot = (MANIFEST.parent / row["source_snapshot_path"]).resolve()
        assert snapshot.is_file()
        assert sha256(snapshot) == row["source_snapshot_sha256"]
        normalized = "".join(character.casefold() for character in row["mpn"] if character.isalnum())
        assert normalized not in normalized_mpns
        normalized_mpns.add(normalized)


def test_current_names_are_exactly_pinned_to_wave205_input():
    manifest, _ = build()
    with (ROOT / "docs/audits/generated/rb-b2b-next-source-batch-wave205.csv").open(encoding="utf-8-sig", newline="") as handle:
        input_rows = {row["product_external_id"]: row for row in csv.DictReader(handle)}
    assert all(row["current_name"] == input_rows[row["external_id"]]["name"] for row in manifest["products"])
