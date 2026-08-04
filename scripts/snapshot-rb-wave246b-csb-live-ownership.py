#!/usr/bin/env python3
"""Capture read-only exact-owner evidence for the 92-row Wave246B CSB partition."""

from __future__ import annotations

import csv
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCOPE = ROOT / "docs/audits/generated/rb-wave246-b2b-scope.csv"
OUTPUT = ROOT / "docs/audits/sources/wave246b-csb/live-db-exact-owner-snapshot.json"


def normalized(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def name_has_exact_model(name: str, model: str) -> bool:
    pieces = [re.escape(piece) for piece in re.findall(r"[A-Z0-9]+", model.upper())]
    pattern = r"(?<![A-Z0-9])" + r"[^A-Z0-9]*".join(pieces) + r"(?![A-Z0-9])"
    return bool(re.search(pattern, name.upper()))


def main() -> None:
    with SCOPE.open(encoding="utf-8-sig", newline="") as handle:
        scope = [row for row in csv.DictReader(handle) if row["partition"] == "csb"]
    if len(scope) != 92 or len({row["product_external_id"] for row in scope}) != 92:
        raise SystemExit("Wave246B CSB scope must contain exactly 92 unique rows")
    ids = [row["product_external_id"] for row in scope]
    php = r'''
$site=App\Models\Site::query()->where('key','microchips-by')->sole();
$ids=%s;
$targets=App\Models\Product::query()->whereIn('external_id',$ids)->get()->map(function($p) use($site){
 $sp=App\Models\SiteProduct::query()->where('site_id',$site->id)->where('product_id',$p->id)->first();
 return ['external_id'=>$p->external_id,'name'=>$p->name,'manufacturer'=>$p->manufacturer,'mpn'=>$p->mpn,'sku'=>$p->sku,'status'=>$p->status,
  'site_product_count'=>App\Models\SiteProduct::query()->where('site_id',$site->id)->where('product_id',$p->id)->count(),
  'site_product_id'=>$sp?->id,'is_published'=>$sp?->is_published,'availability'=>$sp?->availability,'price'=>$sp?->price,
  'verified_published_media_count'=>$p->media()->where('verification_status','verified')->where('is_published',true)->count()];
})->sortBy('external_id')->values();
$pool=App\Models\Product::query()->where(function($q){$q->whereNotNull('mpn')->orWhereNotNull('sku')->orWhere('manufacturer','ilike','%%CSB%%')->orWhere('name','ilike','%%CSB%%');})
 ->get()->map(fn($p)=>['external_id'=>$p->external_id,'name'=>$p->name,'manufacturer'=>$p->manufacturer,'mpn'=>$p->mpn,'sku'=>$p->sku,'status'=>$p->status])->sortBy('external_id')->values();
echo 'WAVE246B_JSON='.json_encode(['checked_at'=>'2026-07-30','site_key'=>$site->key,'target_rows'=>$targets,'csb_candidate_pool'=>$pool],JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES).PHP_EOL;
''' % json.dumps(ids, ensure_ascii=False)
    result = subprocess.run(
        ["docker", "compose", "exec", "-T", "backend", "php", "artisan", "tinker", f"--execute={php}"],
        cwd=ROOT, check=True, capture_output=True, text=True, encoding="utf-8",
    )
    marker = "WAVE246B_JSON="
    line = next((line for line in result.stdout.splitlines() if line.startswith(marker)), None)
    if line is None:
        raise SystemExit(f"snapshot marker missing: {result.stdout}{result.stderr}")
    raw = json.loads(line[len(marker):])
    if {row["external_id"] for row in raw["target_rows"]} != set(ids):
        raise SystemExit("live snapshot does not contain all 92 targets")
    pool = raw.pop("csb_candidate_pool")
    by_id = {row["external_id"]: row for row in raw["target_rows"]}
    ownership = []
    for item in scope:
        external_id, mpn = item["product_external_id"], item["mpn"]
        matches = []
        for candidate in pool:
            if candidate["external_id"] == external_id:
                continue
            exact_structured = normalized(candidate.get("mpn") or candidate.get("sku") or "") == normalized(mpn)
            exact_name = not (candidate.get("mpn") or candidate.get("sku")) and name_has_exact_model(candidate["name"], mpn)
            if exact_structured or exact_name:
                matches.append({**candidate, "match_basis": "normalized_mpn_or_sku" if exact_structured else "exact_name_token"})
        ownership.append({
            "external_id": external_id,
            "mpn": mpn,
            "target": by_id[external_id],
            "exact_non_target_owner_candidates": matches,
            "decision": "NO_EXACT_NON_TARGET_OWNER" if not matches else "HOLD_EXACT_NON_TARGET_OWNER",
        })
    raw["ownership"] = ownership
    raw["counts"] = {
        "targets": len(ownership),
        "no_exact_non_target_owner": sum(row["decision"] == "NO_EXACT_NON_TARGET_OWNER" for row in ownership),
        "hold_exact_non_target_owner": sum(row["decision"] == "HOLD_EXACT_NON_TARGET_OWNER" for row in ownership),
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(raw["counts"], sort_keys=True))


if __name__ == "__main__":
    main()
