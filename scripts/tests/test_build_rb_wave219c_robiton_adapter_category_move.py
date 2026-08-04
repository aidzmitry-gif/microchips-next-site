import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GEN = ROOT / "docs/audits/generated"
CANDIDATES = GEN / "rb-wave219c-robiton-adapter-category-move-candidates.csv"
SUMMARY = GEN / "rb-wave219c-robiton-adapter-category-move.summary.json"
DRY = GEN / "wave219c-robiton-adapter-category-move-laravel-dry-run.json"
MANIFEST = ROOT / "docs/imports/rb-site-category-move-wave219c-robiton-adapter.csv"


def rows(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_wave219c_manifest_is_one_strict_explicit_robiton_move():
    manifest = rows(MANIFEST)
    candidates = rows(CANDIDATES)
    assert list(manifest[0]) == ["product_external_id", "from_category_external_id", "to_category_external_id"]
    assert manifest == [{"product_external_id": "КА-00002676", "from_category_external_id": "seo:chargers", "to_category_external_id": "seo:power-supplies"}]
    assert len(candidates) == 1 and candidates[0]["product_external_id"] == "КА-00002676"
    assert "ФР-00001523" not in {row["product_external_id"] for row in candidates}


def test_wave219c_dry_run_rolled_back_and_preserved_phoenix_identity():
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    dry = json.loads(DRY.read_text(encoding="utf-8"))
    assert dry["mode"] == "dry_run" and dry["apply_flag_used"] is False and dry["exit_code"] == 0
    assert dry["records"] == 1 and dry["validation_error_count"] == 0
    assert dry["manifest_sha256"] == hashlib.sha256(MANIFEST.read_bytes()).hexdigest()
    assert all(dry[key] == 0 for key in ["category_link_mutations", "url_mutations", "canonical_mutations", "publication_fields_changed", "identity_fields_changed"])
    assert summary["laravel_dry_run"]["rolled_back_live_state"] is True
    assert summary["explicit_exclusion"] == {
        "external_id": "ФР-00001523",
        "reason": "category_already_correct_and_live_identity_correct",
        "live_state": {"external_id": "ФР-00001523", "manufacturer": "Phoenix Contact", "mpn": "2938646", "category_external_ids": ["seo:power-supplies"]},
    }
    assert summary["policy"] == {"single_explicit_category_move": True, "identity_updates": False, "database_apply": False, "deterministic_local_render": True}
