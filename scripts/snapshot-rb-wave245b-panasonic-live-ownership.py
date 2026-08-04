#!/usr/bin/env python3
"""Capture read-only live ownership evidence for exactly two Wave245B rows."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs/audits/sources/wave245b-panasonic-new-rows/live-db-ownership-snapshot.json"
IDS = ["bitrix:1596", "bitrix:1159"]
PHP = r'''
$site=App\Models\Site::query()->where('key','microchips-by')->sole();
$ids=['bitrix:1596','bitrix:1159'];
$models=['LC-XC1238P','LC-XD1217PG'];
$targets=App\Models\Product::query()->whereIn('external_id',$ids)->get()->map(function($p) use($site){
 $sp=App\Models\SiteProduct::query()->where('site_id',$site->id)->where('product_id',$p->id)->first();
 return ['external_id'=>$p->external_id,'name'=>$p->name,'manufacturer'=>$p->manufacturer,'mpn'=>$p->mpn,
  'status'=>$p->status,'site_product_count'=>App\Models\SiteProduct::query()->where('site_id',$site->id)->where('product_id',$p->id)->count(),
  'site_product_id'=>$sp?->id,'is_published'=>$sp?->is_published,'availability'=>$sp?->availability,'price'=>$sp?->price,
  'verified_published_media_count'=>$p->media()->where('verification_status','verified')->where('is_published',true)->count()];
})->sortBy('external_id')->values();
$candidates=App\Models\Product::query()->where(function($q) use($models){foreach($models as $m){$q->orWhere('name','ilike','%'.$m.'%')->orWhere('mpn','ilike','%'.$m.'%');}})
 ->get()->map(fn($p)=>['external_id'=>$p->external_id,'name'=>$p->name,'manufacturer'=>$p->manufacturer,'mpn'=>$p->mpn,'status'=>$p->status])->sortBy('external_id')->values();
echo 'WAVE245B_JSON='.json_encode(['checked_at'=>'2026-07-30','site_key'=>$site->key,'target_rows'=>$targets,'exact_model_candidates'=>$candidates],JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES).PHP_EOL;
'''


def main() -> None:
    result = subprocess.run(
        ["docker", "compose", "exec", "-T", "backend", "php", "artisan", "tinker", f"--execute={PHP}"],
        cwd=ROOT, check=True, capture_output=True, text=True, encoding="utf-8",
    )
    marker = "WAVE245B_JSON="
    line = next((line for line in result.stdout.splitlines() if line.startswith(marker)), None)
    if line is None:
        raise SystemExit(f"snapshot marker missing: {result.stdout}{result.stderr}")
    payload = json.loads(line[len(marker):])
    if {row["external_id"] for row in payload["target_rows"]} != set(IDS):
        raise SystemExit("live snapshot does not contain exactly the two requested queue rows")
    non_targets = [row for row in payload["exact_model_candidates"] if row["external_id"] not in IDS]
    payload["exact_non_target_owner_candidates"] = non_targets
    payload["ownership_decision"] = "NO_EXACT_1C_OWNER" if not non_targets else "HOLD_EXACT_OWNER_EXISTS"
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"targets": len(payload["target_rows"]), "non_target_owners": len(non_targets), "decision": payload["ownership_decision"]}))


if __name__ == "__main__":
    main()
