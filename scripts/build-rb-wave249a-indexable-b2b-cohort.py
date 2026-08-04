#!/usr/bin/env python3
"""Build a fail-closed, read-only Wave249A RB indexable B2B cohort.

The output is evidence for a later release transaction, not a publication
manifest.  Every selected card already has a unique exact catalogue identity,
an applied source-backed description, storefront-ready verified media, a
single noindex canonical URL, and no unresolved duplicate/identity conflict.
Visible numeric prices are allowed only when a single current pinned evidence
row matches the storefront price and is no older than the release policy.
"""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import subprocess
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "docs" / "audits" / "generated"
OUTPUT_JSON = GENERATED / "rb-wave249a-indexable-b2b-cohort-2026-07-30.json"
OUTPUT_CSV = GENERATED / "rb-wave249a-indexable-b2b-cohort-2026-07-30.csv"
SITE_KEY = "microchips-by"
AS_OF = date(2026, 7, 30)
PRICE_CUTOFF = "2026-06-30 00:00:00+03"
LIMIT = 100

CATEGORY_RANK = {
    "seo:ups-systems": 1,
    "seo:batteries-traction": 2,
    "seo:batteries-industrial": 3,
    "seo:power-systems": 4,
    "seo:power-converters": 5,
    "seo:power-supplies": 6,
    "seo:batteries-ups": 7,
    "seo:replacement-batteries": 8,
}

SOURCE_PAIRS = {
    ("official_manufacturer_catalogue", "manufacturer_primary"),
    ("official_manufacturer_product_page", "manufacturer_primary"),
    ("official_dealer_product_page", "dealer_backed"),
}

CSV_FIELDS = [
    "cohort_order", "release_score", "product_external_id", "product_id",
    "site_product_id", "name", "manufacturer", "mpn", "category_external_id",
    "category_name", "canonical_path", "description_characters",
    "description_source_kind", "description_source_tier",
    "description_identity_scope", "description_source_checked_at",
    "description_source_urls", "verified_media_count", "verified_media_ids",
    "visible_price_byn", "price_evidence_status", "availability",
    "identity_pair_catalogue_count", "product_url_count", "seo_record_count",
    "open_duplicate_conflict_count", "unresolved_identity_candidate_count",
    "release_decision", "remaining_action",
]


class CohortError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def integer(value: Any) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError) as error:
        raise CohortError(f"invalid integer evidence field: {value!r}") from error


def truth(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}


def valid_https(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc)


def decode_json_list(value: Any, field: str) -> list[Any]:
    if isinstance(value, list):
        decoded = value
    else:
        try:
            decoded = json.loads(str(value or ""))
        except json.JSONDecodeError as error:
            raise CohortError(f"invalid {field} JSON") from error
    if not isinstance(decoded, list):
        raise CohortError(f"{field} must be a JSON list")
    return decoded


def query_live_snapshot() -> dict[str, Any]:
    """Read all release evidence from the running DB without mutations."""
    categories = ",".join(repr(value) for value in CATEGORY_RANK)
    php = f'''
$site=app('db')->table('sites')->where('key','{SITE_KEY}')->first(['id','key','currency_code','default_locale']);
if (!$site) {{ throw new RuntimeException('microchips-by site missing'); }}
$rows=app('db')->table('site_products as sp')
 ->join('products as p','p.id','=','sp.product_id')
 ->join('site_category_product as scp',function($join) use($site) {{$join->on('scp.site_product_id','=','sp.id')->where('scp.site_id',$site->id);}})
 ->join('site_categories as sc',function($join) use($site) {{$join->on('sc.id','=','scp.site_category_id')->where('sc.site_id',$site->id);}})
 ->where('sp.site_id',$site->id)->where('sp.is_published',true)->whereIn('sc.external_id',[{categories}])
 ->orderBy('p.external_id')->get([
   'p.id as product_id','p.external_id','p.name','p.manufacturer','p.mpn',
   'p.mpn_normalized','p.short_description',
   'sp.id as site_product_id','sp.is_published','sp.price','sp.availability',
   'sc.external_id as category_external_id','sc.name as category_name',
   app('db')->raw("(select count(*) from product_media pm where pm.product_id=p.id and pm.kind='image' and pm.verification_status='verified' and pm.is_published=true and pm.storage_path is not null and pm.rights_basis is not null) as verified_media_count"),
   app('db')->raw("coalesce((select json_agg(pm.id order by pm.sort_order,pm.id)::text from product_media pm where pm.product_id=p.id and pm.kind='image' and pm.verification_status='verified' and pm.is_published=true and pm.storage_path is not null and pm.rights_basis is not null),'[]') as verified_media_ids"),
   app('db')->raw("(select count(*) from product_description_drafts d where d.product_id=p.id and d.locale='ru-BY' and d.status='applied' and d.content=p.short_description) as matching_applied_description_count"),
   app('db')->raw("(select d.source_urls::text from product_description_drafts d where d.product_id=p.id and d.locale='ru-BY' and d.status='applied' and d.content=p.short_description order by d.id desc limit 1) as description_source_urls"),
   app('db')->raw("(select d.source_kind from product_description_drafts d where d.product_id=p.id and d.locale='ru-BY' and d.status='applied' and d.content=p.short_description order by d.id desc limit 1) as description_source_kind"),
   app('db')->raw("(select d.source_tier from product_description_drafts d where d.product_id=p.id and d.locale='ru-BY' and d.status='applied' and d.content=p.short_description order by d.id desc limit 1) as description_source_tier"),
   app('db')->raw("(select d.identity_scope from product_description_drafts d where d.product_id=p.id and d.locale='ru-BY' and d.status='applied' and d.content=p.short_description order by d.id desc limit 1) as description_identity_scope"),
   app('db')->raw("(select d.source_checked_at from product_description_drafts d where d.product_id=p.id and d.locale='ru-BY' and d.status='applied' and d.content=p.short_description order by d.id desc limit 1) as description_source_checked_at"),
   app('db')->raw("(select count(*) from site_urls u where u.site_id={{$site->id}} and u.target_type='product' and u.target_id=sp.id) as product_url_count"),
   app('db')->raw("(select u.path from site_urls u where u.site_id={{$site->id}} and u.target_type='product' and u.target_id=sp.id order by u.id limit 1) as product_path"),
   app('db')->raw("(select u.is_indexable from site_urls u where u.site_id={{$site->id}} and u.target_type='product' and u.target_id=sp.id order by u.id limit 1) as url_is_indexable"),
   app('db')->raw("(select count(*) from site_seos seo where seo.site_id={{$site->id}} and seo.locale='ru-BY' and seo.resource_type='product' and seo.resource_id=sp.id) as seo_record_count"),
   app('db')->raw("(select seo.canonical_path from site_seos seo where seo.site_id={{$site->id}} and seo.locale='ru-BY' and seo.resource_type='product' and seo.resource_id=sp.id order by seo.id limit 1) as seo_canonical_path"),
   app('db')->raw("(select seo.is_indexable from site_seos seo where seo.site_id={{$site->id}} and seo.locale='ru-BY' and seo.resource_type='product' and seo.resource_id=sp.id order by seo.id limit 1) as seo_is_indexable"),
   app('db')->raw("(select count(*) from site_redirects r where r.site_id={{$site->id}} and r.is_active=true and r.source_path=(select u2.path from site_urls u2 where u2.site_id={{$site->id}} and u2.target_type='product' and u2.target_id=sp.id order by u2.id limit 1)) as canonical_redirect_source_count"),
   app('db')->raw("(select count(*) from site_product_price_evidences pe where pe.site_id={{$site->id}} and pe.site_product_id=sp.id and pe.is_current=true) as current_price_evidence_count"),
   app('db')->raw("(select count(*) from site_product_price_evidences pe where pe.site_id={{$site->id}} and pe.site_product_id=sp.id and pe.is_current=true and pe.currency='BYN' and pe.calculated_price=sp.price and pe.observed_at >= timestamp with time zone '{PRICE_CUTOFF}' and pe.evidence_key is not null and pe.source_reference is not null) as fresh_matching_price_evidence_count"),
   app('db')->raw("(select count(*) from duplicate_conflicts dc cross join lateral jsonb_array_elements_text(dc.candidate_ids::jsonb) cid where dc.status='open' and cid.value in (p.id::text,p.external_id)) as open_duplicate_conflict_count"),
   app('db')->raw("(select count(*) from catalog_identity_candidates cic where cic.legacy_source='bitrix' and cic.legacy_id=replace(p.external_id,'bitrix:','') and cic.review_status not in ('approved','rejected','resolved')) as unresolved_identity_candidate_count")
 ]);
$identityPairCounts=[];
foreach (app('db')->table('products')->get(['manufacturer','mpn']) as $identity) {{
 $manufacturerNormalized=\\App\\Domain\\Imports\\ProductIdentity::normalize($identity->manufacturer);
 $mpnNormalized=\\App\\Domain\\Imports\\ProductIdentity::normalize($identity->mpn);
 if ($manufacturerNormalized && $mpnNormalized) {{
  $pairKey=$manufacturerNormalized."\0".$mpnNormalized;
  $identityPairCounts[$pairKey]=($identityPairCounts[$pairKey] ?? 0)+1;
 }}
}}
foreach ($rows as $row) {{
 $row->manufacturer_normalized=\\App\\Domain\\Imports\\ProductIdentity::normalize($row->manufacturer);
 $row->mpn_normalized=\\App\\Domain\\Imports\\ProductIdentity::normalize($row->mpn);
 $pairKey=($row->manufacturer_normalized ?? '')."\0".($row->mpn_normalized ?? '');
 $row->identity_pair_catalogue_count=$identityPairCounts[$pairKey] ?? 0;
}}
$meta=[
 'open_duplicate_conflicts'=>(int) app('db')->table('duplicate_conflicts')->where('status','open')->count(),
 'unresolved_identity_candidates'=>(int) app('db')->table('catalog_identity_candidates')->whereNotIn('review_status',['approved','rejected','resolved'])->count(),
 'duplicate_site_url_paths'=>(int) app('db')->table('site_urls')->where('site_id',$site->id)->select('path')->groupBy('path')->havingRaw('count(*) > 1')->get()->count(),
];
// Docker Desktop on Windows may transcode non-ASCII console output before
// Python receives it.  Transfer the JSON as ASCII base64 so product names and
// source metadata survive the read-only snapshot byte-for-byte.
echo base64_encode(json_encode(['site_key'=>$site->key,'currency'=>$site->currency_code,'locale'=>$site->default_locale,'rows'=>$rows,'meta'=>$meta],JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES|JSON_THROW_ON_ERROR));
'''
    encoded = base64.b64encode(php.encode("utf-8")).decode("ascii")
    result = subprocess.run(
        ["docker", "compose", "exec", "-T", "backend", "php", "artisan", "tinker",
         f"--execute=eval(base64_decode('{encoded}')); "],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise CohortError(f"live read-only query failed: {result.stderr.strip() or result.stdout.strip()}")
    try:
        payload = base64.b64decode(result.stdout.strip(), validate=True).decode("utf-8")
        return json.loads(payload)
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CohortError("live read-only query returned an invalid base64 JSON payload") from error


def choose_primary_categories(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    chosen: dict[str, dict[str, Any]] = {}
    for raw in rows:
        external_id = str(raw.get("external_id") or "").strip()
        category = str(raw.get("category_external_id") or "").strip()
        if not external_id or category not in CATEGORY_RANK:
            raise CohortError("live snapshot contains an invalid B2B product/category row")
        prior = chosen.get(external_id)
        if prior is None or CATEGORY_RANK[category] < CATEGORY_RANK[str(prior["category_external_id"])]:
            chosen[external_id] = raw
    return list(chosen.values())


def provenance(row: dict[str, Any]) -> tuple[bool, list[str], str]:
    try:
        urls = decode_json_list(row.get("description_source_urls"), "description_source_urls")
    except CohortError:
        return False, [], "description_source_urls_invalid"
    if not urls or any(not isinstance(url, str) or not valid_https(url) for url in urls):
        return False, [], "description_source_urls_invalid"
    pair = (str(row.get("description_source_kind") or ""), str(row.get("description_source_tier") or ""))
    if pair not in SOURCE_PAIRS:
        return False, urls, "description_source_policy_invalid"
    scope = str(row.get("description_identity_scope") or "")
    if scope not in {"exact", "model_core"}:
        return False, urls, "description_identity_scope_invalid"
    try:
        checked = date.fromisoformat(str(row.get("description_source_checked_at") or ""))
    except ValueError:
        return False, urls, "description_checked_at_invalid"
    if checked > AS_OF:
        return False, urls, "description_checked_at_in_future"
    return True, urls, ""


def build(snapshot: dict[str, Any]) -> tuple[list[dict[str, str]], dict[str, Any]]:
    if snapshot.get("site_key") != SITE_KEY or snapshot.get("currency") != "BYN" or snapshot.get("locale") != "ru-BY":
        raise CohortError("expected the live ru-BY/BYN microchips-by site")
    raw_rows = snapshot.get("rows")
    meta = snapshot.get("meta")
    if not isinstance(raw_rows, list) or not isinstance(meta, dict):
        raise CohortError("snapshot rows/meta contract is invalid")
    if integer(meta.get("duplicate_site_url_paths", 0)) != 0:
        raise CohortError("site URL path uniqueness is not proven")

    candidates: list[dict[str, Any]] = []
    excluded: Counter[str] = Counter()
    invalid_provenance_pairs: Counter[str] = Counter()
    price_only_blockers: list[dict[str, str]] = []
    for row in choose_primary_categories(raw_rows):
        manufacturer = str(row.get("manufacturer") or "").strip()
        mpn = str(row.get("mpn") or "").strip()
        manufacturer_normalized = str(row.get("manufacturer_normalized") or "").strip()
        mpn_normalized = str(row.get("mpn_normalized") or "").strip()
        description = str(row.get("short_description") or "").strip()
        if not truth(row.get("is_published")):
            excluded["not_published"] += 1
            continue
        if not manufacturer or not mpn or not manufacturer_normalized or not mpn_normalized:
            excluded["identity_incomplete"] += 1
            continue
        if integer(row.get("identity_pair_catalogue_count")) != 1:
            excluded["identity_pair_collision"] += 1
            continue
        if len(description) < 200:
            excluded["description_under_200"] += 1
            continue
        if integer(row.get("matching_applied_description_count")) < 1:
            excluded["matching_applied_description_missing"] += 1
            continue
        provenance_ok, source_urls, provenance_error = provenance(row)
        if not provenance_ok:
            excluded[provenance_error] += 1
            invalid_provenance_pairs[
                f"{str(row.get('description_source_kind') or '<blank>')}|"
                f"{str(row.get('description_source_tier') or '<blank>')}"
            ] += 1
            continue
        if integer(row.get("verified_media_count")) < 1:
            excluded["exact_verified_published_media_missing"] += 1
            continue
        media_ids = decode_json_list(row.get("verified_media_ids"), "verified_media_ids")
        if not media_ids:
            excluded["verified_media_id_evidence_missing"] += 1
            continue
        if integer(row.get("product_url_count")) != 1 or integer(row.get("seo_record_count")) != 1:
            excluded["canonical_url_or_seo_cardinality_invalid"] += 1
            continue
        path = str(row.get("product_path") or "").strip()
        if not path.startswith("/") or path != str(row.get("seo_canonical_path") or "").strip():
            excluded["canonical_path_mismatch"] += 1
            continue
        if truth(row.get("url_is_indexable")) or truth(row.get("seo_is_indexable")):
            excluded["not_currently_noindex"] += 1
            continue
        if integer(row.get("canonical_redirect_source_count")) != 0:
            excluded["canonical_path_is_active_redirect_source"] += 1
            continue
        if integer(row.get("open_duplicate_conflict_count")) != 0:
            excluded["open_duplicate_conflict"] += 1
            continue
        if integer(row.get("unresolved_identity_candidate_count")) != 0:
            excluded["unresolved_identity_candidate"] += 1
            continue
        if str(row.get("availability") or "") != "on_request":
            excluded["availability_not_release_policy"] += 1
            continue
        price = str(row.get("price") or "").strip()
        if price:
            if integer(row.get("current_price_evidence_count")) != 1 or integer(row.get("fresh_matching_price_evidence_count")) != 1:
                excluded["visible_price_not_fresh_unique_and_pinned"] += 1
                price_only_blockers.append({
                    "product_external_id": str(row["external_id"]),
                    "name": str(row["name"]),
                    "manufacturer": manufacturer,
                    "mpn": mpn,
                    "visible_price_byn": price,
                    "current_price_evidence_count": str(row["current_price_evidence_count"]),
                    "fresh_matching_price_evidence_count": str(row["fresh_matching_price_evidence_count"]),
                    "safe_next_action": "CLEAR_STALE_VISIBLE_PRICE_OR_IMPORT_FRESH_PINNED_PRICE_EVIDENCE",
                })
                continue
            price_status = "fresh_unique_matching_pinned"
        else:
            price_status = "no_visible_numeric_price_request_quote"

        row = dict(row)
        row["source_urls"] = source_urls
        row["media_ids"] = media_ids
        row["price_status"] = price_status
        tier = str(row["description_source_tier"])
        scope = str(row["description_identity_scope"])
        row["release_score"] = (
            100 + (20 if tier == "manufacturer_primary" else 0)
            + (10 if scope == "exact" else 0)
            + min(len(description) // 100, 10)
            + min(integer(row["verified_media_count"]), 3)
            - CATEGORY_RANK[str(row["category_external_id"])]
        )
        candidates.append(row)

    candidates.sort(key=lambda row: (
        -integer(row["release_score"]), CATEGORY_RANK[str(row["category_external_id"])],
        str(row["manufacturer"]).casefold(), str(row["mpn"]).casefold(), str(row["external_id"]),
    ))
    selected = candidates[:LIMIT]
    ids = [str(row["external_id"]) for row in selected]
    pairs = [(str(row["manufacturer_normalized"]), str(row["mpn_normalized"])) for row in selected]
    paths = [str(row["product_path"]) for row in selected]
    if len(ids) != len(set(ids)) or len(pairs) != len(set(pairs)) or len(paths) != len(set(paths)):
        raise CohortError("selected ID, identity-pair, or canonical-path uniqueness failed")

    output: list[dict[str, str]] = []
    for order, row in enumerate(selected, start=1):
        output.append({
            "cohort_order": str(order), "release_score": str(row["release_score"]),
            "product_external_id": str(row["external_id"]), "product_id": str(row["product_id"]),
            "site_product_id": str(row["site_product_id"]), "name": str(row["name"]),
            "manufacturer": str(row["manufacturer"]), "mpn": str(row["mpn"]),
            "category_external_id": str(row["category_external_id"]), "category_name": str(row["category_name"]),
            "canonical_path": str(row["product_path"]), "description_characters": str(len(str(row["short_description"]).strip())),
            "description_source_kind": str(row["description_source_kind"]),
            "description_source_tier": str(row["description_source_tier"]),
            "description_identity_scope": str(row["description_identity_scope"]),
            "description_source_checked_at": str(row["description_source_checked_at"]),
            "description_source_urls": json.dumps(row["source_urls"], ensure_ascii=False, separators=(",", ":")),
            "verified_media_count": str(row["verified_media_count"]),
            "verified_media_ids": json.dumps(row["media_ids"], ensure_ascii=False, separators=(",", ":")),
            "visible_price_byn": str(row.get("price") or ""), "price_evidence_status": str(row["price_status"]),
            "availability": str(row["availability"]),
            "identity_pair_catalogue_count": str(row["identity_pair_catalogue_count"]),
            "product_url_count": str(row["product_url_count"]), "seo_record_count": str(row["seo_record_count"]),
            "open_duplicate_conflict_count": str(row["open_duplicate_conflict_count"]),
            "unresolved_identity_candidate_count": str(row["unresolved_identity_candidate_count"]),
            "release_decision": "READY_FOR_BOUNDED_INDEXABLE_RELEASE",
            "remaining_action": "RUN_RELEASE_TRANSACTION_AND_POST_RELEASE_SEO_AUDIT",
        })

    shortfall = max(0, LIMIT - len(output))
    summary: dict[str, Any] = {
        "schema_version": 1, "wave": "wave249a_first_indexable_b2b_cohort", "as_of": AS_OF.isoformat(),
        "mode": "live_database_read_only", "site_key": SITE_KEY,
        "selection_policy": {
            "target": LIMIT, "fail_closed": True, "price_max_age_days": 30,
            "b2b_categories": list(CATEGORY_RANK), "excluded_categories": ["seo:electronic-components"],
            "required": [
                "published noindex product with exactly one matching URL and SEO record",
                "unique normalized manufacturer+MPN pair across the catalogue",
                "matching applied source-backed description >=200 characters with valid HTTPS provenance",
                "exact verified published local media (legacy_exact_preview is not accepted)",
                "no open duplicate/identity candidate conflict",
                "no visible numeric price unless one fresh matching pinned evidence row exists",
                "on_request availability",
            ],
        },
        "source_snapshot": {
            "b2b_rows_before_primary_category_dedup": len(raw_rows),
            "b2b_products_after_primary_category_dedup": len(choose_primary_categories(raw_rows)),
            "open_duplicate_conflicts_global": integer(meta.get("open_duplicate_conflicts", 0)),
            "unresolved_identity_candidates_global": integer(meta.get("unresolved_identity_candidates", 0)),
            "duplicate_site_url_paths": integer(meta.get("duplicate_site_url_paths", 0)),
        },
        "candidate_pool_after_all_gates": len(candidates), "selected": len(output),
        "target": LIMIT, "target_met": len(output) == LIMIT, "shortfall": shortfall,
        "release_blocker": None if shortfall == 0 else f"ONLY_{len(output)}_CARDS_PASS_ALL_STRICT_GATES",
        "excluded": dict(sorted(excluded.items())),
        "invalid_description_provenance_pair_distribution": dict(sorted(invalid_provenance_pairs.items())),
        "price_only_near_ready_blockers": price_only_blockers,
        "category_distribution": dict(sorted(Counter(row["category_external_id"] for row in output).items())),
        "source_tier_distribution": dict(sorted(Counter(row["description_source_tier"] for row in output).items())),
        "price_status_distribution": dict(sorted(Counter(row["price_evidence_status"] for row in output).items())),
        "quality": {
            "selected_unique_external_ids": len(set(ids)), "selected_unique_identity_pairs": len(set(pairs)),
            "selected_unique_canonical_paths": len(set(paths)), "selected_with_verified_media": len(output),
            "selected_with_valid_source_provenance": len(output), "selected_open_conflicts": 0,
            "selected_stale_or_unpinned_visible_prices": 0, "database_mutations": 0, "network_requests": 0,
        },
        "records": output,
    }
    return output, summary


def write_outputs(rows: list[dict[str, str]], summary: dict[str, Any], output_dir: Path = GENERATED) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / OUTPUT_CSV.name
    json_path = output_dir / OUTPUT_JSON.name
    with csv_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    summary["outputs"] = {
        "csv": {"path": csv_path.relative_to(ROOT).as_posix(), "rows": len(rows), "sha256": sha256(csv_path)},
        "json": {"path": json_path.relative_to(ROOT).as_posix()},
    }
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, help="Use a test snapshot instead of the live read-only Docker query")
    parser.add_argument("--output-dir", type=Path, default=GENERATED)
    args = parser.parse_args()
    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8")) if args.snapshot else query_live_snapshot()
    rows, summary = build(snapshot)
    write_outputs(rows, summary, args.output_dir)
    print(json.dumps({
        "selected": len(rows), "target": LIMIT, "target_met": summary["target_met"],
        "shortfall": summary["shortfall"], "release_blocker": summary["release_blocker"],
        "database_mutations": 0,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
