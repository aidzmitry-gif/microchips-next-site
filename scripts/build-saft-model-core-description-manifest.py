#!/usr/bin/env python3
"""Build a bounded SAFT model-core description manifest from the verified queue.

The official datasheets describe a cell model core, not each local connector,
terminal, bundle or OEM assembly.  Therefore generated rows intentionally omit
MPN and carry `identity_scope=model_core`; the Laravel import gate must keep the
existing exact identity untouched.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path


SERIES = {
    "LS14250": {
        "source_url": "https://saft4u.saft.com/en/download_file/133c84de-f6e9-46b6-a412-fc4ed453fb5c/English",
        "size": "1/2 AA",
        "capacity": "1,2 А·ч при 1 мА, +20 °C, до 2,0 В",
        "energy": "4,32 Вт·ч",
        "pulse": "до 100 мА",
        "continuous": "35 мА",
        "dimensions": "диаметр не более 14,62 мм; высота не более 25,13 мм",
        "weight": "типично 9 г",
    },
    "LS14500": {
        "source_url": "https://saft4u.saft.com/en/download_file/738dfd7b-3131-4e31-8924-401cd9a36bbc/English",
        "size": "AA",
        "capacity": "2,6 А·ч при 2 мА, +20 °C, до 2,0 В",
        "energy": "9,36 Вт·ч",
        "pulse": "до 250 мА",
        "continuous": "50 мА",
        "dimensions": "диаметр не более 14,62 мм; высота не более 50,28 мм",
        "weight": "типично 17 г",
    },
    "LS17330": {
        "source_url": "https://saft4u.saft.com/en/download_file/da7e4f7d-920b-46c7-bce2-5febf9abe7d1/English",
        "size": "2/3 A",
        "capacity": "2,1 А·ч при 3 мА, +20 °C, до 2,0 В",
        "energy": "7,56 Вт·ч",
        "pulse": "до 120 мА",
        "continuous": "25 мА",
        "dimensions": "диаметр не более 16,5 мм; высота не более 33,4 мм",
        "weight": "типично 14,4 г",
    },
    "LS17500": {
        "source_url": "https://saft4u.saft.com/fr/download_file/6fbdd60f-bba6-4f67-81a0-85ce1b412664/English",
        "size": "A",
        "capacity": "3,6 А·ч при 3 мА, +20 °C, до 2,0 В",
        "energy": "12,96 Вт·ч",
        "pulse": "до 250 мА",
        "continuous": "100 мА",
        "dimensions": "диаметр не более 17,16 мм; высота не более 50,77 мм",
        "weight": "типично 22 г",
    },
    "LS26500": {
        "source_url": "https://saft4u.saft.com/en/download_file/e9a98622-3564-4570-bca2-d6ce1504589a/English",
        "size": "C",
        "capacity": "7,7 А·ч при 4 мА, +20 °C, до 2,0 В",
        "energy": "27,72 Вт·ч",
        "pulse": "до 300 мА",
        "continuous": "150 мА",
        "dimensions": "диаметр не более 26,0 мм; высота зависит от исполнения и требует сверки",
        "weight": "типично 48 г",
    },
    "LS33600": {
        "source_url": "https://saft4u.saft.com/en/download_file/5241def1-8668-4a68-9d2e-820bd3c68589/English",
        "size": "D",
        "capacity": "17 А·ч при 5 мА, +20 °C, до 2,0 В",
        "energy": "61,2 Вт·ч",
        "pulse": "до 400 мА",
        "continuous": "250 мА",
        "dimensions": "диаметр не более 33,3 мм; высота не более 61,5 мм",
        "weight": "типично 90 г",
    },
    "LSH14": {
        "source_url": "https://saft4u.saft.com/fr/download_file/e45bd03f-3674-4eeb-bd5d-431d53253df1/English",
        "size": "C",
        "capacity": "5,8 А·ч при 15 мА, +20 °C, до 2,0 В",
        "energy": "20,88 Вт·ч",
        "pulse": "до 2,0 А",
        "continuous": "1,3 А",
        "dimensions": "диаметр не более 26,0 мм; высота не более 50,4 мм",
        "weight": "типично 51 г",
    },
    "LSH20": {
        "source_url": "https://saft4u.saft.com/en/download_file/8bdd6f76-c9c5-422e-95bd-a18e0a12d80f/English",
        "size": "D",
        "capacity": "13 А·ч при 14 мА, +20 °C, до 2,0 В",
        "energy": "47 Вт·ч",
        "pulse": "до 4 А",
        "continuous": "1,8 А",
        "dimensions": "диаметр не более 33,4 мм; высота не более 61,31 мм",
        "weight": "типично 100 г",
    },
}


def model_core(name: str) -> str | None:
    compact = re.sub(r"\s+", "", name.upper())
    if "2LS17500" in compact or "СБОРКА" in compact:
        return None
    for model in ("LSH20", "LSH14", "LS33600", "LS26500", "LS17500", "LS17330", "LS14500", "LS14250"):
        if model in compact:
            if model == "LS26500" and "LS26500PLUS" in compact:
                return None
            if model == "LSH20" and ("LSH20HTS" in compact or "LSH20-150" in compact):
                return None
            return model
    return None


def product_row(source: dict[str, str], model: str) -> dict[str, object]:
    facts = SERIES[model]
    return {
        "external_id": source["product_external_id"],
        "manufacturer": "Saft",
        "identity_scope": "model_core",
        "model_core": model,
        "display_name": source["name"].strip(),
        "technology": "Первичный литий-тионилхлоридный элемент (Li-SOCl₂)",
        "source_url": facts["source_url"],
        "source_kind": f"Official Saft {model} model-core datasheet",
        "checked_at": "2026-07-27",
        "technical_attributes": {
            "Химическая система": "Li-SOCl₂, первичный элемент, перезарядка не допускается",
            "Конструкция": "Бобинная" if not model.startswith("LSH") else "Спиральная, высокой мощности",
            "Типоразмер одного элемента": facts["size"],
            "Номинальное напряжение одного элемента": "3,6 В",
            "Напряжение холостого хода при +20 °C": "3,67 В",
            "Типичная ёмкость одного элемента": facts["capacity"],
            "Номинальная энергия одного элемента": facts["energy"],
            "Импульсный ток": facts["pulse"],
            "Максимальный продолжительный ток": facts["continuous"],
            "Рабочая температура": "от −60 до +85 °C",
            "Габариты одного элемента": facts["dimensions"],
            "Масса одного элемента": facts["weight"],
            "Ограничение источника": "Клеммы, провода, разъём, комплектность и схема сборки требуют отдельного подтверждения для этой позиции",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("queue", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expected", type=int, default=50)
    args = parser.parse_args()

    with args.queue.open("r", encoding="utf-8-sig", newline="") as handle:
        queue = list(csv.DictReader(handle))

    products: list[dict[str, object]] = []
    skipped: list[dict[str, str]] = []
    for row in queue:
        if "SAFT" not in row["name"].upper():
            continue
        model = model_core(row["name"])
        if model is None:
            skipped.append({"external_id": row["product_external_id"], "name": row["name"]})
            continue
        if row["category_external_id"] != "seo:primary-cells":
            raise RuntimeError(f"SAFT row escaped primary-cells: {row['product_external_id']}")
        products.append(product_row(row, model))

    ids = [row["external_id"] for row in products]
    if len(ids) != len(set(ids)):
        raise RuntimeError("Generated manifest contains duplicate external IDs")
    if len(products) != args.expected:
        raise RuntimeError(f"Expected {args.expected} safe rows, got {len(products)}; skipped={skipped}")

    payload = {
        "schema_version": 1,
        "purpose": "Official SAFT model-core facts. Exact connector, terminal, bundle, assembly topology and country facts are explicitly excluded.",
        "locale": "ru-BY",
        "products": products,
        "blocked_rows": skipped,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"products": len(products), "blocked": len(skipped)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
