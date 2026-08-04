#!/usr/bin/env python3
"""Register only exact, saved first-party Panasonic evidence for Wave200.

It never downloads pages and accepts no technical facts.  Each accepted record
must name the same catalog product and complete pack-variant key as its
candidate, making a model-level source unusable for another pack variant.
"""
from __future__ import annotations

import argparse, csv, hashlib, json
from pathlib import Path
from urllib.parse import urlparse

HOSTS={"industrial.panasonic.com", "na.industrial.panasonic.com", "energy.panasonic.com"}
FIELDS=["product_external_id","model_token","pack_variant_key","source_url","source_kind","snapshot_path","snapshot_sha256","safe_to_apply"]
def sha(path: Path)->str: return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path: Path)->list[dict[str,str]]:
    with path.open(encoding="utf-8-sig", newline="") as f: return list(csv.DictReader(f))
def write(path:Path, rows:list[dict[str,str]]):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=FIELDS);w.writeheader();w.writerows(rows)
def build(candidates:Path,evidence:Path|None,out_dir:Path)->dict[str,object]:
    cand=read(candidates); index={r["product_external_id"]:r for r in cand}
    if len(index)!=len(cand): raise ValueError("candidate external IDs must be unique")
    accepted=[]
    for n,row in enumerate(read(evidence) if evidence else [],2):
        if any((row.get(x) or "").strip() for x in ("price","stock","availability")): raise ValueError(f"commercial field at evidence line {n}")
        c=index.get((row.get("product_external_id") or "").strip())
        if not c: raise ValueError(f"unknown candidate at evidence line {n}")
        if row.get("model_token","").strip().upper()!=c["model_token"].upper() or row.get("pack_variant_key","").strip()!=c["pack_variant_key"]: raise ValueError(f"cross-variant evidence at line {n}")
        u=urlparse(row.get("source_url", ""));
        if u.scheme!="https" or u.hostname not in HOSTS or u.query or u.fragment: raise ValueError(f"non-first-party exact URL at line {n}")
        if row.get("source_kind") not in {"exact_product_page","exact_datasheet"}: raise ValueError(f"unsupported source kind at line {n}")
        snap=Path(row.get("snapshot_path", "")); declared=row.get("snapshot_sha256", "").lower()
        if not snap.is_file() or sha(snap).lower()!=declared: raise ValueError(f"snapshot hash mismatch at line {n}")
        accepted.append({k:(row.get(k,"").strip()) for k in FIELDS[:-1]}|{"safe_to_apply":"false"})
    if len({r['product_external_id'] for r in accepted})!=len(accepted): raise ValueError("duplicate evidence product")
    out=out_dir/"rb-panasonic-wave200-official-registry.csv"; write(out,accepted)
    summary={"wave":"wave200","candidate_sha256":sha(candidates),"candidate_records":len(cand),"accepted_exact_first_party_records":len(accepted),"acquisition_required_records":len(cand)-len(accepted),"registry_artifact":str(out),"registry_artifact_sha256":sha(out),"allowed_hosts":sorted(HOSTS),"cross_pack_fact_transfer":"forbidden","commercial_facts":"forbidden","safe_to_apply":False,"automatic_database_mutations":0}
    (out_dir/"rb-panasonic-wave200-acquisition-contract.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return summary
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--candidates",type=Path,required=True);p.add_argument("--evidence",type=Path);p.add_argument("--out-dir",type=Path,required=True);a=p.parse_args();print(json.dumps(build(a.candidates,a.evidence,a.out_dir),ensure_ascii=False,indent=2))
