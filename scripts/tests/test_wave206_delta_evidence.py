from __future__ import annotations

import csv
import hashlib
import json
import runpy
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/build-rb-wave206-delta-evidence.py"
OUTPUT = ROOT / "docs/audits/generated/rb-delta-wave206-official-evidence.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-delta-wave206-official-evidence.summary.json"
NEW = ROOT / "docs/audits/generated/rb-delta-wave206-new-official-evidence.csv"
PRIOR = ROOT / "docs/audits/generated/rb-delta-wave198-official-evidence.csv"
ACQUIRE_SCRIPT = ROOT / "scripts/acquire-rb-delta-wave206-current-pages.py"


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_wave206_builder_is_deterministic_and_partitions_all_62_rows() -> None:
    subprocess.run([sys.executable, str(SCRIPT), "build"], cwd=ROOT, check=True, capture_output=True)
    first = digest(OUTPUT)
    subprocess.run([sys.executable, str(SCRIPT), "build"], cwd=ROOT, check=True, capture_output=True)
    assert digest(OUTPUT) == first

    evidence = rows(OUTPUT)
    assert len(evidence) == 62
    assert len({row["product_external_id"] for row in evidence}) == 62
    counts = {name: sum(row["partition"] == name for row in evidence) for name in ("exact_safe", "compatibility_only", "conflict", "no_evidence")}
    assert counts == {"exact_safe": 27, "compatibility_only": 0, "conflict": 19, "no_evidence": 16}
    assert sum(row["safe_to_apply"] == "true" for row in evidence) == 27


def test_every_exact_row_has_hash_verified_official_snapshot_and_exact_identity() -> None:
    for row in rows(OUTPUT):
        if row["partition"] != "exact_safe":
            continue
        snapshot = ROOT / row["snapshot_path"]
        assert snapshot.is_file()
        assert digest(snapshot) == row["snapshot_sha256"]
        assert row["source_url"].startswith("https://")
        assert "delta-batt.com" in row["source_url"]
        assert row["replacement_manufacturer"] == "Delta"
        assert row["replacement_mpn"] == row["legacy_model"]
        assert row["duplicate_review"] == "no_strict_duplicate"
        assert row["strict_duplicate_cluster"] == ""


def test_ct_scope_and_capacity_conflict_are_fail_closed() -> None:
    evidence = rows(OUTPUT)
    ct = [row for row in evidence if row["legacy_model"].upper().startswith("CT ")]
    assert len(ct) == 18
    assert all(row["partition"] == "conflict" and row["safe_to_apply"] == "false" for row in ct)
    assert len({row["snapshot_sha256"] for row in ct}) == 1
    for row in ct:
        snapshot = ROOT / row["snapshot_path"]
        assert digest(snapshot) == row["snapshot_sha256"]

    dtm_1215 = next(row for row in evidence if row["product_external_id"] == "bitrix:1520")
    assert dtm_1215["partition"] == "conflict"
    assert "15Ah" in dtm_1215["conflict_reason"]
    assert "14.5Ah" in dtm_1215["conflict_reason"]
    assert dtm_1215["replacement_mpn"] == ""


def test_new_evidence_does_not_repeat_wave198_models_and_summary_covers_full_registry() -> None:
    new_keys = {row["content_model_key"] for row in rows(NEW)}
    prior_keys = {row["content_model_key"] for row in rows(PRIOR)}
    assert len(new_keys) == 18
    assert new_keys.isdisjoint(prior_keys)

    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert summary["reused_evidence"]["matched_rows"] == 10
    assert summary["new_evidence"]["matched_rows"] == 18
    assert summary["full_registry"]["rows"] == 17207
    assert summary["strict_duplicates"] == {"clusters": 0, "rows": 0, "details": {}}
    assert summary["prior_wave200_204_overlap_rows"] == 0
    assert summary["policy"]["database_mutations"] == 0


def test_current_snapshots_reparse_to_the_recorded_exact_model_and_facts() -> None:
    module = runpy.run_path(str(ACQUIRE_SCRIPT))
    for row in rows(NEW):
        snapshot = ROOT / row["source_snapshot_path"]
        raw = snapshot.read_bytes()
        assert digest(snapshot) == row["source_sha256"]
        assert module["model_key"](module["page_model"](raw)) == row["content_model_key"]
        assert module["property_value"](raw, "Напряжение, В") == row["voltage_v"]
        assert module["property_value"](raw, "Емкость, Ач") == row["capacity_ah"]


def test_no_evidence_and_conflict_rows_never_infer_identity() -> None:
    for row in rows(OUTPUT):
        if row["partition"] in {"no_evidence", "conflict", "compatibility_only"}:
            assert row["safe_to_apply"] == "false"
            assert row["replacement_manufacturer"] == ""
            assert row["replacement_mpn"] == ""
            assert row["manufacturer_mpn_inference"] == "none"
