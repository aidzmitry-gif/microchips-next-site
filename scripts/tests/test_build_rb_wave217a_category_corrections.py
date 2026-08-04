import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GEN = ROOT / "docs/audits/generated"
CANDIDATES = GEN / "rb-wave217a-category-correction-candidates.csv"
SUMMARY = GEN / "rb-wave217a-category-correction.summary.json"
DRY = GEN / "wave217a-category-correction-laravel-dry-run.json"
MANIFEST = ROOT / "docs/imports/rb-site-category-move-wave217a-obvious-product-type.csv"

def rows(path):
    with path.open(encoding="utf-8-sig", newline="") as handle: return list(csv.DictReader(handle))

def test_wave217a_only_moves_obvious_existing_leaf_mismatches():
    candidates = rows(CANDIDATES); manifest = rows(MANIFEST); summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert len(candidates) == len(manifest) == len({row["product_external_id"] for row in candidates}) == 91
    assert Counter(row["to_category_external_id"] for row in candidates) == {"seo:power-supplies":53,"seo:power-converters":26,"seo:ups-systems":12}
    assert {(row["factual_product_type"], row["to_category_external_id"]) for row in candidates} == {("power_supply_adapter","seo:power-supplies"),("laboratory_power_supply","seo:power-supplies"),("dc_dc_power_converter","seo:power-converters"),("ups_system","seo:ups-systems")}
    assert summary["held_uncertain"]["tool_battery_charger_kits"] == 24
    assert summary["scope"] == {"automotive_rows":0,"electronics_component_rows":0}

def test_wave217a_category_mover_is_dry_run_only():
    dry = json.loads(DRY.read_text(encoding="utf-8")); summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert dry["mode"] == "dry_run" and dry["apply_flag_used"] is False and dry["exit_code"] == 0
    assert dry["records"] == 91 and dry["validation_error_count"] == 0
    assert dry["manifest_sha256"] == hashlib.sha256(MANIFEST.read_bytes()).hexdigest()
    assert dry["category_link_mutations"] == dry["url_mutations"] == dry["canonical_mutations"] == dry["publication_fields_changed"] == 0
    assert summary["policy"] == {"obvious_product_type_only":True,"uncertain_rows_not_moved":True,"database_apply":False}
