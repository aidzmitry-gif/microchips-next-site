#!/usr/bin/env python3
"""Build exact Delta descriptions from pinned manufacturer product pages."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]
IDENTITY = ROOT / "docs/imports/rb-delta-identity-stage-manifest-wave233a-2026-07-29.json"
MANIFEST = ROOT / "docs/imports/rb-source-backed-descriptions-wave233e-delta-2026-07-29.json"
SUMMARY = ROOT / "docs/audits/generated/rb-wave233e-delta-descriptions.summary.json"
IDENTITY_SHA256 = "407c187cbb53fd2193c96be18265f404cabdd1bb7ae086d4ecfe0619f05eab98"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def normalize(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def clean(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().rstrip(":")


def product_properties(snapshot: Path) -> tuple[str, dict[str, str], str]:
    soup = BeautifulSoup(snapshot.read_text(encoding="utf-8"), "html.parser")
    title_node = soup.select_one("h1") or soup.select_one("title")
    title = clean(title_node.get_text(" ", strip=True)) if title_node else ""
    properties: dict[str, str] = {}
    for item in soup.select(".properties__item"):
        key = item.select_one(".properties__title")
        value = item.select_one(".properties__value")
        if key and value:
            properties[clean(key.get_text(" ", strip=True))] = clean(value.get_text(" ", strip=True))
    if not properties:
        for item in soup.select(".product-page__info-properties .item"):
            key = item.select_one(".label")
            value = item.select_one("span") or item.select_one("a")
            if key and value:
                properties[clean(key.get_text(" ", strip=True))] = clean(value.get_text(" ", strip=True))
    return title, properties, clean(soup.get_text(" ", strip=True))


def first(properties: dict[str, str], *keys: str) -> str:
    for key in keys:
        if key in properties and properties[key]:
            return properties[key]
    return ""


def technical_attributes(properties: dict[str, str], source_text: str) -> dict[str, str]:
    voltage = first(properties, "Напряжение, В")
    capacity = first(properties, "Емкость, Ач")
    mass = first(properties, "Масса, кг", "Вес, кг")
    dimensions = first(properties, "Габариты ДхШхВ, мм", "Габариты ДxШxВ, мм")
    if not dimensions:
        length = first(properties, "Длина, мм")
        width = first(properties, "Ширина, мм")
        height = first(properties, "Высота, мм")
        if length and width and height:
            dimensions = f"{length} × {width} × {height}"
    dimensions = re.sub(r"\s*[xхXХ×]\s*", " × ", dimensions)
    attributes: dict[str, str] = {}
    if voltage:
        attributes["Номинальное напряжение"] = f"{voltage.replace('.', ',')} В"
    if capacity:
        attributes["Номинальная ёмкость"] = f"{capacity.replace('.', ',')} А·ч"
    if dimensions:
        attributes["Габариты (Д × Ш × В)"] = f"{dimensions} мм"
    if mass:
        attributes["Масса"] = f"{mass.replace('.', ',')} кг"
    terminals = first(properties, "Код типа клемм")
    if terminals:
        attributes["Тип выводов"] = terminals
    polarity = first(properties, "Полярность")
    if polarity:
        attributes["Полярность"] = polarity
    lifetime = first(properties, "Срок службы, лет")
    if lifetime:
        attributes["Заявленный срок службы"] = lifetime
    require(re.search(r"\bAGM\b", source_text, re.I) is not None, "Official Delta page lacks AGM evidence")
    attributes["Технология"] = "свинцово-кислотный аккумулятор с AGM-сепаратором"
    return attributes


def build() -> dict[str, object]:
    require(sha256(IDENTITY) == IDENTITY_SHA256, "Wave233-A identity manifest pin drift")
    identity = json.loads(IDENTITY.read_text(encoding="utf-8-sig"))
    require(len(identity["products"]) == 16, "Wave233-E Delta scope drift")
    products: list[dict[str, object]] = []
    source_pins: dict[str, str] = {}
    for row in identity["products"]:
        snapshot = (IDENTITY.parent / row["source_snapshot_path"]).resolve()
        require(snapshot.is_file(), f"Missing pinned Delta source for {row['external_id']}")
        require(sha256(snapshot) == row["source_snapshot_sha256"], f"Delta source hash drift for {row['external_id']}")
        title, properties, source_text = product_properties(snapshot)
        require(normalize(row["mpn"]) in normalize(title), f"Official page title lacks exact MPN for {row['external_id']}")
        attributes = technical_attributes(properties, source_text)
        require("Номинальное напряжение" in attributes and "Номинальная ёмкость" in attributes, f"Essential Delta facts missing for {row['external_id']}")
        products.append({
            "external_id": row["external_id"],
            "identity_scope": "exact",
            "manufacturer": "Delta",
            "mpn": row["mpn"],
            "display_name": row["current_name"],
            "technology": attributes["Технология"],
            "source_url": row["source_url"],
            "source_kind": "official_manufacturer_product_page",
            "source_tier": "manufacturer_primary",
            "source_publisher": "Delta Battery",
            "manufacturer_primary": True,
            "evidence_scope": "exact_model",
            "checked_at": "2026-07-29",
            "technical_attributes": attributes,
        })
        source_pins[snapshot.relative_to(ROOT).as_posix()] = sha256(snapshot)
    require(len({row["external_id"] for row in products}) == 16, "Wave233-E repeats product IDs")
    require(len({normalize(str(row["mpn"])) for row in products}) == 16, "Wave233-E repeats normalized MPNs")
    manifest = {
        "schema_version": 1,
        "purpose": "Exact Delta technical descriptions from pinned official manufacturer product pages; no price, stock, warranty, publication, URL or media-rights claim.",
        "locale": "ru-BY",
        "products": products,
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = {
        "schema_version": 1,
        "wave": "wave233e_delta_exact_descriptions",
        "rows": 16,
        "source_pins": dict(sorted(source_pins.items())),
        "manifest": MANIFEST.relative_to(ROOT).as_posix(),
        "manifest_sha256": sha256(MANIFEST),
        "commercial_fields": 0,
        "publication_fields": 0,
        "media_fields": 0,
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False))
