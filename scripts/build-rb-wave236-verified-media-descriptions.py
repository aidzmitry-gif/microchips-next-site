#!/usr/bin/env python3
"""Build the complete Wave236 description package for verified-media gaps."""
from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path

from bs4 import BeautifulSoup
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
READINESS = ROOT / "docs/audits/generated/rb-full-content-readiness-wave235-after.csv"
OUTPUT = ROOT / "docs/imports/rb-source-backed-descriptions-wave236-verified-media-2026-07-29.json"
LEDGER = ROOT / "docs/audits/generated/rb-wave236-verified-media-descriptions.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-wave236-verified-media-descriptions.summary.json"

IDENTITIES = {
    "bb": ROOT / "docs/imports/rb-verified-oem-identities-wave206-bb-2026-07-29.json",
    "pvm": ROOT / "docs/imports/rb-verified-oem-identities-wave206-panasonic-ventura-mnb-2026-07-29.json",
    "wave209a": ROOT / "docs/imports/rb-verified-oem-identities-wave209a-2026-07-29.json",
    "wave209c": ROOT / "docs/imports/rb-verified-oem-identities-wave209c-stationary-2026-07-29.json",
    "general": ROOT / "docs/imports/rb-verified-oem-identities-wave234c-general-security-2026-07-29.json",
}
SOURCES = {
    "bb_bc": ROOT / "docs/audits/sources/wave206-fiamm-bb-csb/bb-bc-series-2026-07-29.html",
    "bb_hr": ROOT / "docs/audits/sources/wave206-fiamm-bb-csb/bb-hr-series-2026-07-29.html",
    "mnb_pdf": ROOT / "docs/audits/sources/wave206-panasonic-ventura-mnb/mnb-official-catalogue.pdf",
    "mnb_text": ROOT / "docs/audits/sources/wave206-panasonic-ventura-mnb/mnb-official-catalogue.txt",
    "ventura_pdf": ROOT / "docs/audits/sources/wave206-panasonic-ventura-mnb/ventura-catalogue-2023.pdf",
    "ventura_text": ROOT / "docs/audits/sources/wave206-panasonic-ventura-mnb/ventura-catalogue-2023.txt",
    "enersys": ROOT / "docs/audits/sources/wave209a/enersys-cyclon-selection-guide.pdf",
    "sonnenschein": ROOT / "docs/audits/sources/wave209a/exide-sonnenschein-a600-solar.pdf",
    "general": ROOT / "docs/audits/sources/wave234c/general-security-product.html",
}

PINS = {
    READINESS: "2b872e94e710a9997024f418332bd79d940faf0201267d7316cd0e37b78d537d",
    IDENTITIES["bb"]: "72f3f1ac60bd9720294fede943c826d13a01272422c500f65fc8560aa1df2afb",
    IDENTITIES["pvm"]: "73bfc5abd4649ec4b2c5982ee78b2508f3ce1e0fc9d8ca2cf7af7d9421dd6d0a",
    IDENTITIES["wave209a"]: "ae1cced58e0b29937e0cbb0ee64e77447c7100d9051c26b61cc645c789070467",
    IDENTITIES["wave209c"]: "0034afde9010c292f9c5175916ea6849014c774560eb40d755f7a1ab14c65415",
    IDENTITIES["general"]: "3cd236915ce0ed154ba145b8278b9fe59f9f567b50b5dff35270d1b6102b923e",
    SOURCES["bb_bc"]: "9f42041705a2c87c54e4cda7346eba8fcdfd6cada985e21beb94683a5b8892f4",
    SOURCES["bb_hr"]: "bd379d1ecac28698be0ea7bf271c63732251131464db1bf994d7ae5f73fe2c68",
    SOURCES["mnb_pdf"]: "85dac18f2953eeb29e306434b0af658a49f96afcc04d182ea2a2b8ef7b207859",
    SOURCES["mnb_text"]: "c98577d15147e74b03ab645f1a926784d2dee2570e223a8a6c532b55b9e76372",
    SOURCES["ventura_pdf"]: "68d09cc1255c5b8fbec04c669701ca21616ae501484d043dbc6fb512ae3ea839",
    SOURCES["ventura_text"]: "005fb1d171d5aee334eaffaac058e92aa96898dc543836e0c9e5b0da0709eae7",
    SOURCES["enersys"]: "3c6ecbb7f5379fccd8c2f5e31b999ac6f4d62117377b56b5f1e9df578e8fec5f",
    SOURCES["sonnenschein"]: "75954856154e15289c53f4caf00422e95cc4308816628e7e2ac09fd2a9a7b801",
    SOURCES["general"]: "9b3d5c6276c1df6b751233e78875449241a504fb36a010e603b1d0648f17f400",
}

TARGETS = {
    "bitrix:1526": ("bb", "bb_bc", "AGM VRLA", "B.B. Battery Co., Ltd."),
    "bitrix:1617": ("wave209c", "bb_hr", "высокомощная AGM VRLA", "B.B.Battery (Taiwan) Co., Ltd."),
    "bitrix:24551": ("wave209a", "enersys", "CYCLON AGM с пластинами из чистого свинца", "EnerSys"),
    "bitrix:2849": ("general", "general", "AGM VRLA", "General Security"),
    "bitrix:1464": ("pvm", "mnb_text", "AGM VRLA", "MNB Battery"),
    "bitrix:1561": ("pvm", "mnb_text", "AGM VRLA", "MNB Battery"),
    "bitrix:1789": ("wave209a", "sonnenschein", "GEL VRLA с трубчатыми пластинами", "Exide Technologies / Sonnenschein"),
    "bitrix:1493": ("pvm", "ventura_text", "AGM VRLA", "Ventura"),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def compact(value: str) -> str:
    return re.sub(r"[^0-9A-ZА-Я]", "", value.upper())


def source_text(key: str) -> str:
    path = SOURCES[key]
    if path.suffix == ".html":
        return BeautifulSoup(path.read_text(encoding="utf-8", errors="replace"), "html.parser").get_text(" ", strip=True)
    if path.suffix == ".txt":
        return path.read_text(encoding="utf-8", errors="replace")
    return " ".join(page.extract_text() or "" for page in PdfReader(path).pages)


def main() -> None:
    for path, digest in PINS.items():
        require(path.is_file() and sha256(path) == digest, f"Pinned Wave236 input drift: {path.relative_to(ROOT)}")

    with READINESS.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    queue = {
        row["product_external_id"]: row
        for row in rows
        if row["has_verified_published_image"] == "true" and row["has_applied_description"] == "false"
    }
    require(set(queue) == set(TARGETS), f"Wave236 verified-media gap drift: {sorted(set(queue) ^ set(TARGETS))}")
    require(all(row["identity_ready"] == "true" and row["is_published"] == "true" for row in queue.values()),
            "Wave236 target lost identity or publication state")

    identity_rows: dict[str, dict[str, str]] = {}
    for key, path in IDENTITIES.items():
        for row in json.loads(path.read_text(encoding="utf-8"))["products"]:
            if row.get("external_id") in TARGETS:
                require(row["external_id"] not in identity_rows, f"Identity source overlap: {row['external_id']}")
                identity_rows[row["external_id"]] = {**row, "identity_registry": key}
    require(set(identity_rows) == set(TARGETS), "Wave236 identity registry coverage drift")

    texts = {key: compact(source_text(key)) for key in {spec[1] for spec in TARGETS.values()}}
    products = []
    ledger = []
    for external_id in sorted(TARGETS):
        identity_key, source_key, technology, publisher = TARGETS[external_id]
        identity, ready = identity_rows[external_id], queue[external_id]
        require(identity["identity_registry"] == identity_key, f"Identity registry drift: {external_id}")
        require(identity["manufacturer"] == ready["manufacturer"] and identity["mpn"] == ready["mpn"],
                f"Readiness/identity drift: {external_id}")
        require(compact(identity["mpn"]) in texts[source_key], f"Exact model absent from pinned source: {external_id}")
        source_path = SOURCES[source_key]
        expected_source_hash = identity["source_snapshot_sha256"]
        # Text extractions are companions to their pinned PDFs; the identity
        # registry always pins the PDF/HTML source itself.
        if source_key == "mnb_text":
            source_path = SOURCES["mnb_pdf"]
        elif source_key == "ventura_text":
            source_path = SOURCES["ventura_pdf"]
        require(sha256(source_path) == expected_source_hash, f"Identity/source hash drift: {external_id}")

        product = {
            "external_id": external_id,
            "identity_scope": "model_core",
            "manufacturer": identity["manufacturer"],
            "model_core": identity["mpn"],
            "technology": technology,
            "source_url": identity["source_url"],
            "technical_attributes": {"Модель": identity["mpn"], "Технология": technology},
            "source_kind": identity["source_kind"],
            "source_tier": "manufacturer_primary",
            "source_publisher": publisher,
            "manufacturer_primary": True,
            "evidence_scope": "model_core",
            "checked_at": "2026-07-29",
        }
        products.append(product)
        ledger.append({
            "external_id": external_id,
            "manufacturer": identity["manufacturer"],
            "mpn": identity["mpn"],
            "source_key": source_key,
            "source_snapshot_path": source_path.relative_to(ROOT).as_posix(),
            "source_snapshot_sha256": sha256(source_path),
            "source_exact_model_present": "true",
            "verified_image_present": ready["has_verified_published_image"],
            "prior_applied_description": ready["has_applied_description"],
            "decision": "STAGE",
        })

    manifest = {
        "schema_version": 1,
        "purpose": "Complete all current verified-image/missing-description RB cards from hash-pinned manufacturer-primary evidence; no commercial, publication, URL or media mutation.",
        "locale": "ru-BY",
        "products": products,
    }
    OUTPUT.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with LEDGER.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(ledger[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(ledger)
    summary = {
        "schema_version": 1,
        "wave": "wave236_verified_media_descriptions",
        "checked_at": "2026-07-29",
        "coverage": {"verified_image_missing_description": 8, "stage": 8, "hold": 0},
        "inputs": {path.relative_to(ROOT).as_posix(): digest for path, digest in PINS.items()},
        "manifest": {"path": OUTPUT.relative_to(ROOT).as_posix(), "sha256": sha256(OUTPUT), "rows": len(products)},
        "ledger": {"path": LEDGER.relative_to(ROOT).as_posix(), "sha256": sha256(LEDGER), "rows": len(ledger)},
        "safety": {"database_operations": 0, "commercial_changes": 0, "publication_changes": 0, "media_changes": 0},
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"rows": len(products), "holds": 0}))


if __name__ == "__main__":
    main()
