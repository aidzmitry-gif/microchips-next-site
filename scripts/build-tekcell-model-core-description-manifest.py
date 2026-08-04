#!/usr/bin/env python3
"""Build a bounded TEKCELL/Vitzrocell model-core description manifest.

Only exact bare-cell model tokens are resolved.  TC/AX, terminal layouts,
lead/connector codes and pack-like suffixes are retained as unverified signals;
they are never converted into technical facts for the concrete sellable item.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Iterable


CHECKED_AT = "2026-07-28"
PRIMARY_CELL_CATEGORY = "seo:primary-cells"
CHEMISTRY_SOURCE_URL = (
    "https://www.vitzrocell.com/catalog/"
    "%EA%B3%A0%EC%98%A8%EC%A0%84%EC%A7%80%20%EC%B9%B4%ED%83%88%EB%A1%9C%EA%B7%B8.pdf"
)

ALLOWED_ATTRIBUTE_KEYS = {
    "Химическая система",
    "Конструкция одного элемента",
    "Номинальное напряжение одного элемента",
    "Номинальная ёмкость одного элемента",
    "Условия измерения ёмкости",
    "Максимальный рекомендуемый продолжительный ток одного элемента",
    "Максимальный импульсный ток одного элемента",
    "Рабочая температура",
    "Масса одного элемента",
    "Саморазряд",
    "Ограничение источника",
}

MODELS: dict[str, dict[str, str]] = {
    "SB-AA02": {
        "source_url": "https://www.vitzrocell.com/en/sub/sub02_01.php?cat_no=&idx=11&mode=view&offset=0",
        "capacity": "1,2 А·ч",
        "capacity_test": "при токе 1 мА, 20 °C и конечном напряжении 2,0 В",
        "continuous": "20 мА",
        "pulse": "50 мА",
        "weight": "9 г",
    },
    "SB-AA11": {
        "source_url": "https://www.vitzrocell.com/en/sub/sub02_01.php?cat_no=&idx=9&mode=view&offset=0",
        "capacity": "2,5 А·ч",
        "capacity_test": "при токе 2 мА, 20 °C и конечном напряжении 2,0 В",
        "continuous": "60 мА",
        "pulse": "100 мА",
        "weight": "16 г",
    },
    "SB-A01": {
        "source_url": "https://www.vitzrocell.com/en/sub/sub02_01.php?cat_no=&idx=8&mode=view&offset=",
        "capacity": "3,6 А·ч",
        "capacity_test": "при токе 3 мА, 20 °C и конечном напряжении 2,0 В",
        "continuous": "70 мА",
        "pulse": "160 мА",
        "weight": "24 г",
    },
    "SB-C02": {
        "source_url": "https://www.vitzrocell.com/sub/sub02_01.php?cat_no=10&idx=7&mode=view&offset=",
        "capacity": "8,5 А·ч",
        "capacity_test": "при токе 4 мА, 20 °C и конечном напряжении 2,0 В",
        "continuous": "80 мА",
        "pulse": "180 мА",
        "weight": "51 г",
    },
    "SB-D02": {
        "source_url": "https://www.vitzrocell.com/en/sub/sub02_01.php?cat_no=&idx=6&mode=view&offset=0",
        "capacity": "19 А·ч",
        "capacity_test": "при токе 6 мА, 20 °C и конечном напряжении 2,0 В",
        "continuous": "100 мА",
        "pulse": "250 мА",
        "weight": "100 г",
    },
}

MODEL_PATTERNS = {
    model: re.compile(
        rf"(?<![A-Z0-9]){re.escape(model).replace(r'\-', r'[\s-]+')}(?![A-Z0-9])",
        re.IGNORECASE,
    )
    for model in MODELS
}

SIGNAL_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("TC", re.compile(r"(?<![A-Z0-9])TC(?![A-Z0-9])", re.I)),
    ("AX", re.compile(r"(?<![A-Z0-9])AX(?![A-Z0-9])", re.I)),
    ("2PF", re.compile(r"(?<![A-Z0-9])2\s*PF(?![A-Z0-9])", re.I)),
    ("3PF", re.compile(r"(?<![A-Z0-9])3\s*PF(?![A-Z0-9])", re.I)),
    ("4PF", re.compile(r"(?<![A-Z0-9])4\s*PF(?![A-Z0-9])", re.I)),
    ("2P", re.compile(r"(?<![A-Z0-9])2P(?![A-Z0-9F])", re.I)),
    ("3P", re.compile(r"(?<![A-Z0-9])3P(?![A-Z0-9F])", re.I)),
    ("1S", re.compile(r"(?<![A-Z0-9])1S(?![A-Z0-9])", re.I)),
    ("CNR", re.compile(r"(?<![A-Z0-9])CNR(?![A-Z0-9])", re.I)),
    ("JST", re.compile(r"(?<![A-Z0-9])JST(?![A-Z0-9])", re.I)),
    ("PHR-2", re.compile(r"(?<![A-Z0-9])PHR-?2(?![A-Z0-9])", re.I)),
    ("MU-2F", re.compile(r"(?<![A-Z0-9])MU-?2F(?![A-Z0-9])", re.I)),
    ("EHR-2", re.compile(r"(?<![A-Z0-9])EHR-?2(?![A-Z0-9])", re.I)),
    ("BSL-2", re.compile(r"(?<![A-Z0-9])BSL-?2(?![A-Z0-9])", re.I)),
    ("BR-AGCF2W", re.compile(r"(?<![A-Z0-9])BR-?AGCF2W(?![A-Z0-9])", re.I)),
    ("connector", re.compile(r"(?:коннектор|разъ[её]м)", re.I)),
    ("leads", re.compile(r"(?:вывод|провод)", re.I)),
)


def model_core(name: str) -> str | None:
    matches = [model for model, pattern in MODEL_PATTERNS.items() if pattern.search(name)]
    return matches[0] if len(matches) == 1 else None


def execution_signals(name: str) -> list[str]:
    return [label for label, pattern in SIGNAL_PATTERNS if pattern.search(name)]


def blocked_reason(name: str) -> str:
    upper = name.upper()
    if re.search(r"(?<![A-Z0-9])SB[\s-]+CO2(?![A-Z0-9])", upper):
        return "ambiguous_CO2_cannot_be_silently_normalized_to_SB-C02"
    if re.search(r"(?<![A-Z0-9])SB[\s-]+AA(?![A-Z0-9])", upper):
        return "ambiguous_SB-AA_without_02_or_11"
    if re.search(r"(?<![A-Z0-9])CR[\s-]*\d", upper):
        return "CR_family_outside_this_source_bounded_wave"
    if re.search(r"(?<![A-Z0-9])SW[\s-]+D03(?![A-Z0-9])", upper):
        return "SW-D03_is_not_an_SB_model_core"
    return "no_exact_supported_model_core"


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
        "Химическая система": "Первичный литий-тионилхлоридный элемент (Li-SOCl₂); перезарядка не допускается",
        "Конструкция одного элемента": "Бобинная",
        "Номинальное напряжение одного элемента": "3,6 В",
        "Номинальная ёмкость одного элемента": facts["capacity"],
        "Условия измерения ёмкости": facts["capacity_test"],
        "Максимальный рекомендуемый продолжительный ток одного элемента": facts["continuous"],
        "Максимальный импульсный ток одного элемента": facts["pulse"],
        "Рабочая температура": "от −55 до +85 °C",
        "Масса одного элемента": facts["weight"],
        "Саморазряд": "менее 1 % в год при хранении при 20 °C",
        "Ограничение источника": (
            "Характеристики относятся только к базовой ячейке указанной модели. "
            "TC/AX, 2P/3P/2PF/3PF/4PF, CNR, разъём, выводы, провода, их длина, "
            "полярность и схема сборки требуют отдельного подтверждения конкретного исполнения."
        ),
    }
    validate_attributes(attributes)
    return {
        "external_id": source["product_external_id"],
        "manufacturer": "TEKCELL / Vitzrocell",
        "identity_scope": "model_core",
        "model_core": model,
        "display_name": source["name"].strip(),
        "technology": "Первичный литий-тионилхлоридный элемент (Li-SOCl₂)",
        "source_url": facts["source_url"],
        "supporting_source_urls": [CHEMISTRY_SOURCE_URL],
        "source_kind": f"Official Vitzrocell {model} model-core product page",
        "checked_at": CHECKED_AT,
        "unverified_execution_signals": execution_signals(source["name"]),
        "technical_attributes": attributes,
    }


def serialize_payload(payload: dict[str, object]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def write_payload(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(serialize_payload(payload))


def build_payload(queue: Iterable[dict[str, str]], expected: int) -> dict[str, object]:
    products: list[dict[str, object]] = []
    blocked: list[dict[str, object]] = []

    for row in queue:
        name = row.get("name", "")
        if "TEKCELL" not in name.upper():
            continue
        external_id = row.get("product_external_id", "").strip()
        if not external_id:
            raise RuntimeError("TEKCELL queue row has no product_external_id")
        if row.get("category_external_id") != PRIMARY_CELL_CATEGORY:
            raise RuntimeError(f"TEKCELL row escaped primary-cells: {external_id}")

        model = model_core(name)
        if model is None:
            blocked.append(
                {
                    "external_id": external_id,
                    "name": name,
                    "reason": blocked_reason(name),
                    "unverified_execution_signals": execution_signals(name),
                }
            )
            continue
        products.append(product_row(row, model))

    ids = [str(row["external_id"]) for row in products]
    if len(ids) != len(set(ids)):
        raise RuntimeError("Generated manifest contains duplicate external IDs")
    if len(products) != expected:
        raise RuntimeError(
            f"Expected {expected} safe TEKCELL rows, got {len(products)}; blocked={blocked}"
        )

    return {
        "schema_version": 1,
        "purpose": (
            "Official Vitzrocell model-core facts for exact TEKCELL SB cells. "
            "All execution, connector, lead and pack facts are explicitly excluded."
        ),
        "locale": "ru-BY",
        "products": products,
        "blocked_rows": blocked,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("queue", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expected", type=int, default=20)
    args = parser.parse_args()

    with args.queue.open("r", encoding="utf-8-sig", newline="") as handle:
        queue = list(csv.DictReader(handle))

    payload = build_payload(queue, args.expected)
    write_payload(args.output, payload)
    print(json.dumps({"products": len(payload["products"]), "blocked": len(payload["blocked_rows"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
