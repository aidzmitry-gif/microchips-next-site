#!/usr/bin/env python3
"""Read-only audit of the live RB tree, real catalogue facets and fact coverage.

The public API is the authority for filters. Stored technical attributes are
coverage evidence only; this tool never promotes them into a filter or page.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs/audits/generated/rb-wave248c-category-filter-audit-2026-07-30.json"
SITE_KEY = "microchips-by"
API_BASE = os.environ.get("RB_CATALOG_API", "http://localhost:8080").rstrip("/")
OVERLOADED_LEAF_THRESHOLD = 1000
INTERNAL_KEYS = {"chemistry_provenance", "source_evidence", "_rejected_fields", "_sanitization", "removed_technical_attributes"}


def fetch_json(url: str) -> dict[str, Any]:
    with urllib.request.urlopen(urllib.request.Request(url, headers={"Accept": "application/json"}), timeout=30) as response:  # nosec B310
        if response.status != 200:
            raise RuntimeError(f"GET {url} returned HTTP {response.status}")
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"GET {url} did not return an object")
    return payload


def flatten_tree(nodes: list[dict[str, Any]], parent_slug: str | None = None) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for node in nodes:
        slug, name, path, children = node.get("slug"), node.get("name"), node.get("path"), node.get("children", [])
        if not isinstance(slug, str) or not isinstance(name, str) or not isinstance(path, str) or not isinstance(children, list):
            raise RuntimeError("catalog categories response has an invalid node")
        result.append({"slug": slug, "name": name, "path": path, "parent_slug": parent_slug})
        result.extend(flatten_tree(children, slug))
    return result


def live_api_snapshot(api_base: str) -> dict[str, Any]:
    roots = fetch_json(f"{api_base}/api/v1/sites/{SITE_KEY}/catalog/categories").get("data")
    if not isinstance(roots, list):
        raise RuntimeError("catalog categories response has no data list")
    categories = flatten_tree(roots)
    if not categories:
        raise RuntimeError("catalog category tree is empty")
    metrics: dict[str, dict[str, Any]] = {}
    for category in categories:
        query = urllib.parse.urlencode({"per_page": "1", "category": category["slug"]})
        meta = fetch_json(f"{api_base}/api/v1/sites/{SITE_KEY}/catalog/products?{query}").get("meta")
        if not isinstance(meta, dict) or not isinstance(meta.get("total"), int):
            raise RuntimeError(f"invalid catalogue meta for {category['slug']}")
        # Laravel serializes an empty PHP associative array as JSON [].
        # Normalize that transport quirk before the report contract insists on
        # a mapping of facet key to options.
        facets = meta.get("facets", {})
        if facets == []:
            facets = {}
        if not isinstance(facets, dict):
            raise RuntimeError(f"invalid catalogue facets for {category['slug']}")
        metrics[category["slug"]] = {"total": meta["total"], "price_sort_enabled": meta.get("price_sort_enabled") is True, "visible_facets": facets}
    root_meta = fetch_json(f"{api_base}/api/v1/sites/{SITE_KEY}/catalog/products?per_page=1").get("meta")
    if not isinstance(root_meta, dict) or not isinstance(root_meta.get("total"), int):
        raise RuntimeError("root catalogue response has no integer total")
    metrics["__catalog_total"] = {"total": root_meta["total"]}
    return {"api_base": api_base, "category_tree": roots, "categories": categories, "api_metrics": metrics}


def postgres_category_facts() -> dict[str, Any]:
    sql = r"""
WITH RECURSIVE pc AS (
 SELECT sc.id,sc.site_id,sc.external_id,sc.slug,sc.category_id,c.parent_id
 FROM site_categories sc JOIN sites s ON s.id=sc.site_id JOIN categories c ON c.id=sc.category_id
 WHERE s.key='microchips-by' AND sc.is_published=true
), d(root_id,node_id) AS (
 SELECT id,id FROM pc
 UNION ALL
 SELECT d.root_id,child.id FROM d JOIN pc cur ON cur.id=d.node_id
 JOIN categories cc ON cc.parent_id=cur.category_id
 JOIN pc child ON child.category_id=cc.id AND child.site_id=cur.site_id
), direct_counts AS (
 SELECT l.site_category_id,COUNT(DISTINCT sp.id)::int AS count
 FROM site_category_product l JOIN site_products sp ON sp.id=l.site_product_id JOIN sites s ON s.id=sp.site_id
 WHERE s.key='microchips-by' AND sp.is_published=true GROUP BY l.site_category_id
), subtree_counts AS (
 SELECT d.root_id,COUNT(DISTINCT sp.id)::int AS count FROM d JOIN site_category_product l ON l.site_category_id=d.node_id
 JOIN site_products sp ON sp.id=l.site_product_id AND sp.is_published=true GROUP BY d.root_id
), af AS (
 SELECT root.external_id AS root_external_id,a.key AS attribute_key,COUNT(DISTINCT sp.id)::int AS product_count,
 COUNT(DISTINCT a.value)::int AS distinct_value_count,
 (ARRAY_AGG(DISTINCT a.value ORDER BY a.value) FILTER (WHERE a.value<>''))[1:5] AS sample_values
 FROM pc root JOIN d ON d.root_id=root.id JOIN site_category_product l ON l.site_category_id=d.node_id
 JOIN site_products sp ON sp.id=l.site_product_id AND sp.is_published=true JOIN products p ON p.id=sp.product_id
 CROSS JOIN LATERAL jsonb_each_text(COALESCE(p.technical_attributes::jsonb,'{}'::jsonb)) AS a(key,value)
 WHERE a.key NOT IN ('chemistry_provenance','source_evidence','_rejected_fields','_sanitization','removed_technical_attributes') AND btrim(a.value)<>''
 GROUP BY root.external_id,a.key
)
SELECT jsonb_build_object(
 'categories',COALESCE((SELECT jsonb_agg(jsonb_build_object('external_id',pc.external_id,'slug',pc.slug,'direct_published_products',COALESCE(dc.count,0),'subtree_published_products',COALESCE(sc.count,0)) ORDER BY pc.id) FROM pc LEFT JOIN direct_counts dc ON dc.site_category_id=pc.id LEFT JOIN subtree_counts sc ON sc.root_id=pc.id),'[]'::jsonb),
 'attribute_facts',COALESCE((SELECT jsonb_agg(jsonb_build_object('root_external_id',root_external_id,'attribute_key',attribute_key,'product_count',product_count,'distinct_value_count',distinct_value_count,'sample_values',sample_values) ORDER BY root_external_id,product_count DESC,attribute_key) FROM af),'[]'::jsonb)
) AS report;
"""
    command = ["docker", "compose", "exec", "-T", "postgres", "sh", "-lc", 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At -v ON_ERROR_STOP=1 -c "$1"', "sh", sql]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="strict")
    if result.returncode:
        raise RuntimeError(f"PostgreSQL aggregate query failed: {result.stderr.strip() or result.stdout.strip()}")
    try:
        data = json.loads(result.stdout.strip())
    except json.JSONDecodeError as error:
        raise RuntimeError("PostgreSQL aggregate query returned invalid JSON") from error
    if not isinstance(data, dict):
        raise RuntimeError("PostgreSQL aggregate query returned invalid shape")
    return data


def coverage_label(count: int, total: int) -> str:
    if total <= 0:
        return "not_applicable"
    return "broad" if count / total >= .9 else "partial" if count / total >= .1 else "sparse"


def implementation_checks() -> dict[str, Any]:
    """Prove the report describes the current backend and frontend contracts."""
    backend = (ROOT / "backend/app/Http/Controllers/Api/V1/CatalogController.php").read_text(encoding="utf-8")
    frontend = (ROOT / "frontend/src/components/catalog-view.tsx").read_text(encoding="utf-8")
    page = (ROOT / "frontend/src/app/[[...path]]/page.tsx").read_text(encoding="utf-8")
    checks = {
        "backend_visibility_gate": "facetPassesVisibilityGate" in backend and "minimumFilled = max(10" in backend,
        "backend_source_backed_price_sort_gate": "Price sorting requires current source-backed prices" in backend,
        "frontend_omits_empty_facet_control": "if (!options?.length) return null;" in frontend,
        "frontend_omits_price_sort_without_backend_flag": "catalog.meta.price_sort_enabled &&" in frontend,
        "query_variants_noindex_follow": "hasCatalogQuery" in page and "{ index: false, follow: true }" in page,
    }
    if not all(checks.values()):
        failed = ", ".join(key for key, passed in checks.items() if not passed)
        raise RuntimeError(f"frontend/backend filter contract drift: {failed}")
    return {
        "checks": checks,
        "files": {
            "backend": "backend/app/Http/Controllers/Api/V1/CatalogController.php",
            "frontend": "frontend/src/components/catalog-view.tsx",
            "seo_metadata": "frontend/src/app/[[...path]]/page.tsx",
        },
    }


def audit(snapshot: dict[str, Any]) -> dict[str, Any]:
    categories, metrics, db = snapshot.get("categories"), snapshot.get("api_metrics"), snapshot.get("db_facts")
    if not isinstance(categories, list) or not isinstance(metrics, dict) or not isinstance(db, dict):
        raise RuntimeError("snapshot has invalid top-level fields")
    facts, attributes = db.get("categories"), db.get("attribute_facts")
    if not isinstance(facts, list) or not isinstance(attributes, list):
        raise RuntimeError("snapshot has invalid database facts")
    facts_by_slug = {x.get("slug"): x for x in facts if isinstance(x, dict) and isinstance(x.get("slug"), str)}
    if len(facts_by_slug) != len(categories):
        raise RuntimeError(f"category scope drift: API={len(categories)}, database={len(facts_by_slug)}")
    children: dict[str | None, list[str]] = {}
    rows: list[dict[str, Any]] = []
    for node in categories:
        if not isinstance(node, dict):
            raise RuntimeError("invalid category")
        slug, parent = node.get("slug"), node.get("parent_slug")
        metric, fact = metrics.get(slug), facts_by_slug.get(slug)
        if not isinstance(slug, str) or not isinstance(metric, dict) or not isinstance(fact, dict):
            raise RuntimeError(f"missing evidence for {slug!r}")
        total, direct, subtree = metric.get("total"), fact.get("direct_published_products"), fact.get("subtree_published_products")
        if not isinstance(total, int) or not isinstance(direct, int) or not isinstance(subtree, int) or total != subtree:
            raise RuntimeError(f"category count drift for {slug}: api={total}, db={subtree}")
        children.setdefault(parent if isinstance(parent, str) else None, []).append(slug)
        rows.append({"slug":slug,"name":node.get("name"),"path":node.get("path"),"parent_slug":parent,"direct_published_products":direct,"subtree_published_products":subtree,"is_leaf":False,"price_sort_enabled":metric.get("price_sort_enabled") is True})
    by_slug = {x["slug"]: x for x in rows}
    for row in rows:
        row["is_leaf"] = not children.get(row["slug"])
    roots, leaves = [x for x in rows if x["parent_slug"] is None], [x for x in rows if x["is_leaf"]]
    empty = [x["slug"] for x in rows if x["subtree_published_products"] == 0]
    overloaded = [{"slug":x["slug"],"name":x["name"],"published_products":x["subtree_published_products"],"threshold":OVERLOADED_LEAF_THRESHOLD} for x in leaves if x["subtree_published_products"] > OVERLOADED_LEAF_THRESHOLD]
    mixed = [{"slug":x["slug"],"name":x["name"],"direct_published_products":x["direct_published_products"],"child_count":len(children[x["slug"]])} for x in rows if not x["is_leaf"] and x["direct_published_products"] > 0]
    safe_by_category, visible = [], Counter()
    for row in rows:
        exposed = metrics[row["slug"]].get("visible_facets", {})
        if not isinstance(exposed, dict):
            raise RuntimeError(f"invalid facets for {row['slug']}")
        safe = []
        for key, options in sorted(exposed.items()):
            if not isinstance(key, str) or not isinstance(options, list):
                raise RuntimeError(f"invalid facet shape for {row['slug']}")
            values = []
            for option in options:
                if not isinstance(option, dict) or not isinstance(option.get("value"), str) or not isinstance(option.get("count"), int):
                    raise RuntimeError(f"invalid option for {row['slug']}/{key}")
                values.append({"value":option["value"],"count":option["count"]})
            if values:
                visible[key] += 1
                safe.append({"key":key,"option_count":len(values),"options":values})
        safe_by_category.append({"slug":row["slug"],"published_products":row["subtree_published_products"],"safe_visible_facets":safe})
    renderable_coverage = []
    for category in safe_by_category:
        for facet in category["safe_visible_facets"]:
            # CatalogController forms one facet value per product.  The sum of
            # its option counts is therefore the API-visible filled-value
            # coverage for this displayable facet.
            filled = sum(option["count"] for option in facet["options"])
            renderable_coverage.append({
                "category_slug": category["slug"],
                "facet_key": facet["key"],
                "products_with_api_visible_value": filled,
                "category_published_products": category["published_products"],
                "coverage": coverage_label(filled, category["published_products"]),
                "safe_for_public_filter": True,
                "reason": "CatalogController visibility gate returned this facet for the selected category.",
            })
    roots_by_external = {facts_by_slug[slug].get("external_id"): row for slug,row in by_slug.items()}
    coverage = []
    for fact in attributes:
        if not isinstance(fact, dict):
            raise RuntimeError("invalid raw attribute fact")
        root,key,count,samples = roots_by_external.get(fact.get("root_external_id")),fact.get("attribute_key"),fact.get("product_count"),fact.get("sample_values")
        if root is None or not isinstance(key,str) or key in INTERNAL_KEYS or not isinstance(count,int) or not isinstance(samples,list):
            raise RuntimeError("raw attribute fact failed scope/provenance validation")
        coverage.append({"root_slug":root["slug"],"root_name":root["name"],"attribute_key":key,"products_with_stored_value":count,"root_published_products":root["subtree_published_products"],"coverage":coverage_label(count,root["subtree_published_products"]),"distinct_value_count":fact.get("distinct_value_count"),"sample_values":samples,"safe_for_public_filter":False,"reason":"Stored value is coverage evidence only; use the live API visibility gate for public filters."})
    return {
      "schema_version":1,"batch":"rb_wave248c_category_filter_audit",
      "scope":{"site_key":SITE_KEY,"electronic_components_excluded":True,"database_mutations":0,"source_of_filter_truth":"live CatalogController API visibility gate"},
      "summary":{"roots":len(roots),"category_nodes":len(rows),"leaf_nodes":len(leaves),"published_catalog_products":metrics.get("__catalog_total",{}).get("total"),"empty_categories":len(empty),"overloaded_leaf_categories":len(overloaded),"mixed_navigation_categories":len(mixed),"facet_keys_visible_in_at_least_one_category":dict(sorted(visible.items()))},
      "categories":rows,"empty_categories":empty,"overloaded_leaf_categories":overloaded,"mixed_navigation_categories":mixed,"public_safe_filters_by_category":safe_by_category,"api_visibility_gated_renderable_facet_coverage":renderable_coverage,"stored_technical_attribute_coverage":coverage,
      "frontend_backend_contract":implementation_checks(),
      "bounded_delta":{"database_apply":False,"category_creations":0,"category_moves":0,"product_attribute_writes":0,"indexable_filter_url_creations":0,"allowed_ui_change":"Render only safe_visible_facets returned by the existing API for the selected category; keep filter/query URLs noindex and canonical to the category URL.","review_queue":{"overloaded_leaf_categories":[x["slug"] for x in overloaded],"mixed_navigation_categories":[x["slug"] for x in mixed],"rule":"Create a child category only after a product-type evidence manifest proves an exclusive buyer-intent assignment. Never derive a category from a sparse raw technical attribute."}},
      "verification":{"api_category_and_database_category_counts_must_match":True,"all_category_totals_match_api_and_database_subtree_counts":True,"no_name_parsing":True,"raw_attributes_not_automatically_promoted_to_filters":True},
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--api-base", default=API_BASE)
    args = parser.parse_args()
    if args.snapshot:
        raw = args.snapshot.read_bytes()
        snapshot = json.loads(raw.decode("utf-8"))
        source = {"kind":"offline_snapshot","path":str(args.snapshot),"sha256":hashlib.sha256(raw).hexdigest()}
    else:
        snapshot = live_api_snapshot(args.api_base.rstrip("/"))
        snapshot["db_facts"] = postgres_category_facts()
        source = {"kind":"live_local_api_and_read_only_postgresql","api_base":args.api_base.rstrip("/")}
    report = audit(snapshot)
    report["input"],report["generated_at_utc"] = source,datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"output":str(args.output),**report["summary"]},ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError,urllib.error.URLError,json.JSONDecodeError,subprocess.SubprocessError) as error:
        print(f"ERROR: {error}",file=sys.stderr)
        raise SystemExit(1)
