import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load(path: str):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_wave245a_builder_is_exact_fail_closed_and_deterministic():
    subprocess.run([sys.executable, str(ROOT / "scripts/build-rb-wave245a-panasonic-artifacts.py")], cwd=ROOT, check=True, capture_output=True)
    summary = load("docs/audits/generated/rb-wave245a-panasonic.summary.json")
    assert summary["scope"] == {"queue_rows": 2, "external_ids": ["bitrix:1569", "bitrix:1580"]}
    assert summary["prior_scan"]["files"] == 375
    assert summary["prior_scan"]["url_occurrences"] == 2654
    assert summary["prior_scan"]["sha256_occurrences"] == 1145
    assert summary["prior_scan"]["new_url_overlap"] == summary["prior_scan"]["new_sha256_overlap"] == 0
    assert summary["result"]["identity"] == {"PASS": 2}
    assert summary["result"]["description"] == {"PASS": 2}
    assert summary["result"]["media"] == {"HOLD_RIGHTS_NOT_ESTABLISHED": 2}
    assert summary["result"]["duplicate"] == {"PASS_NO_DUPLICATE_ACTION": 2}
    assert summary["database_operations"] == 0

    identities = load("docs/imports/rb-verified-oem-identities-wave245a-panasonic-2026-07-30.json")["products"]
    descriptions = load("docs/imports/rb-source-backed-descriptions-wave245a-panasonic-2026-07-30.json")["products"]
    assert [(r["external_id"], r["mpn"]) for r in identities] == [("bitrix:1569", "LC-XC1222P"), ("bitrix:1580", "LC-XC1228P")]
    assert all(r["source_kind"] == "official_manufacturer_catalogue" for r in identities + descriptions)
    assert [r["technical_attributes"]["Номинальная ёмкость (20 ч), А·ч"] for r in descriptions] == ["22.0", "28.0"]
    assert all(r["technology"] == "VRLA" for r in descriptions)

    exclusions = load("docs/audits/generated/rb-wave245a-prior-source-exclusions.json")
    prior_urls = {r["value"] for r in exclusions["source_urls"]}
    prior_hashes = {r["value"] for r in exclusions["snapshot_sha256"]}
    registry = load("docs/audits/sources/wave245a-panasonic/registry.json")["assets"]
    for asset in registry:
        path = ROOT / asset["local_path"]
        assert asset["source_url"] not in prior_urls
        assert asset["sha256"] not in prior_hashes
        assert hashlib.sha256(path.read_bytes()).hexdigest() == asset["sha256"]

    media = load("docs/audits/generated/rb-wave245a-panasonic-media-decisions.json")["candidates"]
    assert all(r["decision"] == "HOLD_RIGHTS_NOT_ESTABLISHED" and not r["promotion_allowed"] for r in media)
    assert all(r["width"] >= 177 and r["height"] == 205 for r in media)
    assert all(hashlib.sha256((ROOT / r["candidate_path"]).read_bytes()).hexdigest() == r["candidate_sha256"] for r in media)

    duplicates = load("docs/audits/generated/rb-wave245a-panasonic-duplicate-decisions.json")
    assert duplicates["collapse_manifest_created"] is False
    assert all(r["decision"] == "PASS_NO_DUPLICATE_ACTION" and r["one_c_owner_external_ids"] == [] for r in duplicates["decisions"])
    with (ROOT / "docs/audits/generated/rb-wave245a-panasonic-evidence-ledger.csv").open(encoding="utf-8-sig", newline="") as handle:
        assert len(list(csv.DictReader(handle))) == 2
