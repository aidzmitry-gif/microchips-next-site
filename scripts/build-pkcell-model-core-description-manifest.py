#!/usr/bin/env python3
"""Build a bounded PKCELL model-core description manifest.

The current RB enrichment queue contains PKCELL Ni-MH AA/AAA rows, including
electrical packs and retail packs.  Only the generic single-cell AAA Ni-MH
core is source-safe in this wave.  The AA rows claim 2800 mAh while PKCELL's
official AA product page currently specifies 350-2700 mAh, so they are blocked.

ER/CR identities are parsed separately and H/M suffixes are preserved, but no
such row exists in the current queue and this generator never guesses one from
another family.
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
AAA_SOURCE_URL = "https://www.pkcell.com/product/aaa-ni-mh-battery/"
AA_SOURCE_URL = "https://www.pkcell.com/product/aa-ni-mh-battery/"

ALLOWED_ATTRIBUTE_KEYS = {
    "Химическая система",
    "Типоразмер одного элемента",
    "Номинальное напряжение одного элемента",
    "Диапазон ёмкости на официальной странице",
    "Температура заряда",
    "Температура разряда",
    "Ограничение источника",
}

AAA_PATTERN = re.compile(r"(?<![A-Z0-9])(?:AAA(?:/R0?3)?|R0?3)(?![A-Z0-9])", re.I)
AA_PATTERN = re.compile(r"(?<![A-Z0-9])(?:AA(?:/R0?6)?|R0?6)(?![A-Z0-9])", re.I)
NIMH_PATTERN = re.compile(r"(?<![A-Z])NI[\s-]*MH(?![A-Z])", re.I)
BRAND_PATTERN = re.compile(r"PKCELL", re.I)
CAPACITY_2800_PATTERN = re.compile(r"(?<!\d)2800\s*MAH(?![A-Z0-9])", re.I)

PRIMARY_LITHIUM_PATTERN = re.compile(
    r"(?<![A-Z0-9])(?P<family>ER|CR)[\s-]*(?P<size>\d{4,5})\s*(?P<suffix>[HM]?)(?![A-Z0-9])",
    re.I,
)


def primary_lithium_token(name: str) -> str | None:
    """Return an exact ER/CR token without collapsing ER/CR or H/M."""

    matches = list(PRIMARY_LITHIUM_PATTERN.finditer(name))
    if len(matches) != 1:
        return None
    match = matches[0]
    return f"{match.group('family').upper()}{match.group('size')}{match.group('suffix').upper()}"


def model_core(name: str) -> str | None:
    if not BRAND_PATTERN.search(name) or not NIMH_PATTERN.search(name):
        return None
    if AAA_PATTERN.search(name):
        return "R03"
    if AA_PATTERN.search(name):
        return "R06"
    return None


def identity_evidence(name: str, expected_model_core: str) -> dict[str, str]:
    """Require all three source-name signals before emitting model-core facts."""

    actual_core = model_core(name)
    if actual_core != expected_model_core:
        raise RuntimeError(
            f"PKCELL identity guard expected {expected_model_core}, got {actual_core!r}"
        )
    if not BRAND_PATTERN.search(name):
        raise RuntimeError("PKCELL identity guard requires the PKCELL brand token")
    if not NIMH_PATTERN.search(name):
        raise RuntimeError("PKCELL identity guard requires Ni-MH evidence")
    return {
        "model_core_token": expected_model_core,
        "required_brand_token": "PKCELL",
        "required_chemistry_token": "Ni-MH",
    }


def execution_signals(name: str) -> list[str]:
    signals: list[str] = []

    pack_patterns = (
        re.compile(r"(?<!\d)(\d+)\s*[*XХ×]?\s*NI[\s-]*MH\s+PKCELL", re.I),
        re.compile(r"NI[\s-]*MH\s+(\d+)\s*[*XХ×]?\s*PKCELL", re.I),
    )
    for pattern in pack_patterns:
        match = pattern.search(name)
        if match:
            signals.append(f"electrical_pack:{int(match.group(1))}_cells")
            break

    retail_match = re.search(
        r"(?:\(\s*[ПP]\s*(\d+)\s*\)|\bBL\.?\s*(\d+)\b|\(\s*(\d+)\s*BL\s*\))",
        name,
        re.I,
    )
    if retail_match:
        count = next(value for value in retail_match.groups() if value)
        signals.append(f"retail_pack:{int(count)}_pieces")

    if re.search(r"(?<![A-Z0-9])RTU(?![A-Z0-9])", name, re.I):
        signals.append("RTU")
    if re.search(r"(?:коннектор|разъ[её]м)", name, re.I):
        signals.append("connector")
    if re.search(r"(?:вывод|провод)", name, re.I):
        signals.append("leads")
    return signals


def blocked_reason(name: str) -> str:
    token = primary_lithium_token(name)
    if token:
        return f"exact_primary_lithium_model_{token}_outside_current_NiMH_wave"
    core = model_core(name)
    if core == "R06" and CAPACITY_2800_PATTERN.search(name):
        return "official_AA_page_caps_range_at_2700mAh_but_queue_claims_2800mAh"
    if core == "R06":
        return "AA_model_core_not_source_safe_in_this_bounded_wave"
    return "no_exact_supported_model_core"


def validate_attributes(attributes: dict[str, str]) -> None:
    actual = set(attributes)
    if actual != ALLOWED_ATTRIBUTE_KEYS:
        raise RuntimeError(
            "Model-core attribute whitelist mismatch: "
            f"missing={sorted(ALLOWED_ATTRIBUTE_KEYS - actual)}, "
            f"unexpected={sorted(actual - ALLOWED_ATTRIBUTE_KEYS)}"
        )


def product_row(source: dict[str, str]) -> dict[str, object]:
    evidence = identity_evidence(source["name"], "R03")
    attributes = {
        "Химическая система": "Никель-металлогидридный аккумулятор (Ni-MH)",
        "Типоразмер одного элемента": "AAA / R03",
        "Номинальное напряжение одного элемента": "1,2 В",
        "Диапазон ёмкости на официальной странице": "80–1100 мА·ч",
        "Температура заряда": "от 0 до +45 °C",
        "Температура разряда": "от −20 до +55 °C",
        "Ограничение источника": (
            "Официальная страница подтверждает семейство AAA Ni-MH, а не конкретное "
            "исполнение 1000 мА·ч. Число элементов, напряжение сборки, RTU, розничная "
            "упаковка, выводы, провода и разъёмы требуют отдельного подтверждения."
        ),
    }
    validate_attributes(attributes)
    return {
        "external_id": source["product_external_id"],
        "manufacturer": "PKCELL",
        "identity_scope": "model_core",
        "model_core": "R03",
        "identity_evidence": evidence,
        "display_name": source["name"].strip(),
        "technology": "Никель-металлогидридный аккумулятор (Ni-MH)",
        "source_url": AAA_SOURCE_URL,
        "source_kind": "Official PKCELL AAA Ni-MH model-core product page",
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
        if "PKCELL" not in name.upper():
            continue
        external_id = row.get("product_external_id", "").strip()
        if not external_id:
            raise RuntimeError("PKCELL queue row has no product_external_id")
        if row.get("category_external_id") != PRIMARY_CELL_CATEGORY:
            raise RuntimeError(f"PKCELL row escaped primary-cells: {external_id}")

        core = model_core(name)
        if core == "R03":
            products.append(product_row(row))
            continue
        blocked.append(
            {
                "external_id": external_id,
                "name": name,
                "parsed_model_core": core,
                "primary_lithium_token": primary_lithium_token(name),
                "reason": blocked_reason(name),
                "unverified_execution_signals": execution_signals(name),
            }
        )

    ids = [str(row["external_id"]) for row in products]
    if len(ids) != len(set(ids)):
        raise RuntimeError("Generated manifest contains duplicate external IDs")
    if len(products) != expected:
        raise RuntimeError(
            f"Expected {expected} safe PKCELL rows, got {len(products)}; blocked={blocked}"
        )

    return {
        "schema_version": 1,
        "purpose": (
            "Official PKCELL model-core facts for source-safe current RB queue rows. "
            "Exact capacity, RTU, pack, retail package, terminal and connector facts are excluded."
        ),
        "locale": "ru-BY",
        "products": products,
        "blocked_rows": blocked,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("queue", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expected", type=int, default=4)
    args = parser.parse_args()

    with args.queue.open("r", encoding="utf-8-sig", newline="") as handle:
        queue = list(csv.DictReader(handle))

    payload = build_payload(queue, args.expected)
    write_payload(args.output, payload)
    print(json.dumps({"products": len(payload["products"]), "blocked": len(payload["blocked_rows"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
