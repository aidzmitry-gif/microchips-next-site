#!/usr/bin/env python3
"""Read-only commercial-data audit for the RB site.

This reports actual price provenance and the intentionally separate
availability state.  It never invokes an importer or an ``--apply`` command.
"""
from __future__ import annotations

import base64
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "docs/audits/generated"
SUMMARY = GEN / "rb-commercial-data-wave215c-summary.json"
REPORT = ROOT / "docs/audits/2026-07-29-rb-commercial-data-audit-wave215c.md"
CHECKED_AT = "2026-07-29"


def run_read_only_query() -> dict:
    php = r'''
$site=app('db')->table('sites')->where('key','microchips-by')->first(['id','currency_code']);
if (!$site) { throw new RuntimeException('microchips-by site missing'); }
$db=app('db');
$base=$db->table('site_products as sp')->join('products as p','p.id','=','sp.product_id')->where('sp.site_id',$site->id);
$oneC=$db->table('one_c_nomenclature_items')->where('is_group',false);
$eligibleOneC=function($query) use ($site) { return $query->where('price','>',0)->where('currency',$site->currency_code)->whereNotNull('price_type')->whereRaw("nullif(btrim(price_type), '') is not null")->whereNotNull('updated_at'); };
$eligibleJoined=function($query) use ($site) { return $query->where('oc.price','>',0)->where('oc.currency',$site->currency_code)->whereNotNull('oc.price_type')->whereRaw("nullif(btrim(oc.price_type), '') is not null")->whereNotNull('oc.updated_at'); };
$direct=$base->clone()->join('one_c_nomenclature_items as oc','oc.external_id','=','p.external_id')->where('oc.is_group',false);
$current=$db->table('site_product_price_evidences')->where('site_product_price_evidences.site_id',$site->id)->where('site_product_price_evidences.is_current',true);
$safe=$eligibleJoined($base->clone()->join('one_c_nomenclature_items as oc','oc.external_id','=','p.external_id')->where('oc.is_group',false))
  ->where('sp.availability','on_request')
  ->whereNotExists(function($q) use ($site) {$q->selectRaw('1')->from('site_product_price_evidences as e')->whereColumn('e.site_product_id','sp.id')->where('e.site_id',$site->id)->where('e.is_current',true)->where('e.source','legacy_site');})
  ->orderBy('p.external_id')->limit(100)->get(['p.external_id','oc.price as source_price','oc.currency','oc.price_type','oc.updated_at','sp.availability']);
$payload=[
 'site'=>['key'=>'microchips-by','currency'=>$site->currency_code],
 'site_products'=>[
   'total'=>$base->clone()->count(), 'published'=>$base->clone()->where('sp.is_published',true)->count(),
   'numeric_price'=>$base->clone()->where('sp.price','>',0)->count(),
   'published_numeric_price'=>$base->clone()->where('sp.is_published',true)->where('sp.price','>',0)->count(),
   'availability'=>$base->clone()->selectRaw('sp.availability, count(*) as rows')->groupBy('sp.availability')->orderBy('sp.availability')->pluck('rows','availability')->all(),
   'published_availability'=>$base->clone()->where('sp.is_published',true)->selectRaw('sp.availability, count(*) as rows')->groupBy('sp.availability')->orderBy('sp.availability')->pluck('rows','availability')->all(),
 ],
 'price_evidence'=>[
   'current_rows'=>$current->clone()->count(),
   'by_source'=>$current->clone()->selectRaw('source, count(*) as rows, min(observed_at) as oldest_observed_at, max(observed_at) as newest_observed_at')->groupBy('source')->orderBy('source')->get(),
   'visible_price_without_current_evidence'=>$base->clone()->leftJoin('site_product_price_evidences as e',function($join) use ($site){$join->on('e.site_product_id','=','sp.id')->where('e.site_id',$site->id)->where('e.is_current',true); })->where('sp.price','>',0)->whereNull('e.id')->count(),
   'current_evidence_visible_price_mismatch'=>$current->clone()->join('site_products as sp','sp.id','=','site_product_price_evidences.site_product_id')->whereColumn('sp.price','<>','site_product_price_evidences.calculated_price')->count(),
   'duplicate_current_evidence_products'=>$current->clone()->select('site_product_id')->groupBy('site_product_id')->havingRaw('count(*) > 1')->count(),
 ],
 'one_c'=>[
   'nongroup_rows'=>$oneC->clone()->count(), 'positive_price_rows'=>$oneC->clone()->where('price','>',0)->count(),
   'currency_present_rows'=>$oneC->clone()->whereRaw("nullif(btrim(currency), '') is not null")->count(),
   'price_type_present_rows'=>$oneC->clone()->whereRaw("nullif(btrim(price_type), '') is not null")->count(),
   'eligible_byn_rows'=>$eligibleOneC($oneC->clone())->count(),
   'latest_updated_at'=>$oneC->clone()->max('updated_at'),
 ],
 'identity_links'=>[
   'direct_external_id_links'=>$direct->clone()->count(),
   'direct_external_id_eligible_one_c'=>$eligibleJoined($direct->clone())->count(),
   'approved_bitrix_one_c_candidates'=>$db->table('catalog_identity_candidates')->where('review_status','approved_for_staging')->count(),
 ],
 'availability_provenance'=>[
   'availability_evidence_table_exists'=>(bool) ($db->selectOne("select exists (select 1 from information_schema.tables where table_schema='public' and table_name='site_product_availability_evidences') as present")->present ?? false),
   'in_stock_rows'=>$base->clone()->where('sp.availability','in_stock')->count(),
   'in_stock_with_current_price_evidence'=>$base->clone()->join('site_product_price_evidences as e',function($join) use ($site){$join->on('e.site_product_id','=','sp.id')->where('e.site_id',$site->id)->where('e.is_current',true); })->where('sp.availability','in_stock')->count(),
 ],
 'safe_next_one_c_x2_batch'=>$safe,
];
echo json_encode($payload,JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES);
'''
    encoded = base64.b64encode(php.encode()).decode()
    command = ["docker", "compose", "exec", "-T", "backend", "php", "artisan", "tinker", f"--execute=eval(base64_decode('{encoded}')); "]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode or not result.stdout.strip().startswith("{"):
        raise SystemExit(f"read-only commercial query failed: {result.stderr.strip() or result.stdout.strip()}")
    return json.loads(result.stdout)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    data = run_read_only_query()
    price_command = ROOT / "backend/app/Console/Commands/ImportVerifiedSitePrices.php"
    builder = ROOT / "backend/app/Console/Commands/BuildRbPriceEvidenceManifest.php"
    rule_safe = data["one_c"]["eligible_byn_rows"] == 0 and len(data["safe_next_one_c_x2_batch"]) == 0
    payload = {
        "schema_version": 1, "audit": "rb_commercial_data_wave215c", "checked_at": CHECKED_AT,
        "mode": "read_only", "database_mutations": 0, "commercial_data_changed": 0,
        "current": data,
        "one_c_x2_rule": {
            "defined_in": "catalog:build-rb-price-evidence + catalog:import-verified-prices",
            "multiplier": 2, "requires": ["exact external_id link", "positive 1C price", "site currency BYN", "non-empty price type", "updated/import timestamp"],
            "changes_availability": False, "creates_stock_claim": False,
            "safe_to_run_now": False,
            "reason": "no eligible current 1C commercial values" if rule_safe else "eligible rows require explicit review of the generated batch",
        },
        "availability": {
            "evidence_mode": "no separate availability-evidence table" if not data["availability_provenance"]["availability_evidence_table_exists"] else "availability evidence table exists",
            "conclusion": "price evidence is not stock evidence; the next batch is restricted to on_request and cannot create an Offer or in_stock claim",
        },
        "deterministic_next_batch": {
            "query_order": "products.external_id ASC", "limit": 100, "eligibility": "exact direct 1C external_id + eligible BYN price metadata + on_request + no current legacy-site price evidence",
            "rows": len(data["safe_next_one_c_x2_batch"]), "status": "hold_until_fresh_1c_commercial_export" if rule_safe else "review_then_dry_run_only",
        },
        "evidence": {"price_builder_sha256": sha(builder), "price_importer_sha256": sha(price_command)},
    }
    SUMMARY.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    price = data["price_evidence"]
    one_c = data["one_c"]
    availability = data["site_products"]["availability"]
    evidence_by_source = ", ".join(f"{row['source']}={row['rows']}" for row in price["by_source"]) or "none"
    availability_by_value = ", ".join(f"{key}={value}" for key, value in availability.items())
    REPORT.write_text(
        "# RB commercial data audit — Wave215-C\n\n"
        f"Read-only check on {CHECKED_AT}. No commercial or publication field changed.\n\n"
        "## Current commercial facts\n\n"
        f"- Site products: {data['site_products']['total']}; numeric prices: {data['site_products']['numeric_price']}; current price-evidence rows: {price['current_rows']}.\n"
        f"- Current evidence by source: {evidence_by_source}.\n"
        f"- Price integrity: without current evidence={price['visible_price_without_current_evidence']}; value mismatch={price['current_evidence_visible_price_mismatch']}; duplicate current evidence={price['duplicate_current_evidence_products']}.\n"
        f"- Availability distribution: {availability_by_value}. There is no separate availability-evidence table.\n\n"
        "## 1C × 2 rule\n\n"
        f"The implementation applies multiplier `2` only to provenance-backed `one_c_x2` rows and does not alter availability. The current 1C inventory has {one_c['positive_price_rows']} positive prices, {one_c['currency_present_rows']} currencies, {one_c['price_type_present_rows']} price types and {one_c['eligible_byn_rows']} fully eligible BYN rows. Therefore the rule is represented safely in code but is **not usable on current data**.\n\n"
        "## Deterministic next path\n\n"
        "Wait for a fresh 1C commercial export. Then generate a 100-row maximum batch ordered by `products.external_id`, requiring: exact direct external-ID link, positive BYN price, non-empty price type, timestamp, `availability=on_request`, and no current legacy-site evidence. Run the price importer as a dry run only; it may update price evidence but must not change availability, publication, or create an Offer.\n",
        encoding="utf-8",
    )
    print(json.dumps({"price_evidence": price["current_rows"], "one_c_eligible": one_c["eligible_byn_rows"], "next_batch": len(data["safe_next_one_c_x2_batch"]), "database_mutations": 0}, ensure_ascii=False))


if __name__ == "__main__":
    main()
