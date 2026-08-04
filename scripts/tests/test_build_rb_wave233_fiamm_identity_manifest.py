from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BUILDER = ROOT / "scripts/build-rb-wave233-fiamm-identity-manifest.py"
AUDIT = ROOT / "scripts/audit-rb-wave233-fiamm-identities.py"
LEDGER = ROOT / "docs/audits/generated/rb-wave233-fiamm-identity-ledger.csv"
LIVE = ROOT / "docs/audits/generated/rb-wave233-fiamm-live-identity-collisions.json"
SUMMARY = ROOT / "docs/audits/generated/rb-wave233-fiamm-identity.summary.json"
MANIFEST = ROOT / "docs/imports/rb-fiamm-identity-candidates-wave233-2026-07-29.json"


def rows() -> list[dict[str, str]]:
    with LEDGER.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_wave233_fiamm_builder_is_deterministic_and_exact_scope() -> None:
    subprocess.run([sys.executable, str(BUILDER)], cwd=ROOT, check=True, capture_output=True)
    before = tuple(hashlib.sha256(path.read_bytes()).hexdigest() for path in (LEDGER, LIVE, MANIFEST, SUMMARY))
    subprocess.run([sys.executable, str(BUILDER)], cwd=ROOT, check=True, capture_output=True)
    after = tuple(hashlib.sha256(path.read_bytes()).hexdigest() for path in (LEDGER, LIVE, MANIFEST, SUMMARY))
    assert before == after
    data = rows()
    assert len(data) == 106
    assert len({row["external_id"] for row in data}) == len({row["title_mpn"] for row in data}) == 106


def test_wave233_fiamm_evidence_and_review_only_policy() -> None:
    data = rows()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    live = json.loads(LIVE.read_text(encoding="utf-8"))
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert live["mode"] == "read_only" and live["database_mutations"] == 0 and live["candidate_rows_checked"] == 106
    assert summary["policy"]["network_fetches"] == summary["policy"]["database_mutations"] == summary["policy"]["media_promotions"] == 0
    assert manifest["purpose"].startswith("review-only") and summary["manifest"]["review_only"]
    safe_ids = {row["external_id"] for row in data if row["safe_to_apply"] == "true"}
    assert safe_ids == {row["external_id"] for row in manifest["products"]}
    assert all(row["local_exact_text"] == "true" and not row["normalized_mpn_sku_conflict_ids"] for row in data if row["safe_to_apply"] == "true")
    assert sum(Counter(row["partition"] for row in data).values()) == 106


def test_wave233_fiamm_audit_passes() -> None:
    completed = subprocess.run([sys.executable, str(AUDIT)], cwd=ROOT, check=True, capture_output=True, text=True)
    assert '"audit": "ok"' in completed.stdout
