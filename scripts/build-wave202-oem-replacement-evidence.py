#!/usr/bin/env python3
"""Fail-closed Wave202 ledger: OEM-device tokens are never replacement evidence."""
from __future__ import annotations
import argparse, csv, json, re
from collections import Counter
from pathlib import Path

TARGETS = {"datalogic_data_capture", "intermec_mobile_computers"}
TOKEN = re.compile(r"\b(?:CS-[A-Z0-9-]+|(?:BTDL|BT|94ACC|700)\w*[0-9][A-Z0-9-]*)\b", re.I)

def build(input_path: Path, output: Path, summary: Path) -> dict[str, object]:
    with input_path.open(encoding="utf-8-sig", newline="") as f: rows=list(csv.DictReader(f))
    selected=[r for r in rows if r.get("batch") in TARGETS]
    counts=Counter(r["batch"] for r in selected)
    if counts != Counter({"datalogic_data_capture":26,"intermec_mobile_computers":18}): raise ValueError("Wave202 source partition mismatch")
    out=[]
    overrides={
        "bitrix:12150":("compatibility_only","manufacturer_primary","https://cdn.datalogic.com/eng/support-service/downloads-dw-82.html?cat=5","OEM Datalogic 94ACC1329 standard battery; replacement identity unproven"),
        "bitrix:12218":("previously_processed","none","","wave174 applied; excluded from research"),
        "bitrix:12290":("compatibility_only","manufacturer_primary","https://prod-edam.honeywell.com/content/dam/honeywell-edam/sps/ppr/en-gb/public/products/common/documents/certifications-regulatory-information/sps-ppr-943-175.pdf","OEM AB18 3.6V 5000mAh conflicts with legacy 4400mAh"),
        "bitrix:12291":("compatibility_only","manufacturer_primary","https://prod-edam.honeywell.com/content/dam/honeywell-edam/sps/ppr/en-gb/public/products/common/documents/certifications-regulatory-information/sps-ppr-943-175.pdf","OEM AB18 3.6V 5000mAh conflicts with legacy 5200mAh"),
    }
    for r in selected:
        tokens="|".join(dict.fromkeys(TOKEN.findall(r["name"])))
        partition,tier,url,reason=overrides.get(r["product_external_id"],("no_evidence","none","","no exact replacement battery manufacturer or MPN source; OEM device docs not substituted"))
        out.append({"batch":r["batch"],"product_external_id":r["product_external_id"],"name":r["name"],"model_tokens_unverified":tokens,"partition":partition,"source_tier":tier,"source_url":url,"verified_facts":"","hold_reason":reason,"safe_to_apply":"false"})
    if len({r["product_external_id"] for r in out}) != 44: raise ValueError("duplicate or incomplete candidate set")
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(out[0]));w.writeheader();w.writerows(out)
    result={"input_path":str(input_path),"candidate_records":44,"batch_counts":dict(counts),"partition_counts":dict(Counter(r["partition"] for r in out)),"exact_safe_records":0,"automatic_database_mutations":0,"safe_to_apply_records":0}
    summary.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return result
def main()->int:
    p=argparse.ArgumentParser();p.add_argument("--input",type=Path,required=True);p.add_argument("--output",type=Path,required=True);p.add_argument("--summary",type=Path,required=True);a=p.parse_args();print(json.dumps(build(a.input,a.output,a.summary),ensure_ascii=False));return 0
if __name__=="__main__": raise SystemExit(main())
