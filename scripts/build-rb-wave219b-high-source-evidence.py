#!/usr/bin/env python3
"""Fail-closed Wave219-B evidence for the final 60 high-source brand rows.

Only snapshots already pinned in this repository are considered.  A series,
retailer, distributor, or merely similar model is never promoted to a
manufacturer identity.  The live product query is read-only; application is
left to the separately recorded Laravel dry run.
"""
from __future__ import annotations

import base64, csv, hashlib, json, re, subprocess
from collections import Counter, defaultdict
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "docs/audits/generated"
INPUT = GEN / "rb-b2b-next-source-batch-wave218.csv"
REGISTRY = GEN / "full-catalog-canonical-registry.csv"
OUTPUT = GEN / "rb-wave219b-high-source-evidence.csv"
SUMMARY = GEN / "rb-wave219b-high-source-evidence.summary.json"
LIVE = GEN / "wave219b-high-source-live-identity-collisions.json"
DRY = GEN / "wave219b-high-source-laravel-dry-run.json"
MANIFEST = ROOT / "docs/imports/rb-verified-oem-identities-wave219b-high-source-2026-07-29.json"
REPORT = ROOT / "docs/audits/2026-07-29-rb-wave219b-high-source-remainder.md"
CHECKED_AT = "2026-07-29"
TARGETS = {"APC": 6, "B.B. Battery": 10, "CSB": 13, "Delta": 26, "Fiamm": 2, "Sonnenschein": 2, "Sprinter": 1}
FIELDS = ["batch", "product_external_id", "name", "manufacturer_cluster", "model_token", "partition", "source_tier", "source_publisher", "source_url", "source_snapshot_path", "source_snapshot_sha256", "source_assertion", "canonical_registry_collision_ids", "live_db_collision_ids", "hold_reason", "safe_to_apply"]

def sha(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as h: return list(csv.DictReader(h))
def norm(value: str) -> str: return re.sub(r"[^A-Z0-9]", "", (value or "").upper())
def text(path: Path) -> str:
    raw = "\n".join(p.extract_text() or "" for p in PdfReader(path).pages) if path.suffix.casefold()==".pdf" else path.read_text(encoding="utf-8", errors="replace")
    return re.sub(r"\s+", " ", raw)

# id -> (model, publisher, url, snapshot path, kind).  These are the only
# exact model mappings admitted by this wave.  The source path itself is
# SHA-checked and the model token is rechecked in its extracted text.
EXACT = {
 "КА-00003244": ("BPS40-12", "B.B.Battery (Taiwan) Co., Ltd.", "https://www.bb-bat.com/en/BPS.html", "docs/audits/sources/wave206-fiamm-bb-csb/bb-bps-series-2026-07-29.html", "official_manufacturer_product_page"),
 "КА-00004165": ("HR5.8-12", "B.B.Battery (Taiwan) Co., Ltd.", "https://www.bb-bat.com/en/HR.html", "docs/audits/sources/wave206-fiamm-bb-csb/bb-hr-series-2026-07-29.html", "official_manufacturer_product_page"),
 "КА-00006069": ("HR9-6", "B.B.Battery (Taiwan) Co., Ltd.", "https://www.bb-bat.com/en/HR.html", "docs/audits/sources/wave206-fiamm-bb-csb/bb-hr-series-2026-07-29.html", "official_manufacturer_product_page"),
 "КА-00001923": ("HRL5.5-12", "B.B.Battery (Taiwan) Co., Ltd.", "https://www.bb-bat.com/en/HRL.html", "docs/audits/sources/wave206-fiamm-bb-csb/bb-hrl-series-2026-07-29.html", "official_manufacturer_product_page"),
 "КА-00003094": ("BPS28-12", "B.B.Battery (Taiwan) Co., Ltd.", "https://www.bb-bat.com/en/BPS.html", "docs/audits/sources/wave206-fiamm-bb-csb/bb-bps-series-2026-07-29.html", "official_manufacturer_product_page"),
 "ФР-00001952": ("BPS26-12", "B.B.Battery (Taiwan) Co., Ltd.", "https://www.bb-bat.com/en/BPS.html", "docs/audits/sources/wave206-fiamm-bb-csb/bb-bps-series-2026-07-29.html", "official_manufacturer_product_page"),
 "КА-00003582": ("HR33-12", "B.B.Battery (Taiwan) Co., Ltd.", "https://www.bb-bat.com/en/HR.html", "docs/audits/sources/wave206-fiamm-bb-csb/bb-hr-series-2026-07-29.html", "official_manufacturer_product_page"),
 "КА-00003200": ("RBC31", "APC by Schneider Electric", "https://www.se.com/us/en/product/RBC31/apc-replacement-battery-cartridge-vrla-battery-9ah-48vdc-2year-warranty/", "docs/audits/sources/apc-wave199/381358c49663abe109d021b2be8f7a9df9ff6af6c71005885d0c9afc6ff8653c.html", "official_manufacturer_product_page"),
 "КА-00003351": ("RBC11", "APC by Schneider Electric", "https://www.se.com/us/en/product/RBC11/apc-replacement-battery-cartridge-11-with-2-year-warranty/", "docs/audits/sources/apc-wave199/8402c02cba77e5f98c03aa8525e50313cfd1fe2ed7d6db0574cee7d490b798d6.html", "official_manufacturer_product_page"),
 "ФР-00000052": ("DT6033", "DELTA Battery / ENERGON", "https://delta-batt.com/catalog/statsionarnye/dt/dt-6033/", "docs/audits/sources/wave211b-delta/c759bc5d7ee72bab.html", "official_manufacturer_product_page"),
 "ФР-00000295": ("DT1226", "DELTA Battery / ENERGON", "https://delta-batt.com/catalog/statsionarnye/dt/dt-1226/", "docs/audits/sources/wave211b-delta/fb54d24e780b6d44.html", "official_manufacturer_product_page"),
 "ФР-00000902": ("DT606", "DELTA Battery / ENERGON", "https://delta-batt.com/catalog/statsionarnye/dt/dt-606/", "docs/audits/sources/wave211b-delta/e7d6680303869767.html", "official_manufacturer_product_page"),
 "ФР-00001005": ("DT6045", "DELTA Battery / ENERGON", "https://delta-batt.com/catalog/statsionarnye/dt/dt-6045/", "docs/audits/sources/wave211b-delta/c30e369cb318aa68.html", "official_manufacturer_product_page"),
 "ФР-00001307": ("DT1207", "DELTA Battery / ENERGON", "https://delta-batt.com/catalog/statsionarnye/dt/dt-1207/", "docs/audits/sources/wave211b-delta/48be64d320ae7465.html", "official_manufacturer_product_page"),
 "КА-00002661": ("DTM1265L", "DELTA Battery / ENERGON", "https://delta-batt.com/catalog/statsionarnye/dtm-l/dtm-1265-l/", "docs/audits/sources/wave211b-delta/9f7ecca02e10b512.html", "official_manufacturer_product_page"),
 "КА-00002596": ("A606/200", "Exide Technologies", "https://www.exidegroup.com/eu/sites/default/files/2017-01/Sonnenschein_A600_en.pdf", "docs/audits/sources/wave209a/exide-sonnenschein-a600.pdf", "official_manufacturer_catalogue"),
 "ФР-00001154": ("A502/10S", "Exide Technologies", "https://www.exidegroup.com/eu/sites/default/files/2017-01/Sonnenschein_A500_en.pdf", "docs/audits/sources/wave209a/exide-sonnenschein-a500.pdf", "official_manufacturer_catalogue"),
}

def live_products() -> list[dict]:
    php="$r=app('db')->table('products')->select('external_id','name','sku','mpn','manufacturer','sku_normalized','mpn_normalized')->orderBy('external_id')->get();echo json_encode($r,JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES);"
    encoded=base64.b64encode(php.encode()).decode()
    run=subprocess.run(["docker","compose","exec","-T","backend","php","artisan","tinker",f"--execute=eval(base64_decode('{encoded}'));"],cwd=ROOT,capture_output=True,text=True,encoding="utf-8",errors="replace")
    if run.returncode or not run.stdout.strip().startswith("["): raise SystemExit(run.stderr.strip() or run.stdout.strip())
    rows=json.loads(run.stdout)
    if len(rows)!=len({r["external_id"] for r in rows}): raise SystemExit("live external_id duplicate")
    return rows

def main() -> None:
    selected=[r for r in read(INPUT) if r["manufacturer_cluster"] in TARGETS]
    counts=Counter(r["manufacturer_cluster"] for r in selected)
    if counts!=Counter(TARGETS) or len(selected)!=60 or len({r["product_external_id"] for r in selected})!=60: raise SystemExit(f"Wave219-B target drift: {dict(counts)}")
    sources={}
    for _, (_, publisher, url, relative, kind) in EXACT.items():
        path=ROOT/relative
        if not path.is_file() or not url.startswith("https://") or "official_manufacturer" not in kind: raise SystemExit(f"invalid pinned primary source: {relative}")
        if norm(_ if False else "") is None: raise SystemExit("unreachable")
        sources[relative]={"publisher":publisher,"source_url":url,"source_kind":kind,"snapshot_sha256":sha(path),"text":norm(text(path))}
    for external_id,(model,_,_,relative,_) in EXACT.items():
        if norm(model) not in sources[relative]["text"]: raise SystemExit(f"pinned snapshot lacks exact model {external_id}:{model}")
    registry=read(REGISTRY); live=live_products(); live_by_id={r["external_id"] for r in live}
    if not {r["product_external_id"] for r in selected} <= live_by_id: raise SystemExit("candidate missing from live product registry")
    evidence=[]; collisions=[]
    for row in selected:
        eid=row["product_external_id"]; source=EXACT.get(eid); model=""; registry_peers=[]; live_peers=[]
        fields={k:"" for k in FIELDS[6:12]}
        partition="hold_no_exact_primary_source"; reason="no_SHA_pinned_official_exact_model_source"
        if source:
            model,publisher,url,relative,kind=source; src=sources[relative]
            registry_peers=sorted({r["registry_id"] for r in registry if r["registry_id"]!=eid and row["manufacturer_cluster"].casefold() in r.get("name","").casefold() and norm(model) in norm(r.get("name",""))})
            for product in live:
                if product["external_id"]==eid: continue
                identifiers={norm(str(product.get(x) or "")) for x in ("sku","mpn","sku_normalized","mpn_normalized")}
                if norm(model) in identifiers or (row["manufacturer_cluster"].casefold() in str(product.get("name") or "").casefold() and norm(model) in norm(str(product.get("name") or ""))): live_peers.append(product["external_id"])
            peers=sorted(set(registry_peers+live_peers))
            # This importer intentionally handles existing Bitrix noindex
            # drafts only.  A source-proven 1C-style ID is evidence, not an
            # excuse to widen that contract, so it stays a distinct hold.
            if peers:
                partition, reason = "hold_identity_collision", "canonical_registry_or_live_database_identity_collision"
            elif not eid.startswith("bitrix:"):
                partition, reason = "hold_importer_ineligible_not_bitrix_draft", "exact_source_proven_but_verified_oem_importer_accepts_Bitrix_drafts_only"
            else:
                partition, reason = "exact_safe", ""
            fields={"source_tier":"manufacturer_primary","source_publisher":publisher,"source_url":url,"source_snapshot_path":"../audits/"+relative.removeprefix("docs/audits/"),"source_snapshot_sha256":src["snapshot_sha256"],"source_assertion":"exact_model_in_SHA_pinned_official_source"}
            if peers: collisions.append({"candidate_external_id":eid,"model":model,"conflicting_external_ids":peers})
        evidence.append({"batch":"wave219b_high_source_remainder","product_external_id":eid,"name":row["name"],"manufacturer_cluster":row["manufacturer_cluster"],"model_token":model,"partition":partition,**fields,"canonical_registry_collision_ids":"|".join(registry_peers),"live_db_collision_ids":"|".join(sorted(set(live_peers))),"hold_reason":reason,"safe_to_apply":"true" if partition=="exact_safe" else "false"})
    with OUTPUT.open("w",encoding="utf-8-sig",newline="") as h:
        w=csv.DictWriter(h,fieldnames=FIELDS,lineterminator="\n");w.writeheader();w.writerows(evidence)
    manifest_products=[{"external_id":r["product_external_id"],"current_name":r["name"],"manufacturer":r["manufacturer_cluster"],"mpn":r["model_token"],"source_url":r["source_url"],"source_kind":"official_manufacturer_product_page" if r["source_url"].endswith("/") else "official_manufacturer_catalogue","source_publisher":r["source_publisher"],"checked_at":CHECKED_AT,"product_type":"battery or UPS battery module","source_snapshot_path":r["source_snapshot_path"],"source_snapshot_sha256":r["source_snapshot_sha256"]} for r in evidence if r["safe_to_apply"]=="true"]
    MANIFEST.write_text(json.dumps({"schema_version":1,"site_key":"microchips-by","products":manifest_products},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    LIVE.write_text(json.dumps({"schema_version":1,"mode":"read_only","query_exit_code":0,"candidate_rows_checked":len(EXACT),"collisions":collisions,"database_mutations":0},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    dry_ok=False
    if DRY.is_file():
        receipt=json.loads(DRY.read_text(encoding="utf-8-sig"))
        dry_ok = all((receipt.get("mode")=="dry_run", receipt.get("records")==len(manifest_products), receipt.get("manifest_sha256")==sha(MANIFEST), receipt.get("database_mutations")==0, receipt.get("commercial_fields_changed")==0, receipt.get("publication_fields_changed")==0)) and ((not manifest_products and receipt.get("exit_code")==1 and receipt.get("expected_fail_closed_reason")=="empty_exact_safe_manifest") or (bool(manifest_products) and receipt.get("exit_code")==0))
    summary={"schema_version":1,"batch":"wave219b_high_source_remainder","checked_at":CHECKED_AT,"input":{"path":INPUT.relative_to(ROOT).as_posix(),"sha256":sha(INPUT),"rows":60,"manufacturer_counts":dict(sorted(counts.items()))},"source_policy":"reuse_SHA_pinned_official_manufacturer_exact_model_evidence_only","pinned_primary_sources":len(sources),"exact_source_rows":len(EXACT),"partition_counts":dict(sorted(Counter(r["partition"] for r in evidence).items())),"live_collision_guard":{"path":LIVE.relative_to(ROOT).as_posix(),"sha256":sha(LIVE),"collision_rows":len(collisions),"database_mutations":0},"output":{"path":OUTPUT.relative_to(ROOT).as_posix(),"sha256":sha(OUTPUT),"rows":60},"manifest":{"path":MANIFEST.relative_to(ROOT).as_posix(),"sha256":sha(MANIFEST),"rows":len(manifest_products),"laravel_dry_run_verified":dry_ok},"laravel_dry_run":{"path":DRY.relative_to(ROOT).as_posix(),"verified":dry_ok},"policy":{"commercial_changes":0,"publication_changes":0,"database_mutations":0,"apply_performed":False}}
    SUMMARY.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    REPORT.write_text(f"# Wave219-B high-source remainder evidence\n\nWave219-B covers the exact final 60 Wave218 high-source-brand rows: APC 6, B.B. Battery 10, CSB 13, Delta 26, Fiamm 2, Sonnenschein 2 and Sprinter 1. Evidence is limited to SHA-pinned official manufacturer pages/catalogues already in the repository and requires an exact model token. FIAMM distributor evidence, unpinned CSB/Sprinter evidence, and all series-only matches remain held.\n\n{len(EXACT)} rows have exact pinned source evidence. Canonical-registry and live PostgreSQL collision guards remove colliding identities from the exact-safe manifest. The only otherwise unique evidence row is 1C-style `ФР-00001952`, which is held because `catalog:apply-verified-oem-identities` accepts Bitrix noindex drafts only; the command contract is not widened. The manifest is therefore empty and Laravel is invoked only to confirm its expected fail-closed response. No commercial, publication, or application action is performed.\n",encoding="utf-8")
    print(json.dumps({"rows":len(evidence),"partitions":summary["partition_counts"],"manifest_rows":len(manifest_products),"dry_run_verified":dry_ok},ensure_ascii=False))
if __name__=="__main__": main()
