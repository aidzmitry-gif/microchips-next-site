#!/usr/bin/env python3
"""Create an evidence-based target taxonomy from the complete registry.

The old Bitrix path is used only for classification.  The output intentionally
has a small stable hierarchy that customers can navigate; model/brand pages are
filters, not a mass of indexable categories.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Rule:
    slug: str
    parent: str
    name: str
    prefixes: tuple[str, ...]
    filters: str
    index_policy: str


RULES = (
    Rule("batteries-ups", "industrial-batteries", "Аккумуляторы для ИБП", ("akkumulyatory/dlya_ibp",), "manufacturer,technology,voltage,capacity,terminal", "category_after_content_gate"),
    Rule("batteries-industrial", "industrial-batteries", "Промышленные аккумуляторы", ("akkumulyatory/promyshlennye",), "manufacturer,technology,voltage,capacity,application", "category_after_content_gate"),
    Rule("batteries-traction", "industrial-batteries", "Тяговые аккумуляторы", ("akkumulyatory/tyagovye",), "manufacturer,technology,voltage,capacity,application", "category_after_content_gate"),
    Rule("replacement-laptops", "replacement-batteries", "Аккумуляторы для ноутбуков", ("akkumulyatory/dlya-kompyuternoy-tekhniki",), "manufacturer,device_brand,device_model,voltage,capacity", "category_after_content_gate; model filters noindex"),
    Rule("replacement-mobile", "replacement-batteries", "Аккумуляторы для телефонов и планшетов", ("akkumulyatory/smartfony-i-gadzhety",), "manufacturer,device_brand,device_model,voltage,capacity", "category_after_content_gate; model filters noindex"),
    Rule("replacement-photo", "replacement-batteries", "Аккумуляторы для фото-, видео- и аудиотехники", ("akkumulyatory/dlya-foto-video-audio-tekhniki",), "manufacturer,device_brand,device_model,voltage,capacity", "category_after_content_gate; model filters noindex"),
    Rule("replacement-tools", "replacement-batteries", "Аккумуляторы для электроинструмента", ("akkumulyatory/dlya_elektroinstrumenta",), "manufacturer,device_brand,device_model,voltage,capacity", "category_after_content_gate; model filters noindex"),
    Rule("replacement-home", "replacement-batteries", "Аккумуляторы для бытовой техники", ("akkumulyatory/dlya-bytovoy-domashney-tekhniki",), "manufacturer,device_type,device_model,voltage,capacity", "category_after_content_gate; model filters noindex"),
    Rule("replacement-transport", "replacement-batteries", "Аккумуляторы для электротранспорта", ("akkumulyatory/dlya_elektrotransporta",), "manufacturer,device_type,voltage,capacity,technology", "category_after_content_gate"),
    Rule("replacement-medical", "replacement-batteries", "Аккумуляторы для медицинской техники", ("akkumulyatory/promyshlennye/dlya-meditsinskoy-tekhniki",), "manufacturer,device_brand,device_model,voltage,capacity", "category_after_content_gate; model filters noindex"),
    Rule("primary-cells", "", "Батарейки", ("batareyki",), "manufacturer,chemistry,format,voltage,package_size", "category_after_content_gate"),
    Rule("rechargeable-cells", "", "Аккумуляторные элементы", ("akkumulyatornye-batareyki",), "manufacturer,chemistry,format,voltage,capacity", "category_after_content_gate"),
    Rule("power-systems", "", "Источники питания", ("istochniki-pitaniya",), "manufacturer,device_type,power,voltage,input_voltage", "category_after_content_gate"),
    Rule("chargers", "", "Зарядные устройства", ("zaryadnye_ustroystva",), "manufacturer,chemistry,channel_count,input_voltage", "category_after_content_gate"),
    Rule("electronic-components", "", "Электронные компоненты", ("mikroelektronika",), "manufacturer,component_type,package,parameters", "noindex_until_component_data_gate"),
    Rule("warehouse-equipment", "", "Складское оборудование", ("skladskoe-oborudovanie",), "manufacturer,equipment_type,load_capacity", "content_required"),
    Rule("flashlights", "", "Фонари", ("fonari",), "manufacturer,light_type,power,supply_type", "content_required"),
)

ROOTS = {
    "industrial-batteries": "Аккумуляторы для бизнеса",
    "replacement-batteries": "Аккумуляторы для устройств",
}


def select_rule(path: str) -> Rule | None:
    matches = [
        (len(prefix), rule)
        for rule in RULES
        for prefix in rule.prefixes
        if path == prefix or path.startswith(prefix + "/")
    ]
    return max(matches, key=lambda item: item[0])[1] if matches else None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    with args.registry.open(encoding="utf-8-sig", newline="") as handle:
        products = [row for row in csv.DictReader(handle) if row["is_active"] == "true"]

    totals: Counter[str] = Counter()
    unassigned: list[dict[str, str]] = []
    for product in products:
        rule = select_rule(product["legacy_section_path"])
        if rule is None:
            unassigned.append(product)
        else:
            totals[rule.slug] += 1
    if unassigned:
        raise SystemExit(f"Unassigned active products: {len(unassigned)}")

    args.out.mkdir(parents=True, exist_ok=True)
    tree_path = args.out / "full-catalog-seo-tree-proposal.csv"
    with tree_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["slug", "parent_slug", "name", "active_products", "filters", "index_policy", "source_rule"])
        for slug, name in ROOTS.items():
            writer.writerow([slug, "", name, sum(totals[rule.slug] for rule in RULES if rule.parent == slug), "", "navigation_with_unique_editorial_content", "target_root"])
        for rule in RULES:
            writer.writerow([rule.slug, rule.parent, rule.name, totals[rule.slug], rule.filters, rule.index_policy, "|".join(rule.prefixes)])
    draft_rows: list[list[str]] = []
    for slug, name in ROOTS.items():
        draft_rows.append([f"seo:{slug}", "", name, f"catalog/{slug}"])
    for rule in RULES:
        parent_id = f"seo:{rule.parent}" if rule.parent else ""
        path = f"catalog/{rule.parent}/{rule.slug}" if rule.parent else f"catalog/{rule.slug}"
        draft_rows.append([f"seo:{rule.slug}", parent_id, rule.name, path])
    with (args.out / "full-catalog-seo-tree-draft.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["external_id", "parent_external_id", "name", "path"])
        writer.writerows(draft_rows)

    # Only exact Bitrix-to-1C identity links may become automatic assignments.
    # A similar title, an article fragment or a legacy URL is not sufficient
    # evidence that a shared 1C product is the same physical product.
    exact_assignments: list[list[str]] = []
    for product in products:
        if product["identity_status"] != "linked_exact_name" or not product["one_c_code"]:
            continue
        rule = select_rule(product["legacy_section_path"])
        if rule is None:
            raise SystemExit(f"No target rule for exact-linked product {product['registry_id']}")
        exact_assignments.append([product["one_c_code"], f"seo:{rule.slug}"])
    with (args.out / "full-catalog-seo-tree-exact-linked-assignments.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["product_external_id", "category_external_id"])
        writer.writerows(exact_assignments)
    summary = {
        "active_products": len(products),
        "target_leaf_categories": len(RULES),
        "target_roots": len(ROOTS) + sum(1 for rule in RULES if not rule.parent),
        "assigned_products": sum(totals.values()),
        "draft_categories": len(draft_rows),
        "exact_identity_assignments": len(exact_assignments),
        "assignment_rule": "Only active linked_exact_name rows with a 1C code are emitted; every other legacy row remains out of automatic assignment.",
        "distribution": dict(totals),
        "invariant": "Every active legacy product maps to exactly one target leaf; URL filters are not automatically indexable.",
    }
    (args.out / "full-catalog-seo-tree-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
