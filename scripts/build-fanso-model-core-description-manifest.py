#!/usr/bin/env python3
"""Build a bounded FANSO model-core description manifest.

The official FANSO pages used here describe the bare cell model. They do not
prove a local connector, terminal, lead, pack topology or country of origin.
Generated rows therefore carry ``identity_scope=model_core`` and intentionally
omit those assembly-specific facts.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Iterable


CHECKED_AT = "2026-07-27"
PRIMARY_CELL_CATEGORY = "seo:primary-cells"
ALLOWED_ATTRIBUTE_KEYS = {
    "Химическая система",
    "Конструкция одного элемента",
    "Номинальное напряжение одного элемента",
    "Конечное напряжение разряда",
    "Номинальная ёмкость одного элемента",
    "Максимальный продолжительный ток одного элемента",
    "Рабочая температура",
    "Габариты одного элемента",
    "Масса одного элемента",
    "Саморазряд",
    "Условия хранения",
    "Ограничение источника",
}


MODELS: dict[str, dict[str, str]] = {
    "ER14250H": {
        "source_url": "https://www.fansobattery.com/?list_43%2F507.html=",
        "construction": "Бобинная",
        "capacity": "1200 мА·ч при токе 1,0 мА и конечном напряжении 2,0 В",
        "continuous": "15 мА",
        "temperature": "от −55 до +85 °C",
        "dimensions": "диаметр не более 14,5 мм; высота не более 25,4 мм",
        "weight": "10 г",
        "self_discharge": "не более 1 % при 25 °C",
    },
    "ER14335H": {
        "source_url": "https://www.fansobattery.com/?list_43%2F508.html=",
        "construction": "Бобинная",
        "capacity": "1650 мА·ч при токе 1,0 мА и конечном напряжении 2,0 В",
        "continuous": "35 мА",
        "temperature": "от −55 до +85 °C",
        "dimensions": "диаметр не более 14,5 мм; высота не более 33,5 мм",
        "weight": "13 г",
        "self_discharge": "не более 1 % при 25 °C",
    },
    "ER14505H": {
        "source_url": "https://www.fansobattery.com/?list_43%2F506.html=",
        "construction": "Бобинная",
        "capacity": "2600 мА·ч при токе 1,0 мА и конечном напряжении 2,0 В",
        "continuous": "60 мА",
        "temperature": "от −55 до +85 °C",
        "dimensions": "диаметр не более 14,5 мм; высота не более 50,5 мм",
        "weight": "19 г",
        "self_discharge": "не более 1 % при 25 °C",
    },
    "ER17505H": {
        "source_url": "https://www.fansobattery.com/?list_43%2F505.html=",
        "construction": "Бобинная",
        "capacity": "3600 мА·ч при токе 3,0 мА и конечном напряжении 2,0 В",
        "continuous": "70 мА",
        "temperature": "от −55 до +85 °C",
        "dimensions": "диаметр не более 17,5 мм; высота не более 51,0 мм",
        "weight": "26 г",
        "self_discharge": "не более 1 % при 25 °C",
    },
    "ER18505H": {
        "source_url": "https://www.fansobattery.com/?list_43%2F504.html=",
        "construction": "Бобинная",
        "capacity": "4000 мА·ч при токе 3,0 мА и конечном напряжении 2,0 В",
        "continuous": "70 мА",
        "temperature": "от −55 до +85 °C",
        "dimensions": "диаметр не более 18,7 мм; высота не более 50,5 мм",
        "weight": "28 г",
        "self_discharge": "не более 1 % при 25 °C",
    },
    "ER26500H": {
        "source_url": "https://www.fansobattery.com/?list_43%2F503.html=",
        "construction": "Бобинная",
        "capacity": "8500 мА·ч при токе 2,0 мА и конечном напряжении 2,0 В",
        "continuous": "100 мА",
        "temperature": "от −55 до +85 °C",
        "dimensions": "диаметр не более 26,2 мм; высота не более 50,0 мм",
        "weight": "около 52 г",
        "self_discharge": "не более 1 % при 25 °C",
    },
    "ER34615H": {
        "source_url": "https://www.fansobattery.com/?list_43%2F502.html=",
        "construction": "Бобинная",
        "capacity": "19000 мА·ч при токе 2,0 мА и конечном напряжении 2,0 В",
        "continuous": "100 мА",
        "temperature": "от −55 до +85 °C",
        "dimensions": "диаметр не более 33,1 мм; высота не более 61,5 мм",
        "weight": "около 88 г",
        "self_discharge": "не более 1 % при 25 °C",
    },
    "ER18505M": {
        "source_url": "https://www.fansobattery.com/?list_44%2F511.html=",
        "construction": "Спиральная",
        "capacity": "3500 мА·ч при токе 5,0 мА и конечном напряжении 2,0 В",
        "continuous": "800 мА",
        "temperature": "от −55 до +80 °C",
        "dimensions": "диаметр не более 18,5 мм; высота не более 50,5 мм",
        "weight": "30 г",
        "self_discharge": "не более 2 % при 25 °C",
    },
    "ER26500M": {
        "source_url": "https://www.fansobattery.com/?list_44%2F510.html=",
        "construction": "Спиральная",
        "capacity": "6000 мА·ч при токе 10 мА и конечном напряжении 2,0 В",
        "continuous": "1000 мА",
        "temperature": "от −55 до +80 °C",
        "dimensions": "диаметр не более 26,2 мм; высота не более 50,0 мм",
        "weight": "57 г",
        "self_discharge": "не более 2 % при 25 °C",
    },
    "ER34615M": {
        "source_url": "https://www.fansobattery.com/?list_44%2F509.html=",
        "construction": "Спиральная",
        "capacity": "13000 мА·ч при токе 15 мА и конечном напряжении 2,0 В",
        "continuous": "1800 мА",
        "temperature": "от −55 до +80 °C",
        "dimensions": "диаметр не более 34,2 мм; высота не более 61,5 мм",
        "weight": "109 г",
        "self_discharge": "не более 2 % при 25 °C",
    },
}


MODEL_PATTERNS = {
    model: re.compile(rf"(?<![A-Z0-9]){re.escape(model)}(?![A-Z0-9])", re.IGNORECASE)
    for model in MODELS
}
ASSEMBLY_PATTERN = re.compile(
    r"(?:\b(?:PACK|BATTERY\s*PACK|СБОРКА|КОМПЛЕКТ)\b|\d+\s*[xх*]\s*ER\d)",
    re.IGNORECASE,
)


def model_core(name: str) -> str | None:
    """Return only an exact H/M model token for a single-cell row."""

    if ASSEMBLY_PATTERN.search(name):
        return None
    matches = [model for model, pattern in MODEL_PATTERNS.items() if pattern.search(name)]
    return matches[0] if len(matches) == 1 else None


def validate_attributes(attributes: dict[str, str]) -> None:
    actual = set(attributes)
    if actual != ALLOWED_ATTRIBUTE_KEYS:
        raise RuntimeError(
            "Model-core attribute whitelist mismatch: "
            f"missing={sorted(ALLOWED_ATTRIBUTE_KEYS - actual)}, "
            f"unexpected={sorted(actual - ALLOWED_ATTRIBUTE_KEYS)}"
        )


def product_row(source: dict[str, str], model: str) -> dict[str, object]:
    facts = MODELS[model]
    attributes = {
        "Химическая система": "Li-SOCl₂, первичный элемент, перезарядка не допускается",
        "Конструкция одного элемента": facts["construction"],
        "Номинальное напряжение одного элемента": "3,6 В",
        "Конечное напряжение разряда": "2,0 В",
        "Номинальная ёмкость одного элемента": facts["capacity"],
        "Максимальный продолжительный ток одного элемента": facts["continuous"],
        "Рабочая температура": facts["temperature"],
        "Габариты одного элемента": facts["dimensions"],
        "Масса одного элемента": facts["weight"],
        "Саморазряд": facts["self_discharge"],
        "Условия хранения": "чистое, сухое и проветриваемое место; предпочтительно ниже +20 °C, не выше +30 °C",
        "Ограничение источника": (
            "Разъём, клеммы, выводы, длина проводов, схема сборки, совместимость и страна "
            "происхождения требуют отдельного подтверждения для конкретной позиции"
        ),
    }
    validate_attributes(attributes)
    return {
        "external_id": source["product_external_id"],
        "manufacturer": "FANSO",
        "identity_scope": "model_core",
        "model_core": model,
        "display_name": source["name"].strip(),
        "technology": "Первичный литий-тионилхлоридный элемент (Li-SOCl₂)",
        "source_url": facts["source_url"],
        "source_kind": f"Official FANSO {model} model-core product page",
        "checked_at": CHECKED_AT,
        "technical_attributes": attributes,
    }


def serialize_payload(payload: dict[str, object]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def write_payload(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(serialize_payload(payload))


def build_payload(queue: Iterable[dict[str, str]], expected: int) -> dict[str, object]:
    products: list[dict[str, object]] = []
    blocked: list[dict[str, str]] = []

    for row in queue:
        name = row.get("name", "")
        if "FANSO" not in name.upper():
            continue
        external_id = row.get("product_external_id", "").strip()
        if not external_id:
            raise RuntimeError("FANSO queue row has no product_external_id")
        if row.get("category_external_id") != PRIMARY_CELL_CATEGORY:
            raise RuntimeError(f"FANSO row escaped primary-cells: {external_id}")

        model = model_core(name)
        if model is None:
            blocked.append({"external_id": external_id, "name": name})
            continue
        products.append(product_row(row, model))

    ids = [str(row["external_id"]) for row in products]
    if len(ids) != len(set(ids)):
        raise RuntimeError("Generated manifest contains duplicate external IDs")
    if len(products) != expected:
        raise RuntimeError(
            f"Expected {expected} safe FANSO rows, got {len(products)}; blocked={blocked}"
        )

    return {
        "schema_version": 1,
        "purpose": (
            "Official FANSO model-core facts. Connector, terminal, leads, pack topology, "
            "compatible equipment and country facts are explicitly excluded."
        ),
        "locale": "ru-BY",
        "products": products,
        "blocked_rows": blocked,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("queue", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expected", type=int, default=27)
    args = parser.parse_args()

    with args.queue.open("r", encoding="utf-8-sig", newline="") as handle:
        queue = list(csv.DictReader(handle))

    payload = build_payload(queue, args.expected)
    write_payload(args.output, payload)
    print(
        json.dumps(
            {
                "products": len(payload["products"]),
                "blocked": len(payload["blocked_rows"]),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
