#!/usr/bin/env python3
"""Capture a read-only, compact live DB safety snapshot for Wave244C."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs/audits/generated/rb-wave244c-live-safety.json"
IDS = [
    "bitrix:23799", "КА-00005164", "bitrix:23811", "КА-00003200",
    "bitrix:20088", "КА-00003292", "bitrix:23818", "КА-00003237",
]


PHP = r'''
$site=App\Models\Site::query()->where('key','microchips-by')->sole();
$ids=%s;
$rows=App\Models\SiteProduct::query()->where('site_id',$site->id)
 ->whereHas('product',fn($q)=>$q->whereIn('external_id',$ids))
 ->with(['product','categories','priceEvidences'])->get()->map(function($sp) use($site){
  $paths=App\Models\SiteUrl::query()->where('site_id',$site->id)->where('target_type','product')->where('target_id',$sp->id);
  return ['external_id'=>$sp->product->external_id,'site_product_id'=>$sp->id,'product_id'=>$sp->product_id,
   'name'=>$sp->product->name,'manufacturer'=>$sp->product->manufacturer,'mpn'=>$sp->product->mpn,
   'published'=>$sp->is_published,'availability'=>$sp->availability,'price'=>$sp->price,
   'categories'=>$sp->categories->pluck('external_id')->sort()->values()->all(),
   'urls'=>$paths->get(['path','is_indexable'])->toArray(),
   'seo'=>App\Models\SiteSeo::query()->where('site_id',$site->id)->where('resource_type','product')->where('resource_id',$sp->id)->get(['locale','is_indexable','schema'])->toArray(),
   'price_evidence_count'=>$sp->priceEvidences->count(),
   'current_price_evidence'=>$sp->priceEvidences->where('is_current',true)->values()->map(fn($e)=>['calculated_price'=>$e->calculated_price,'currency'=>$e->currency])->all(),
   'family_canonical_count'=>App\Models\ProductFamily::query()->where('site_id',$site->id)->where('canonical_product_id',$sp->product_id)->count(),
   'family_variant_count'=>App\Models\ProductVariant::query()->where('product_id',$sp->product_id)->whereHas('family',fn($q)=>$q->where('site_id',$site->id))->count(),
   'verified_published_media_count'=>$sp->product->media()->where('verification_status','verified')->where('is_published',true)->count(),
   'redirect_count'=>App\Models\SiteRedirect::query()->where('site_id',$site->id)->whereIn('source_path',$paths->pluck('path'))->count()];
 })->sortBy('external_id')->values();
echo 'WAVE244C_JSON='.json_encode(['captured_at'=>'2026-07-30','site'=>$site->key,'currency'=>$site->currency_code,'rows'=>$rows],JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES).PHP_EOL;
''' % json.dumps(IDS, ensure_ascii=False)


def main() -> None:
    result = subprocess.run(
        ["docker", "compose", "exec", "-T", "backend", "php", "artisan", "tinker", f"--execute={PHP}"],
        cwd=ROOT, check=True, capture_output=True, text=True, encoding="utf-8",
    )
    marker = "WAVE244C_JSON="
    line = next((line for line in result.stdout.splitlines() if line.startswith(marker)), None)
    if line is None:
        raise SystemExit(f"live snapshot marker missing: {result.stdout}{result.stderr}")
    data = json.loads(line[len(marker):])
    if {row["external_id"] for row in data["rows"]} != set(IDS):
        raise SystemExit("live snapshot does not contain exactly the eight requested products")
    OUTPUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"rows": len(data["rows"]), "output": OUTPUT.relative_to(ROOT).as_posix()}))


if __name__ == "__main__":
    main()
