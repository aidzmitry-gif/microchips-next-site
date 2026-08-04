#!/usr/bin/env python3
"""Build a fail-closed bulk noindex preview manifest from applied evidence.

The output makes already enriched products visible to users without claiming
indexability, stock or an unverified price. It never resolves duplicate
identities by choosing an arbitrary winner.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse


CATEGORY_SLUGS = {
    "seo:batteries-industrial": "catalog/industrial-batteries/batteries-industrial",
    "seo:batteries-traction": "catalog/industrial-batteries/batteries-traction",
    "seo:batteries-ups": "catalog/industrial-batteries/batteries-ups",
    "seo:chargers": "catalog/chargers",
    "seo:power-converters": "catalog/power-systems/power-converters",
    "seo:power-supplies": "catalog/power-systems/power-supplies",
    "seo:power-systems": "catalog/power-systems",
    "seo:primary-cells": "catalog/primary-cells",
    "seo:rechargeable-cells": "catalog/rechargeable-cells",
    "seo:ups-systems": "catalog/power-systems/ups-systems",
}


def compact(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "").casefold().replace("ё", "е")
    return re.sub(r"[^a-zа-я0-9]+", "", value)


def brand(value: str) -> str:
    aliases = {
        "apc by schneider electric": "apc",
        "b.b. battery": "bbbattery",
        "bb battery": "bbbattery",
        "csb energy technology": "csb",
    }
    normalized = unicodedata.normalize("NFKC", value or "").casefold().strip()
    return aliases.get(normalized, compact(normalized.split(" by ", 1)[0]))


def slug(value: str) -> str:
    aliases = {"b.b. battery": "bb-battery"}
    value = aliases.get(value.casefold(), value)
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().casefold()
    return re.sub(r"[^a-z0-9]+", "-", value).strip("-")


def csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def hard_excluded_ids(imports_dir: Path, generated_dir: Path) -> set[str]:
    paths = [
        *imports_dir.glob("rb-scope-exclusion-*.csv"),
        *imports_dir.glob("rb-strict-duplicate-exclusion-*.csv"),
        *imports_dir.glob("rb-duplicate-exclusion-*.csv"),
        *generated_dir.glob("one-c-clear-out-of-scope-refresh-*.csv"),
        *generated_dir.glob("one-c-seo-category-out-of-scope-refresh-*.csv"),
    ]
    result: set[str] = set()
    for path in paths:
        if not path.is_file():
            continue
        for row in csv_rows(path):
            external_id = (row.get("product_external_id") or row.get("1С-код") or "").strip()
            if external_id:
                result.add(external_id)
    return result


def valid_https_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc)


def build(applied_path: Path, site_state_path: Path, imports_dir: Path,
          generated_dir: Path, output: Path) -> dict[str, object]:
    applied = json.loads(applied_path.read_text(encoding="utf-8-sig"))
    site_state = json.loads(site_state_path.read_text(encoding="utf-8-sig"))
    exclusions = hard_excluded_ids(imports_dir, generated_dir)
    site_by_external: dict[str, dict[str, object]] = {}
    for row in site_state:
        product = row.get("product") or {}
        external_id = product.get("external_id")
        if isinstance(external_id, str) and external_id:
            if external_id in site_by_external:
                raise ValueError(f"duplicate site state external_id {external_id}")
            site_by_external[external_id] = row

    evidence: list[dict[str, object]] = []
    identity_members: dict[tuple[str, str], list[str]] = defaultdict(list)
    for index, draft in enumerate(applied):
        if not isinstance(draft, dict):
            raise ValueError(f"applied row {index} must be an object")
        product = draft.get("product") or {}
        fields = draft.get("verified_fields") or {}
        external_id = str(product.get("external_id") or "").strip()
        manufacturer = str(fields.get("manufacturer") or product.get("manufacturer") or "").strip()
        identity = str(fields.get("mpn") or fields.get("model") or "").strip()
        scope = "exact" if fields.get("mpn") else "model_core"
        source_urls = draft.get("source_urls") or []
        source_url = str(source_urls[0] if source_urls else "").strip()
        identity_key = (brand(manufacturer), compact(identity))
        if external_id and len(identity_key[0]) >= 2 and len(identity_key[1]) >= 4:
            identity_members[identity_key].append(external_id)
        evidence.append({
            "external_id": external_id,
            "manufacturer": manufacturer,
            "identity": identity,
            "identity_scope": scope,
            "source_url": source_url,
            "identity_key": identity_key,
        })

    provisional: list[dict[str, object]] = []
    rejected: list[dict[str, str]] = []
    for item in evidence:
        external_id = str(item["external_id"])
        identity_key = item["identity_key"]
        if not external_id or len(identity_key[0]) < 2 or len(identity_key[1]) < 4:
            rejected.append({"external_id": external_id, "reason": "missing_stable_identity_or_manufacturer"})
            continue
        if external_id in exclusions:
            rejected.append({"external_id": external_id, "reason": "hard_scope_or_duplicate_exclusion"})
            continue
        if len(identity_members[identity_key]) != 1:
            rejected.append({"external_id": external_id, "reason": "duplicate_current_brand_model_identity"})
            continue
        site = site_by_external.get(external_id)
        if site is None:
            rejected.append({"external_id": external_id, "reason": "not_assigned_to_rb_site"})
            continue
        categories = {str(row.get("external_id")) for row in site.get("categories", [])}
        if len(categories) != 1 or not categories.issubset(CATEGORY_SLUGS):
            rejected.append({"external_id": external_id, "reason": "ambiguous_or_out_of_scope_taxonomy"})
            continue
        product = site.get("product") or {}
        current_name = str(product.get("name") or "")
        if identity_key[0] not in compact(current_name) or identity_key[1] not in compact(current_name):
            rejected.append({"external_id": external_id, "reason": "current_name_missing_brand_or_identity"})
            continue
        source_url = str(item["source_url"])
        if not valid_https_url(source_url):
            rejected.append({"external_id": external_id, "reason": "missing_https_source_url"})
            continue
        product_slug = slug(f"{item['manufacturer']} {item['identity']}")
        if not product_slug:
            rejected.append({"external_id": external_id, "reason": "empty_product_slug"})
            continue
        category_external_id = next(iter(categories))
        row: dict[str, object] = {
            "external_id": external_id,
            "manufacturer": item["manufacturer"],
            "identity_scope": item["identity_scope"],
            "source_url": source_url,
            "category_slug": CATEGORY_SLUGS[category_external_id],
            "product_slug": product_slug,
        }
        row["mpn" if item["identity_scope"] == "exact" else "model_core"] = item["identity"]
        if site.get("price") is not None:
            row["allow_verified_price"] = True
        provisional.append(row)

    slug_members: dict[str, list[str]] = defaultdict(list)
    for row in provisional:
        slug_members[str(row["product_slug"])].append(str(row["external_id"]))
    products: list[dict[str, object]] = []
    for row in provisional:
        if len(slug_members[str(row["product_slug"])]) != 1:
            rejected.append({"external_id": str(row["external_id"]), "reason": "duplicate_product_slug"})
        else:
            products.append(row)

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({
        "schema_version": 1,
        "purpose": "Bulk source-backed noindex preview; no stock, offer or indexability claim.",
        "locale": "ru-BY",
        "products": products,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    rejected_path = output.with_name(output.stem + "-rejected.csv")
    with rejected_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["external_id", "reason"])
        writer.writeheader()
        writer.writerows(rejected)
    reasons: dict[str, int] = defaultdict(int)
    for row in rejected:
        reasons[row["reason"]] += 1
    summary: dict[str, object] = {
        "applied_drafts": len(applied),
        "hard_exclusion_ids": len(exclusions),
        "preview_products": len(products),
        "already_published_in_snapshot": sum(
            1 for row in products if bool(site_by_external[str(row["external_id"])].get("is_published"))
        ),
        "rejected": len(rejected),
        "rejection_reasons": dict(sorted(reasons.items())),
        "indexable_urls": 0,
        "offers_created": 0,
    }
    output.with_suffix(".summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--applied", type=Path, required=True)
    parser.add_argument("--site-state", type=Path, required=True)
    parser.add_argument("--imports-dir", type=Path, required=True)
    parser.add_argument("--generated-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.applied, args.site_state, args.imports_dir,
                           args.generated_dir, args.output), ensure_ascii=False))


if __name__ == "__main__":
    main()
