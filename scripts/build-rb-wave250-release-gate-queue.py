#!/usr/bin/env python3
"""Build the read-only Wave250 RB B2B release-gate remediation queue.

The queue never mutates catalogue data.  It excludes electronic components,
already-indexable cards, strict-ready cards, and product identities previously
processed by Waves 242-249.  Every remaining card carries *all* failed release
gates, grouped into identity, description, media, URL/SEO, and price lanes.
"""

from __future__ import annotations

import argparse
import base64
import csv
import gzip
import hashlib
import json
import subprocess
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "docs" / "audits" / "generated"
OUTPUT_JSON = GENERATED / "rb-wave250-release-gate-queue-2026-07-30.json"
OUTPUT_CSV = GENERATED / "rb-wave250-release-gate-queue-2026-07-30.csv"
OUTPUT_LEDGER = GENERATED / "rb-wave250-processed-no-repeat-ledger-2026-07-30.csv"
SITE_KEY = "microchips-by"
LOCALE = "ru-BY"
CURRENCY = "BYN"
AS_OF = date(2026, 7, 30)
PRICE_CUTOFF = "2026-06-30 00:00:00+03"
LIMIT = 300

# Intentionally B2B-only.  Consumer replacement groups and electronic
# components are absent even when they have catalogue rows.
CATEGORY_RANK = {
    "seo:ups-systems": 1,
    "seo:batteries-industrial": 2,
    "seo:batteries-traction": 3,
    "seo:batteries-ups": 4,
    "seo:warehouse-equipment": 5,
    "seo:replacement-medical": 6,
    "seo:power-systems": 7,
    "seo:power-converters": 8,
    "seo:power-supplies": 9,
    "seo:replacement-tools": 10,
    "seo:replacement-transport": 11,
    "seo:rechargeable-cells": 12,
}
EXCLUDED_CATEGORIES = {"seo:electronic-components"}
SOURCE_PAIRS = {
    ("official_manufacturer_catalogue", "manufacturer_primary"),
    ("official_manufacturer_product_page", "manufacturer_primary"),
    ("official_dealer_product_page", "dealer_backed"),
}

PRIOR_JSON_FILES = (
    GENERATED / "rb-wave248a-release-cohort-2026-07-30.json",
    GENERATED / "rb-wave249a-indexable-b2b-cohort-2026-07-30.json",
    GENERATED / "rb-wave249-product-release-2026-07-30.json",
)
QUEUE_FILES = tuple(GENERATED / f"rb-enrichment-queue-wave{wave}.csv" for wave in (242, 243, 244, 245, 246))
DIRECT_PATTERNS = (
    "rb-wave24[2-7]*-evidence-ledger.csv",
    "rb-wave24[2-7]*-decision-ledger.csv",
    "rb-wave24[2-7]*-scope.csv",
    "rb-wave24[2-7]*-exact-media-review.csv",
    "rb-reviewed-legacy-preview-media-wave246.csv",
)

LANES = ("identity", "description", "media", "url_seo", "price")
ACTION = {
    "IDENTITY_EXTERNAL_ID_MISSING": "RESTORE_STABLE_SOURCE_IDENTITY",
    "IDENTITY_MANUFACTURER_MISSING": "VERIFY_MANUFACTURER_FROM_PRIMARY_SOURCE",
    "IDENTITY_MPN_MISSING": "VERIFY_EXACT_MPN_FROM_PRIMARY_SOURCE",
    "IDENTITY_PAIR_NOT_UNIQUE": "RESOLVE_MANUFACTURER_MPN_COLLISION",
    "DUPLICATE_CONFLICT_OPEN": "RESOLVE_OPEN_DUPLICATE_CONFLICT",
    "IDENTITY_CANDIDATE_UNRESOLVED": "RESOLVE_BITRIX_ONE_C_IDENTITY_CANDIDATE",
    "DESCRIPTION_TOO_SHORT": "WRITE_SOURCE_BACKED_DESCRIPTION_AT_LEAST_200_CHARS",
    "DESCRIPTION_APPLIED_MATCH_MISSING": "APPLY_DESCRIPTION_DRAFT_MATCHING_STOREFRONT_TEXT",
    "DESCRIPTION_PROVENANCE_SOURCE_INVALID": "PIN_ALLOWED_PRIMARY_OR_DEALER_SOURCE_KIND",
    "DESCRIPTION_PROVENANCE_URL_INVALID": "PIN_VALID_HTTPS_SOURCE_URL",
    "DESCRIPTION_PROVENANCE_SCOPE_INVALID": "VERIFY_EXACT_OR_MODEL_CORE_SCOPE",
    "DESCRIPTION_PROVENANCE_DATE_INVALID": "PIN_NON_FUTURE_SOURCE_CHECK_DATE",
    "EXACT_VERIFIED_MEDIA_MISSING": "FIND_AND_VISUALLY_VERIFY_EXACT_RIGHTS_CLEARED_MEDIA",
    "SITE_URL_COUNT_INVALID": "CREATE_ONE_CANONICAL_PRODUCT_URL",
    "URL_LOCALE_INVALID": "SET_PRODUCT_URL_LOCALE_RU_BY",
    "URL_PATH_UNSAFE": "REPAIR_CANONICAL_PRODUCT_PATH",
    "URL_IS_ACTIVE_REDIRECT_SOURCE": "REMOVE_CANONICAL_PATH_REDIRECT_CONFLICT",
    "SEO_RECORD_COUNT_INVALID": "CREATE_ONE_RU_BY_PRODUCT_SEO_RECORD",
    "SEO_CANONICAL_NOT_SELF": "ALIGN_SEO_CANONICAL_WITH_PRODUCT_URL",
    "SEO_NOT_NOINDEX": "RESTORE_NOINDEX_UNTIL_ALL_GATES_PASS",
    "AVAILABILITY_NOT_ON_REQUEST": "SET_SAFE_ON_REQUEST_AVAILABILITY",
    "VISIBLE_PRICE_CURRENT_EVIDENCE_COUNT_INVALID": "RETAIN_ONE_CURRENT_PINNED_PRICE_EVIDENCE_OR_HIDE_PRICE",
    "VISIBLE_PRICE_FRESH_MATCH_MISSING": "IMPORT_FRESH_MATCHING_PRICE_EVIDENCE_OR_HIDE_PRICE",
}

CSV_FIELDS = [
    "queue_order", "blocker_count", "commercial_priority", "product_external_id", "product_id",
    "site_product_id", "name", "manufacturer", "mpn", "product_status", "category_external_id",
    "category_name", "canonical_path", "is_indexable", "description_characters",
    "description_source_kind", "description_source_tier", "description_identity_scope",
    "description_source_checked_at", "description_source_urls", "verified_media_count",
    "availability", "visible_price_byn", "current_price_evidence_count",
    "fresh_matching_price_evidence_count", "identity_blockers", "identity_actions",
    "description_blockers", "description_actions", "media_blockers", "media_actions",
    "url_seo_blockers", "url_seo_actions", "price_blockers", "price_actions",
    "all_blockers", "recommended_next_action", "no_repeat_basis",
]
LEDGER_FIELDS = ["product_external_id", "ledger_state", "reasons", "source_paths", "source_sha256"]


class QueueError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def content_sha(payload: Any) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def integer(value: Any) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError) as error:
        raise QueueError(f"invalid integer evidence field: {value!r}") from error


def truth(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}


def valid_https(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc)


def json_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    try:
        decoded = json.loads(str(value or "[]"))
    except json.JSONDecodeError:
        return []
    return decoded if isinstance(decoded, list) else []


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def first_present(row: dict[str, Any], *fields: str) -> str:
    for field in fields:
        value = str(row.get(field) or "").strip()
        if value:
            return value
    return ""


def recognized_id(value: str) -> bool:
    return value.startswith("bitrix:") or value.startswith("manufacturer:") or value.startswith("1c:")


def read_processed() -> tuple[dict[str, list[dict[str, str]]], list[dict[str, Any]]]:
    entries: dict[str, list[dict[str, str]]] = defaultdict(list)
    pins: list[dict[str, Any]] = []

    def add(external_id: str, reason: str, path: Path, digest: str) -> None:
        if recognized_id(external_id):
            entries[external_id].append({"reason": reason, "path": path.relative_to(ROOT).as_posix(), "sha256": digest})

    for path in PRIOR_JSON_FILES:
        if not path.is_file():
            raise QueueError(f"required prior-wave artifact missing: {path.name}")
        digest = sha256(path)
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        records = payload.get("records") or payload.get("released_records") or payload.get("released") or []
        if isinstance(records, dict):
            records = list(records.values())
        found = 0
        for row in records if isinstance(records, list) else []:
            if not isinstance(row, dict):
                continue
            external_id = first_present(row, "product_external_id", "external_id", "source_external_id")
            if recognized_id(external_id):
                add(external_id, f"processed_{payload.get('wave', path.stem)}", path, digest)
                found += 1
        pins.append({"path": path.relative_to(ROOT).as_posix(), "sha256": digest, "recognized_product_ids": found})

    latest_status: dict[str, tuple[str, Path, str]] = {}
    for path in QUEUE_FILES:
        if not path.is_file():
            raise QueueError(f"required prior queue missing: {path.name}")
        digest = sha256(path)
        rows = read_csv(path)
        for row in rows:
            external_id = first_present(row, "product_external_id", "external_id")
            if recognized_id(external_id):
                latest_status[external_id] = (str(row.get("research_status") or "").strip(), path, digest)
        pins.append({"path": path.relative_to(ROOT).as_posix(), "sha256": digest, "rows": len(rows)})
    pending = {"pending_official_source_research", "new_after_verified_duplicate_retirement"}
    for external_id, (status, path, digest) in latest_status.items():
        if status not in pending:
            add(external_id, f"terminal_queue_status:{status or '<blank>'}", path, digest)

    paths = sorted({p for pattern in DIRECT_PATTERNS for p in GENERATED.glob(pattern) if p.is_file()})
    if not paths:
        raise QueueError("no direct Wave242-247 research artifacts found")
    for path in paths:
        digest = sha256(path)
        rows = read_csv(path)
        found = 0
        for row in rows:
            external_id = first_present(row, "product_external_id", "external_id", "source_external_id", "duplicate_external_id")
            if recognized_id(external_id):
                add(external_id, "direct_wave242_247_research", path, digest)
                found += 1
        pins.append({"path": path.relative_to(ROOT).as_posix(), "sha256": digest, "rows": len(rows), "recognized_product_ids": found})
    return dict(entries), pins


def query_live_snapshot() -> dict[str, Any]:
    """Read all gate evidence in one DB snapshot; no update/insert/delete exists."""
    categories = ",".join(repr(value) for value in CATEGORY_RANK)
    php = f'''
$site=app('db')->table('sites')->where('key','{SITE_KEY}')->first(['id','key','domain','currency_code','default_locale']);
if (!$site) {{ throw new RuntimeException('microchips-by site missing'); }}
$rows=app('db')->table('site_products as sp')
 ->join('products as p','p.id','=','sp.product_id')
 ->join('site_category_product as scp',function($join) use($site) {{$join->on('scp.site_product_id','=','sp.id')->where('scp.site_id',$site->id);}})
 ->join('site_categories as sc',function($join) use($site) {{$join->on('sc.id','=','scp.site_category_id')->where('sc.site_id',$site->id);}})
 ->where('sp.site_id',$site->id)->where('sp.is_published',true)->whereIn('sc.external_id',[{categories}])
 ->orderBy('p.external_id')->get([
  'p.id as product_id','p.external_id','p.name','p.manufacturer','p.mpn','p.status as product_status','p.short_description',
  'sp.id as site_product_id','sp.is_published','sp.price','sp.availability','sc.external_id as category_external_id','sc.name as category_name',
  app('db')->raw("(select count(*) from product_media pm where pm.product_id=p.id and pm.kind='image' and pm.verification_status='verified' and pm.is_published=true and pm.storage_path is not null and pm.rights_basis is not null) as verified_media_count"),
  app('db')->raw("(select count(*) from product_description_drafts d where d.product_id=p.id and d.locale='{LOCALE}' and d.status='applied' and d.content=p.short_description) as matching_applied_description_count"),
  app('db')->raw("(select d.source_urls::text from product_description_drafts d where d.product_id=p.id and d.locale='{LOCALE}' and d.status='applied' and d.content=p.short_description order by d.id desc limit 1) as description_source_urls"),
  app('db')->raw("(select d.source_kind from product_description_drafts d where d.product_id=p.id and d.locale='{LOCALE}' and d.status='applied' and d.content=p.short_description order by d.id desc limit 1) as description_source_kind"),
  app('db')->raw("(select d.source_tier from product_description_drafts d where d.product_id=p.id and d.locale='{LOCALE}' and d.status='applied' and d.content=p.short_description order by d.id desc limit 1) as description_source_tier"),
  app('db')->raw("(select d.identity_scope from product_description_drafts d where d.product_id=p.id and d.locale='{LOCALE}' and d.status='applied' and d.content=p.short_description order by d.id desc limit 1) as description_identity_scope"),
  app('db')->raw("(select d.source_checked_at from product_description_drafts d where d.product_id=p.id and d.locale='{LOCALE}' and d.status='applied' and d.content=p.short_description order by d.id desc limit 1) as description_source_checked_at"),
  app('db')->raw("(select count(*) from site_urls u where u.site_id={{$site->id}} and u.target_type='product' and u.target_id=sp.id) as product_url_count"),
  app('db')->raw("(select u.path from site_urls u where u.site_id={{$site->id}} and u.target_type='product' and u.target_id=sp.id order by u.id limit 1) as product_path"),
  app('db')->raw("(select u.locale from site_urls u where u.site_id={{$site->id}} and u.target_type='product' and u.target_id=sp.id order by u.id limit 1) as product_url_locale"),
  app('db')->raw("(select u.is_indexable from site_urls u where u.site_id={{$site->id}} and u.target_type='product' and u.target_id=sp.id order by u.id limit 1) as url_is_indexable"),
  app('db')->raw("(select count(*) from site_seos seo where seo.site_id={{$site->id}} and seo.locale='{LOCALE}' and seo.resource_type='product' and seo.resource_id=sp.id) as seo_record_count"),
  app('db')->raw("(select seo.canonical_path from site_seos seo where seo.site_id={{$site->id}} and seo.locale='{LOCALE}' and seo.resource_type='product' and seo.resource_id=sp.id order by seo.id limit 1) as seo_canonical_path"),
  app('db')->raw("(select seo.is_indexable from site_seos seo where seo.site_id={{$site->id}} and seo.locale='{LOCALE}' and seo.resource_type='product' and seo.resource_id=sp.id order by seo.id limit 1) as seo_is_indexable"),
  app('db')->raw("(select seo.title from site_seos seo where seo.site_id={{$site->id}} and seo.locale='{LOCALE}' and seo.resource_type='product' and seo.resource_id=sp.id order by seo.id limit 1) as seo_title"),
  app('db')->raw("(select seo.description from site_seos seo where seo.site_id={{$site->id}} and seo.locale='{LOCALE}' and seo.resource_type='product' and seo.resource_id=sp.id order by seo.id limit 1) as seo_description"),
  app('db')->raw("(select count(*) from site_redirects r where r.site_id={{$site->id}} and r.is_active=true and r.source_path=(select u2.path from site_urls u2 where u2.site_id={{$site->id}} and u2.target_type='product' and u2.target_id=sp.id order by u2.id limit 1)) as canonical_redirect_source_count"),
  app('db')->raw("(select count(*) from site_product_price_evidences pe where pe.site_id={{$site->id}} and pe.site_product_id=sp.id and pe.is_current=true) as current_price_evidence_count"),
  app('db')->raw("(select count(*) from site_product_price_evidences pe where pe.site_id={{$site->id}} and pe.site_product_id=sp.id and pe.is_current=true and pe.currency='{CURRENCY}' and pe.calculated_price=sp.price and pe.observed_at >= timestamp with time zone '{PRICE_CUTOFF}' and pe.evidence_key is not null and pe.source_reference is not null) as fresh_matching_price_evidence_count"),
  app('db')->raw("(select count(*) from duplicate_conflicts dc cross join lateral jsonb_array_elements_text(dc.candidate_ids::jsonb) cid where dc.status='open' and cid.value in (p.id::text,p.external_id)) as open_duplicate_conflict_count"),
  app('db')->raw("(select count(*) from catalog_identity_candidates cic where cic.legacy_source='bitrix' and cic.legacy_id=replace(p.external_id,'bitrix:','') and cic.review_status not in ('approved','rejected','resolved')) as unresolved_identity_candidate_count")
 ]);
$identityPairCounts=[];
foreach (app('db')->table('products')->get(['manufacturer','mpn']) as $identity) {{
 $m=\\App\\Domain\\Imports\\ProductIdentity::normalize($identity->manufacturer); $n=\\App\\Domain\\Imports\\ProductIdentity::normalize($identity->mpn);
 if ($m && $n) {{ $key=$m."\\0".$n; $identityPairCounts[$key]=($identityPairCounts[$key] ?? 0)+1; }}
}}
foreach ($rows as $row) {{
 $row->manufacturer_normalized=\\App\\Domain\\Imports\\ProductIdentity::normalize($row->manufacturer);
 $row->mpn_normalized=\\App\\Domain\\Imports\\ProductIdentity::normalize($row->mpn);
 $key=($row->manufacturer_normalized ?? '')."\\0".($row->mpn_normalized ?? ''); $row->identity_pair_catalogue_count=$identityPairCounts[$key] ?? 0;
}}
$meta=['site_domain'=>$site->domain,
 'root_url_count'=>(int) app('db')->table('site_urls')->where('site_id',$site->id)->where('path','/')->count(),
 'root_indexable_url_count'=>(int) app('db')->table('site_urls')->where('site_id',$site->id)->where('path','/')->where('is_indexable',true)->count(),
 'duplicate_site_url_paths'=>(int) app('db')->table('site_urls')->where('site_id',$site->id)->select('path')->groupBy('path')->havingRaw('count(*) > 1')->get()->count()];
echo base64_encode(gzencode(json_encode(['site_key'=>$site->key,'currency'=>$site->currency_code,'locale'=>$site->default_locale,'rows'=>$rows,'meta'=>$meta],JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES|JSON_THROW_ON_ERROR),9));
'''
    encoded = base64.b64encode(php.encode("utf-8")).decode("ascii")
    result = subprocess.run(
        ["docker", "compose", "exec", "-T", "backend", "php", "artisan", "tinker", f"--execute=eval(base64_decode('{encoded}')); "],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise QueueError(f"live read-only query failed: {result.stderr.strip() or result.stdout.strip()}")
    try:
        compressed = base64.b64decode(result.stdout.strip(), validate=True)
        return json.loads(gzip.decompress(compressed).decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise QueueError("live query returned invalid base64 JSON") from error


def primary_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    chosen: dict[str, dict[str, Any]] = {}
    for row in rows:
        external_id = str(row.get("external_id") or "").strip()
        category = str(row.get("category_external_id") or "").strip()
        if not external_id or category not in CATEGORY_RANK:
            raise QueueError("snapshot contains blank identity or non-B2B category")
        prior = chosen.get(external_id)
        if prior is None or CATEGORY_RANK[category] < CATEGORY_RANK[str(prior["category_external_id"])]:
            chosen[external_id] = row
    return list(chosen.values())


def add(blockers: dict[str, list[str]], lane: str, code: str, condition: bool) -> None:
    if condition:
        blockers[lane].append(code)


def evaluate(row: dict[str, Any]) -> tuple[dict[str, list[str]], list[str]]:
    blockers = {lane: [] for lane in LANES}
    external_id = str(row.get("external_id") or "").strip()
    manufacturer = str(row.get("manufacturer") or "").strip()
    mpn = str(row.get("mpn") or "").strip()
    add(blockers, "identity", "IDENTITY_EXTERNAL_ID_MISSING", not external_id)
    add(blockers, "identity", "IDENTITY_MANUFACTURER_MISSING", not manufacturer or not str(row.get("manufacturer_normalized") or "").strip())
    add(blockers, "identity", "IDENTITY_MPN_MISSING", not mpn or not str(row.get("mpn_normalized") or "").strip())
    add(blockers, "identity", "IDENTITY_PAIR_NOT_UNIQUE", bool(manufacturer and mpn) and integer(row.get("identity_pair_catalogue_count", 0)) != 1)
    add(blockers, "identity", "DUPLICATE_CONFLICT_OPEN", integer(row.get("open_duplicate_conflict_count", 0)) > 0)
    add(blockers, "identity", "IDENTITY_CANDIDATE_UNRESOLVED", integer(row.get("unresolved_identity_candidate_count", 0)) > 0)

    description = str(row.get("short_description") or "").strip()
    add(blockers, "description", "DESCRIPTION_TOO_SHORT", len(description) < 200)
    matching = integer(row.get("matching_applied_description_count", 0))
    add(blockers, "description", "DESCRIPTION_APPLIED_MATCH_MISSING", matching < 1)
    if matching > 0:
        pair = (str(row.get("description_source_kind") or ""), str(row.get("description_source_tier") or ""))
        add(blockers, "description", "DESCRIPTION_PROVENANCE_SOURCE_INVALID", pair not in SOURCE_PAIRS)
        urls = json_list(row.get("description_source_urls"))
        add(blockers, "description", "DESCRIPTION_PROVENANCE_URL_INVALID", not urls or any(not isinstance(url, str) or not valid_https(url) for url in urls))
        add(blockers, "description", "DESCRIPTION_PROVENANCE_SCOPE_INVALID", str(row.get("description_identity_scope") or "") not in {"exact", "model_core"})
        try:
            checked = date.fromisoformat(str(row.get("description_source_checked_at") or ""))
            invalid_date = checked > AS_OF
        except ValueError:
            invalid_date = True
        add(blockers, "description", "DESCRIPTION_PROVENANCE_DATE_INVALID", invalid_date)

    add(blockers, "media", "EXACT_VERIFIED_MEDIA_MISSING", integer(row.get("verified_media_count", 0)) < 1)

    url_count = integer(row.get("product_url_count", 0))
    seo_count = integer(row.get("seo_record_count", 0))
    path = str(row.get("product_path") or "").strip()
    add(blockers, "url_seo", "SITE_URL_COUNT_INVALID", url_count != 1)
    if url_count == 1:
        add(blockers, "url_seo", "URL_LOCALE_INVALID", str(row.get("product_url_locale") or "") != LOCALE)
        add(blockers, "url_seo", "URL_PATH_UNSAFE", not path.startswith("/catalog/") or "//" in path or "?" in path or "#" in path)
        add(blockers, "url_seo", "URL_IS_ACTIVE_REDIRECT_SOURCE", integer(row.get("canonical_redirect_source_count", 0)) > 0)
    add(blockers, "url_seo", "SEO_RECORD_COUNT_INVALID", seo_count != 1)
    if seo_count == 1:
        add(blockers, "url_seo", "SEO_CANONICAL_NOT_SELF", str(row.get("seo_canonical_path") or "").strip() != path or url_count != 1)
        add(blockers, "url_seo", "SEO_NOT_NOINDEX", truth(row.get("seo_is_indexable")))
    add(blockers, "url_seo", "AVAILABILITY_NOT_ON_REQUEST", str(row.get("availability") or "") != "on_request")

    price = str(row.get("price") or "").strip()
    if price:
        add(blockers, "price", "VISIBLE_PRICE_CURRENT_EVIDENCE_COUNT_INVALID", integer(row.get("current_price_evidence_count", 0)) != 1)
        add(blockers, "price", "VISIBLE_PRICE_FRESH_MATCH_MISSING", integer(row.get("fresh_matching_price_evidence_count", 0)) != 1)
    all_codes = [code for lane in LANES for code in blockers[lane]]
    return blockers, all_codes


def actions(codes: list[str]) -> str:
    return "|".join(dict.fromkeys(ACTION[code] for code in codes))


def build(snapshot: dict[str, Any], processed: dict[str, list[dict[str, str]]]) -> tuple[list[dict[str, str]], dict[str, Any]]:
    if snapshot.get("site_key") != SITE_KEY or snapshot.get("currency") != CURRENCY or snapshot.get("locale") != LOCALE:
        raise QueueError("expected live microchips-by / ru-BY / BYN snapshot")
    rows = snapshot.get("rows")
    meta = snapshot.get("meta")
    if not isinstance(rows, list) or not isinstance(meta, dict):
        raise QueueError("snapshot rows/meta contract invalid")
    if integer(meta.get("duplicate_site_url_paths", 0)):
        raise QueueError("global site URL path uniqueness is not proven")
    global_blockers = []
    domain = str(meta.get("site_domain") or "")
    if not domain or domain.endswith(".test") or domain in {"localhost", "127.0.0.1"}:
        global_blockers.append("SITE_DOMAIN_NOT_PRODUCTION")
    if integer(meta.get("root_url_count", 0)) != 1 or integer(meta.get("root_indexable_url_count", 0)) != 1:
        global_blockers.append("ROOT_URL_NOT_SINGLE_AND_INDEXABLE")

    excluded = Counter()
    candidates: list[dict[str, Any]] = []
    already_indexable: set[str] = set()
    ready: set[str] = set()
    for raw in primary_rows(rows):
        external_id = str(raw["external_id"])
        if external_id in processed:
            excluded["prior_processed_no_repeat"] += 1
            continue
        if truth(raw.get("url_is_indexable")) or truth(raw.get("seo_is_indexable")):
            excluded["already_indexable"] += 1
            already_indexable.add(external_id)
            continue
        blockers, all_codes = evaluate(raw)
        if not all_codes:
            excluded["strict_ready_no_remediation_needed"] += 1
            ready.add(external_id)
            continue
        candidate = dict(raw)
        candidate["blockers"] = blockers
        candidate["all_codes"] = all_codes
        candidates.append(candidate)
    candidates.sort(key=lambda row: (
        len(row["all_codes"]), CATEGORY_RANK[str(row["category_external_id"])],
        str(row.get("manufacturer") or "").casefold(), str(row.get("mpn") or "").casefold(), str(row["external_id"]),
    ))
    selected = candidates[:LIMIT]
    if len(selected) != LIMIT:
        raise QueueError(f"Wave250 requires exactly {LIMIT} unique remediation cards; found {len(selected)}")
    ids = [str(row["external_id"]) for row in selected]
    site_product_ids = [str(row["site_product_id"]) for row in selected]
    if len(ids) != len(set(ids)) or len(site_product_ids) != len(set(site_product_ids)):
        raise QueueError("selected external/site-product identities are not unique")
    if set(ids) & set(processed) or set(ids) & already_indexable or set(ids) & ready:
        raise QueueError("no-repeat/indexable/ready exclusion failed")

    output: list[dict[str, str]] = []
    for order, row in enumerate(selected, 1):
        blockers = row["blockers"]
        lane_actions = {lane: actions(blockers[lane]) for lane in LANES}
        all_actions = [action for lane in LANES for action in lane_actions[lane].split("|") if action]
        output.append({
            "queue_order": str(order), "blocker_count": str(len(row["all_codes"])),
            "commercial_priority": str(CATEGORY_RANK[str(row["category_external_id"])]),
            "product_external_id": str(row["external_id"]), "product_id": str(row["product_id"]),
            "site_product_id": str(row["site_product_id"]), "name": str(row.get("name") or ""),
            "manufacturer": str(row.get("manufacturer") or ""), "mpn": str(row.get("mpn") or ""),
            "product_status": str(row.get("product_status") or ""), "category_external_id": str(row["category_external_id"]),
            "category_name": str(row.get("category_name") or ""), "canonical_path": str(row.get("product_path") or ""),
            "is_indexable": "false", "description_characters": str(len(str(row.get("short_description") or "").strip())),
            "description_source_kind": str(row.get("description_source_kind") or ""),
            "description_source_tier": str(row.get("description_source_tier") or ""),
            "description_identity_scope": str(row.get("description_identity_scope") or ""),
            "description_source_checked_at": str(row.get("description_source_checked_at") or ""),
            "description_source_urls": json.dumps(json_list(row.get("description_source_urls")), ensure_ascii=False),
            "verified_media_count": str(row.get("verified_media_count") or "0"), "availability": str(row.get("availability") or ""),
            "visible_price_byn": str(row.get("price") or ""), "current_price_evidence_count": str(row.get("current_price_evidence_count") or "0"),
            "fresh_matching_price_evidence_count": str(row.get("fresh_matching_price_evidence_count") or "0"),
            **{f"{lane}_blockers": "|".join(blockers[lane]) for lane in LANES},
            **{f"{lane}_actions": lane_actions[lane] for lane in LANES},
            "all_blockers": "|".join(row["all_codes"]),
            "recommended_next_action": "|".join(dict.fromkeys(all_actions)),
            "no_repeat_basis": "not_prior_processed_not_indexable_not_strict_ready",
        })

    blocker_distribution = Counter(code for row in output for code in row["all_blockers"].split("|") if code)
    lane_distribution = {lane: sum(bool(row[f"{lane}_blockers"]) for row in output) for lane in LANES}
    summary: dict[str, Any] = {
        "schema_version": 1, "wave": "wave250_b2b_release_gate_queue", "as_of": AS_OF.isoformat(),
        "mode": "live_database_read_only", "site_key": SITE_KEY,
        "selection_policy": {
            "target": LIMIT, "sort": ["blocker_count ASC", "B2B category priority ASC", "manufacturer", "mpn", "external_id"],
            "b2b_categories_in_priority_order": list(CATEGORY_RANK), "excluded_categories": sorted(EXCLUDED_CATEGORIES),
            "excluded_states": ["already indexable", "strict ready", "prior processed Waves 242-249"],
            "description_minimum_characters": 200, "price_freshness_cutoff": PRICE_CUTOFF,
            "all_failed_gates_accumulated": True,
        },
        "global_release_blockers": global_blockers,
        "source_snapshot": {"rows_before_primary_category_dedup": len(rows), "products_after_primary_category_dedup": len(primary_rows(rows)), **meta},
        "candidate_pool_after_exclusions": len(candidates), "selected": len(output), "excluded": dict(sorted(excluded.items())),
        "aggregates": {
            "blocker_distribution": dict(sorted(blocker_distribution.items())), "lane_card_distribution": lane_distribution,
            "blocker_count_distribution": dict(sorted(Counter(row["blocker_count"] for row in output).items(), key=lambda item: int(item[0]))),
            "category_distribution": dict(sorted(Counter(row["category_external_id"] for row in output).items())),
            "manufacturer_distribution": dict(sorted(Counter(row["manufacturer"] for row in output).items())),
        },
        "uniqueness": {"selected_external_ids": len(set(ids)), "selected_site_product_ids": len(set(site_product_ids)), "target": LIMIT},
        "no_repeat": {
            "prior_processed_ids": len(processed), "already_indexable_excluded": len(already_indexable),
            "strict_ready_excluded": len(ready), "selected_overlap_prior_processed": len(set(ids) & set(processed)),
            "selected_overlap_indexable": len(set(ids) & already_indexable, ), "selected_overlap_strict_ready": len(set(ids) & ready),
        },
        "quality": {"database_mutations": 0, "network_requests": 0, "exactly_300": len(output) == LIMIT, "all_selected_have_blockers": all(integer(row["blocker_count"]) > 0 for row in output)},
        "records": output,
    }
    summary["payload_sha256"] = content_sha(summary)
    return output, summary


def ledger_rows(processed: dict[str, list[dict[str, str]]], selected: list[dict[str, str]], selected_source_sha: str) -> list[dict[str, str]]:
    rows = []
    for external_id, evidence in sorted(processed.items()):
        rows.append({
            "product_external_id": external_id, "ledger_state": "excluded_prior_processed",
            "reasons": "|".join(sorted({item["reason"] for item in evidence})),
            "source_paths": "|".join(sorted({item["path"] for item in evidence})),
            "source_sha256": "|".join(sorted({item["sha256"] for item in evidence})),
        })
    for row in selected:
        rows.append({
            "product_external_id": row["product_external_id"], "ledger_state": "selected_wave250_queue",
            "reasons": "wave250_release_gate_remediation", "source_paths": OUTPUT_CSV.relative_to(ROOT).as_posix(), "source_sha256": selected_source_sha,
        })
    if len(rows) != len({row["product_external_id"] for row in rows}):
        raise QueueError("processed/no-repeat ledger identities are not unique")
    return rows


def label(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def write_outputs(rows: list[dict[str, str]], summary: dict[str, Any], processed: dict[str, list[dict[str, str]]], pins: list[dict[str, Any]], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path, ledger_path, json_path = output_dir / OUTPUT_CSV.name, output_dir / OUTPUT_LEDGER.name, output_dir / OUTPUT_JSON.name
    with csv_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS, lineterminator="\n"); writer.writeheader(); writer.writerows(rows)
    csv_digest = sha256(csv_path)
    ledger = ledger_rows(processed, rows, csv_digest)
    with ledger_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=LEDGER_FIELDS, lineterminator="\n"); writer.writeheader(); writer.writerows(ledger)
    summary["source_pins"] = pins
    summary["no_repeat"]["ledger_unique_ids"] = len(ledger)
    # Re-pin the canonical payload after source evidence and ledger cardinality
    # are attached, but before output metadata (which would be self-referential).
    summary.pop("outputs", None)
    summary.pop("payload_sha256", None)
    summary["payload_sha256"] = content_sha(summary)
    summary["outputs"] = {
        "csv": {"path": label(csv_path), "rows": len(rows), "sha256": csv_digest},
        "processed_no_repeat_ledger": {"path": label(ledger_path), "rows": len(ledger), "sha256": sha256(ledger_path)},
        "json": {"path": label(json_path), "payload_sha256": summary["payload_sha256"]},
    }
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, help="read a pinned JSON snapshot instead of Docker")
    parser.add_argument("--output-dir", type=Path, default=GENERATED)
    args = parser.parse_args()
    processed, pins = read_processed()
    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8")) if args.snapshot else query_live_snapshot()
    rows, summary = build(snapshot, processed)
    write_outputs(rows, summary, processed, pins, args.output_dir)
    print(json.dumps({"selected": len(rows), "candidate_pool": summary["candidate_pool_after_exclusions"], "database_mutations": 0, "payload_sha256": summary["payload_sha256"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
