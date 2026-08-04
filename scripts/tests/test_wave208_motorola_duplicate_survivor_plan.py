from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/build-rb-wave208-motorola-duplicate-survivor-plan.py"
OUTPUT = ROOT / "docs/audits/generated/wave208-motorola-duplicate-survivor-plan.csv"
SUMMARY = ROOT / "docs/audits/generated/wave208-motorola-duplicate-survivor-plan-summary.json"
SNAPSHOT = ROOT / "docs/audits/generated/wave208-motorola-duplicate-db-snapshot.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows() -> list[dict[str, str]]:
    with OUTPUT.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_default_builder_replays_the_read_only_snapshot() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True, text=True)
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert summary["groups"] == 9
    assert summary["records"] == 21
    assert summary["inputs"]["db_snapshot_sha256"] == sha256(SNAPSHOT)
    assert summary["output"]["sha256"] == sha256(OUTPUT)
    assert summary["database_mutations"] == 0
    assert summary["automatic_collapses"] == 0


def test_scope_preserves_all_nine_wave207_groups() -> None:
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    groups = summary["group_decisions"]
    assert set(groups) == {
        "Motorola:HNN9008A", "Motorola:HNN9628A", "Motorola:NNTN4851",
        "Motorola:PMNN4251", "Motorola:HNN9008", "Motorola:HNN9628",
        "Motorola:HNN4002", "Motorola:PMNN4021", "Motorola:PMNN4077",
    }
    assert groups["Motorola:HNN9008A"]["members"] == ["bitrix:26135", "bitrix:26136", "bitrix:26137"]
    assert groups["Motorola:HNN9628A"]["members"] == ["bitrix:26139", "bitrix:26140", "bitrix:26141", "bitrix:26290"]
    assert summary["group_size_counts"] == {"2": 7, "3": 1, "4": 1}


def test_no_survivor_is_selected_without_verified_shared_identity() -> None:
    evidence = rows()
    assert len(evidence) == 21
    assert len({row["product_external_id"] for row in evidence}) == 21
    assert all(row["evidence_partition"] == "no_evidence" for row in evidence)
    assert all(row["group_decision"] == "hold_no_verified_shared_product_identity" for row in evidence)
    assert all(row["survivor_external_id"] == "" for row in evidence)
    assert all(row["safe_to_collapse"] == "false" for row in evidence)
    assert all("identity_unverified" in row["content_loss_flags"] for row in evidence)


def test_commercial_state_is_empty_but_legacy_claims_are_retained_for_review() -> None:
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert summary["current_price_records"] == 0
    assert summary["price_evidence_records"] == 0
    assert summary["in_stock_records"] == 0
    assert summary["offer_schema_records"] == 0
    assert summary["legacy_price_claim_records"] == 21
    assert summary["legacy_in_stock_claim_records"] == 21
    assert all(row["availability"] == "on_request" for row in rows())


def test_media_description_url_seo_redirect_and_one_c_dimensions_are_explicit() -> None:
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert summary["media_records"] == 0
    assert summary["verified_media_records"] == 0
    assert summary["description_records"] == 21
    assert summary["applied_description_records"] == 21
    assert summary["site_url_records"] == 21
    assert summary["seo_records"] == 21
    assert summary["indexable_seo_records"] == 0
    assert summary["legacy_redirect_records"] == 0
    assert summary["one_c_link_records"] == 0
    assert all(int(row["site_url_count"]) == 1 and int(row["seo_count"]) == 1 for row in rows())


def test_every_group_requires_content_merge_and_recheck_before_collapse() -> None:
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert summary["safe_survivor_groups"] == 0
    assert summary["held_groups"] == 9
    for group in summary["group_decisions"].values():
        assert group["safe_to_collapse"] is False
        assert group["survivor_external_id"] == ""
        assert "compatibility_or_title_content_differs" in group["loss_flags"]
        assert "descriptions_require_merge_review" in group["loss_flags"]
