#!/usr/bin/env python3
"""Build the reviewed RB UPS/power taxonomy correction manifests.

The lists are deliberately explicit. They come from a complete read-only
review of every live assignment in seo:batteries-ups and seo:power-systems;
this script does not classify products from loose keywords at apply time.
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path


UPS = """КА-00001846 КА-00002908 КА-00003387 КА-00003699 КА-00003710 КА-00003748 КА-00003883 КА-00003944 КА-00003956 КА-00003995 КА-00004112 КА-00004113 КА-00004358 КА-00004366 КА-00004707 КА-00004863 КА-00004889 КА-00004901 КА-00004902 КА-00005082 КА-00005524 КА-00005606 КА-00005636 КА-00005733 КА-00005734 КА-00005755 КА-00005756 КА-00006759 КА-00006872 ФР-00000965""".split()

POWER_SUPPLIES_FROM_BATTERIES = "КА-00002488 КА-00002489".split()

POWER_SUPPLIES = """КА-00000247 КА-00001286 КА-00001420 КА-00001490 КА-00002534 КА-00002579 КА-00002590 КА-00002775 КА-00002806 КА-00002863 КА-00002986 КА-00003330 КА-00003556 КА-00003558 КА-00003567 КА-00003730 КА-00003840 КА-00003887 КА-00003914 КА-00003983 КА-00003991 КА-00003997 КА-00004035 КА-00004050 КА-00004085 КА-00004150 КА-00004151 КА-00004155 КА-00004170 КА-00004242 КА-00004367 КА-00004406 КА-00004504 КА-00004523 КА-00004724 КА-00004725 КА-00004813 КА-00005107 КА-00005111 КА-00005310 КА-00005366 КА-00005376 КА-00005471 КА-00005472 КА-00005497 КА-00005508 КА-00005525 КА-00005564 КА-00005633 КА-00005634 КА-00005657 КА-00005658 КА-00005712 КА-00005763 КА-00005877 КА-00005970 КА-00006078 КА-00006084 КА-00006448 КА-00006664 КА-00006738 КА-00006819 КА-00006822 КА-00006936 КА-00006941 КА-00007021 КА-00007105 КА-00007146 ФР-00000727 ФР-00001269 ФР-00001270 ФР-00001519 ФР-00001523 ФР-00001908 ФР-00001909""".split()

POWER_CONVERTERS = """КА-00002068 КА-00002634 КА-00003555 КА-00004226 КА-00004228 КА-00004229 КА-00004230 КА-00004650 КА-00004651 КА-00005203 КА-00006118 КА-00007148 ФР-00000846 ФР-00001109 ФР-00001347""".split()

OTHER_CORRECTIONS = {
    "seo:chargers": "КА-00002987 КА-00003580 КА-00005374 КА-00005738".split(),
    "seo:primary-cells": "КА-00001851 КА-00004319 КА-00004521 КА-00005036 КА-00005353".split(),
    "seo:rechargeable-cells": ["КА-00006030"],
    "seo:electrical-protection-control": ["КА-00004081"],
    "seo:assembly-materials": ["КА-00005706"],
}

TAXONOMY = [
    ("seo:power-systems", "", "Системы и источники питания", "catalog/power-systems"),
    ("seo:ups-systems", "seo:power-systems", "Источники бесперебойного питания (ИБП)", "catalog/power-systems/ups-systems"),
    ("seo:power-supplies", "seo:power-systems", "Блоки и источники питания", "catalog/power-systems/power-supplies"),
    ("seo:power-converters", "seo:power-systems", "Преобразователи напряжения и инверторы", "catalog/power-systems/power-converters"),
]


def write_csv(path: Path, headers: list[str], rows: list[tuple[str, ...]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path("docs/imports"))
    args = parser.parse_args()

    assert len(UPS) == 30
    assert len(POWER_SUPPLIES_FROM_BATTERIES) == 2
    assert len(POWER_SUPPLIES) == 75
    assert len(POWER_CONVERTERS) == 15
    assert sum(map(len, OTHER_CORRECTIONS.values())) == 12
    reviewed_ids = UPS + POWER_SUPPLIES_FROM_BATTERIES + POWER_SUPPLIES + POWER_CONVERTERS + [
        item for items in OTHER_CORRECTIONS.values() for item in items
    ]
    assert len(reviewed_ids) == len(set(reviewed_ids)), "A product occurs in more than one target list"

    write_csv(
        args.out / "rb-power-taxonomy-wave-73.csv",
        ["external_id", "parent_external_id", "name", "path"],
        TAXONOMY,
    )
    from_batteries = [
        *((product, "seo:batteries-ups", "seo:ups-systems") for product in UPS),
        *((product, "seo:batteries-ups", "seo:power-supplies") for product in POWER_SUPPLIES_FROM_BATTERIES),
    ]
    write_csv(
        args.out / "rb-site-category-move-wave-73-from-batteries-ups.csv",
        ["product_external_id", "from_category_external_id", "to_category_external_id"],
        from_batteries,
    )
    from_power = [("КА-00005756", "seo:power-systems", "seo:ups-systems")]
    from_power.extend((product, "seo:power-systems", "seo:power-supplies") for product in POWER_SUPPLIES)
    from_power.extend((product, "seo:power-systems", "seo:power-converters") for product in POWER_CONVERTERS)
    for target, products in OTHER_CORRECTIONS.items():
        from_power.extend((product, "seo:power-systems", target) for product in products)
    write_csv(
        args.out / "rb-site-category-move-wave-74-from-power-systems.csv",
        ["product_external_id", "from_category_external_id", "to_category_external_id"],
        from_power,
    )
    write_csv(
        args.out / "rb-site-category-move-wave-75-electronics-cleanup.csv",
        ["product_external_id", "from_category_external_id", "to_category_external_id"],
        [("КА-00003325", "seo:electronic-components", "seo:primary-cells")],
    )
    print(f"taxonomy={len(TAXONOMY)} from_batteries={len(from_batteries)} from_power={len(from_power)}")


if __name__ == "__main__":
    main()
