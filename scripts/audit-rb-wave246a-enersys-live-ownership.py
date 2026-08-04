#!/usr/bin/env python3
"""Read-only live exact-owner snapshot for all 92 Wave246A EnerSys rows."""
from __future__ import annotations
import base64, csv, json, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCOPE = ROOT / "docs/audits/generated/rb-wave246-b2b-scope.csv"
OUT = ROOT / "docs/audits/generated/rb-wave246a-enersys-live-ownership.json"

def php_query(targets: list[dict[str,str]]) -> str:
    payload = json.dumps([{"external_id":r["product_external_id"],"mpn":r["mpn"]} for r in targets], ensure_ascii=False)
    encoded = base64.b64encode(payload.encode()).decode()
    return (
        f"$targets=json_decode(base64_decode('{encoded}'),true);"
        "$site=App\\Models\\Site::where('key','microchips-by')->sole();"
        "$pool=App\\Models\\Product::query()->whereRaw(\"lower(coalesce(manufacturer,''))='enersys'\")->orWhereRaw(\"lower(name) like '%enersys%'\")->get();$out=[];"
        "foreach($targets as $t){$needle=strtolower(preg_replace('/[^a-z0-9]+/i','',$t['mpn']));$tokens=preg_split('/[^A-Za-z0-9]+/',$t['mpn'],-1,PREG_SPLIT_NO_EMPTY);$pattern='/(?<![A-Za-z0-9])'.implode('[^A-Za-z0-9]*',array_map(fn($x)=>preg_quote($x,'/'),$tokens)).(str_contains($t['mpn'],'+')?'\\+':'').'(?![A-Za-z0-9])/i';$hits=[];"
        "foreach($pool as $p){$norm=strtolower(preg_replace('/[^a-z0-9]+/i','',(string)$p->mpn));$name=strtolower(preg_replace('/[^a-z0-9]+/i','',(string)$p->name));"
        "$nameMatch=$norm===''&&preg_match($pattern,(string)$p->name)===1;if($norm!==$needle&&!$nameMatch){continue;}"
        "$sps=App\\Models\\SiteProduct::where('site_id',$site->id)->where('product_id',$p->id)->get();$sp=$sps->first();"
        "$hits[]=['external_id'=>$p->external_id,'namespace'=>str_contains((string)$p->external_id,':')?explode(':',$p->external_id,2)[0]:'unknown','name'=>$p->name,'manufacturer'=>$p->manufacturer,'mpn'=>$p->mpn,'status'=>$p->status,'site_product_count'=>$sps->count(),'is_published'=>(bool)($sp?->is_published),'availability'=>$sp?->availability,'price'=>$sp?->price,'current_price_evidence'=>$sp?$sp->priceEvidences()->where('is_current',true)->count():0,'verified_published_media'=>App\\Models\\ProductMedia::where('product_id',$p->id)->where('verification_status','verified')->where('is_published',true)->count()];}"
        "$out[]=['external_id'=>$t['external_id'],'mpn'=>$t['mpn'],'hits'=>$hits];}echo json_encode($out,JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES);"
    )

def main() -> None:
    rows=[r for r in csv.DictReader(SCOPE.open(encoding="utf-8-sig",newline="")) if r["partition"]=="enersys"]
    if len(rows)!=92: raise SystemExit(f"EnerSys scope drift: {len(rows)}")
    encoded=base64.b64encode(php_query(rows).encode()).decode(); expression=f"eval(base64_decode('{encoded}'));"
    p=subprocess.run(["docker","compose","exec","-T","backend","php","artisan","tinker",f"--execute={expression}"],cwd=ROOT,capture_output=True,text=True,encoding="utf-8",errors="replace")
    raw=p.stdout.strip()
    if p.returncode or not raw.startswith("["): raise SystemExit(f"Live query failed: {raw or p.stderr.strip()}")
    data=json.loads(raw)
    if len(data)!=92: raise SystemExit("Live result cardinality drift")
    result={"schema_version":1,"site_key":"microchips-by","checked_at":"2026-07-30","rows":data,"database_operations":0}
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); print(json.dumps({"rows":len(data),"hit_counts":{str(n):sum(len(r['hits'])==n for r in data) for n in sorted({len(r['hits']) for r in data})}},ensure_ascii=False))
if __name__=="__main__": main()
