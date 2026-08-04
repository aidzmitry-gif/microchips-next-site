#!/usr/bin/env python3
"""Build Wave239 exact FIAMM source-backed description artifacts offline."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from decimal import Decimal
from pathlib import Path

import pdfplumber


ROOT = Path(__file__).resolve().parents[1]
IDENTITY_PATH = ROOT / "docs/imports/rb-verified-oem-identities-wave237-fiamm-2026-07-29.json"
QUEUE_PATH = ROOT / "docs/audits/generated/rb-enrichment-queue-wave238.csv"
SOURCE_DIR = ROOT / "docs/audits/sources/wave237-fiamm-primary"
MANIFEST_PATH = ROOT / "docs/imports/rb-source-backed-descriptions-wave239-fiamm-2026-07-29.json"
LEDGER_PATH = ROOT / "docs/audits/generated/rb-wave239-fiamm-exact-description-ledger.json"
SUMMARY_PATH = ROOT / "docs/audits/generated/rb-wave239-fiamm-exact-description-summary.json"

CHECKED_AT = "2026-07-29"
PUBLISHER = "FIAMM Energy Technology S.p.A."

INPUT_PINS = {
    "identity_manifest": "85faeabdb97e269018907dacb1f9e4798dca990ad58c925f092ad2577af00ee3",
    "queue": "297533e25b9422969b51b2a819aac04ba65afb56ed67d8aee0364760cf5fb59b",
}

PDFS = {
    "FG": {
        "filename": "fiamm-fg-manufacturer-brochure.pdf",
        "sha256": "f3de28bc8469263f2c1a472ab1fae7a79a92f554acf774ea7d1c4007e8a603ca",
        "url": "https://www.fiamm.ru/upload/uf/37f/d3hnm0fdfsq00v8hlvz1hsi1lunuhd45.pdf",
    },
    "FGH": {
        "filename": "fiamm-fgh-manufacturer-brochure.pdf",
        "sha256": "e87abb9411441472119b5d8df8076f2ecccdcfdcf29eea8e5fb883cb7aeaa980",
        "url": "https://www.fiamm.ru/upload/uf/0a7/zbf2yf39iceptbd77lbmu8btak6oaxhq.pdf",
    },
    "FGL": {
        "filename": "fiamm-fgl-manufacturer-brochure.pdf",
        "sha256": "28312f35aa1b8be0bc1046b76dfa4db2936f2082eed76453e0e2e00c0ed51c45",
        "url": "https://www.fiamm.ru/upload/uf/754/4okq6sd39k1z6j1rutvma6ckvp07xlt8.pdf",
    },
    "FLB": {
        "filename": "fiamm-flb-manufacturer-brochure.pdf",
        "sha256": "f136865bd8ee3d2dd0baea5b77f1363ed5eb9155fa5a7194c5f90d22ef2e8259",
        "url": "https://www.fiamm.ru/upload/uf/23a/nqca7ygtoejpde7fjhzxq6jfwwwqzm3o.pdf",
    },
    "SLA": {
        "filename": "fiamm-sla-manufacturer-brochure.pdf",
        "sha256": "2ce0c15ad9b3334dad54880b14bd74a2e9730063acf5f75602d980d779057f2e",
        "url": "https://www.fiamm.ru/upload/uf/e1b/g37frazu0hbhurid4a4z4qzq9im2qpdv.pdf",
    },
}

FROZEN = (
    ("bitrix:858", "2SLA800"),
    ("bitrix:1427", "12FLB400 P"),
    ("bitrix:1444", "12FLB450 P"),
    ("bitrix:1462", "12FGL80"),
    ("bitrix:1483", "12FGH50"),
    ("bitrix:1484", "12FGHL48"),
    ("bitrix:1495", "12FGL120"),
    ("bitrix:1509", "12FLB540 P"),
    ("bitrix:1510", "12FGL150"),
    ("bitrix:1524", "12FGL70"),
    ("bitrix:1541", "12FGH65"),
    ("bitrix:1690", "2SLA1000"),
    ("bitrix:1704", "2SLA1500"),
    ("bitrix:1715", "2SLA2000"),
    ("bitrix:2917", "12FLB100 P"),
    ("bitrix:2930", "12FGL27"),
    ("bitrix:3010", "FG10451"),
    ("bitrix:3032", "12FLB150 P"),
    ("bitrix:3065", "12FGHL22"),
    ("bitrix:3079", "12SLA50L"),
    ("bitrix:3094", "12FLB200 P"),
    ("bitrix:3119", "12FGL33"),
    ("bitrix:3178", "12FGHL28"),
    ("bitrix:3199", "12FGL70/L"),
    ("bitrix:3200", "12FLB250 P"),
    ("bitrix:3217", "12FLB300P"),
    ("bitrix:3241", "12SLA80L"),
    ("bitrix:3267", "12FGHL34"),
    ("bitrix:3293", "12FLB350P"),
)

USES = {
    "FGH": "источники бесперебойного питания",
    "FGHL": "источники бесперебойного питания",
    "FGL": "широкий спектр применений",
    "FLB": "системы бесперебойного электропитания",
    "SLA": "энергоснабжение критически важных объектов",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalized(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def number(token: str) -> Decimal:
    return Decimal(token.replace(",", "."))


def display_number(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text.replace(".", ",")


def series_for(mpn: str) -> str:
    compact = normalized(mpn)
    if compact.startswith("12FGHL"):
        return "FGHL"
    if compact.startswith("12FGH"):
        return "FGH"
    if "FGL" in compact:
        return "FGL"
    if "FLB" in compact:
        return "FLB"
    if "SLA" in compact:
        return "SLA"
    if compact.startswith("FG"):
        return "FG"
    raise ValueError(f"Unsupported MPN series: {mpn}")


def pdf_key_for(series: str) -> str:
    return "FGH" if series == "FGHL" else series


def assert_pin(path: Path, expected: str) -> None:
    actual = sha256(path)
    if actual != expected:
        raise RuntimeError(f"SHA-256 mismatch for {path}: expected {expected}, got {actual}")


def extract_exact_row(page, mpn: str) -> tuple[list[str], str]:
    words = page.extract_words(use_text_flow=False, keep_blank_chars=False)
    target = normalized(mpn)
    hits = [word for word in words if normalized(word["text"]) == target]
    if len(hits) != 1:
        raise RuntimeError(f"Expected one exact bounded page-2 row for {mpn}, got {len(hits)}")
    top = float(hits[0]["top"])
    row = sorted((word for word in words if abs(float(word["top"]) - top) <= 3.0), key=lambda word: float(word["x0"]))
    tokens = [word["text"] for word in row]
    positions = [index for index, token in enumerate(tokens) if normalized(token) == target]
    if len(positions) != 1:
        raise RuntimeError(f"Could not bound the unique row for {mpn}")
    tokens = tokens[positions[0] :]
    return tokens, " | ".join(tokens)


def parse_row(series: str, mpn: str, tokens: list[str]) -> dict[str, object]:
    if not tokens or normalized(tokens[0]) != normalized(mpn):
        raise RuntimeError(f"Row does not start with {mpn}: {tokens}")
    values = tokens[1:]
    horizontal = False
    if values and values[0] == "*":
        horizontal = True
        values = values[1:]

    if series in {"FG", "FGH", "FGHL"}:
        if len(values) < 8:
            raise RuntimeError(f"Malformed {series} row for {mpn}: {tokens}")
        voltage, capacity, length, width, height, _terminal_height, mass = map(number, values[:7])
        terminal = " ".join(values[7:])
        power = None
    elif series == "FGL":
        if len(values) != 7:
            raise RuntimeError(f"Malformed FGL row for {mpn}: {tokens}")
        voltage, capacity, length, width, height, _terminal_height, mass = map(number, values)
        terminal = None
        power = None
    elif series == "FLB":
        if len(values) != 7:
            raise RuntimeError(f"Malformed FLB row for {mpn}: {tokens}")
        voltage, power, capacity, length, width, height, mass = map(number, values)
        terminal = None
    elif series == "SLA":
        if len(values) != 6:
            raise RuntimeError(f"Malformed SLA row for {mpn}: {tokens}")
        voltage, capacity, length, width, height, mass = map(number, values)
        terminal = None
        power = None
    else:
        raise RuntimeError(f"Unsupported series {series}")

    return {
        "voltage": voltage,
        "capacity": capacity,
        "length": length,
        "width": width,
        "height": height,
        "mass": mass,
        "terminal": terminal,
        "power": power,
        "horizontal": horizontal,
    }


def attributes(series: str, facts: dict[str, object]) -> dict[str, str]:
    capacity_key = (
        "Номинальная ёмкость (10 ч, 1,80 В/эл., 20 °C)"
        if series == "SLA"
        else "Номинальная ёмкость (20 ч, 1,75 В/эл., 25 °C)"
    )
    result = {
        "Серия": series,
        "Технология": "AGM",
        "Номинальное напряжение": f"{display_number(facts['voltage'])} В",
        capacity_key: f"{display_number(facts['capacity'])} А·ч",
        "Габариты (Д × Ш × В)": (
            f"{display_number(facts['length'])} × {display_number(facts['width'])} × "
            f"{display_number(facts['height'])} мм"
        ),
        "Масса": f"{display_number(facts['mass'])} кг",
    }
    if series in USES:
        result["Применение"] = USES[series]
    if facts["terminal"]:
        result["Тип выводов"] = str(facts["terminal"])
    if facts["power"] is not None:
        result["Номинальная мощность (15 мин, 1,67 В/эл., 25 °C)"] = (
            f"{display_number(facts['power'])} Вт/эл."
        )
    if facts["horizontal"]:
        result["Монтаж"] = "только горизонтальное положение"
    return result


def load_scope() -> tuple[dict[str, dict[str, object]], dict[str, dict[str, str]]]:
    identity_payload = json.loads(IDENTITY_PATH.read_text(encoding="utf-8"))
    identities = {row["external_id"]: row for row in identity_payload["products"]}
    with QUEUE_PATH.open("r", encoding="utf-8-sig", newline="") as stream:
        queue = {row["product_external_id"]: row for row in csv.DictReader(stream)}
    if len(FROZEN) != 29 or len(set(FROZEN)) != 29:
        raise RuntimeError("Frozen Wave239 scope must contain 29 unique pairs")
    for external_id, mpn in FROZEN:
        identity = identities.get(external_id)
        item = queue.get(external_id)
        if identity is None or identity.get("mpn") != mpn:
            raise RuntimeError(f"Wave237 identity mismatch for {external_id}/{mpn}")
        if item is None or item.get("mpn") != mpn:
            raise RuntimeError(f"Wave238 queue mismatch for {external_id}/{mpn}")
        if item.get("manufacturer") != "Fiamm" or item.get("identity_fields_present") != "2":
            raise RuntimeError(f"Wave238 eligibility mismatch for {external_id}/{mpn}")
        if item.get("has_applied_description") != "false":
            raise RuntimeError(f"Wave239 frozen item already has a description: {external_id}/{mpn}")
    return identities, queue


def build() -> None:
    assert_pin(IDENTITY_PATH, INPUT_PINS["identity_manifest"])
    assert_pin(QUEUE_PATH, INPUT_PINS["queue"])
    for source in PDFS.values():
        assert_pin(SOURCE_DIR / source["filename"], source["sha256"])
    identities, queue = load_scope()

    pages = {}
    documents = []
    try:
        for key, source in PDFS.items():
            document = pdfplumber.open(SOURCE_DIR / source["filename"])
            documents.append(document)
            if len(document.pages) < 2:
                raise RuntimeError(f"Pinned {key} PDF has no page 2")
            pages[key] = document.pages[1]

        products = []
        ledger_rows = []
        for external_id, mpn in FROZEN:
            series = series_for(mpn)
            pdf_key = pdf_key_for(series)
            source = PDFS[pdf_key]
            tokens, row_text = extract_exact_row(pages[pdf_key], mpn)
            facts = parse_row(series, mpn, tokens)
            tech = attributes(series, facts)
            products.append(
                {
                    "external_id": external_id,
                    "identity_scope": "exact",
                    "manufacturer": "Fiamm",
                    "mpn": mpn,
                    "display_name": (
                        f"Аккумулятор Fiamm {mpn} "
                        f"(AGM, {display_number(facts['capacity'])}Ah)"
                    ),
                    "technology": "AGM",
                    "source_url": source["url"],
                    "technical_attributes": tech,
                    "source_kind": "official_manufacturer_catalogue",
                    "source_tier": "manufacturer_primary",
                    "source_publisher": PUBLISHER,
                    "manufacturer_primary": True,
                    "evidence_scope": "exact_model",
                    "checked_at": CHECKED_AT,
                }
            )
            ledger_rows.append(
                {
                    "external_id": external_id,
                    "manufacturer": identities[external_id]["manufacturer"],
                    "mpn": mpn,
                    "normalized_mpn": normalized(mpn),
                    "series": series,
                    "source_snapshot_path": f"docs/audits/sources/wave237-fiamm-primary/{source['filename']}",
                    "source_snapshot_sha256": source["sha256"],
                    "source_url": source["url"],
                    "source_page": 2,
                    "exact_bounded_row_count": 1,
                    "source_row_text": row_text,
                    "technical_attributes": tech,
                    "decision": "PASS",
                }
            )
    finally:
        for document in documents:
            document.close()

    manifest = {
        "schema_version": 1,
        "purpose": "Wave239 exact FIAMM manufacturer-primary source-backed descriptions",
        "locale": "ru-BY",
        "products": products,
    }
    ledger = {
        "schema_version": 1,
        "wave": "wave239-fiamm-exact-descriptions",
        "checked_at": CHECKED_AT,
        "scope": {"frozen_pairs": 29, "pass": 29, "hold": 0},
        "input_pins": {
            "identity_manifest": {"path": IDENTITY_PATH.relative_to(ROOT).as_posix(), "sha256": INPUT_PINS["identity_manifest"]},
            "queue": {"path": QUEUE_PATH.relative_to(ROOT).as_posix(), "sha256": INPUT_PINS["queue"]},
            "pdfs": {
                key: {
                    "path": f"docs/audits/sources/wave237-fiamm-primary/{source['filename']}",
                    "sha256": source["sha256"],
                    "source_url": source["url"],
                }
                for key, source in PDFS.items()
            },
        },
        "rows": ledger_rows,
    }
    write_json(MANIFEST_PATH, manifest)
    write_json(LEDGER_PATH, ledger)
    summary = {
        "schema_version": 1,
        "wave": "wave239-fiamm-exact-descriptions",
        "checked_at": CHECKED_AT,
        "frozen_scope_count": 29,
        "pass_count": 29,
        "hold_count": 0,
        "manifest": {"path": MANIFEST_PATH.relative_to(ROOT).as_posix(), "sha256": sha256(MANIFEST_PATH)},
        "ledger": {"path": LEDGER_PATH.relative_to(ROOT).as_posix(), "sha256": sha256(LEDGER_PATH)},
        "source_page": 2,
        "exact_bounded_row_count_per_product": 1,
        "price_facts": 0,
        "stock_facts": 0,
        "warranty_facts": 0,
        "database_calls": 0,
        "network_calls": 0,
    }
    write_json(SUMMARY_PATH, summary)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    build()
    print(f"Built {len(FROZEN)} Wave239 FIAMM exact descriptions.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
