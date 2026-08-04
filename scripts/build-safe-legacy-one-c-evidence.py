#!/usr/bin/env python3
"""Build a fail-closed Bitrix-to-1C evidence manifest.

The output is evidence only. It never creates, publishes, merges, or updates a
product. A row is accepted only when two independent matchers agree and the
legacy source still has an active, in-scope page with company-held media.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y"}


def normalized_article(value: str) -> str:
    return re.sub(r"[^0-9A-ZА-ЯЁ]+", "", value.upper())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--bitrix-products", type=Path, required=True)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--site-state", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--rejected", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    args = parser.parse_args()

    candidates = read_csv(args.candidates)
    bitrix_rows = read_csv(args.bitrix_products)
    registry_rows = read_csv(args.registry)
    site_rows = json.loads(args.site_state.read_text(encoding="utf-8-sig"))

    bitrix_by_id = {row["legacy_element_id"].strip(): row for row in bitrix_rows}
    registry_by_id = {row["bitrix_id"].strip(): row for row in registry_rows}
    site_by_external_id = {
        row.get("product", {}).get("external_id", "").strip(): row
        for row in site_rows
        if row.get("product", {}).get("external_id", "").strip()
    }

    prelim: list[dict[str, str]] = []
    rejected: list[dict[str, str]] = []

    def reject(row: dict[str, str], reason: str) -> None:
        rejected.append(
            {
                "legacy_element_id": row.get("Bitrix ID", "").strip(),
                "one_c_external_id": row.get("1С-код", "").strip(),
                "reason": reason,
            }
        )

    seen_legacy: set[str] = set()
    seen_one_c: set[str] = set()
    for row in candidates:
        legacy_id = row.get("Bitrix ID", "").strip()
        one_c_id = row.get("1С-код", "").strip()
        if row.get("confidence", "").strip() != "0.95":
            reject(row, "confidence_not_0_95")
            continue
        if row.get("method", "").strip() != "sig+brand":
            reject(row, "matcher_not_sig_brand")
            continue
        if row.get("brand_ok", "").strip().lower() != "yes":
            reject(row, "brand_gate_failed")
            continue
        if row.get("сравнение", "").strip().lower() != "agree":
            reject(row, "independent_matchers_disagree")
            continue
        if not legacy_id or not one_c_id:
            reject(row, "missing_identity")
            continue
        if legacy_id in seen_legacy or one_c_id in seen_one_c:
            reject(row, "non_unique_candidate_identity")
            continue
        seen_legacy.add(legacy_id)
        seen_one_c.add(one_c_id)

        legacy = bitrix_by_id.get(legacy_id)
        if legacy is None:
            reject(row, "legacy_row_missing")
            continue
        if legacy.get("active", "").strip().upper() != "Y":
            reject(row, "legacy_row_inactive")
            continue
        if not truthy(legacy.get("is_first_focus_candidate", "")):
            reject(row, "outside_first_focus")
            continue
        if not legacy.get("legacy_url_candidate", "").strip():
            reject(row, "legacy_url_missing")
            continue
        if not (
            legacy.get("preview_picture_file_id", "").strip()
            or legacy.get("detail_picture_file_id", "").strip()
        ):
            reject(row, "legacy_media_missing")
            continue

        # The canonical registry predates the independently agreed review queue
        # and contains weaker scored alternatives. Keep it as drift evidence,
        # but never let it override two agreeing strict matchers.
        registry = registry_by_id.get(legacy_id, {})
        site_row = site_by_external_id.get(one_c_id)
        if site_row is None:
            reject(row, "rb_site_product_missing")
            continue
        category_ids = {
            category.get("external_id", "").strip()
            for category in site_row.get("categories", [])
            if category.get("external_id", "").strip()
        }
        if "seo:electronic-components" in category_ids:
            reject(row, "rb_electronics_scope_excluded")
            continue
        prelim.append(
            {**row, "_legacy": legacy, "_registry": registry, "_site": site_row}
        )

    article_groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in prelim:
        article = normalized_article(row.get("1С-Артикул", ""))
        if article:
            article_groups[article].append(row)
    colliding_articles = {
        article
        for article, rows in article_groups.items()
        if len({row["1С-код"].strip() for row in rows}) > 1
    }

    accepted: list[dict[str, object]] = []
    for row in prelim:
        legacy = row["_legacy"]
        registry = row["_registry"]
        site_row = row["_site"]
        article = normalized_article(row.get("1С-Артикул", ""))
        if article and article in colliding_articles:
            reject(row, f"article_collision:{article}")
            continue
        accepted.append(
            {
                "legacy_element_id": row["Bitrix ID"].strip(),
                "legacy_name": legacy["name"].strip(),
                "legacy_url_candidate": legacy["legacy_url_candidate"].strip(),
                "legacy_section_paths": legacy["matched_section_paths"].strip(),
                "preview_picture_file_id": legacy["preview_picture_file_id"].strip(),
                "detail_picture_file_id": legacy["detail_picture_file_id"].strip(),
                "one_c_external_id": row["1С-код"].strip(),
                "one_c_name": row["1С-Наименование"].strip(),
                "article_raw": row["1С-Артикул"].strip(),
                "article_normalized": article,
                "signature": row["signature"].strip(),
                "match_method": row["method"].strip(),
                "match_confidence": row["confidence"].strip(),
                "brand_ok": row["brand_ok"].strip(),
                "matcher_comparison": row["сравнение"].strip(),
                "registry_identity_status": registry.get("identity_status", "").strip(),
                "registry_one_c_external_id": registry.get("one_c_code", "").strip(),
                "registry_agrees": registry.get("one_c_code", "").strip() == row["1С-код"].strip(),
                "rb_site_product_id": site_row.get("id"),
                "rb_is_published": bool(site_row.get("is_published")),
                "rb_category_external_ids": sorted(
                    category.get("external_id", "").strip()
                    for category in site_row.get("categories", [])
                    if category.get("external_id", "").strip()
                ),
                "decision": "safe_staging_evidence",
                "safe_to_apply": False,
            }
        )

    accepted.sort(key=lambda item: (item["one_c_external_id"], item["legacy_element_id"]))
    rejected.sort(key=lambda item: (item["reason"], item["legacy_element_id"]))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "purpose": "Bitrix evidence for already-existing 1C products; never auto-apply",
                "records": accepted,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    with args.rejected.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["legacy_element_id", "one_c_external_id", "reason"],
        )
        writer.writeheader()
        writer.writerows(rejected)

    summary = {
        "candidate_rows": len(candidates),
        "accepted_rows": len(accepted),
        "rejected_rows": len(rejected),
        "rejection_reasons": dict(Counter(row["reason"] for row in rejected)),
        "auto_apply_rows": 0,
    }
    args.summary.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
