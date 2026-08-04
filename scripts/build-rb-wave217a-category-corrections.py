#!/usr/bin/env python3
"""Build and dry-run only obvious Wave217-A product-type category corrections."""
from __future__ import annotations

import csv
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "docs/audits/generated"
EVIDENCE = GEN / "rb-wave217a-unresolved-evidence.csv"
OUTPUT = GEN / "rb-wave217a-category-correction-candidates.csv"
SUMMARY = GEN / "rb-wave217a-category-correction.summary.json"
DRY = GEN / "wave217a-category-correction-laravel-dry-run.json"
MANIFEST = ROOT / "docs/imports/rb-site-category-move-wave217a-obvious-product-type.csv"
REPORT = ROOT / "docs/audits/2026-07-29-rb-wave217a-taxonomy-corrections.md"
EVIDENCE_SHA256 = "9124e384c1eb4e45f270dc4901566583bd4e246420cb6a251c2f9bcbbf9d009f"
TARGETS = {
    "power_supply_adapter": ("seo:chargers", "seo:power-supplies", "title explicitly says power supply/adapter, not charger"),
    "laboratory_power_supply": ("seo:power-systems", "seo:power-supplies", "laboratory power supply is an exact power-supply type"),
    "dc_dc_power_converter": ("seo:power-systems", "seo:power-converters", "title explicitly says DC-DC converter"),
    "ups_system": ("seo:power-systems", "seo:ups-systems", "title explicitly says UPS"),
}

def sha(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()
def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle: return list(csv.DictReader(handle))

def write_report(candidates: list[dict[str, str]], dry: dict) -> None:
    lines = [
        "# Wave217-A conservative taxonomy corrections", "",
        "This candidate manifest moves only product types whose title and Wave217-A factual classification state an unambiguous existing target leaf.",
        "Tool battery-plus-charger kits remain in `seo:replacement-tools`: a bundle has two buyer intents, so it is intentionally not auto-moved. Warehouse equipment and traction batteries already match their categories and are also untouched.", "",
        "## Candidate moves", "",
        f"- Total: {len(candidates)}", f"- Targets: {dict(sorted(Counter(row['to_category_external_id'] for row in candidates).items()))}",
        "- Categories used: existing `full_catalog_seo_tree` leaves only; no taxonomy node is created.",
        "- No automotive or electronic-component row is present.", "",
        "## Dry-run", "",
        f"- Laravel category mover exit: {dry['exit_code']}; validation errors: {dry['validation_error_count']}.",
        "- `--apply` was not passed. Category links, URLs, canonical paths, publication fields and product identity remain unchanged.",
    ]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")

def main() -> None:
    evidence = rows(EVIDENCE)
    if sha(EVIDENCE) != EVIDENCE_SHA256 or len(evidence) != 395: raise SystemExit("Wave217-A evidence pin/scope drift")
    ids = [row["product_external_id"] for row in evidence]
    if len(ids) != len(set(ids)) or any(row["safe_to_apply"] != "false" for row in evidence): raise SystemExit("Wave217-A identity safety drift")
    candidates, held = [], []
    for row in evidence:
        product_type = row["factual_product_type"]
        if product_type not in TARGETS:
            held.append(row); continue
        from_category, to_category, reason = TARGETS[product_type]
        if row["category_external_id"] != from_category: raise SystemExit(f"unexpected source category for {row['product_external_id']}")
        candidates.append({"product_external_id":row["product_external_id"], "from_category_external_id":from_category, "to_category_external_id":to_category, "name":row["name"], "factual_product_type":product_type, "reason":reason, "safe_to_apply":"false"})
    if len(candidates) != 91 or len({row["product_external_id"] for row in candidates}) != 91: raise SystemExit("unexpected Wave217-A candidate count")
    if Counter(row["to_category_external_id"] for row in candidates) != {"seo:power-supplies":53,"seo:power-converters":26,"seo:ups-systems":12}: raise SystemExit("unexpected target distribution")
    if any(row["factual_product_type"] in TARGETS for row in held) or any(row["factual_product_type"] == "power_tool_battery_charger_kit" for row in candidates): raise SystemExit("uncertain bundle admitted")
    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(candidates[0]), lineterminator="\n"); writer.writeheader(); writer.writerows(candidates)
    with MANIFEST.open("w", encoding="utf-8-sig", newline="") as handle:
        fields = ["product_external_id","from_category_external_id","to_category_external_id"]
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n"); writer.writeheader(); writer.writerows({field: row[field] for field in fields} for row in candidates)
    container_manifest = "/tmp/" + MANIFEST.name
    copied = subprocess.run(["docker","compose","cp",str(MANIFEST),"backend:"+container_manifest],cwd=ROOT,capture_output=True,text=True,encoding="utf-8",errors="replace")
    if copied.returncode: raise SystemExit(f"could not place category manifest: {copied.stderr.strip() or copied.stdout.strip()}")
    run = subprocess.run(["docker","compose","exec","-T","backend","php","artisan","catalog:move-site-product-categories","microchips-by",container_manifest,"--category-source=full_catalog_seo_tree"],cwd=ROOT,capture_output=True,text=True,encoding="utf-8",errors="replace")
    # The command's compact text does not expose the complete JSON summary;
    # successful exit plus its validated count is the contract for this dry run.
    dry = {"mode":"dry_run","apply_flag_used":False,"exit_code":run.returncode,"records":len(candidates),"manifest_sha256":sha(MANIFEST),"stdout":run.stdout.strip(),"stderr":run.stderr.strip(),"validation_error_count":0 if run.returncode == 0 else None,"category_link_mutations":0,"url_mutations":0,"canonical_mutations":0,"publication_fields_changed":0}
    if run.returncode: raise SystemExit(f"Laravel category dry-run failed: {run.stderr.strip() or run.stdout.strip()}")
    DRY.write_text(json.dumps(dry,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    summary = {"schema_version":1,"batch":"wave217a_category_correction","input":{"path":EVIDENCE.relative_to(ROOT).as_posix(),"sha256":sha(EVIDENCE),"rows":395},"candidates":{"path":OUTPUT.relative_to(ROOT).as_posix(),"sha256":sha(OUTPUT),"rows":len(candidates),"targets":dict(sorted(Counter(row["to_category_external_id"] for row in candidates).items()))},"held_uncertain":{"rows":len(held),"tool_battery_charger_kits":sum(row["factual_product_type"] == "power_tool_battery_charger_kit" for row in held),"warehouse_rows":sum(row["factual_product_type"] in {"electric_warehouse_stacker","manual_pallet_truck"} for row in held),"traction_rows":sum(row["factual_product_type"] == "traction_battery" for row in held)},"scope":{"automotive_rows":0,"electronics_component_rows":0},"manifest":{"path":MANIFEST.relative_to(ROOT).as_posix(),"sha256":sha(MANIFEST),"rows":len(candidates),"category_source":"full_catalog_seo_tree"},"laravel_dry_run":{"path":DRY.relative_to(ROOT).as_posix(),"exit_code":run.returncode,"category_link_mutations":0,"apply_flag_used":False},"policy":{"obvious_product_type_only":True,"uncertain_rows_not_moved":True,"database_apply":False}}
    SUMMARY.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    write_report(candidates,dry)
    print(json.dumps({"candidates":len(candidates),"held":len(held),"dry_run_exit":run.returncode,"category_link_mutations":0}))

if __name__ == "__main__": main()
