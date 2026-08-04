#!/usr/bin/env python3
"""Build a fail-closed bulk legacy-media review queue from applied evidence."""
from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path


ALLOWED_CATEGORIES = {
    "seo:batteries-industrial", "seo:batteries-traction", "seo:batteries-ups",
    "seo:chargers", "seo:power-converters", "seo:power-supplies", "seo:power-systems",
    "seo:primary-cells", "seo:rechargeable-cells", "seo:ups-systems",
}


def compact(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "").casefold().replace("ё", "е")
    return re.sub(r"[^a-zа-я0-9]+", "", value)


def brand(value: str) -> str:
    aliases = {
        "apc by schneider electric": "apc",
        "b.b. battery": "bbbattery",
        "bb battery": "bbbattery",
    }
    normalized = unicodedata.normalize("NFKC", value or "").casefold().strip()
    return aliases.get(normalized, compact(normalized.split(" by ", 1)[0]))


def csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def excluded_ids(imports_dir: Path, generated_dir: Path) -> set[str]:
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
            value = row.get("product_external_id") or row.get("1С-код")
            if isinstance(value, str) and re.fullmatch(r"(?:КА|ФР)-\d+", value.strip()):
                result.add(value.strip())
    return result


def strict_links(path: Path) -> dict[str, set[str]]:
    links: dict[str, set[str]] = defaultdict(set)
    for row in csv_rows(path):
        if row.get("confidence") != "0.95" or row.get("brand_ok") != "yes":
            continue
        external_id = (row.get("1С-код") or "").strip()
        legacy_id = (row.get("Bitrix ID") or "").strip()
        if external_id and legacy_id:
            links[external_id].add(legacy_id)
    return links


def previously_reviewed_ids(generated_dir: Path, ignored_visual_names: set[str] | None = None) -> set[str]:
    ignored_visual_names = ignored_visual_names or set()
    reviewed: set[str] = set()
    for path in generated_dir.glob("rb-company-owned-media-visual-*.csv"):
        if path.name in ignored_visual_names:
            continue
        for row in csv_rows(path):
            external_id = (row.get("external_id") or "").strip()
            if external_id:
                reviewed.add(external_id)
    return reviewed


def build(applied_path: Path, site_state_path: Path, media_ids_path: Path,
          legacy_path: Path, strict_links_path: Path, imports_dir: Path,
          generated_dir: Path, output: Path,
          ignored_visual_names: set[str] | None = None) -> dict[str, int]:
    applied = json.loads(applied_path.read_text(encoding="utf-8-sig"))
    site_state = json.loads(site_state_path.read_text(encoding="utf-8-sig"))
    existing_media = set(json.loads(media_ids_path.read_text(encoding="utf-8-sig")))
    legacy = csv_rows(legacy_path)
    exclusions = excluded_ids(imports_dir, generated_dir)
    reviewed_media = previously_reviewed_ids(generated_dir, ignored_visual_names)
    links = strict_links(strict_links_path)
    link_owners: dict[str, set[str]] = defaultdict(set)
    for linked_external_id, legacy_ids in links.items():
        for legacy_id in legacy_ids:
            link_owners[legacy_id].add(linked_external_id)

    site_by_external: dict[str, dict] = {}
    for row in site_state:
        product = row.get("product") or {}
        external_id = product.get("external_id")
        if external_id:
            site_by_external[external_id] = row
    legacy_by_id = {row["legacy_element_id"]: row for row in legacy}

    evidence: list[dict[str, str]] = []
    rejected: list[dict[str, str]] = []
    identities: dict[tuple[str, str], list[str]] = defaultdict(list)
    for draft in applied:
        product = draft.get("product") or {}
        fields = draft.get("verified_fields") or {}
        external_id = str(product.get("external_id") or "").strip()
        identity = str(fields.get("mpn") or fields.get("model") or "").strip()
        manufacturer = str(fields.get("manufacturer") or product.get("manufacturer") or "").strip()
        scope = "exact" if fields.get("mpn") else "model_core"
        if not external_id or len(compact(identity)) < 4 or len(brand(manufacturer)) < 2:
            rejected.append({"external_id": external_id, "reason": "missing_stable_identity_or_manufacturer"})
            continue
        evidence.append({
            "external_id": external_id,
            "manufacturer": manufacturer,
            "identity": identity,
            "identity_scope": scope,
            "source_url": str((draft.get("source_urls") or [""])[0]),
        })
        identities[(brand(manufacturer), compact(identity))].append(external_id)

    candidates: list[dict[str, str]] = []
    used_legacy: set[str] = set()
    for item in evidence:
        external_id = item["external_id"]
        site = site_by_external.get(external_id)
        if site is None:
            rejected.append({"external_id": external_id, "reason": "not_assigned_to_rb_site"})
            continue
        if external_id in existing_media:
            rejected.append({"external_id": external_id, "reason": "storefront_media_already_exists"})
            continue
        if external_id in reviewed_media:
            rejected.append({"external_id": external_id, "reason": "legacy_media_already_visually_reviewed"})
            continue
        if external_id in exclusions:
            rejected.append({"external_id": external_id, "reason": "scope_or_duplicate_exclusion"})
            continue
        categories = {str(row.get("external_id")) for row in site.get("categories", [])}
        if not categories or not categories.issubset(ALLOWED_CATEGORIES):
            rejected.append({"external_id": external_id, "reason": "unclassified_or_out_of_scope_taxonomy"})
            continue
        identity_key = (brand(item["manufacturer"]), compact(item["identity"]))
        if len(identities[identity_key]) != 1:
            rejected.append({"external_id": external_id, "reason": "duplicate_current_brand_model_identity"})
            continue
        product = site.get("product") or {}
        if identity_key[1] not in compact(str(product.get("name") or "")) or identity_key[0] not in compact(str(product.get("name") or "")):
            rejected.append({"external_id": external_id, "reason": "current_name_missing_brand_or_identity"})
            continue

        def matches(row: dict[str, str]) -> bool:
            name = compact(row.get("name", ""))
            return (identity_key[1] in name and identity_key[0] in name
                    and bool(row.get("preview_picture_file_id")) and bool(row.get("detail_picture_file_id")))

        linked_matches = [legacy_by_id[value] for value in links.get(external_id, set())
                          if value in legacy_by_id and matches(legacy_by_id[value])]
        if any(len(link_owners[row["legacy_element_id"]]) != 1 for row in linked_matches):
            rejected.append({"external_id": external_id, "reason": "ambiguous_strict_legacy_links"})
            continue
        linked = linked_matches
        if len(linked) == 1:
            legacy_matches = linked
            link_evidence = "reviewed_strict_link_plus_literal_brand_model"
        elif len(linked) > 1:
            rejected.append({"external_id": external_id, "reason": "ambiguous_strict_legacy_links"})
            continue
        else:
            legacy_matches = [row for row in legacy if matches(row)]
            link_evidence = "unique_legacy_literal_brand_model"
        if len(legacy_matches) != 1:
            rejected.append({"external_id": external_id, "reason": "missing_or_ambiguous_legacy_brand_model"})
            continue
        legacy_row = legacy_matches[0]
        legacy_id = legacy_row["legacy_element_id"]
        if legacy_id in used_legacy:
            rejected.append({"external_id": external_id, "reason": "legacy_element_reused"})
            continue
        used_legacy.add(legacy_id)
        candidates.append({
            **item,
            "legacy_element_id": legacy_id,
            "legacy_name": legacy_row["name"],
            "preview_picture_file_id": legacy_row["preview_picture_file_id"],
            "detail_picture_file_id": legacy_row["detail_picture_file_id"],
            "category_external_ids": "|".join(sorted(categories)),
            "identity_evidence": link_evidence,
            "decision": "requires_archive_hash_and_visual_exact_model_rating_check",
        })

    fields = ["external_id", "manufacturer", "identity", "identity_scope", "source_url",
              "legacy_element_id", "legacy_name", "preview_picture_file_id", "detail_picture_file_id",
              "category_external_ids", "identity_evidence", "decision"]
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(candidates)
    rejected_path = output.with_name(output.stem + "-rejected.csv")
    with rejected_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["external_id", "reason"])
        writer.writeheader()
        writer.writerows(rejected)
    reasons: dict[str, int] = defaultdict(int)
    for row in rejected:
        reasons[row["reason"]] += 1
    summary = {
        "applied_drafts": len(applied),
        "stable_evidence_rows": len(evidence),
        "existing_media_excluded": len(existing_media),
        "previously_reviewed_media_ids": len(reviewed_media),
        "explicit_exclusion_ids": len(exclusions),
        "candidates_for_visual_review": len(candidates),
        "rejected": len(rejected),
        "rejection_reasons": dict(sorted(reasons.items())),
        "automatic_imports": 0,
    }
    output.with_suffix(".summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--applied", type=Path, required=True)
    parser.add_argument("--site-state", type=Path, required=True)
    parser.add_argument("--media-ids", type=Path, required=True)
    parser.add_argument("--legacy-products", type=Path, required=True)
    parser.add_argument("--strict-links", type=Path, required=True)
    parser.add_argument("--imports-dir", type=Path, required=True)
    parser.add_argument("--generated-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ignore-visual-file", action="append", default=[],
                        help="Exact current-wave visual CSV filename to ignore when reproducing its frozen queue")
    args = parser.parse_args()
    print(json.dumps(build(args.applied, args.site_state, args.media_ids, args.legacy_products,
                           args.strict_links, args.imports_dir, args.generated_dir, args.output,
                           set(args.ignore_visual_file)), ensure_ascii=False))


if __name__ == "__main__":
    main()
