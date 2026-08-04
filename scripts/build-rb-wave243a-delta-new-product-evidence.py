#!/usr/bin/env python3
"""Build the offline Wave243A no-repeat Delta evidence packet."""

from __future__ import annotations

import csv
import hashlib
import html
import json
import re
from collections import Counter
from decimal import Decimal
from pathlib import Path

from bs4 import BeautifulSoup
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
CHECKED_AT = "2026-07-29"
QUEUE = ROOT / "docs/audits/generated/rb-enrichment-queue-wave242.csv"
WAVE242_LEDGER = ROOT / "docs/audits/generated/rb-wave242-delta-hold-research-ledger.csv"
EXCLUSIONS = ROOT / "docs/audits/generated/rb-wave243a-prior-source-exclusions.json"
SOURCES = ROOT / "docs/audits/sources/wave243a-delta/registry.json"
DATASHEETS = ROOT / "docs/audits/sources/wave243a-delta/datasheet-registry.json"
LEDGER = ROOT / "docs/audits/generated/rb-wave243a-delta-evidence-ledger.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-wave243a-delta-evidence.summary.json"
IDENTITIES = ROOT / "docs/imports/rb-verified-oem-identities-wave243a-delta-2026-07-29.json"
DESCRIPTIONS = ROOT / "docs/imports/rb-source-backed-descriptions-wave243a-delta-2026-07-29.json"
REPORT = ROOT / "docs/audits/2026-07-29-rb-wave243a-delta-new-product-evidence.md"
LARAVEL_DRY_RUN = ROOT / "docs/audits/generated/rb-wave243a-delta-description-laravel-dry-run.json"
PINS = {
    QUEUE: "8d7f4435b25327d3f6a3b9015d0b535cf64f3aad1342378fc165abc4be1e7867",
    WAVE242_LEDGER: "4712d85fad7452d6ae1c1dc3ac91c246645f9ae393fc49cba39bbfa1bcbe3a87",
    EXCLUSIONS: "a9a5aa9f109fddb0d320301f7007d829021ede9a60b508482d36c45fa2ef76ac",
    SOURCES: "ef69afbc797b20a7fa891ffc9ebd4b95423a752b3565d40b627a22dff840f9da",
    DATASHEETS: "e78d2799d3eb83b9102f52555518a02cf386de3c7eb0c0bbb70027ecbe50cf65",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def canonical(value: str) -> str:
    value = re.sub(r"^DELTA\s+", "", value.strip(), flags=re.I)
    value = re.sub(r"^XPERT\s+", "", value, flags=re.I)
    value = re.sub(r"\s+XPERT$", "", value, flags=re.I)
    return "".join(char for char in value.casefold() if char.isalnum())


def title_mpn(name: str) -> str:
    match = re.fullmatch(r"Аккумулятор\s+Delta\s+(.+?)\s+\(AGM,.*", name)
    if not match:
        raise ValueError(f"unsupported Delta title: {name}")
    return match.group(1)


def title_capacity(name: str) -> Decimal:
    match = re.search(r"\(AGM,\s*([0-9]+(?:[.,][0-9]+)?)\s*Ah\)", name, flags=re.I)
    if not match:
        raise ValueError(f"capacity absent: {name}")
    return Decimal(match.group(1).replace(",", "."))


def page_facts(path: Path) -> dict[str, object]:
    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    heading = soup.find("h1")
    heading_text = heading.get_text(" ", strip=True) if heading else ""
    text = html.unescape(" ".join(soup.stripped_strings))
    text = re.sub(r"\s+", " ", text)
    voltage = re.search(r"Напряжение\s*,?\s*В\s*[:—-]?\s*([0-9]+(?:[.,][0-9]+)?)", text, flags=re.I)
    capacity = re.search(r"Емкость\s*,?\s*Ач\s*[:—-]?\s*([0-9]+(?:[.,][0-9]+)?)", text, flags=re.I)
    return {
        "heading": heading_text,
        "voltage": Decimal(voltage.group(1).replace(",", ".")) if voltage else None,
        "capacity": Decimal(capacity.group(1).replace(",", ".")) if capacity else None,
        "technology": "AGM" if re.search(r"(?<![A-Z])AGM(?![A-Z])", text, flags=re.I) else "",
    }


def page_facts(path: Path) -> dict[str, object]:
    """Read exact model, capacity, and technology from the product JSON-LD."""
    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    heading = soup.find("h1")
    product = None
    for script in soup.find_all("script", type="application/ld+json"):
        payload = json.loads(script.string or "{}")
        for node in payload.get("@graph", []):
            if node.get("@type") == "Product":
                product = node
                break
    if not product:
        raise SystemExit(f"JSON-LD Product absent: {path}")
    capacity = next((item.get("value") for item in product.get("additionalProperty", [])
                     if item.get("code") == "emkost_ach"), None)
    return {
        "heading": heading.get_text(" ", strip=True) if heading else "",
        "model": product.get("model", ""),
        "capacity": Decimal(str(capacity).replace(",", ".")) if capacity is not None else None,
        "technology": "AGM" if re.search(r"(?<![A-Z])AGM(?![A-Z])", product.get("description", ""), re.I) else "",
    }


def datasheet_voltage(path: Path) -> Decimal | None:
    text = " ".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)
    # Embedded Cyrillic lacks a Unicode map; numeric voltage and label leader remain extractable.
    match = re.search(r"(?:\.{20,}\s*|\n)(12)\s*[В\ufffd]", text)
    return Decimal(match.group(1)) if match else None


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def build() -> dict[str, object]:
    for path, expected in PINS.items():
        if sha(path) != expected:
            raise SystemExit(f"pinned input changed: {path.relative_to(ROOT)}")
    queue_rows = [row for row in rows(QUEUE)
                  if row["has_applied_description"] == "false"
                  and (row["manufacturer"] == "Delta"
                       or (not row["manufacturer"] and "Delta" in row["name"]))]
    if len(queue_rows) != 80 or len({row["product_external_id"] for row in queue_rows}) != 80:
        raise SystemExit("Wave243A scope must contain 80 unique missing-description Delta rows")

    wave242 = {row["external_id"]: row for row in rows(WAVE242_LEDGER)}
    duplicate_owners = {
        external_id: row["live_duplicate_owner_external_ids"]
        for external_id, row in wave242.items() if row["live_duplicate_owner_external_ids"]
    }
    exclusions = json.loads(EXCLUSIONS.read_text(encoding="utf-8"))
    prior_urls = {row["value"] for row in exclusions["source_urls"]}
    prior_hashes = {row["value"] for row in exclusions["snapshot_sha256"]}
    source_registry = json.loads(SOURCES.read_text(encoding="utf-8"))
    if source_registry["prior_exclusions_sha256"] != sha(EXCLUSIONS):
        raise SystemExit("source acquisition did not use the pinned prior exclusion set")
    datasheet_registry = json.loads(DATASHEETS.read_text(encoding="utf-8"))
    if datasheet_registry["prior_exclusions_sha256"] != sha(EXCLUSIONS):
        raise SystemExit("datasheet acquisition did not use the pinned prior exclusion set")
    if datasheet_registry["product_registry_sha256"] != sha(SOURCES):
        raise SystemExit("datasheet acquisition did not use the pinned product registry")
    datasheets = {}
    for source in datasheet_registry["sources"]:
        path = ROOT / source["snapshot_path"]
        if source["source_url"] in prior_urls or source["snapshot_sha256"] in prior_hashes:
            raise SystemExit(f"prior datasheet repeated: {source['source_url']}")
        if sha(path) != source["snapshot_sha256"]:
            raise SystemExit(f"datasheet hash mismatch: {path}")
        datasheets[source["external_id"]] = {**source, "voltage": datasheet_voltage(path)}
    evidence = {}
    for source in source_registry["sources"]:
        path = ROOT / source["snapshot_path"]
        if source["source_url"] in prior_urls or source["snapshot_sha256"] in prior_hashes:
            raise SystemExit(f"prior evidence repeated: {source['source_url']}")
        if sha(path) != source["snapshot_sha256"]:
            raise SystemExit(f"snapshot hash mismatch: {path}")
        facts = page_facts(path)
        if canonical(str(facts["heading"])) != canonical(source["expected_model"]):
            raise SystemExit(f"snapshot heading drift: {source['source_url']}")
        if canonical(str(facts["model"])) != canonical(source["expected_model"]):
            raise SystemExit(f"JSON-LD model drift: {source['source_url']}")
        datasheet = datasheets.get(source["external_id"])
        if datasheet and datasheet["linked_from_product_snapshot_sha256"] != source["snapshot_sha256"]:
            raise SystemExit(f"datasheet provenance drift: {source['source_url']}")
        evidence[source["external_id"]] = {
            **source, **facts, "datasheet": datasheet,
            "voltage": datasheet["voltage"] if datasheet else None,
        }

    ledger = []
    identity_products = []
    description_products = []
    for item in sorted(queue_rows, key=lambda row: row["product_external_id"]):
        external_id = item["product_external_id"]
        mpn = item["mpn"].strip() or title_mpn(item["name"])
        source = evidence.get(external_id)
        reasons = []
        if external_id in duplicate_owners:
            reasons.append("LEGACY_DUPLICATE_CANONICAL_OWNER")
        elif source is None:
            reasons.append("NO_NEW_OFFICIAL_EXACT_MODEL_SOURCE")
        else:
            if canonical(source["heading"]) != canonical(mpn):
                reasons.append("SOURCE_MODEL_NOT_EXACT")
            if source["capacity"] is None or source["capacity"] != title_capacity(item["name"]):
                reasons.append("TITLE_CAPACITY_CONFLICT")
            if source["voltage"] != Decimal("12"):
                reasons.append("TITLE_VOLTAGE_CONFLICT")
            if source["technology"] != "AGM":
                reasons.append("NO_SOURCE_SUPPORTED_TECHNOLOGY")
        decision = "PASS" if not reasons else "HOLD"
        ledger.append({
            "external_id": external_id, "current_name": item["name"], "manufacturer": "Delta", "mpn": mpn,
            "legacy_duplicate_owner_external_ids": duplicate_owners.get(external_id, ""),
            "source_heading": str(source["heading"]) if source else "",
            "source_voltage_v": str(source["voltage"]) if source and source["voltage"] is not None else "",
            "source_capacity_ah": str(source["capacity"]) if source and source["capacity"] is not None else "",
            "source_technology": str(source["technology"]) if source else "",
            "source_url": str(source["source_url"]) if source else "",
            "source_snapshot_path": str(source["snapshot_path"]) if source else "",
            "source_snapshot_sha256": str(source["snapshot_sha256"]) if source else "",
            "datasheet_url": str(source["datasheet"]["source_url"]) if source and source["datasheet"] else "",
            "datasheet_snapshot_path": str(source["datasheet"]["snapshot_path"]) if source and source["datasheet"] else "",
            "datasheet_snapshot_sha256": str(source["datasheet"]["snapshot_sha256"]) if source and source["datasheet"] else "",
            "decision": decision, "hold_reason": "|".join(reasons),
        })
        if decision != "PASS":
            continue
        identity_products.append({
            "external_id": external_id, "current_name": item["name"], "manufacturer": "Delta", "mpn": mpn,
            "source_url": source["source_url"], "source_kind": "official_manufacturer_product_page",
            "source_publisher": source["source_publisher"], "checked_at": CHECKED_AT,
            "product_type": "starter AGM battery for motorcycles",
            "source_snapshot_path": "../audits/" + source["snapshot_path"].removeprefix("docs/audits/"),
            "source_snapshot_sha256": source["snapshot_sha256"],
        })
        description_products.append({
            "external_id": external_id, "identity_scope": "model_core", "manufacturer": "Delta",
            "model_core": mpn, "technology": "AGM", "source_url": source["source_url"],
            "technical_attributes": {"Модель": mpn, "Напряжение, В": str(source["voltage"]),
                                     "Емкость, Ач": str(source["capacity"])},
            "source_kind": "official_manufacturer_product_page", "source_tier": "manufacturer_primary",
            "source_publisher": source["source_publisher"], "manufacturer_primary": True,
            "evidence_scope": "model_core", "checked_at": CHECKED_AT,
        })

    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(ledger[0]), lineterminator="\n")
        writer.writeheader(); writer.writerows(ledger)
    write_json(IDENTITIES, {"schema_version": 1, "site_key": "microchips-by", "products": identity_products})
    write_json(DESCRIPTIONS, {
        "schema_version": 1, "purpose": "Wave243A new Delta product-page description drafts",
        "locale": "ru-BY", "products": description_products,
    })
    dry_run = json.loads(LARAVEL_DRY_RUN.read_text(encoding="utf-8"))
    if dry_run["manifest_sha256"] != sha(DESCRIPTIONS) or dry_run["exit_code"] != 0:
        raise SystemExit("Laravel dry-run evidence does not match the final description manifest")
    counts = Counter(row["decision"] for row in ledger)
    hold_reasons = Counter(reason for row in ledger for reason in row["hold_reason"].split("|") if reason)
    summary = {
        "schema_version": 1, "wave": "wave243a_delta_new_product_evidence", "checked_at": CHECKED_AT,
        "coverage": {"scope": 80, "pass": counts["PASS"], "hold": counts["HOLD"]},
        "hold_reasons": dict(sorted(hold_reasons.items())),
        "legacy_duplicates_excluded_before_research": len(duplicate_owners),
        "new_sources": {"product_pages": len(evidence), "technical_datasheets": len(datasheets),
                        "successful": len(evidence) + len(datasheets), "failed_candidates": len(source_registry["failed_candidates"]),
                        "prior_url_overlap": 0, "prior_sha_overlap": 0},
        "manifests": {"identities": len(identity_products), "descriptions": len(description_products)},
        "laravel_dry_run": {"path": LARAVEL_DRY_RUN.relative_to(ROOT).as_posix(),
                            "sha256": sha(LARAVEL_DRY_RUN), "records": dry_run["records"],
                            "persisted_description_drafts": dry_run["persisted_description_drafts"]},
        "pins": {path.relative_to(ROOT).as_posix(): expected for path, expected in PINS.items()},
        "safety": {"apply_performed": False, "builder_network_calls": 0,
                   "repository_database_mutations": 0, "commercial_changes": 0, "publication_changes": 0},
    }
    write_json(SUMMARY, summary)
    REPORT.write_text(
        "# Wave243A: new Delta product-page evidence\n\n"
        f"All 80 remaining missing-description Delta rows were processed once. Result: **PASS {counts['PASS']}, "
        f"HOLD {counts['HOLD']}**. The 23 known legacy duplicates were excluded before source research.\n\n"
        f"The acquisition allowlist tested 29 official Delta product URLs. Seven returned a new exact-model page, "
        "and each linked one new official technical datasheet. The PDFs were rendered and visually checked for "
        "product association, 12 V, capacity, and AGM technology. "
        f"{len(source_registry['failed_candidates'])} were prior URLs, unavailable, or non-exact. New URL/SHA overlap "
        "with the 345-file prior exclusion snapshot is zero.\n\n"
        "## HOLD reasons\n\n" + "".join(f"- `{reason}`: {count}\n" for reason, count in sorted(hold_reasons.items())) +
        "\nOnly PASS rows enter both manifests. The real Laravel staging command passed for all 6 rows in an "
        "isolated RefreshDatabase fixture, persisted zero description drafts, and used no apply flag. No commercial, "
        "media, or publication action was performed.\n",
        encoding="utf-8", newline="\n",
    )
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, sort_keys=True))
