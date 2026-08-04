#!/usr/bin/env python3
"""Build a fail-closed Honeywell Wave202 evidence register; no HTTP or DB writes."""
from __future__ import annotations
import argparse, csv, json, re
from pathlib import Path

FIELDS=["product_external_id","legacy_name","model_token","classification","source_url","source_kind","verified_facts","no_repeat_prior_artifact","research_method","evidence_boundary","safe_to_apply"]
PRIOR_EXACT={
 "bitrix:12116":("https://prod-edam.honeywell.com/content/dam/honeywell-edam/sps/ppr/en-gb/localized/accessories-guides/sps-ppr-eda51k-accessory-guide-en-a4.pdf","BAT-EDA50K-1","model_core: Honeywell EDA50K/EDA51K; 3.8V; 4000mAh"),
 "bitrix:12270":("https://prod-edam.honeywell.com/content/dam/honeywell-edam/sps/ppr/en-gb/localized/accessories-guides/sps-ppr-eda51k-accessory-guide-en-a4.pdf","BAT-EDA50K-1","model_core: Honeywell EDA50K/EDA51K; 3.8V; 4000mAh"),
 "bitrix:12258":("https://prod-edam.honeywell.com/content/dam/honeywell-edam/sps/ppr/en-us/public/products/mobile-computers/handheld-computers/ct40/documents/sps-ppr-ct40-a-en-ug.pdf?download=false","CT50-BTSC","exact: Honeywell CT40/CT40 XP compatibility"),
}
def build(source:Path,out:Path)->dict:
    with source.open(encoding="utf-8-sig",newline="") as f: rows=list(csv.DictReader(f))
    selected=[r for r in rows if r.get("batch")=="honeywell_mobile_computers"]
    if len(selected)!=42: raise ValueError(f"expected 42 Honeywell rows, got {len(selected)}")
    seen=set(); output=[]
    for r in selected:
        ident=r["product_external_id"].strip()
        if not ident or ident in seen: raise ValueError("missing or duplicate external_id")
        seen.add(ident)
        # Candidate labels name devices/OEM packs, not a verified replacement
        # maker identity. Empty URL/facts is intentional until exact evidence is saved.
        token=(re.search(r"(?i)\b(?:BAT|BTRY|CT|EDA|SL)-[A-Z0-9-]+",r["name"]) or [""])[0]
        prior=PRIOR_EXACT.get(ident)
        output.append({"product_external_id":ident,"legacy_name":r["name"],"model_token":prior[1] if prior else token.upper(),"classification":"previously_processed" if prior else "no_evidence","source_url":prior[0] if prior else "","source_kind":"Honeywell official documentation" if prior else "","verified_facts":prior[2] if prior else "","no_repeat_prior_artifact":"wave174_exact" if prior else "none_found","research_method":"prior_wave174_primary_evidence" if prior else "official_source_required_per_exact_candidate; no source record supplied","evidence_boundary":"OEM documentation may prove device compatibility only; it must not set replacement manufacturer or MPN without exact replacement identity.","safe_to_apply":"false"})
    out.mkdir(parents=True,exist_ok=True); target=out/"rb-wave202-honeywell-evidence.csv"
    with target.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=FIELDS);w.writeheader();w.writerows(output)
    previous=sum(r["classification"]=="previously_processed" for r in output)
    summary={"wave":"wave202","candidate_records":len(output),"classification_counts":{"exact_safe":0,"compatibility_only":0,"conflict":0,"previously_processed":previous,"no_evidence":len(output)-previous},"prior_artifact_overlap_records":previous,"evidence_artifact":str(target),"safety_invariant":"No manufacturer/MPN/technical facts were inferred from OEM compatibility labels.","safe_to_apply":False,"automatic_database_mutations":0}
    (out/"rb-wave202-honeywell-evidence-summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return summary
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--source",type=Path,required=True);p.add_argument("--out-dir",type=Path,required=True);a=p.parse_args();print(json.dumps(build(a.source,a.out_dir),ensure_ascii=False,indent=2))
