#!/usr/bin/env python3
"""Build a strict Wave228-B primary-source description refresh stage manifest."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "docs/audits/generated"
IMPORTS = ROOT / "docs/imports"
SOURCES = ROOT / "docs/audits/sources"

READINESS = GEN / "rb-full-content-readiness-wave227-after.csv"
DELTA_W206 = GEN / "rb-delta-wave206-official-evidence.csv"
DELTA_W211B = GEN / "rb-wave211b-delta-fiamm-leoch-csb-evidence.csv"
VENTURA_PDF = SOURCES / "wave206-panasonic-ventura-mnb/ventura-catalogue-2023.pdf"
VENTURA_TEXT = SOURCES / "wave206-panasonic-ventura-mnb/ventura-catalogue-2023.txt"

MANIFEST = IMPORTS / "rb-source-backed-description-stage-manifest-wave228b-2026-07-29.json"
LEDGER = GEN / "rb-wave228b-delta-ventura-description-ledger.csv"
HOLDS = GEN / "rb-wave228b-delta-ventura-description-holds.csv"
SUMMARY = GEN / "rb-wave228b-delta-ventura-description.summary.json"
REPORT = ROOT / "docs/audits/2026-07-29-rb-wave228b-delta-ventura-descriptions.md"

PINS = {
    READINESS: "57fcb5e7f2f8b159001a707547025ddc8fd93e1e9576bfd67fc074eefed4dd6e",
    DELTA_W206: "9aef716d13d9dbbaf1a13473641469d61dd130a148b87e89d8c45fc776a0b36c",
    DELTA_W211B: "ce03acb5153b4a8fc65ef9365d0acc39ff10f32dba32c77fe56f05b88e8e4156",
    VENTURA_PDF: "68d09cc1255c5b8fbec04c669701ca21616ae501484d043dbc6fb512ae3ea839",
    VENTURA_TEXT: "005fb1d171d5aee334eaffaac058e92aa96898dc543836e0c9e5b0da0709eae7",
}

TARGETS = {
    "Delta": {
        "bitrix:1548", "bitrix:1458", "bitrix:1503", "bitrix:3212",
        "bitrix:1417", "bitrix:1550", "bitrix:1477", "bitrix:1479",
    },
    "Ventura": {"bitrix:1437", "bitrix:1609", "bitrix:1643", "bitrix:1624", "bitrix:1635"},
}

VENTURA_ROWS = {
    "bitrix:1437": ("GP 12-100", "VRLA AGM", {"Номинальное напряжение": "12 В", "Номинальная ёмкость C20": "100 А·ч"}),
    "bitrix:1609": ("GP 12-40", "VRLA AGM", {"Номинальное напряжение": "12 В", "Номинальная ёмкость C20": "42 А·ч"}),
    "bitrix:1643": ("GP 6-9", "VRLA AGM", {"Номинальное напряжение": "6 В", "Номинальная ёмкость C20": "8,7 А·ч"}),
    "bitrix:1624": ("HR 1228W", "VRLA AGM", {"Номинальное напряжение": "12 В", "Мощность (15 мин до 1,6 В/эл)": "192 Вт/блок"}),
    "bitrix:1635": ("HR 1234W", "VRLA AGM", {"Номинальное напряжение": "12 В", "Мощность (15 мин до 1,6 В/эл)": "222 Вт/блок"}),
}
VENTURA_URL = "https://ventura-battery.ru/upload/iblock/836/n52d2cyekiv52rav9o0vwctttvggje9j/Catalog_Ventura_2023.pdf"

PRODUCT_FIELDS = {
    "external_id", "identity_scope", "manufacturer", "mpn", "technology", "source_url",
    "technical_attributes", "source_kind", "source_tier", "source_publisher",
    "manufacturer_primary", "evidence_scope", "checked_at",
}
LEDGER_FIELDS = (
    "external_id", "manufacturer", "mpn", "stage_status", "identity_scope", "source_kind",
    "source_url", "source_snapshot_path", "source_snapshot_sha256", "source_assertion",
    "technical_attributes_json", "refresh_existing", "refresh_applied", "safe_to_apply",
)
HOLD_FIELDS = ("external_id", "manufacturer", "mpn", "hold_reason", "source_checked")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fields: tuple[str, ...], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def source_path(value: str) -> Path:
    path = ROOT / value.replace("/", "\\")
    require(path.is_file(), f"pinned source snapshot absent: {value}")
    return path


def parse_delta_facts(value: str) -> dict[str, str]:
    facts = dict(part.split("=", 1) for part in value.split("|") if "=" in part)
    require(set(("manufacturer", "mpn", "voltage_v", "capacity_ah")) <= set(facts), "incomplete Delta official facts")
    return facts


def ready_targets() -> list[dict[str, str]]:
    rows = [
        row for row in read_csv(READINESS)
        if row["manufacturer"] in TARGETS
        and row["has_applied_description"] == "false"
        and row["has_verified_published_image"] == "true"
    ]
    ids_by_maker = {maker: {row["product_external_id"] for row in rows if row["manufacturer"] == maker} for maker in TARGETS}
    require(ids_by_maker == TARGETS, f"Wave227 target set drift: {ids_by_maker}")
    require(len(rows) == 13 and len({row["product_external_id"] for row in rows}) == 13, "Wave228-B requires 13 unique targets")
    return rows


def delta_evidence() -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for path in (DELTA_W206, DELTA_W211B):
        for row in read_csv(path):
            external_id = row.get("product_external_id", "")
            if external_id in TARGETS["Delta"]:
                require(external_id not in result, f"duplicate Delta source evidence: {external_id}")
                require(row.get("safe_to_apply") == "true", f"unsafe Delta source evidence: {external_id}")
                result[external_id] = row
    require(set(result) == TARGETS["Delta"], "missing exact Delta primary evidence")
    return result


def delta_product(row: dict[str, str]) -> tuple[dict[str, object], dict[str, str]]:
    facts = parse_delta_facts(row["verified_facts"])
    snapshot = source_path(row["snapshot_path"])
    require(digest(snapshot) == row["snapshot_sha256"], f"Delta snapshot hash drift: {row['product_external_id']}")
    source_text = snapshot.read_text(encoding="utf-8")
    require(facts["mpn"] in source_text, f"Delta exact MPN absent from snapshot: {row['product_external_id']}")
    product = {
        "external_id": row["product_external_id"], "identity_scope": "exact", "manufacturer": facts["manufacturer"],
        "mpn": facts["mpn"], "technology": "VRLA AGM", "source_url": row["source_url"],
        "technical_attributes": {"Номинальное напряжение": f"{facts['voltage_v']} В", "Номинальная ёмкость": f"{facts['capacity_ah']} А·ч"},
        "source_kind": "official_manufacturer_product_page", "source_tier": "manufacturer_primary",
        "source_publisher": "DELTA Battery / ENERGON", "manufacturer_primary": True,
        "evidence_scope": "exact_model", "checked_at": "2026-07-29",
    }
    ledger = {
        "external_id": product["external_id"], "manufacturer": product["manufacturer"], "mpn": product["mpn"],
        "stage_status": "STAGE", "identity_scope": "exact", "source_kind": product["source_kind"],
        "source_url": product["source_url"], "source_snapshot_path": row["snapshot_path"],
        "source_snapshot_sha256": row["snapshot_sha256"], "source_assertion": row["source_assertion"],
        "technical_attributes_json": json.dumps(product["technical_attributes"], ensure_ascii=False, sort_keys=True),
        "refresh_existing": "true", "refresh_applied": "true", "safe_to_apply": "false",
    }
    return product, ledger


def ventura_product(row: dict[str, str], catalogue_text: str) -> tuple[dict[str, object] | None, dict[str, str]]:
    external_id, mpn = row["product_external_id"], row["mpn"]
    expected_mpn, technology, attributes = VENTURA_ROWS[external_id]
    require(mpn == expected_mpn, f"Ventura readiness MPN drift: {external_id}")
    if mpn not in catalogue_text:
        return None, {"external_id": external_id, "manufacturer": "Ventura", "mpn": mpn, "hold_reason": "exact_mpn_absent_from_pinned_official_catalogue", "source_checked": VENTURA_TEXT.relative_to(ROOT).as_posix()}
    product = {
        "external_id": external_id, "identity_scope": "exact", "manufacturer": "Ventura", "mpn": mpn,
        "technology": technology, "source_url": VENTURA_URL, "technical_attributes": attributes,
        "source_kind": "official_manufacturer_catalogue", "source_tier": "manufacturer_primary",
        "source_publisher": "Ventura", "manufacturer_primary": True, "evidence_scope": "exact_model",
        "checked_at": "2026-07-29",
    }
    ledger = {
        "external_id": external_id, "manufacturer": "Ventura", "mpn": mpn, "stage_status": "STAGE",
        "identity_scope": "exact", "source_kind": product["source_kind"], "source_url": VENTURA_URL,
        "source_snapshot_path": VENTURA_PDF.relative_to(ROOT).as_posix(), "source_snapshot_sha256": digest(VENTURA_PDF),
        "source_assertion": "exact_model_table_row", "technical_attributes_json": json.dumps(attributes, ensure_ascii=False, sort_keys=True),
        "refresh_existing": "true", "refresh_applied": "true", "safe_to_apply": "false",
    }
    return product, ledger


def build() -> dict[str, object]:
    for path, expected in PINS.items():
        require(digest(path) == expected, f"pinned input drift: {path.relative_to(ROOT)}")
    readiness = ready_targets()
    delta = delta_evidence()
    catalogue_text = VENTURA_TEXT.read_text(encoding="utf-8")

    products: list[dict[str, object]] = []
    ledger: list[dict[str, str]] = []
    holds: list[dict[str, str]] = []
    for row in readiness:
        if row["manufacturer"] == "Delta":
            product, row_ledger = delta_product(delta[row["product_external_id"]])
            require(product["mpn"] == row["mpn"], f"Delta readiness MPN drift: {row['product_external_id']}")
            products.append(product)
            ledger.append(row_ledger)
        else:
            product, result = ventura_product(row, catalogue_text)
            if product is None:
                holds.append(result)
            else:
                products.append(product)
                ledger.append(result)

    require(len({row["external_id"] for row in products + [{"external_id": row["external_id"]} for row in holds]}) == 13, "target coverage drift")
    require(all(set(row) == PRODUCT_FIELDS for row in products), "stage product contract drift")
    require(all(row["identity_scope"] == "exact" and row["evidence_scope"] == "exact_model" for row in products), "exact-scope contract drift")
    manifest = {
        "schema_version": 1,
        "purpose": "Wave228-B exact-MPN manufacturer-primary description refresh stage only.",
        "locale": "ru-BY",
        "application_contract": {"stage_only": True, "refresh_existing": True, "refresh_applied": True, "database_apply": False},
        "products": products,
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_csv(LEDGER, LEDGER_FIELDS, ledger)
    write_csv(HOLDS, HOLD_FIELDS, holds)
    summary = {
        "schema_version": 1, "batch": "wave228b_delta_ventura_exact_description_stage",
        "inputs": {path.relative_to(ROOT).as_posix(): digest(path) for path in PINS},
        "coverage": {"wave227_image_verified_no_description_targets": 13, "delta_targets": 8, "ventura_targets": 5, "staged": len(products), "holds": len(holds)},
        "manifest": {"path": MANIFEST.relative_to(ROOT).as_posix(), "sha256": digest(MANIFEST), "rows": len(products)},
        "ledger": {"path": LEDGER.relative_to(ROOT).as_posix(), "sha256": digest(LEDGER), "rows": len(ledger)},
        "holds": {"path": HOLDS.relative_to(ROOT).as_posix(), "sha256": digest(HOLDS), "rows": len(holds)},
        "application_contract": manifest["application_contract"],
        "safety": {"database_operations": 0, "apply_performed": False, "price_changes": 0, "stock_changes": 0, "media_changes": 0, "publication_changes": 0, "url_changes": 0, "identity_changes": 0},
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REPORT.write_text(
        "# Wave228-B: Delta and Ventura exact-source description refresh\n\n"
        "Wave228-B selects only the 13 Wave227 rows that have a verified published image, no applied description, and manufacturer Delta (8) or Ventura (5). Every staged row has exact MPN scope and manufacturer-primary evidence. Delta facts are copied from the hash-pinned Wave206/Wave211B official product-page evidence and then rechecked against the pinned HTML snapshot. Ventura facts are read from the hash-pinned official 2023 catalogue PDF/text snapshot.\n\n"
        "The manifest is a stage-only refresh contract for existing legacy-preview drafts: `--refresh-existing --refresh-applied`. It does not run an importer or make a database change. Products without their exact MPN in the pinned official source are written to the HOLD ledger and excluded from the manifest.\n\n"
        "The Ventura GP 12-40 and GP 6-9 catalogue rows expose 42 Ah and 8.7 Ah respectively; these official values are retained rather than inferring the legacy title's rounded capacity. HR 1228W and HR 1234W are represented with the catalogue's 15-minute watt/block rating, not an inferred Ah rating.\n",
        encoding="utf-8",
    )
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False))
