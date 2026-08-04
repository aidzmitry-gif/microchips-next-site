#!/usr/bin/env python3
"""Build a read-only, commercial-safe survivor plan for Wave207 Motorola groups."""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs/audits/generated/wave207-motorola-kenwood-evidence.csv"
WAVE207_SUMMARY = ROOT / "docs/audits/generated/wave207-motorola-kenwood-evidence-summary.json"
CANONICAL = ROOT / "docs/audits/generated/full-catalog-canonical-registry.csv"
PROPERTIES = ROOT / "docs/audits/generated/bitrix-b2b-catalog-property-values.csv"
DB_SNAPSHOT = ROOT / "docs/audits/generated/wave208-motorola-duplicate-db-snapshot.json"
OUTPUT = ROOT / "docs/audits/generated/wave208-motorola-duplicate-survivor-plan.csv"
SUMMARY = ROOT / "docs/audits/generated/wave208-motorola-duplicate-survivor-plan-summary.json"
SITE_KEY = "microchips-by"
EXPECTED_GROUPS = 9
EXPECTED_ROWS = 21

FIELDS = [
    "group_key", "group_size", "product_external_id", "name", "evidence_partition",
    "current_product_status", "current_manufacturer", "current_mpn", "current_sku",
    "site_product_count", "is_published", "availability", "price", "price_evidence_count",
    "current_price_evidence_count", "legacy_minimum_price", "legacy_maximum_price",
    "legacy_in_stock", "media_count", "published_media_count", "verified_media_count",
    "preview_media_count", "description_count", "applied_description_count",
    "manufacturer_primary_description_count", "site_url_count", "site_paths",
    "seo_count", "seo_indexable_count", "seo_canonical_paths", "offer_schema_count",
    "legacy_redirect_count", "legacy_redirects", "one_c_link_count", "one_c_external_ids",
    "one_c_articles", "one_c_review_statuses", "content_loss_flags", "group_decision",
    "survivor_external_id", "safe_to_collapse", "required_before_collapse",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def candidate_groups() -> dict[str, list[str]]:
    summary = json.loads(WAVE207_SUMMARY.read_text(encoding="utf-8-sig"))
    groups = summary["duplicate_guard"]["groups"]
    if len(groups) != EXPECTED_GROUPS or sum(len(ids) for ids in groups.values()) != EXPECTED_ROWS:
        raise SystemExit("Wave207 strict duplicate group scope drifted")
    if any(not key.startswith("Motorola:") for key in groups):
        raise SystemExit("Wave208 scope contains a non-Motorola group")
    return {key: list(ids) for key, ids in groups.items()}


def php_query(ids: list[str], site_key: str) -> str:
    escaped_ids = ",".join("'" + value.replace("'", "''") + "'" for value in ids)
    escaped_site = site_key.replace("'", "''")
    return (
        f"$siteId=app('db')->table('sites')->where('key','{escaped_site}')->value('id');"
        "if(!$siteId){throw new RuntimeException('Site not found');}"
        f"$ids=[{escaped_ids}];"
        "$q=app('db')->table('products as p')->whereIn('p.external_id',$ids)"
        "->select('p.id','p.external_id','p.name','p.status','p.manufacturer','p.mpn','p.sku')"
        "->selectRaw(\"(select count(*) from site_products sp where sp.product_id=p.id and sp.site_id=?) site_product_count\",[$siteId])"
        "->selectRaw(\"(select sp.is_published from site_products sp where sp.product_id=p.id and sp.site_id=? limit 1) is_published\",[$siteId])"
        "->selectRaw(\"(select sp.availability from site_products sp where sp.product_id=p.id and sp.site_id=? limit 1) availability\",[$siteId])"
        "->selectRaw(\"(select sp.price from site_products sp where sp.product_id=p.id and sp.site_id=? limit 1) price\",[$siteId])"
        "->selectRaw(\"(select count(*) from site_product_price_evidences pe where pe.site_product_id=(select sp.id from site_products sp where sp.product_id=p.id and sp.site_id=? limit 1)) price_evidence_count\",[$siteId])"
        "->selectRaw(\"(select count(*) from site_product_price_evidences pe where pe.site_product_id=(select sp.id from site_products sp where sp.product_id=p.id and sp.site_id=? limit 1) and pe.is_current=true) current_price_evidence_count\",[$siteId])"
        "->selectRaw(\"(select count(*) from product_media pm where pm.product_id=p.id) media_count\")"
        "->selectRaw(\"(select count(*) from product_media pm where pm.product_id=p.id and pm.is_published=true) published_media_count\")"
        "->selectRaw(\"(select count(*) from product_media pm where pm.product_id=p.id and pm.is_published=true and pm.verification_status='verified') verified_media_count\")"
        "->selectRaw(\"(select count(*) from product_media pm where pm.product_id=p.id and pm.is_published=true and pm.verification_status in ('verified','legacy_exact_preview') and pm.storage_path is not null and pm.rights_basis is not null) preview_media_count\")"
        "->selectRaw(\"(select coalesce(string_agg(coalesce(pm.content_sha256,'') || ':' || coalesce(pm.storage_path,''),'|' order by pm.id),'') from product_media pm where pm.product_id=p.id) media_fingerprint\")"
        "->selectRaw(\"(select count(*) from product_description_drafts pd where pd.product_id=p.id) description_count\")"
        "->selectRaw(\"(select count(*) from product_description_drafts pd where pd.product_id=p.id and pd.status in ('applied','legacy_preview_applied')) applied_description_count\")"
        "->selectRaw(\"(select count(*) from product_description_drafts pd where pd.product_id=p.id and pd.manufacturer_primary=true) manufacturer_primary_description_count\")"
        "->selectRaw(\"(select coalesce(string_agg(pd.status || ':' || md5(coalesce(pd.title,'') || '|' || coalesce(pd.content,'')),'|' order by pd.id),'') from product_description_drafts pd where pd.product_id=p.id) description_fingerprint\")"
        "->selectRaw(\"(select count(*) from site_urls su where su.site_id=? and su.target_type='product' and su.target_id=(select sp.id from site_products sp where sp.product_id=p.id and sp.site_id=? limit 1)) site_url_count\",[$siteId,$siteId])"
        "->selectRaw(\"(select coalesce(string_agg(su.path,'|' order by su.path),'') from site_urls su where su.site_id=? and su.target_type='product' and su.target_id=(select sp.id from site_products sp where sp.product_id=p.id and sp.site_id=? limit 1)) site_paths\",[$siteId,$siteId])"
        "->selectRaw(\"(select count(*) from site_seos ss where ss.site_id=? and ss.resource_type='product' and ss.resource_id=(select sp.id from site_products sp where sp.product_id=p.id and sp.site_id=? limit 1)) seo_count\",[$siteId,$siteId])"
        "->selectRaw(\"(select count(*) from site_seos ss where ss.site_id=? and ss.resource_type='product' and ss.resource_id=(select sp.id from site_products sp where sp.product_id=p.id and sp.site_id=? limit 1) and ss.is_indexable=true) seo_indexable_count\",[$siteId,$siteId])"
        "->selectRaw(\"(select coalesce(string_agg(ss.canonical_path,'|' order by ss.canonical_path),'') from site_seos ss where ss.site_id=? and ss.resource_type='product' and ss.resource_id=(select sp.id from site_products sp where sp.product_id=p.id and sp.site_id=? limit 1)) seo_canonical_paths\",[$siteId,$siteId])"
        "->selectRaw(\"(select count(*) from site_seos ss where ss.site_id=? and ss.resource_type='product' and ss.resource_id=(select sp.id from site_products sp where sp.product_id=p.id and sp.site_id=? limit 1) and cast(ss.schema as text) ~ '\\\"(@type|offers?)\\\"') offer_schema_count\",[$siteId,$siteId])"
        "->selectRaw(\"(select count(*) from site_redirects sr where sr.site_id=? and sr.is_active=true and (sr.source_path like '%' || replace(p.external_id,'bitrix:','') || '%' or sr.target_path like '%' || replace(p.external_id,'bitrix:','') || '%' or sr.source_path in (select su.path from site_urls su where su.site_id=? and su.target_type='product' and su.target_id=(select sp.id from site_products sp where sp.product_id=p.id and sp.site_id=? limit 1)) or sr.target_path in (select su.path from site_urls su where su.site_id=? and su.target_type='product' and su.target_id=(select sp.id from site_products sp where sp.product_id=p.id and sp.site_id=? limit 1)))) legacy_redirect_count\",[$siteId,$siteId,$siteId,$siteId,$siteId])"
        "->selectRaw(\"(select coalesce(string_agg(sr.source_path || '->' || sr.target_path || ':' || sr.status_code,'|' order by sr.source_path),'') from site_redirects sr where sr.site_id=? and sr.is_active=true and (sr.source_path like '%' || replace(p.external_id,'bitrix:','') || '%' or sr.target_path like '%' || replace(p.external_id,'bitrix:','') || '%' or sr.source_path in (select su.path from site_urls su where su.site_id=? and su.target_type='product' and su.target_id=(select sp.id from site_products sp where sp.product_id=p.id and sp.site_id=? limit 1)) or sr.target_path in (select su.path from site_urls su where su.site_id=? and su.target_type='product' and su.target_id=(select sp.id from site_products sp where sp.product_id=p.id and sp.site_id=? limit 1)))) legacy_redirects\",[$siteId,$siteId,$siteId,$siteId,$siteId])"
        "->selectRaw(\"(select count(*) from catalog_identity_candidates cic where cic.legacy_source='bitrix' and cic.legacy_id=replace(p.external_id,'bitrix:','')) one_c_link_count\")"
        "->selectRaw(\"(select coalesce(string_agg(oci.external_id,'|' order by oci.external_id),'') from catalog_identity_candidates cic join one_c_nomenclature_items oci on oci.id=cic.one_c_nomenclature_item_id where cic.legacy_source='bitrix' and cic.legacy_id=replace(p.external_id,'bitrix:','')) one_c_external_ids\")"
        "->selectRaw(\"(select coalesce(string_agg(coalesce(oci.article,''),'|' order by oci.external_id),'') from catalog_identity_candidates cic join one_c_nomenclature_items oci on oci.id=cic.one_c_nomenclature_item_id where cic.legacy_source='bitrix' and cic.legacy_id=replace(p.external_id,'bitrix:','')) one_c_articles\")"
        "->selectRaw(\"(select coalesce(string_agg(cic.review_status,'|' order by cic.id),'') from catalog_identity_candidates cic where cic.legacy_source='bitrix' and cic.legacy_id=replace(p.external_id,'bitrix:','')) one_c_review_statuses\");"
        "echo json_encode($q->get(),JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES);"
    )


def refresh_db_snapshot(ids: list[str], site_key: str) -> dict:
    encoded = base64.b64encode(php_query(ids, site_key).encode("utf-8")).decode("ascii")
    expression = f"eval(base64_decode('{encoded}'));"
    process = subprocess.run(
        ["docker", "compose", "exec", "-T", "backend", "php", "artisan", "tinker", f"--execute={expression}"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )
    payload = process.stdout.strip()
    if process.returncode != 0 or not payload.startswith("["):
        raise SystemExit(f"Unexpected read-only DB output: {payload or process.stderr.strip()}")
    rows = json.loads(payload)
    snapshot = {
        "schema_version": 1,
        "site": site_key,
        "checked_at": "2026-07-29",
        "query_scope": "read_only_current_postgresql",
        "rows": rows,
    }
    DB_SNAPSHOT.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return snapshot


def legacy_properties(ids: set[str]) -> dict[str, dict[str, str]]:
    numeric = {external_id.removeprefix("bitrix:"): external_id for external_id in ids}
    wanted = {"MINIMUM_PRICE", "MAXIMUM_PRICE", "IN_STOCK"}
    result: dict[str, dict[str, str]] = defaultdict(dict)
    for row in read_csv(PROPERTIES):
        external_id = numeric.get(row["legacy_element_id"])
        if external_id and row["property_code"] in wanted:
            result[external_id][row["property_code"]] = row["source_value_display"]
    return result


def distinct_nonempty(rows: list[dict], field: str) -> set[str]:
    return {str(row.get(field) or "") for row in rows if str(row.get(field) or "")}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", default=SITE_KEY)
    parser.add_argument("--refresh-db", action="store_true")
    args = parser.parse_args()

    groups = candidate_groups()
    all_ids = [external_id for ids in groups.values() for external_id in ids]
    if len(all_ids) != len(set(all_ids)):
        raise SystemExit("A Wave208 product occurs in more than one strict group")
    evidence = {row["product_external_id"]: row for row in read_csv(EVIDENCE)}
    if set(all_ids) - set(evidence):
        raise SystemExit("Wave208 group member missing from Wave207 evidence")
    if any(evidence[external_id]["partition"] != "no_evidence" for external_id in all_ids):
        raise SystemExit("Wave208 duplicate scope unexpectedly gained exact identity evidence")

    snapshot = refresh_db_snapshot(all_ids, args.site) if args.refresh_db else json.loads(DB_SNAPSHOT.read_text(encoding="utf-8-sig"))
    db = {row["external_id"]: row for row in snapshot["rows"]}
    if set(db) != set(all_ids):
        raise SystemExit(f"DB snapshot scope mismatch: missing={sorted(set(all_ids)-set(db))}, extra={sorted(set(db)-set(all_ids))}")
    properties = legacy_properties(set(all_ids))
    canonical = {row["registry_id"]: row for row in read_csv(CANONICAL) if row["registry_id"] in set(all_ids)}

    output: list[dict[str, object]] = []
    group_decisions = {}
    for group_key, member_ids in groups.items():
        members = [db[external_id] for external_id in member_ids]
        names = {evidence[external_id]["name"] for external_id in member_ids}
        flags = {"identity_unverified"}
        if len(names) > 1:
            flags.add("compatibility_or_title_content_differs")
        if any(int(row["price_evidence_count"]) or row.get("price") is not None for row in members):
            flags.add("commercial_evidence_present")
        if len({str(row.get("availability") or "") for row in members}) > 1 or any(row.get("availability") == "in_stock" for row in members):
            flags.add("availability_differs_or_in_stock")
        if len(distinct_nonempty(members, "media_fingerprint")) > 1 or any(int(row["media_count"]) for row in members):
            flags.add("media_requires_transfer_review")
        if len(distinct_nonempty(members, "description_fingerprint")) > 1 or any(int(row["description_count"]) for row in members):
            flags.add("descriptions_require_merge_review")
        if any(int(row["legacy_redirect_count"]) for row in members):
            flags.add("existing_redirect_topology_present")
        if any(int(row["one_c_link_count"]) for row in members) or any(canonical.get(external_id, {}).get("one_c_code") for external_id in member_ids):
            flags.add("one_c_link_requires_identity_review")
        if any(int(row["site_url_count"]) != 1 or int(row["seo_count"]) != 1 for row in members):
            flags.add("url_or_seo_cardinality_drift")
        if any(int(row["seo_indexable_count"]) or int(row["offer_schema_count"]) for row in members):
            flags.add("indexable_or_offer_state_present")

        # No primary Motorola battery snapshot exists in Wave207. Therefore a
        # shared replacement token cannot prove that independently named packs
        # are the same sellable item, even when all commercial fields are empty.
        decision = "hold_no_verified_shared_product_identity"
        survivor = ""
        safe = False
        required = [
            "pin an exact primary Motorola battery source for the offered part",
            "merge and verify all distinct radio-compatibility claims",
            "re-run commercial/media/description/URL/1C loss audit",
        ]
        group_decisions[group_key] = {
            "members": member_ids,
            "decision": decision,
            "survivor_external_id": survivor,
            "safe_to_collapse": safe,
            "loss_flags": sorted(flags),
        }

        for external_id in member_ids:
            row = db[external_id]
            legacy = properties.get(external_id, {})
            canonical_row = canonical.get(external_id, {})
            one_c_ids = row.get("one_c_external_ids") or canonical_row.get("one_c_code") or ""
            one_c_articles = row.get("one_c_articles") or canonical_row.get("one_c_article") or ""
            output.append({
                "group_key": group_key,
                "group_size": len(member_ids),
                "product_external_id": external_id,
                "name": evidence[external_id]["name"],
                "evidence_partition": evidence[external_id]["partition"],
                "current_product_status": row.get("status") or "",
                "current_manufacturer": row.get("manufacturer") or "",
                "current_mpn": row.get("mpn") or "",
                "current_sku": row.get("sku") or "",
                "site_product_count": int(row["site_product_count"]),
                "is_published": str(bool(row.get("is_published"))).lower(),
                "availability": row.get("availability") or "",
                "price": row.get("price") if row.get("price") is not None else "",
                "price_evidence_count": int(row["price_evidence_count"]),
                "current_price_evidence_count": int(row["current_price_evidence_count"]),
                "legacy_minimum_price": legacy.get("MINIMUM_PRICE", ""),
                "legacy_maximum_price": legacy.get("MAXIMUM_PRICE", ""),
                "legacy_in_stock": legacy.get("IN_STOCK", ""),
                "media_count": int(row["media_count"]),
                "published_media_count": int(row["published_media_count"]),
                "verified_media_count": int(row["verified_media_count"]),
                "preview_media_count": int(row["preview_media_count"]),
                "description_count": int(row["description_count"]),
                "applied_description_count": int(row["applied_description_count"]),
                "manufacturer_primary_description_count": int(row["manufacturer_primary_description_count"]),
                "site_url_count": int(row["site_url_count"]),
                "site_paths": row.get("site_paths") or "",
                "seo_count": int(row["seo_count"]),
                "seo_indexable_count": int(row["seo_indexable_count"]),
                "seo_canonical_paths": row.get("seo_canonical_paths") or "",
                "offer_schema_count": int(row["offer_schema_count"]),
                "legacy_redirect_count": int(row["legacy_redirect_count"]),
                "legacy_redirects": row.get("legacy_redirects") or "",
                "one_c_link_count": int(row["one_c_link_count"]),
                "one_c_external_ids": one_c_ids,
                "one_c_articles": one_c_articles,
                "one_c_review_statuses": row.get("one_c_review_statuses") or "",
                "content_loss_flags": "|".join(sorted(flags)),
                "group_decision": decision,
                "survivor_external_id": survivor,
                "safe_to_collapse": str(safe).lower(),
                "required_before_collapse": "|".join(required),
            })

    with OUTPUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(output)

    summary = {
        "schema_version": 1,
        "wave": "wave208_d",
        "site_key": args.site,
        "source_wave": "wave207",
        "groups": len(groups),
        "records": len(output),
        "group_size_counts": dict(sorted(Counter(len(ids) for ids in groups.values()).items())),
        "safe_survivor_groups": 0,
        "held_groups": len(groups),
        "automatic_collapses": 0,
        "database_mutations": 0,
        "current_price_records": sum(bool(str(row["price"])) for row in output),
        "price_evidence_records": sum(int(row["price_evidence_count"]) for row in output),
        "in_stock_records": sum(row["availability"] == "in_stock" for row in output),
        "media_records": sum(int(row["media_count"]) for row in output),
        "verified_media_records": sum(int(row["verified_media_count"]) for row in output),
        "description_records": sum(int(row["description_count"]) for row in output),
        "applied_description_records": sum(int(row["applied_description_count"]) for row in output),
        "site_url_records": sum(int(row["site_url_count"]) for row in output),
        "seo_records": sum(int(row["seo_count"]) for row in output),
        "indexable_seo_records": sum(int(row["seo_indexable_count"]) for row in output),
        "offer_schema_records": sum(int(row["offer_schema_count"]) for row in output),
        "legacy_redirect_records": sum(int(row["legacy_redirect_count"]) for row in output),
        "one_c_link_records": sum(int(row["one_c_link_count"]) for row in output),
        "legacy_price_claim_records": sum(bool(row["legacy_minimum_price"] or row["legacy_maximum_price"]) for row in output),
        "legacy_in_stock_claim_records": sum(str(row["legacy_in_stock"]).upper() in {"Y", "YES", "TRUE", "1"} for row in output),
        "group_decisions": group_decisions,
        "inputs": {
            "wave207_evidence_sha256": sha256(EVIDENCE),
            "wave207_summary_sha256": sha256(WAVE207_SUMMARY),
            "canonical_registry_sha256": sha256(CANONICAL),
            "legacy_properties_sha256": sha256(PROPERTIES),
            "db_snapshot_sha256": sha256(DB_SNAPSHOT),
        },
        "output": {"path": OUTPUT.relative_to(ROOT).as_posix(), "sha256": sha256(OUTPUT)},
        "policy": {
            "survivor_requires_verified_shared_identity": True,
            "empty_commercial_fields_alone_do_not_prove_duplicate": True,
            "no_automatic_merge": True,
        },
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"groups": len(groups), "records": len(output), "safe_survivor_groups": 0, "held_groups": len(groups)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
