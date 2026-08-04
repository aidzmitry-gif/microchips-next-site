#!/usr/bin/env python3
"""Build the Wave238 Panasonic active-1C identity evidence artifacts.

The builder is deliberately offline and deterministic.  It accepts exactly
three rows from the Wave236 enrichment queue and promotes their MPN only when
the expected model occurs as a bounded token on the pinned page of Panasonic's
official coin-cell catalogue.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import unicodedata
from pathlib import Path

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "docs/audits/generated/rb-enrichment-queue-wave236.csv"
WAVE200_EVIDENCE = ROOT / "docs/audits/generated/rb-panasonic-wave200-official-evidence.csv"
PDF = ROOT / "docs/audits/sources/panasonic-wave200/Introduction_coin_primary_lithium_EN.pdf"
MANIFEST = ROOT / "docs/imports/rb-verified-oem-identities-wave238-panasonic-active-1c-2026-07-29.json"
LEDGER = ROOT / "docs/audits/generated/rb-wave238-panasonic-active-one-c-identity-ledger.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-wave238-panasonic-active-one-c-identity.summary.json"

EXPECTED_PDF_SHA256 = "1ce9b9fa72a6263f34cf2390726ddb009759c04303c1d3f39bc981473af5f343"
CHECKED_AT = "2026-07-29"
TARGET_KIND = "active_1c"
TARGETS = {
    "КА-00003142": {"mpn": "BR2032", "page": 4},
    "ФР-00000639": {"mpn": "CR2012", "page": 3},
    "ФР-00001236": {"mpn": "CR2450", "page": 3},
}
LEDGER_FIELDS = [
    "external_id", "current_name", "target_kind", "manufacturer", "mpn",
    "normalized_mpn", "decision", "source_url", "source_kind",
    "source_publisher", "source_snapshot_path", "source_snapshot_sha256",
    "source_page", "source_excerpt", "safe_to_apply",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def normalize(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", unicodedata.normalize("NFKC", value).upper())


def bounded_model_pattern(model: str) -> re.Pattern[str]:
    return re.compile(rf"(?<![A-Z0-9]){re.escape(model)}(?![A-Z0-9])", re.I)


def exact_excerpt(page_text: str, model: str) -> str:
    pattern = bounded_model_pattern(model)
    matches = [" ".join(line.split()) for line in page_text.splitlines() if pattern.search(line)]
    if len(matches) != 1:
        raise SystemExit(f"Expected one bounded {model} row on pinned page, found {len(matches)}")
    return matches[0]


def source_metadata(evidence: list[dict[str, str]], model: str, page: int) -> dict[str, str]:
    rows = [
        row for row in evidence
        if row.get("model_core") == model
        and row.get("source_page") == str(page)
        and row.get("manufacturer_primary") == "true"
    ]
    if not rows:
        raise SystemExit(f"Wave200 has no official primary metadata for {model} on page {page}")
    fields = ("source_url", "source_kind", "source_publisher", "source_snapshot_sha256")
    variants = {tuple(row.get(field, "") for field in fields) for row in rows}
    if len(variants) != 1:
        raise SystemExit(f"Wave200 source metadata is ambiguous for {model}")
    values = dict(zip(fields, next(iter(variants)), strict=True))
    if values["source_snapshot_sha256"] != EXPECTED_PDF_SHA256:
        raise SystemExit(f"Wave200 source hash drift for {model}")
    if values["source_kind"] != "official_manufacturer_catalogue":
        raise SystemExit(f"Wave200 source kind is not manufacturer-primary for {model}")
    if values["source_publisher"] != "Panasonic Energy Co., Ltd.":
        raise SystemExit(f"Wave200 publisher drift for {model}")
    if not values["source_url"].startswith("https://energy.panasonic.com/"):
        raise SystemExit(f"Wave200 source URL is not official Panasonic evidence for {model}")
    return values


def main() -> None:
    for required in (QUEUE, WAVE200_EVIDENCE, PDF):
        if not required.is_file():
            raise SystemExit(f"Required input is missing: {required.relative_to(ROOT).as_posix()}")
    pdf_hash = sha256(PDF)
    if pdf_hash != EXPECTED_PDF_SHA256:
        raise SystemExit(f"Pinned Panasonic PDF hash mismatch: {pdf_hash}")

    queue = {row["product_external_id"]: row for row in read_csv(QUEUE)}
    if len(queue) != len(read_csv(QUEUE)):
        raise SystemExit("Wave236 queue has duplicate product_external_id values")
    evidence = read_csv(WAVE200_EVIDENCE)
    reader = PdfReader(str(PDF))

    products: list[dict[str, object]] = []
    ledger: list[dict[str, str]] = []
    for external_id, expected in TARGETS.items():
        row = queue.get(external_id)
        if row is None:
            raise SystemExit(f"Wave238 target is absent from Wave236 queue: {external_id}")
        if row["manufacturer"] != "Panasonic" or row["mpn"].strip():
            raise SystemExit(f"Wave238 target manufacturer/blank-MPN contract drift: {external_id}")
        if row["is_published"] != "true" or not external_id.startswith(("КА-", "ФР-")):
            raise SystemExit(f"Wave238 target is not a published active 1C product: {external_id}")
        model = str(expected["mpn"])
        page = int(expected["page"])
        if normalize(model) not in normalize(row["name"]):
            raise SystemExit(f"Wave238 target title lacks exact model candidate: {external_id}")
        if page < 1 or page > len(reader.pages):
            raise SystemExit(f"Pinned source page is out of range for {model}: {page}")
        page_text = reader.pages[page - 1].extract_text() or ""
        excerpt = exact_excerpt(page_text, model)
        source = source_metadata(evidence, model, page)
        snapshot_path = "../audits/sources/panasonic-wave200/Introduction_coin_primary_lithium_EN.pdf"

        products.append({
            "external_id": external_id,
            "current_name": row["name"],
            "manufacturer": "Panasonic",
            "mpn": model,
            "source_url": source["source_url"],
            "source_kind": source["source_kind"],
            "source_publisher": source["source_publisher"],
            "checked_at": CHECKED_AT,
            "product_type": "coin-type primary lithium battery",
            "source_snapshot_path": snapshot_path,
            "source_snapshot_sha256": pdf_hash,
        })
        ledger.append({
            "external_id": external_id,
            "current_name": row["name"],
            "target_kind": TARGET_KIND,
            "manufacturer": "Panasonic",
            "mpn": model,
            "normalized_mpn": normalize(model),
            "decision": "PASS",
            "source_url": source["source_url"],
            "source_kind": source["source_kind"],
            "source_publisher": source["source_publisher"],
            "source_snapshot_path": PDF.relative_to(ROOT).as_posix(),
            "source_snapshot_sha256": pdf_hash,
            "source_page": str(page),
            "source_excerpt": excerpt,
            "safe_to_apply": "true",
        })

    if len(products) != 3 or len({item["external_id"] for item in products}) != 3:
        raise SystemExit("Wave238 must contain exactly three unique targets")
    if len({normalize(str(item["mpn"])) for item in products}) != 3:
        raise SystemExit("Wave238 normalized MPNs must be unique")

    manifest = {
        "schema_version": 1,
        "site_key": "microchips-by",
        "target_kind": TARGET_KIND,
        "checked_at": CHECKED_AT,
        "products": products,
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with LEDGER.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=LEDGER_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(ledger)

    summary = {
        "schema_version": 1,
        "batch": "wave238_panasonic_active_one_c_identities",
        "target_kind": TARGET_KIND,
        "checked_at": CHECKED_AT,
        "inputs": {
            "wave236_queue": {"path": QUEUE.relative_to(ROOT).as_posix(), "sha256": sha256(QUEUE)},
            "wave200_evidence": {"path": WAVE200_EVIDENCE.relative_to(ROOT).as_posix(), "sha256": sha256(WAVE200_EVIDENCE)},
            "panasonic_pdf": {"path": PDF.relative_to(ROOT).as_posix(), "sha256": pdf_hash},
        },
        "records": 3,
        "pass_records": 3,
        "hold_records": 0,
        "external_ids": list(TARGETS),
        "mpns": [str(item["mpn"]) for item in products],
        "manifest": {"path": MANIFEST.relative_to(ROOT).as_posix(), "sha256": sha256(MANIFEST)},
        "ledger": {"path": LEDGER.relative_to(ROOT).as_posix(), "sha256": sha256(LEDGER)},
        "policy": {"database_queries": 0, "network_requests": 0, "catalogue_mutations": 0},
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"records": 3, "manifest_sha256": sha256(MANIFEST), "ledger_sha256": sha256(LEDGER), "summary_sha256": sha256(SUMMARY)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
