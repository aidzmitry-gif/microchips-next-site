#!/usr/bin/env python3
"""Fail-closed official-source ledger for the Wave219-C final remainder."""
from __future__ import annotations

import base64
import csv
import hashlib
import json
import re
import subprocess
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "docs/audits/generated"
INPUT = GEN / "rb-b2b-next-source-batch-wave218.csv"
PROCESSED = GEN / "rb-b2b-processed-register-wave218.csv"
REGISTRY = GEN / "full-catalog-canonical-registry.csv"
VENTURA_INDEX = ROOT / "docs/audits/sources/wave206-panasonic-ventura-mnb/snapshot-index.json"
ROBITON_INDEX = ROOT / "docs/audits/sources/wave217b-devices/source-registry.json"
SOURCE_REGISTRY = ROOT / "docs/audits/sources/wave219c-final-remainder/source-registry.json"
OUTPUT = GEN / "rb-wave219c-final-remainder-evidence.csv"
SUMMARY = GEN / "rb-wave219c-final-remainder-evidence.summary.json"
LIVE = GEN / "wave219c-final-remainder-live-identity-collisions.json"
DRY = GEN / "wave219c-final-remainder-laravel-dry-run.json"
MANIFEST = ROOT / "docs/imports/rb-verified-oem-identities-wave219c-final-remainder-2026-07-29.json"
REPORT = ROOT / "docs/audits/2026-07-29-rb-wave219c-final-remainder-evidence.md"
CHECKED_AT = "2026-07-29"
INPUT_SHA256 = "c39570a34f469c22bc55c3b66091440ed48e406f399f672a722854f188438545"
TARGETS = {"Robiton": 36, "Ventura": 18, "Casil": 1, "Contact": 1, "Восток": 1}
FIELDS = ["batch","product_external_id","name","category_external_id","manufacturer_cluster","factual_product_type","taxonomy_assessment","extracted_model","source_tier","source_publisher","source_url","source_snapshot_path","source_snapshot_sha256","source_assertion","partition","hold_reason","registry_exact_title_duplicates","registry_mpn_duplicates","in_wave_mpn_duplicates","live_db_collision_external_ids","live_current_manufacturer","live_current_mpn","safe_to_apply"]


def sha(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()
def read_csv(path: Path) -> list[dict[str,str]]:
    with path.open(encoding="utf-8-sig", newline="") as f: return list(csv.DictReader(f))
def norm(value: str) -> str: return re.sub(r"[^A-Z0-9]+", "", unicodedata.normalize("NFKC", value or "").upper())
def product_norm(value: str) -> str: return re.sub(r"[\W_]", "", (value or "").casefold(), flags=re.UNICODE)


def source_records() -> tuple[dict[str,dict], str]:
    ventura = next(item for item in json.loads(VENTURA_INDEX.read_text(encoding="utf-8"))["sources"] if item["source_id"] == "ventura_2023_catalogue")
    robiton = next(item for item in json.loads(ROBITON_INDEX.read_text(encoding="utf-8"))["sources"] if item["source_id"] == "robiton_smartdisplay_1000")
    records = {"ventura": ventura, "robiton": robiton}
    texts = {}
    for key, record in records.items():
        if urlparse(record["source_url"]).scheme != "https": raise SystemExit("non-HTTPS source")
        snapshot = ROOT / record["snapshot_path"]
        if not snapshot.is_file() or sha(snapshot) != record["snapshot_sha256"]: raise SystemExit(f"source pin drift: {key}")
        texts[key] = snapshot.read_text(encoding="utf-8", errors="replace") if snapshot.suffix == ".html" else (ROOT / record["extracted_text_path"]).read_text(encoding="utf-8-sig")
    SOURCE_REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    SOURCE_REGISTRY.write_text(json.dumps({"schema_version":1,"checked_at":CHECKED_AT,"policy":"SHA-pinned official sources only","sources":[records[key] for key in sorted(records)]},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return records, texts


def model(row: dict[str,str]) -> str:
    name = row["name"]
    if row["manufacturer_cluster"] == "Ventura":
        match = re.search(r"\b(?:GPL|HRL|HR|VTG|GT|GP|VG|FT)\s*\d+(?:(?:[-/ ]\s*|(?<=\d))\d+(?:\.\d+)?[A-Z]*)?(?:\s+XT)?", name, re.I)
        return match.group(0) if match else ""
    if row["manufacturer_cluster"] == "Robiton":
        if re.search(r"smartdisplay\s+1000", name, re.I): return "SmartDisplay 1000"
        match = re.search(r"\bROBITON\s+(.+?)(?:\s*\(|,|\s+для\s+|\s+BL\d+\b|\s+Производство\b|\s+произв\.\b|\s+серти?\.?\b|$)", name, re.I)
        return match.group(1).strip() if match else "ROBITON title model unresolved"
    if row["manufacturer_cluster"] == "Casil":
        match = re.search(r"\bCA\d+\b", name, re.I); return match.group(0) if match else ""
    if row["manufacturer_cluster"] == "Contact":
        match = re.search(r"\bQUINT-PS-[A-Z0-9/-]+", name, re.I); return match.group(0) if match else ""
    match = re.search(r"\b(?:СК-\d+)\b", name, re.I); return match.group(0) if match else ""


def product_type(row: dict[str,str]) -> tuple[str,str]:
    name, category, brand = row["name"], row["category_external_id"], row["manufacturer_cluster"]
    if brand == "Ventura": return ("traction_battery" if category == "seo:batteries-traction" else "stationary_vrla_ups_battery", "category_matches_product_type")
    if brand == "Casil" or brand == "Восток": return "stationary_vrla_ups_battery", "category_matches_product_type"
    if brand == "Contact": return "industrial_din_rail_power_supply", "brand_cluster_should_be_phoenix_contact_not_contact"
    if category == "seo:power-supplies": return "ac_dc_power_adapter", "category_matches_product_type"
    if re.search(r"адаптер|блок питания", name, re.I): return "ac_dc_power_adapter", "taxonomy_mismatch_expected_seo_power_supplies"
    return "battery_charger", "category_matches_product_type"


def live_products() -> list[dict]:
    php="echo json_encode(app('db')->table('products')->select('external_id','name','sku','mpn','manufacturer','sku_normalized','mpn_normalized')->orderBy('external_id')->get(),JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES);"
    encoded=base64.b64encode(php.encode()).decode(); run=subprocess.run(["docker","compose","exec","-T","backend","php","artisan","tinker",f"--execute=eval(base64_decode('{encoded}'));"],cwd=ROOT,capture_output=True,text=True,encoding="utf-8",errors="replace")
    if run.returncode or not run.stdout.strip().startswith("["): raise SystemExit(f"read-only PostgreSQL query failed: {run.stderr.strip() or run.stdout.strip()}")
    return json.loads(run.stdout)


def main() -> None:
    source, processed, registry = read_csv(INPUT), read_csv(PROCESSED), read_csv(REGISTRY)
    if sha(INPUT) != INPUT_SHA256: raise SystemExit("Wave219-C input pin drift")
    selected=[row for row in source if row["manufacturer_cluster"] in TARGETS]; ids=[row["product_external_id"] for row in selected]
    if Counter(row["manufacturer_cluster"] for row in selected) != TARGETS or len(ids) != 57 or len(set(ids)) != 57: raise SystemExit("Wave219-C target drift")
    overlap=sorted(set(ids)&{row["product_external_id"] for row in processed})
    if overlap: raise SystemExit(f"processed3500 overlap: {overlap[:5]}")
    forbidden=[row["product_external_id"] for row in selected if re.search(r"automotive|автомоб|electronics|электрон", " ".join(row.values()),re.I)]
    if forbidden: raise SystemExit(f"automotive/electronics scope breach: {forbidden}")
    sources,texts=source_records(); live=live_products(); live_by_id={row["external_id"] for row in live}
    if set(ids)-live_by_id: raise SystemExit("candidate absent from live DB")
    current={row["external_id"]:row for row in live}; title_index=defaultdict(list)
    for row in registry: title_index[norm(row.get("name", ""))].append(row["registry_id"])
    prepared=[]
    for row in selected:
        token=model(row); ptype,taxonomy=product_type(row); exact=False; source_key=""
        if row["manufacturer_cluster"] == "Ventura" and token and norm(token) in norm(texts["ventura"]): exact=True; source_key="ventura"
        if row["manufacturer_cluster"] == "Robiton" and token and norm(token) in norm(texts["robiton"]): exact=True; source_key="robiton"
        prepared.append({**row,"model":token,"type":ptype,"taxonomy":taxonomy,"exact":exact,"source_key":source_key})
    in_wave=defaultdict(list)
    for row in prepared:
        if row["exact"]: in_wave[product_norm(row["model"])].append(row["product_external_id"])
    output=[]; live_checks=[]; manifest=[]
    for row in prepared:
        external_id=row["product_external_id"]; token=row["model"]; token_norm=product_norm(token); exact_title=sorted(peer for peer in title_index[norm(row["name"])] if peer!=external_id)
        registry_peers=sorted(other["registry_id"] for other in registry if other["registry_id"]!=external_id and token_norm and token_norm==product_norm(other.get("mpn", "")))
        live_peers=sorted(other["external_id"] for other in live if other["external_id"]!=external_id and token_norm and token_norm in {str(other.get("sku_normalized") or product_norm(str(other.get("sku") or ""))),str(other.get("mpn_normalized") or product_norm(str(other.get("mpn") or "")))})
        wave_peers=sorted(peer for peer in in_wave.get(token_norm,[]) if peer!=external_id)
        partition="exact_source_hold"; hold="no_SHA_pinned_exact_official_source"
        # This command intentionally applies only to Bitrix noindex drafts.
        # Wave219-C carries 1C-style external IDs, so even exact source facts
        # must be held for the separate 1C review route rather than forced
        # through an inapplicable Bitrix manifest.
        if row["exact"] and not external_id.startswith("bitrix:"):
            hold="exact_primary_source_but_non_bitrix_external_id_requires_1c_review_route"
        elif row["exact"] and not exact_title and not registry_peers and not live_peers and not wave_peers and current[external_id]["name"]==row["name"]: partition="exact_safe"; hold=""
        elif row["exact"]: hold="duplicate_or_current_identity_guard_hold" if (exact_title or registry_peers or live_peers or wave_peers) else "live_current_name_drift"
        source=sources.get(row["source_key"])
        record={"batch":"wave219c_final_remainder","product_external_id":external_id,"name":row["name"],"category_external_id":row["category_external_id"],"manufacturer_cluster":row["manufacturer_cluster"],"factual_product_type":row["type"],"taxonomy_assessment":row["taxonomy"],"extracted_model":token,"source_tier":"manufacturer_primary" if source else "","source_publisher":source["publisher"] if source else "","source_url":source["source_url"] if source else "","source_snapshot_path":("../audits/"+source["snapshot_path"].removeprefix("docs/audits/")) if source else "","source_snapshot_sha256":source["snapshot_sha256"] if source else "","source_assertion":f"exact {token} occurs in SHA-pinned official source" if row["exact"] else "","partition":partition,"hold_reason":hold,"registry_exact_title_duplicates":"|".join(exact_title),"registry_mpn_duplicates":"|".join(registry_peers),"in_wave_mpn_duplicates":"|".join(wave_peers),"live_db_collision_external_ids":"|".join(live_peers),"live_current_manufacturer":str(current[external_id].get("manufacturer") or ""),"live_current_mpn":str(current[external_id].get("mpn") or ""),"safe_to_apply":"true" if partition=="exact_safe" else "false"}
        output.append(record); live_checks.append({"candidate_external_id":external_id,"candidate_mpn_normalized":token_norm,"conflicting_external_ids":live_peers})
        if partition=="exact_safe": manifest.append({"external_id":external_id,"current_name":row["name"],"manufacturer":"Ventura" if row["manufacturer_cluster"]=="Ventura" else "ROBITON","mpn":token,"source_url":record["source_url"],"source_kind":source["source_kind"],"source_publisher":record["source_publisher"],"checked_at":CHECKED_AT,"product_type":row["type"],"source_snapshot_path":record["source_snapshot_path"],"source_snapshot_sha256":record["source_snapshot_sha256"]})
    if len({product_norm(item["mpn"]) for item in manifest}) != len(manifest): raise SystemExit("manifest repeats normalized MPN")
    with OUTPUT.open("w",encoding="utf-8-sig",newline="") as f: writer=csv.DictWriter(f,fieldnames=FIELDS,lineterminator="\n");writer.writeheader();writer.writerows(output)
    MANIFEST.write_text(json.dumps({"schema_version":1,"site_key":"microchips-by","products":manifest},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    manifest_sha=sha(MANIFEST); root="/tmp/wave219c-dry-run"; container_manifest=root+"/imports/"+MANIFEST.name
    prep=subprocess.run(["docker","compose","exec","-T","backend","sh","-lc",f"mkdir -p {root}/imports {root}/audits/sources/wave206-panasonic-ventura-mnb {root}/audits/sources/wave217b-devices"],cwd=ROOT,capture_output=True,text=True,encoding="utf-8",errors="replace")
    if prep.returncode: raise SystemExit("could not prepare dry-run source topology")
    for source in sources.values():
        copied=subprocess.run(["docker","compose","cp",str(ROOT/source["snapshot_path"]),"backend:"+root+"/audits/"+source["snapshot_path"].removeprefix("docs/audits/")],cwd=ROOT,capture_output=True,text=True,encoding="utf-8",errors="replace")
        if copied.returncode: raise SystemExit("could not copy dry-run snapshot")
    copied=subprocess.run(["docker","compose","cp",str(MANIFEST),"backend:"+container_manifest],cwd=ROOT,capture_output=True,text=True,encoding="utf-8",errors="replace")
    if copied.returncode: raise SystemExit("could not copy dry-run manifest")
    run=subprocess.run(["docker","compose","exec","-T","backend","php","artisan","catalog:apply-verified-oem-identities","microchips-by",container_manifest],cwd=ROOT,capture_output=True,text=True,encoding="utf-8",errors="replace")
    dry={"mode":"dry_run","attempted_without_apply":True,"apply_flag_used":False,"exit_code":run.returncode,"records":len(manifest),"manifest_sha256":manifest_sha,"stdout":run.stdout.strip(),"stderr":run.stderr.strip(),"database_mutations":0,"commercial_fields_changed":0,"publication_fields_changed":0}
    if manifest:
        if run.returncode or f'"records": {len(manifest)}' not in run.stdout: raise SystemExit(f"Laravel dry-run failed: {run.stderr or run.stdout}")
    elif run.returncode == 0 or "non-empty products list" not in (run.stdout + run.stderr):
        raise SystemExit("Laravel empty exact-safe manifest did not fail closed")
    LIVE.write_text(json.dumps({"schema_version":1,"mode":"read_only","candidate_rows_checked":len(output),"checks":live_checks,"database_mutations":0},ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); DRY.write_text(json.dumps(dry,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    partitions=Counter(row["partition"] for row in output); mismatches=[row["product_external_id"] for row in output if row["taxonomy_assessment"]!="category_matches_product_type"]
    summary={"schema_version":1,"batch":"wave219c_final_remainder","checked_at":CHECKED_AT,"input":{"path":INPUT.relative_to(ROOT).as_posix(),"sha256":sha(INPUT),"rows":394},"target":{"rows":57,"brand_counts":dict(sorted(Counter(row["manufacturer_cluster"] for row in output).items()))},"processed3500_overlap_ids":overlap,"scope_exclusion":{"automotive_rows":0,"electronics_rows":0},"taxonomy":{"mismatch_rows":len(mismatches),"external_ids":mismatches},"source_registry":{"path":SOURCE_REGISTRY.relative_to(ROOT).as_posix(),"sha256":sha(SOURCE_REGISTRY),"pinned_sources":2},"canonical_registry":{"path":REGISTRY.relative_to(ROOT).as_posix(),"rows":len(registry),"collision_rows":sum(bool(row["registry_exact_title_duplicates"] or row["registry_mpn_duplicates"] or row["in_wave_mpn_duplicates"]) for row in output)},"live_db":{"path":LIVE.relative_to(ROOT).as_posix(),"rows_checked":57,"collision_rows":sum(bool(row["live_db_collision_external_ids"]) for row in output),"database_mutations":0},"partition_counts":dict(sorted(partitions.items())),"manifest":{"path":MANIFEST.relative_to(ROOT).as_posix(),"sha256":manifest_sha,"rows":len(manifest),"exact_safe_only":True},"laravel_dry_run":{"path":DRY.relative_to(ROOT).as_posix(),"exit_code":run.returncode,"database_mutations":0},"safe_to_apply_records":len(manifest),"database_mutations":0}
    SUMMARY.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    REPORT.write_text("# Wave219-C final remainder evidence\n\nWave219-C processes exactly 57 rows: 36 Robiton, 18 Ventura, and one each Casil, Contact and Восток. Only exact SHA-pinned primary sources were considered. Ventura catalogue models and the ROBITON SmartDisplay 1000 page can enter the exact-safe path only after duplicate and live guards; ambiguous brands/models remain held.\n\nProduct-type extraction flags taxonomy mismatches without moving any category: a ROBITON adapter currently in chargers, and the Contact cluster whose factual maker label is Phoenix Contact. Registry/live checks are read only and Laravel ran without `--apply`.\n",encoding="utf-8")
    print(json.dumps({"rows":57,"partitions":dict(partitions),"safe":len(manifest),"dry":run.returncode,"db":0}))


if __name__=="__main__": main()
