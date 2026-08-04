#!/usr/bin/env python3
"""Derive safe SEO taxonomy evidence from the complete Bitrix registry.

It does not copy legacy categories into the new site.  Instead, every legacy
path receives a product-count evidence record and a release recommendation.
Thin leaves are explicitly kept out of the index until they gain unique value.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

EVIDENCE_HEADER = [
    "legacy_path", "depth", "active_product_count", "direct_product_count",
    "recommended_state", "seo_reason",
]


def prefixes(path: str) -> list[str]:
    parts = [part for part in path.strip("/").split("/") if part]
    return ["/".join(parts[:index]) for index in range(1, len(parts) + 1)]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    with args.registry.open(encoding="utf-8-sig", newline="") as handle:
        products = list(csv.DictReader(handle))

    aggregate: Counter[str] = Counter()
    direct: Counter[str] = Counter()
    for product in products:
        if product["is_active"] != "true":
            continue
        path = product["legacy_section_path"].strip("/")
        if not path:
            continue
        direct[path] += 1
        aggregate.update(prefixes(path))

    evidence: list[list[str]] = []
    launch: list[list[str]] = []
    thin: list[list[str]] = []
    for path in sorted(aggregate, key=lambda item: (item.count("/"), item)):
        count = aggregate[path]
        own = direct[path]
        depth = path.count("/") + 1
        if count > own:
            state = "navigation_only"
            reason = "Раздел имеет дочерние товарные ветки; это навигационная категория, индексирование зависит от уникального обзора категории."
        elif own < 3:
            state = "merge_or_noindex"
            reason = "Тонкий листинг: менее трёх прямых товаров, без отдельного экспертного содержания в индекс не выпускается."
        elif own < 8:
            state = "content_required"
            reason = "Небольшой листинг: нужны оригинальный обзор, FAQ и проверенные характеристики до индексирования."
        else:
            state = "candidate_after_quality_gate"
            reason = "Достаточная товарная база; всё равно требуются каноникал, качество карточек и локальная коммерческая информация."
        row = [path, str(depth), str(count), str(own), state, reason]
        evidence.append(row)
        if state == "candidate_after_quality_gate":
            launch.append(row)
        if state == "merge_or_noindex":
            thin.append(row)

    args.out.mkdir(parents=True, exist_ok=True)
    for name, rows in [
        ("full-catalog-taxonomy-evidence.csv", evidence),
        ("full-catalog-taxonomy-launch-candidates.csv", launch),
        ("full-catalog-thin-page-candidates.csv", thin),
    ]:
        with (args.out / name).open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(EVIDENCE_HEADER)
            writer.writerows(rows)
    summary = {
        "source_active_products": sum(product["is_active"] == "true" for product in products),
        "legacy_paths_with_products": len(aggregate),
        "states": dict(Counter(row[4] for row in evidence)),
        "launch_candidates": len(launch),
        "thin_page_candidates": len(thin),
        "invariant": "A legacy URL is evidence, not approval to recreate or index it.",
    }
    (args.out / "full-catalog-taxonomy-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
