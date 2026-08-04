from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/build-rb-wave237-fiamm-authorized-identities.py"
SUMMARY = ROOT / "docs/audits/generated/rb-wave237-fiamm-authorized-identity.summary.json"
MANIFEST = ROOT / "docs/imports/rb-verified-oem-identities-wave237-fiamm-2026-07-29.json"
WAVE233 = ROOT / "docs/audits/generated/rb-wave233-fiamm-identity-ledger.csv"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_wave237_reuses_reviewed_rows_and_emits_only_pinned_authorized_evidence() -> None:
    run = subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, capture_output=True, text=True)
    assert run.returncode == 0, run.stderr or run.stdout

    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    with WAVE233.open(encoding="utf-8-sig", newline="") as handle:
        reviewed_ids = {
            row["external_id"] for row in csv.DictReader(handle)
            if row["partition"] == "exact_local_text_unique"
        }

    assert summary["reviewed_candidates"] == 79
    assert summary["partition_counts"] == {
        "exact_authorized_catalogue_unique": 47,
        "hold_no_exact_authorized_catalogue": 32,
    }
    assert summary["database_mutations"] == 0
    assert summary["manifest"]["sha256"] == sha256(MANIFEST)
    assert len(manifest["products"]) == 47
    assert {row["external_id"] for row in manifest["products"]} <= reviewed_ids
    assert len({row["external_id"] for row in manifest["products"]}) == 47
    assert len({"".join(ch for ch in row["mpn"].upper() if ch.isalnum()) for row in manifest["products"]}) == 47

    for row in manifest["products"]:
        assert row["source_kind"] == "official_authorized_distributor_catalogue"
        assert row["source_publisher"] == "FIAMM Industrial RUS"
        assert urlparse(row["source_url"]).hostname == urlparse(row["authority_url"]).hostname
        source = (MANIFEST.parent / row["source_snapshot_path"]).resolve()
        authority = (MANIFEST.parent / row["authority_snapshot_path"]).resolve()
        assert source.is_file() and sha256(source) == row["source_snapshot_sha256"]
        assert authority.is_file() and sha256(authority) == row["authority_snapshot_sha256"]
        assert row["authority_statement"].casefold() in authority.read_text(
            encoding="utf-8", errors="replace"
        ).casefold()
