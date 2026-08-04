from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/build-rb-wave244b-fiamm-duplicate-collapse.py"
SOURCE_DIR = ROOT / "docs/audits/sources/wave244b-fiamm-duplicates"
EVIDENCE = ROOT / "docs/audits/generated/rb-wave244b-fiamm-duplicate-collapse-evidence.csv"
MANIFEST = ROOT / "docs/imports/rb-reviewed-fiamm-duplicates-wave244b-2026-07-30.json"
SUMMARY = ROOT / "docs/audits/generated/rb-wave244b-fiamm-duplicate-collapse.summary.json"


def load_module():
    spec = importlib.util.spec_from_file_location("wave244b_fiamm_duplicates", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_new_official_snapshot_has_two_exact_bounded_rows() -> None:
    module = load_module()
    acquisition = json.loads((SOURCE_DIR / "acquisition.json").read_text(encoding="utf-8"))
    snapshot = ROOT / acquisition["snapshot_path"]
    assert hashlib.sha256(snapshot.read_bytes()).hexdigest() == acquisition["snapshot_sha256"]
    rows = module.exact_rows(snapshot)
    assert rows["FG21202"] == {
        "model": "FG21202", "voltage": "12", "capacity": "12",
        "row": "FG21202* 12 10,8 12 151 98 93 98 3.7 Faston 6.3",
        "remainder": "151 98 93 98 3.7 Faston 6.3",
    }
    assert rows["FG21803"]["voltage"] == "12"
    assert rows["FG21803"]["capacity"] == "18"
    assert rows["FG21803"]["remainder"].endswith("Flag Ø5.5")


def test_live_safety_snapshot_and_manifest_are_exact_and_fail_closed() -> None:
    module = load_module()
    live_rows = json.loads((SOURCE_DIR / "live-db-safety-snapshot.json").read_text(encoding="utf-8"))["products"]
    live = {row["external_id"]: row for row in live_rows}
    assert set(live) == {"bitrix:1488", "bitrix:1542", "ФР-00001439", "ФР-00001513"}
    assert module.safety_reasons(live["bitrix:1488"], duplicate=True) == []
    assert module.safety_reasons(live["bitrix:1542"], duplicate=True) == []
    assert module.safety_reasons(live["ФР-00001439"], duplicate=False) == []
    assert module.safety_reasons(live["ФР-00001513"], duplicate=False) == []

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert [(row["duplicate_external_id"], row["survivor_external_id"]) for row in manifest["duplicates"]] == [
        ("bitrix:1488", "ФР-00001439"),
        ("bitrix:1542", "ФР-00001513"),
    ]
    assert all(row["source_snapshot_sha256"] == "544817b47e43ac6edad1d9b5e17235284de6fa65cf13f650cf37508e6fc3a9bc" for row in manifest["duplicates"])


def test_evidence_and_manifest_hashes_are_pinned() -> None:
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert summary["result"] == {"PASS": 2, "HOLD": 0, "manifest_rows": 2}
    assert summary["source"]["prior_url_collisions"] == 0
    assert summary["source"]["prior_sha_collisions"] == 0
    assert hashlib.sha256(EVIDENCE.read_bytes()).hexdigest() == summary["evidence"]["sha256"]
    assert hashlib.sha256(MANIFEST.read_bytes()).hexdigest() == summary["manifest"]["sha256"]
    with EVIDENCE.open(encoding="utf-8-sig", newline="") as stream:
        evidence = list(csv.DictReader(stream))
    assert len(evidence) == 2
    assert all(row["decision"] == "PASS" and row["hold_reason"] == "" for row in evidence)


def test_prior_source_exclusion_ledgers_do_not_count_as_source_reuse() -> None:
    module = load_module()
    acquisition = json.loads((SOURCE_DIR / "acquisition.json").read_text(encoding="utf-8"))

    # Prior-source exclusion files are generated inventories used to prevent later
    # acquisition attempts. They are not evidence that this source was already
    # used to make a product decision, so they must not block the reviewed wave.
    module.assert_no_repeat(acquisition["source_url"], acquisition["snapshot_sha256"])


def test_safety_policy_rejects_commercial_duplicate() -> None:
    module = load_module()
    row = {
        "missing": False, "status": "draft", "site_product_count": 1,
        "is_published": True, "availability": "on_request", "price": "1.00",
        "price_evidence_total": 1, "current_price_evidence": [], "verified_media": 0,
        "family_roles": 0, "urls": [{"path": "/legacy", "is_indexable": False}],
        "seos": [{"is_indexable": False, "schema": None}], "categories": ["seo:batteries-ups"],
    }
    assert module.safety_reasons(row, duplicate=True) == ["duplicate_has_commercial_price"]
