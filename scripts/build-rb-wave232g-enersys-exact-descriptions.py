#!/usr/bin/env python3
"""Build two exact EnerSys description rows from pinned manufacturer PDFs.

The PDFs prove product identity and technical facts only.  This builder does
not author price, stock, warranty, publication, URL or media-rights fields.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "docs/audits/generated"
IMPORTS = ROOT / "docs/imports"
CYCLON = ROOT / "docs/audits/sources/wave209a/enersys-cyclon-selection-guide.pdf"
POWERSAFE = ROOT / "docs/audits/sources/wave209a/enersys-powersafe-v-range.pdf"
OFFICIAL_EVIDENCE = GEN / "rb-wave209a-official-evidence.csv"
MANIFEST = IMPORTS / "rb-source-backed-descriptions-wave232g-2026-07-29.json"
SUMMARY = GEN / "rb-wave232g-enersys-exact-descriptions.summary.json"

PINS = {
    CYCLON: "3c6ecbb7f5379fccd8c2f5e31b999ac6f4d62117377b56b5f1e9df578e8fec5f",
    POWERSAFE: "bc2664996bb29496c4153bb041c0679296e6c8e1e74f833beceaeb9348c8ba00",
    OFFICIAL_EVIDENCE: "5d093d66deddc3ad25858e918ccf1fa72a9087f78db42785632e8af5ffe62aa9",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def pdf_text(path: Path) -> str:
    return "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)


def compact(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def build() -> dict[str, object]:
    for path, expected in PINS.items():
        require(sha256(path) == expected, f"source pin drift: {path.relative_to(ROOT)}")

    cyclon = compact(pdf_text(CYCLON))
    powersafe = compact(pdf_text(POWERSAFE))
    require(
        re.search(r"0859-0016\s+12V\s*,\s*8\.0Ah\s*,\s*1x6\s+276\.4\s+54\.1\s+102\.1\s+2\.86", cyclon, re.I) is not None,
        "official CYCLON 0859-0016 row is missing",
    )
    require("99.99% pure lead" in cyclon and "Absorbed Glass Mat (AGM)" in cyclon, "CYCLON technology evidence is missing")
    require(
        re.search(r"12V70\s+12\s+68\s+70\s+314\s+164\s+204\s+224\s+24\.9\s+1814\s+6\.95\s+M6\s+F\s+V1", powersafe, re.I) is not None,
        "official PowerSafe 12V70 row is missing",
    )
    require("gas recombination technology" in powersafe and "microporous glass fibre" in powersafe, "PowerSafe technology evidence is missing")

    products = [
        {
            "external_id": "bitrix:24582",
            "identity_scope": "exact",
            "manufacturer": "EnerSys",
            "mpn": "0859-0016",
            "display_name": "Аккумулятор EnerSys CYCLON Monobloc 0859-0016",
            "technology": "герметичный свинцово-кислотный аккумулятор EnerSys CYCLON с пластинами из чистого свинца и AGM-сепаратором",
            "source_url": "https://www.enersys.com/493c0d/globalassets/documents/product-documentation/cyclon/emea/en-cyc-sg-004_0614.pdf",
            "source_kind": "official_manufacturer_catalogue",
            "source_tier": "manufacturer_primary",
            "source_publisher": "EnerSys",
            "manufacturer_primary": True,
            "evidence_scope": "exact_model",
            "checked_at": "2026-07-29",
            "technical_attributes": {
                "Номинальное напряжение": "12 В",
                "Номинальная ёмкость": "8,0 А·ч",
                "Конфигурация": "моноблок 1 × 6 элементов",
                "Габариты": "276,4 × 54,1 × 102,1 мм",
                "Масса": "2,86 кг",
                "Технология": "герметичный свинцово-кислотный аккумулятор EnerSys CYCLON с пластинами из чистого свинца и AGM-сепаратором",
            },
        },
        {
            "external_id": "bitrix:26048",
            "identity_scope": "model_core",
            "manufacturer": "EnerSys",
            "model_core": "12V70",
            "technology": "герметизированный свинцово-кислотный аккумулятор VRLA с газовой рекомбинацией и AGM-сепаратором",
            "source_url": "https://www.enersys.com/493bb4/globalassets/documents/product-documentation/powersafe/v-tt/emea/en-v-rs-013.pdf",
            "source_kind": "official_manufacturer_catalogue",
            "source_tier": "manufacturer_primary",
            "source_publisher": "EnerSys",
            "manufacturer_primary": True,
            "evidence_scope": "model_core",
            "checked_at": "2026-07-29",
            "technical_attributes": {
                "Номинальное напряжение": "12 В",
                "Ёмкость C10": "68 А·ч до 1,80 В/элемент при 20 °C",
                "Ёмкость C8": "70 А·ч до 1,75 В/элемент при 25 °C",
                "Габариты корпуса": "314 × 164 × 204 мм",
                "Высота с соединителями": "224 мм",
                "Масса": "24,9 кг",
                "Внутреннее сопротивление": "6,95 мОм",
                "Ток короткого замыкания": "1814 А",
                "Тип вывода": "M6",
                "Технология": "герметизированный свинцово-кислотный аккумулятор VRLA с газовой рекомбинацией и AGM-сепаратором",
            },
        },
    ]
    manifest = {
        "schema_version": 1,
        "purpose": "Two exact EnerSys descriptions from pinned official catalogues; no price, stock, warranty, publication, URL or image-rights claim.",
        "locale": "ru-BY",
        "products": products,
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    summary = {
        "schema_version": 1,
        "wave": "wave232g_enersys_exact_descriptions",
        "rows": len(products),
        "external_ids": [row["external_id"] for row in products],
        "source_sha256": {str(path.relative_to(ROOT)).replace("\\", "/"): sha256(path) for path in PINS},
        "manifest": str(MANIFEST.relative_to(ROOT)).replace("\\", "/"),
        "manifest_sha256": sha256(MANIFEST),
        "commercial_fields": 0,
        "publication_fields": 0,
        "media_fields": 0,
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False))
