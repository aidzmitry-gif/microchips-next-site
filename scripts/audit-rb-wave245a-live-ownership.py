#!/usr/bin/env python3
"""Read-only exact live Bitrix/1C ownership audit for Wave245A Panasonic models."""

from __future__ import annotations

import base64
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/audits/generated/rb-wave245a-panasonic-live-ownership.json"
MODELS = ["LC-XC1222P", "LC-XC1228P"]


def php_query() -> str:
    return (
        "$site=App\\Models\\Site::where('key','microchips-by')->sole();$out=[];"
        "$models=['LC-XC1222P','LC-XC1228P'];"
        "foreach($models as $model){$needle=strtolower(preg_replace('/[^a-z0-9]+/i','',$model));"
        "$hits=App\\Models\\Product::query()->whereRaw(\"regexp_replace(lower(coalesce(mpn,'')), '[^a-z0-9]', '', 'g') = ?\",[$needle])->orWhereRaw(\"regexp_replace(lower(coalesce(name,'')), '[^a-z0-9]', '', 'g') like ?\",['%'.$needle.'%'])->get();$rows=[];"
        "foreach($hits as $p){$sps=App\\Models\\SiteProduct::where('site_id',$site->id)->where('product_id',$p->id)->get();$sp=$sps->first();"
        "$urls=$sp?App\\Models\\SiteUrl::where('site_id',$site->id)->where('target_type','product')->where('target_id',$sp->id)->get(['path','is_indexable'])->toArray():[];"
        "$categories=$sp?$sp->categories()->pluck('site_categories.external_id')->filter()->sort()->values()->all():[];"
        "$rows[]=['product_id'=>$p->id,'external_id'=>$p->external_id,'namespace'=>str_contains((string)$p->external_id,':')?explode(':',$p->external_id,2)[0]:'unknown','name'=>$p->name,'manufacturer'=>$p->manufacturer,'mpn'=>$p->mpn,'status'=>$p->status,'site_product_count'=>$sps->count(),'site_product_id'=>$sp?->id,'is_published'=>(bool)($sp?->is_published),'availability'=>$sp?->availability,'price'=>$sp?->price,'current_price_evidence'=>$sp?$sp->priceEvidences()->where('is_current',true)->count():0,'verified_published_media'=>App\\Models\\ProductMedia::where('product_id',$p->id)->where('verification_status','verified')->where('is_published',true)->count(),'categories'=>$categories,'urls'=>$urls];}"
        "$out[]=['model'=>$model,'hits'=>$rows];}echo json_encode($out,JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES);"
    )


def main() -> None:
    encoded = base64.b64encode(php_query().encode()).decode()
    expression = f"eval(base64_decode('{encoded}'));"
    process = subprocess.run(
        ["docker", "compose", "exec", "-T", "backend", "php", "artisan", "tinker", f"--execute={expression}"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )
    payload = process.stdout.strip()
    if process.returncode != 0 or not payload.startswith("["):
        raise SystemExit(f"Live query failed: {payload or process.stderr.strip()}")
    rows = json.loads(payload)
    if [row["model"] for row in rows] != MODELS:
        raise SystemExit("Live query model/cardinality drift")
    result = {"schema_version": 1, "site_key": "microchips-by", "checked_at": "2026-07-30", "models": rows, "database_operations": 0}
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
