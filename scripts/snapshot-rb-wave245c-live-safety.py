#!/usr/bin/env python3
"""Capture read-only live Bitrix/1C identity topology for the two Wave245C models."""

from __future__ import annotations

import json
import base64
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs/audits/generated/rb-wave245c-panasonic-live-safety.json"

PHP = r'''
$site=App\Models\Site::query()->where('key','microchips-by')->sole();
$products=App\Models\Product::query()->select('products.*')->selectRaw("encode(convert_to(external_id,'UTF8'),'base64') as external_id_server_b64, encode(convert_to(name,'UTF8'),'base64') as name_server_b64, case when manufacturer is null then null else encode(convert_to(manufacturer,'UTF8'),'base64') end as manufacturer_server_b64, case when mpn is null then null else encode(convert_to(mpn,'UTF8'),'base64') end as mpn_server_b64")->where(function($q){
 $q->whereIn('external_id',['bitrix:3232','bitrix:1598'])
   ->orWhereRaw("upper(name) like '%UP-VW0645P1%'")->orWhereRaw("upper(name) like '%UP-VW1220P1%'")
   ->orWhereIn('mpn_normalized',['upvw0645p1','upvw1220p1']);
})->get()->map(function($p) use($site){
 $sp=App\Models\SiteProduct::query()->where('site_id',$site->id)->where('product_id',$p->id)->with(['categories','priceEvidences'])->first();
 return ['external_id_b64'=>$p->external_id_server_b64,'product_id'=>$p->id,'name_b64'=>$p->name_server_b64,
  'manufacturer_b64'=>$p->manufacturer_server_b64,'mpn_b64'=>$p->mpn_server_b64,
  'site_product'=>$sp ? ['id'=>$sp->id,'published'=>$sp->is_published,'availability'=>$sp->availability,'price'=>$sp->price,
   'categories'=>$sp->categories->pluck('external_id')->sort()->values()->all(),
   'price_evidence_count'=>$sp->priceEvidences->count(),
   'urls'=>App\Models\SiteUrl::query()->where('site_id',$site->id)->where('target_type','product')->where('target_id',$sp->id)->get(['path','is_indexable'])->toArray(),
   'verified_published_media_count'=>$p->media()->where('verification_status','verified')->where('is_published',true)->count()] : null];
})->sortBy('external_id')->values();
echo 'WAVE245C_JSON_B64='.base64_encode(json_encode(['captured_at'=>'2026-07-30','site'=>$site->key,'rows'=>$products],JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES)).PHP_EOL;
'''


def main() -> None:
    result = subprocess.run(
        ["docker", "compose", "exec", "-T", "backend", "php", "-d", "opcache.enable_cli=0", "artisan", "tinker", f"--execute={PHP}"],
        cwd=ROOT, check=True, capture_output=True, text=True, encoding="utf-8",
    )
    marker = "WAVE245C_JSON_B64="
    line = next((line for line in result.stdout.splitlines() if line.startswith(marker)), None)
    if line is None:
        raise SystemExit(f"live snapshot marker missing: {result.stdout}{result.stderr}")
    data = json.loads(base64.b64decode(line[len(marker):]).decode("utf-8"))
    def decode_db(value: str | None) -> str | None:
        if value is None:
            return None
        raw = base64.b64decode(value)
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return raw.decode("cp1251")
    for row in data["rows"]:
        for field in ("external_id", "name", "manufacturer", "mpn"):
            row[field] = decode_db(row.pop(field + "_b64"))
    data["rows"].sort(key=lambda row: row["external_id"])
    if not {"bitrix:3232", "bitrix:1598"}.issubset({row["external_id"] for row in data["rows"]}):
        raise SystemExit("target rows absent from live snapshot")
    OUTPUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"rows": len(data["rows"]), "output": OUTPUT.relative_to(ROOT).as_posix()}))


if __name__ == "__main__":
    main()
