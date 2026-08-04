#!/usr/bin/env python3
"""Fail-closed exact-source evidence for Wave217-B Robiton/Panasonic/EnerSys."""
from __future__ import annotations

import base64
import csv
import hashlib
import json
import re
import subprocess
from collections import Counter, defaultdict
from html import unescape
from pathlib import Path
from urllib.parse import urlparse

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "docs/audits/generated"
INPUT = GEN / "rb-b2b-next-source-batch-wave216.csv"
REGISTRY = GEN / "full-catalog-canonical-registry.csv"
ENER_SYS = ROOT / "docs/audits/sources/wave209a/enersys-cyclon-selection-guide.pdf"
ROBITON = ROOT / "docs/audits/sources/wave217b-devices/robiton-smartdisplay-1000.html"
SOURCES = ROOT / "docs/audits/sources/wave217b-devices/source-registry.json"
OUTPUT = GEN / "rb-wave217b-devices-evidence.csv"
CORRECTIONS = GEN / "wave217b-robiton-power-supply-category-candidates.csv"
MOVE_MANIFEST = ROOT / "docs/imports/rb-site-category-move-wave217b-robiton-power-supplies.csv"
SUMMARY = GEN / "rb-wave217b-devices-evidence.summary.json"
LIVE = GEN / "wave217b-devices-live-identity-collisions.json"
DRY = GEN / "wave217b-devices-laravel-dry-run.json"
MANIFEST = ROOT / "docs/imports/rb-verified-oem-identities-wave217b-devices-2026-07-29.json"
CHECKED_AT = "2026-07-29"
TARGETS = {"Robiton": 45, "Panasonic": 10, "EnerSys": 1}
EXACT = {
    "bitrix:742": ("EnerSys", "Cyclon X Cell", "enersys_cyclon_selection_guide", "stationary battery"),
    "bitrix:3411": ("Robiton", "SmartDisplay 1000", "robiton_smartdisplay_1000", "battery charger"),
}
FIELDS = ["batch", "product_external_id", "name", "category_external_id", "manufacturer_cluster", "model_token", "product_class", "partition", "source_tier", "source_publisher", "source_url", "source_snapshot_path", "source_snapshot_sha256", "source_assertion", "canonical_registry_collision_ids", "live_db_collision_ids", "hold_reason", "safe_to_apply"]
CORRECTION_FIELDS = ["batch", "product_external_id", "name", "current_category_external_id", "proposed_category_external_id", "product_class", "reason", "requires_human_category_review", "safe_to_apply"]

def sha(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle: return list(csv.DictReader(handle))
def norm(value: str) -> str: return re.sub(r"[^A-Z0-9]", "", (value or "").upper())
def pat(value: str) -> re.Pattern[str]:
    chars=[re.escape(ch) for ch in value.upper() if ch.isalnum()]
    return re.compile(r"(?<![A-Z0-9])"+r"[\s,._/-]*".join(chars)+r"(?![A-Z0-9])", re.I)
def html_text(path: Path) -> str:
    value=path.read_text(encoding="utf-8", errors="replace")
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", re.sub(r"<script\b[^>]*>.*?</script>", " ", value, flags=re.I|re.S)))).strip()

def source_index() -> tuple[dict[str, dict[str, str]], dict[str, str]]:
    if not ENER_SYS.is_file() or not ROBITON.is_file(): raise SystemExit("required Wave217-B pinned snapshots are missing")
    texts={
        "enersys_cyclon_selection_guide": "\n".join(page.extract_text() or "" for page in PdfReader(ENER_SYS).pages),
        "robiton_smartdisplay_1000": html_text(ROBITON),
    }
    records={
        "enersys_cyclon_selection_guide": {"publisher":"EnerSys", "source_url":"https://www.enersys.com/493c0d/globalassets/documents/product-documentation/cyclon/emea/en-cyc-sg-004_0614.pdf", "source_kind":"official_manufacturer_catalogue", "snapshot_path":ENER_SYS.relative_to(ROOT).as_posix(), "snapshot_sha256":sha(ENER_SYS)},
        "robiton_smartdisplay_1000": {"publisher":"ROBITON", "source_url":"https://www.robiton.ru/product/11072/", "source_kind":"official_manufacturer_product_page", "snapshot_path":ROBITON.relative_to(ROOT).as_posix(), "snapshot_sha256":sha(ROBITON)},
    }
    for external_id, (_, model, key, _) in EXACT.items():
        # The EnerSys table has the CYCLON family heading and the exact X-cell
        # row separately; ROBITON's product page renders its full product name.
        found = ("CYCLON" in texts[key].upper() and pat("X Cell").search(texts[key].upper())) if key == "enersys_cyclon_selection_guide" else bool(pat(model).search(texts[key].upper()))
        if not found: raise SystemExit(f"pinned official source lacks exact model: {external_id} {model}")
        if urlparse(records[key]["source_url"]).scheme != "https": raise SystemExit("non-HTTPS source")
    SOURCES.parent.mkdir(parents=True, exist_ok=True)
    SOURCES.write_text(json.dumps({"schema_version":1,"checked_at":CHECKED_AT,"policy":"SHA-pinned official manufacturer pages or catalogues only","sources":[{"source_id":key,**value} for key,value in sorted(records.items())]}, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    return records,texts

def live_products() -> list[dict]:
    php="$r=app('db')->table('products')->select('external_id','name','sku','mpn','manufacturer','sku_normalized','mpn_normalized','status')->orderBy('external_id')->get();echo json_encode($r,JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES);"
    encoded=base64.b64encode(php.encode()).decode()
    run=subprocess.run(["docker","compose","exec","-T","backend","php","artisan","tinker",f"--execute=eval(base64_decode('{encoded}'));"],cwd=ROOT,capture_output=True,text=True,encoding="utf-8",errors="replace")
    if run.returncode or not run.stdout.strip().startswith("["): raise SystemExit(f"read-only PostgreSQL query failed: {run.stderr.strip() or run.stdout.strip()}")
    rows=json.loads(run.stdout)
    if len({row["external_id"] for row in rows}) != len(rows): raise SystemExit("live PostgreSQL repeats external ids")
    return rows

def model_from_title(row: dict[str,str]) -> str:
    if row["product_external_id"] in EXACT: return EXACT[row["product_external_id"]][1]
    name=row["name"]
    maker=row["manufacturer_cluster"]
    if maker=="Panasonic":
        hit=re.search(r"Panasonic\s+(.+?)(?:\s+KR\s+\d|\s+\(|$)", name, re.I)
    elif maker=="Robiton":
        hit=re.search(r"Robiton\s+(.+?)(?:\s+\(|$)", name, re.I)
    else: hit=re.search(r"EnerSys\s+(.+?)(?:\s+\(|$)", name, re.I)
    return hit.group(1).strip() if hit else ""

def product_class(name: str) -> str:
    lower=name.casefold()
    if "зарядное устройство" in lower: return "battery charger"
    if "блок питания" in lower: return "power supply"
    return "battery"

def main() -> None:
    selected=[row for row in read(INPUT) if row["manufacturer_cluster"] in TARGETS]
    counts=Counter(row["manufacturer_cluster"] for row in selected); ids=[row["product_external_id"] for row in selected]
    if len(selected)!=56 or len(ids)!=len(set(ids)) or counts != Counter(TARGETS): raise SystemExit(f"Wave217-B target drift: {len(selected)} {dict(counts)}")
    forbidden=[row["product_external_id"] for row in selected if re.search(r"автомоб|starter|electronics|электронн", row["name"], re.I)]
    if forbidden: raise SystemExit(f"automotive/electronic scope breach: {forbidden}")
    sources,_=source_index(); registry=read(REGISTRY); live=live_products(); by_id={row["external_id"]:row for row in live}
    drift=[row["product_external_id"] for row in selected if row["product_external_id"] not in by_id or by_id[row["product_external_id"]]["name"] != row["name"]]
    if drift: raise SystemExit(f"live candidate ID/name drift: {drift}")
    registry_peers=defaultdict(list); live_peers=defaultdict(list)
    for external_id, (maker,model,_,_) in EXACT.items():
        rx=pat(model)
        for item in registry:
            if maker.casefold() in item.get("name","").casefold() and rx.search(item.get("name","").upper()) and item["registry_id"]!=external_id: registry_peers[external_id].append(item["registry_id"])
        for item in live:
            if item["external_id"] == external_id: continue
            existing={norm(str(item.get("mpn_normalized") or item.get("mpn") or "")),norm(str(item.get("sku_normalized") or item.get("sku") or ""))}
            if norm(model) in existing or (maker.casefold() in str(item.get("name") or "").casefold() and rx.search(str(item.get("name") or "").upper())): live_peers[external_id].append(item["external_id"])
    out=[]
    for row in selected:
        external_id=row["product_external_id"]; model=model_from_title(row); exact=EXACT.get(external_id)
        part="hold_no_exact_primary_source"; reason="no_SHA_pinned_official_exact_model_source"; source_fields={key:"" for key in ("source_tier","source_publisher","source_url","source_snapshot_path","source_snapshot_sha256","source_assertion")}
        if exact:
            maker,model,key,_=exact; peers=sorted(set(registry_peers[external_id]+live_peers[external_id])); part="exact_safe" if not peers else "hold_identity_collision"; reason="" if not peers else "canonical_registry_or_live_database_identity_collision"; source=sources[key]
            source_fields={"source_tier":"manufacturer_primary","source_publisher":source["publisher"],"source_url":source["source_url"],"source_snapshot_path":"../audits/"+source["snapshot_path"].removeprefix("docs/audits/"),"source_snapshot_sha256":source["snapshot_sha256"],"source_assertion":"exact_model_in_SHA_pinned_official_source"}
        out.append({"batch":"wave217b_devices","product_external_id":external_id,"name":row["name"],"category_external_id":row["category_external_id"],"manufacturer_cluster":row["manufacturer_cluster"],"model_token":model,"product_class":product_class(row["name"]),"partition":part,**source_fields,"canonical_registry_collision_ids":"|".join(sorted(set(registry_peers[external_id]))),"live_db_collision_ids":"|".join(sorted(set(live_peers[external_id]))),"hold_reason":reason,"safe_to_apply":"true" if part=="exact_safe" else "false"})
    manifest=[{"external_id":r["product_external_id"],"current_name":r["name"],"manufacturer":r["manufacturer_cluster"],"mpn":r["model_token"],"source_url":r["source_url"],"source_kind":"official_manufacturer_catalogue" if "enersys" in r["source_url"] else "official_manufacturer_product_page","source_publisher":r["source_publisher"],"checked_at":CHECKED_AT,"product_type":r["product_class"],"source_snapshot_path":r["source_snapshot_path"],"source_snapshot_sha256":r["source_snapshot_sha256"]} for r in out if r["safe_to_apply"]=="true"]
    # Both source-proved names collide with existing live 1C identities.  The
    # exact-safe manifest must therefore stay empty rather than bypassing the
    # collision guard or treating a retailer/compatibility match as evidence.
    if manifest: raise SystemExit("Wave217-B collision guard requires an empty exact-safe manifest")
    with OUTPUT.open("w",encoding="utf-8-sig",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=FIELDS,lineterminator="\n");writer.writeheader();writer.writerows(out)
    corrections=[{
        "batch":"wave217b_devices", "product_external_id":row["product_external_id"], "name":row["name"],
        "current_category_external_id":row["category_external_id"], "proposed_category_external_id":"seo:power-supplies",
        "product_class":"power supply", "reason":"title explicitly identifies a power supply; legacy charger category is not carried forward automatically",
        "requires_human_category_review":"true", "safe_to_apply":"false",
    } for row in out if row["manufacturer_cluster"]=="Robiton" and row["product_class"]=="power supply" and row["category_external_id"]=="seo:chargers"]
    if len(corrections)!=29 or len({row["product_external_id"] for row in corrections})!=29:
        raise SystemExit("Wave217-B requires exactly 29 unique Robiton power-supply category-review candidates")
    with CORRECTIONS.open("w",encoding="utf-8-sig",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=CORRECTION_FIELDS,lineterminator="\n");writer.writeheader();writer.writerows(corrections)
    moves=[{"product_external_id":row["product_external_id"],"from_category_external_id":"seo:chargers","to_category_external_id":"seo:power-supplies"} for row in corrections]
    with MOVE_MANIFEST.open("w",encoding="utf-8",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=["product_external_id","from_category_external_id","to_category_external_id"],lineterminator="\n");writer.writeheader();writer.writerows(moves)
    MANIFEST.write_text(json.dumps({"schema_version":1,"site_key":"microchips-by","products":manifest},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    guard={"schema_version":1,"mode":"read_only","query_exit_code":0,"candidate_rows_checked":len(EXACT),"collisions":[{"candidate_external_id":key,"conflicting_external_ids":sorted(set(value))} for key,value in sorted(live_peers.items()) if value],"database_mutations":0}
    LIVE.write_text(json.dumps(guard,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    dry_ok=False
    if DRY.is_file():
        dry=json.loads(DRY.read_text(encoding="utf-8-sig")); dry_ok=all((dry.get("mode")=="dry_run",dry.get("exit_code")==1,dry.get("records")==0,dry.get("manifest_sha256")==sha(MANIFEST),dry.get("database_mutations")==0,dry.get("expected_fail_closed_reason")=="empty_exact_safe_manifest"))
    category_dry=GEN/"wave217b-robiton-power-supply-category-laravel-dry-run.json"
    category_dry_ok=False
    if category_dry.is_file():
        receipt=json.loads(category_dry.read_text(encoding="utf-8-sig")); category_dry_ok=all((receipt.get("mode")=="dry_run",receipt.get("exit_code")==0,receipt.get("records")==len(moves),receipt.get("manifest_sha256")==sha(MOVE_MANIFEST),receipt.get("validation_error_count")==0,receipt.get("category_link_mutations")==0,receipt.get("url_mutations")==0,receipt.get("canonical_mutations")==0,receipt.get("publication_fields_changed")==0))
    summary={"schema_version":1,"batch":"wave217b_devices","checked_at":CHECKED_AT,"input":{"path":INPUT.relative_to(ROOT).as_posix(),"sha256":sha(INPUT),"rows":56,"manufacturer_counts":dict(sorted(counts.items()))},"scope_exclusion":{"automotive_rows":0,"electronic_component_rows":0},"source_registry":{"path":SOURCES.relative_to(ROOT).as_posix(),"sha256":sha(SOURCES),"pinned_sources":len(sources)},"canonical_registry":{"path":REGISTRY.relative_to(ROOT).as_posix(),"sha256":sha(REGISTRY),"collision_rows":sum(bool(r["canonical_registry_collision_ids"]) for r in out)},"live_collision_guard":{"path":LIVE.relative_to(ROOT).as_posix(),"sha256":sha(LIVE),"collision_rows":len(guard["collisions"]),"database_mutations":0},"product_class_counts":dict(sorted(Counter(r["product_class"] for r in out).items())),"category_correction_candidates":{"path":CORRECTIONS.relative_to(ROOT).as_posix(),"sha256":sha(CORRECTIONS),"rows":len(corrections),"strict_move_manifest":{"path":MOVE_MANIFEST.relative_to(ROOT).as_posix(),"sha256":sha(MOVE_MANIFEST),"rows":len(moves),"columns":["product_external_id","from_category_external_id","to_category_external_id"],"from":"seo:chargers","to":"seo:power-supplies","category_source":"full_catalog_seo_tree","laravel_dry_run_verified":category_dry_ok},"automatic_database_mutations":0},"partition_counts":dict(sorted(Counter(r["partition"] for r in out).items())),"output":{"path":OUTPUT.relative_to(ROOT).as_posix(),"sha256":sha(OUTPUT),"rows":len(out)},"manifest":{"path":MANIFEST.relative_to(ROOT).as_posix(),"sha256":sha(MANIFEST),"rows":len(manifest),"laravel_dry_run_verified":dry_ok},"laravel_dry_run":{"path":DRY.relative_to(ROOT).as_posix(),"verified":dry_ok},"policy":{"exact_safe_manifest_only":True,"commercial_publication_changes":0,"database_mutations":0}}
    SUMMARY.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"rows":len(out),"partitions":summary["partition_counts"],"manifest_rows":len(manifest),"dry_run_verified":dry_ok},ensure_ascii=False))
if __name__=="__main__": main()
