#!/usr/bin/env python3
"""Capture the read-only live owner/collision state for Wave246C Delta/Leoch."""

from __future__ import annotations

import base64
import csv
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCOPE = ROOT / "docs/audits/generated/rb-wave246-b2b-scope.csv"
OUTPUT = ROOT / "docs/audits/generated/rb-wave246c-delta-leoch-live-safety.json"
CAPTURED_AT = "2026-07-30"


def scope_ids() -> list[str]:
    with SCOPE.open(encoding="utf-8-sig", newline="") as handle:
        rows = [row for row in csv.DictReader(handle) if row["partition"] == "delta_leoch"]
    ids = [row["product_external_id"] for row in rows]
    if len(ids) != 92 or len(set(ids)) != 92:
        raise SystemExit("Wave246C scope drift: expected 92 unique delta_leoch rows")
    return ids


def decode_db(value: str | None) -> str | None:
    if value is None:
        return None
    raw = base64.b64decode(value)
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1251")


def main() -> None:
    targets = scope_ids()
    encoded_ids = base64.b64encode(json.dumps(targets, ensure_ascii=False).encode()).decode()
    php = r'''
$site=App\Models\Site::query()->where('key','microchips-by')->sole();
$targetIds=json_decode(base64_decode('__TARGET_IDS_B64__'),true,512,JSON_THROW_ON_ERROR);
$targets=App\Models\Product::query()->whereIn('external_id',$targetIds)->get();
$fingerprints=$targets->flatMap(fn($p)=>[$p->mpn_normalized,$p->sku_normalized])->filter()->unique()->values();
$products=App\Models\Product::query()
 ->select('products.*')
 ->selectRaw("encode(convert_to(external_id,'UTF8'),'base64') as external_id_server_b64, encode(convert_to(name,'UTF8'),'base64') as name_server_b64, case when manufacturer is null then null else encode(convert_to(manufacturer,'UTF8'),'base64') end as manufacturer_server_b64, case when mpn is null then null else encode(convert_to(mpn,'UTF8'),'base64') end as mpn_server_b64, case when sku is null then null else encode(convert_to(sku,'UTF8'),'base64') end as sku_server_b64")
 ->where(function($q) use($targetIds,$fingerprints){
   $q->whereIn('external_id',$targetIds);
   if($fingerprints->isNotEmpty()) $q->orWhereIn('mpn_normalized',$fingerprints)->orWhereIn('sku_normalized',$fingerprints);
 })->get()->map(function($p) use($site,$targetIds){
   $sp=App\Models\SiteProduct::query()->where('site_id',$site->id)->where('product_id',$p->id)->with(['categories','priceEvidences'])->first();
   return ['is_scope_target'=>in_array($p->external_id,$targetIds,true),'external_id_b64'=>$p->external_id_server_b64,
    'product_id'=>$p->id,'name_b64'=>$p->name_server_b64,'manufacturer_b64'=>$p->manufacturer_server_b64,
    'mpn_b64'=>$p->mpn_server_b64,'sku_b64'=>$p->sku_server_b64,'mpn_normalized'=>$p->mpn_normalized,
    'sku_normalized'=>$p->sku_normalized,'site_product'=>$sp ? ['id'=>$sp->id,'published'=>$sp->is_published,
     'availability'=>$sp->availability,'price'=>$sp->price,'categories'=>$sp->categories->pluck('external_id')->sort()->values()->all(),
     'price_evidence_count'=>$sp->priceEvidences->count(),'urls'=>App\Models\SiteUrl::query()->where('site_id',$site->id)
      ->where('target_type','product')->where('target_id',$sp->id)->get(['path','is_indexable'])->toArray(),
     'verified_published_media_count'=>$p->media()->where('verification_status','verified')->where('is_published',true)->count()]:null];
 })->sortBy(fn($r)=>base64_decode($r['external_id_b64']))->values();
echo 'WAVE246C_JSON_B64='.base64_encode(json_encode(['captured_at'=>'__CAPTURED_AT__','site'=>$site->key,
 'requested_target_count'=>count($targetIds),'matched_target_count'=>$targets->count(),'fingerprints'=>$fingerprints,
 'rows'=>$products],JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES)).PHP_EOL;
'''.replace("__TARGET_IDS_B64__", encoded_ids).replace("__CAPTURED_AT__", CAPTURED_AT)
    result = subprocess.run(
        ["docker", "compose", "exec", "-T", "backend", "php", "-d", "opcache.enable_cli=0", "artisan", "tinker", f"--execute={php}"],
        cwd=ROOT, check=False, capture_output=True, text=True, encoding="utf-8",
    )
    if result.returncode:
        raise SystemExit(f"live snapshot failed ({result.returncode}): {result.stderr or result.stdout}")
    marker = "WAVE246C_JSON_B64="
    line = next((line for line in result.stdout.splitlines() if line.startswith(marker)), None)
    if line is None:
        raise SystemExit(f"live snapshot marker missing: {result.stdout}{result.stderr}")
    data = json.loads(base64.b64decode(line[len(marker):]).decode("utf-8"))
    for row in data["rows"]:
        for field in ("external_id", "name", "manufacturer", "mpn", "sku"):
            row[field] = decode_db(row.pop(field + "_b64"))
    data["rows"].sort(key=lambda row: row["external_id"])
    matched = {row["external_id"] for row in data["rows"] if row["is_scope_target"]}
    if matched != set(targets) or data["matched_target_count"] != 92:
        raise SystemExit(f"live target mismatch: missing={sorted(set(targets)-matched)} extra={sorted(matched-set(targets))}")
    OUTPUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"targets": len(matched), "topology_rows": len(data["rows"]), "output": OUTPUT.relative_to(ROOT).as_posix()}))


if __name__ == "__main__":
    main()
