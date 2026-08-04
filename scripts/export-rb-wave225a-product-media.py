#!/usr/bin/env python3
"""Read-only export of ProductMedia metadata for the canonical Wave224 IDs."""
from __future__ import annotations
import base64,csv,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; IMP=ROOT/'docs/imports'; GEN=ROOT/'docs/audits/generated'
MANIFESTS=[IMP/'rb-source-backed-description-stage-manifest-wave224a-2026-07-29.json',IMP/'rb-source-backed-description-stageable-wave224b-2026-07-29.json']
OUT=GEN/'rb-wave225a-product-media-export.csv'; FIELDS=['external_id','media_id','hash','storage_path','rights_basis','dimensions']
def ids():
 out=[]
 for p in MANIFESTS: out += [r['external_id'] for r in json.loads(p.read_text(encoding='utf-8-sig'))['products']]
 if len(out)!=334 or len(set(out))!=334: raise SystemExit('Wave224 ID scope drift')
 return out
def main():
 encoded=base64.b64encode(json.dumps(ids(),ensure_ascii=False).encode()).decode()
 php="""$ids=json_decode(base64_decode('%s'),true);$r=app('db')->table('product_media as pm')->join('products as p','p.id','=','pm.product_id')->whereIn('p.external_id',$ids)->select('p.external_id',app('db')->raw('pm.id as media_id'),app('db')->raw(\"coalesce(pm.content_sha256,'') as hash\"),app('db')->raw(\"coalesce(pm.storage_path,'') as storage_path\"),app('db')->raw(\"coalesce(pm.rights_basis,'') as rights_basis\"),app('db')->raw(\"'' as dimensions\"))->orderBy('p.external_id')->orderBy('pm.id')->get();echo json_encode($r,JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES);"""%encoded
 command=['docker','compose','exec','-T','backend','php','artisan','tinker',f"--execute=eval(base64_decode('{base64.b64encode(php.encode()).decode()}'));" ]
 result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace')
 if result.returncode: raise SystemExit(result.stderr or result.stdout)
 data=json.loads(result.stdout)
 if any(set(x)!=set(FIELDS) for x in data): raise SystemExit('live export field drift')
 with OUT.open('w',encoding='utf-8-sig',newline='') as h:
  w=csv.DictWriter(h,fieldnames=FIELDS,lineterminator='\n');w.writeheader();w.writerows(data)
 print(json.dumps({'mode':'read_only','ids':334,'media_rows':len(data),'database_mutations':0},ensure_ascii=False))
if __name__=='__main__':main()
