from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "docs/audits/generated/rb-wave209a-official-evidence.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-wave209a-official-evidence.summary.json"
MANIFEST = ROOT / "docs/imports/rb-verified-oem-identities-wave209a-2026-07-29.json"
LIVE_GUARD = ROOT / "docs/audits/generated/wave209a-live-identity-collisions.json"
DRY_RUN = ROOT / "docs/audits/generated/wave209a-laravel-dry-run.json"


def rows() -> list[dict[str, str]]:
    with EVIDENCE.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_bounded_scope_and_fail_closed_partitions() -> None:
    evidence = rows()
    assert len(evidence) == 163
    assert Counter(row["manufacturer_cluster"] for row in evidence) == {"APC": 77, "EnerSys": 42, "Sonnenschein": 44}
    assert Counter(row["partition"] for row in evidence) == {"conflict": 57, "exact_safe": 70, "no_evidence": 35, "compatibility": 1}
    assert all(row["safe_to_apply"] == "false" for row in evidence if row["partition"] != "exact_safe")


def test_safe_manifest_is_exact_subset_with_pinned_primary_snapshots() -> None:
    evidence = rows()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))["products"]
    assert {row["external_id"] for row in manifest} == {row["product_external_id"] for row in evidence if row["safe_to_apply"] == "true"}
    assert len(manifest) == 70
    for row in manifest:
        assert row["source_kind"] in {"official_manufacturer_product_page", "official_manufacturer_catalogue"}
        assert urlparse(row["source_url"]).hostname in {"www.se.com", "www.enersys.com", "www.exidegroup.com"}
        snapshot = (MANIFEST.parent / row["source_snapshot_path"]).resolve()
        assert snapshot.is_file()
        assert hashlib.sha256(snapshot.read_bytes()).hexdigest() == row["source_snapshot_sha256"]


def test_full_registry_live_and_laravel_contracts_are_complete() -> None:
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    live = json.loads(LIVE_GUARD.read_text(encoding="utf-8"))
    dry = json.loads(DRY_RUN.read_text(encoding="utf-8"))
    assert summary["canonical_registry"]["records"] == 17207
    assert live["query_exit_code"] == 0
    assert live["candidate_rows_checked"] == 76
    assert len(live["collisions"]) == 6
    assert dry["mode"] == "dry_run" and dry["exit_code"] == 0 and dry["database_mutations"] == 0
    assert dry["records"] == 70
    assert dry["manifest_sha256"] == hashlib.sha256(MANIFEST.read_bytes()).hexdigest()
    assert summary["manifest"]["laravel_dry_run_verified"] is True


def test_wave199_apc_identity_overlap_and_matcher_holds_are_explicit() -> None:
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert summary["apc_wave199_overlap"] == {
        "pinned_candidate_rows": 77,
        "wave209a_rows": 77,
        "exact_external_id_name_model_match": True,
    }
    assert summary["laravel_matcher_holds"]["external_ids"] == ["bitrix:23785", "bitrix:23786", "bitrix:23821"]
    assert summary["policy"]["database_mutations"] == 0
