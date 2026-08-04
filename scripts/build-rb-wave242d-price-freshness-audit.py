#!/usr/bin/env python3
"""Reconstruct and audit all current RB price evidence without database access."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
IMPORTS = ROOT / "docs/imports"
GENERATED = ROOT / "docs/audits/generated"
WAVE240 = IMPORTS / "rb-price-evidence-wave240-2026-07-29.csv"
WAVE91 = IMPORTS / "rb-price-evidence-wave-91.csv"
RECEIPT = GENERATED / "wave240-commercial-facets-media-receipt.json"
COMMERCIAL_BASELINE = GENERATED / "rb-commercial-data-wave215c-summary.json"
SQL_AUDIT = ROOT / "scripts/audit-rb-price-truth.sql"
LEDGER = GENERATED / "rb-wave242d-price-freshness-ledger.csv"
SUMMARY = GENERATED / "rb-wave242d-price-freshness.summary.json"
REPORT = ROOT / "docs/audits/2026-07-29-rb-wave242d-price-freshness.md"

AS_OF_DATE = date(2026, 7, 29)
INPUT_PINS = {
    WAVE240: "eb740bf443bfe31b251de859a6a69ad2bb8d9237500ce663ca09ee354e850eea",
    WAVE91: "016b0d58f3ebda3f71ef03e80ba91c0a57331cd774eacb7c0a542941cdc39a2c",
    RECEIPT: "39911b3d07bcb33f298d95f3ff0d1bee90c014e9e9219d3d7753031bda2f050e",
    COMMERCIAL_BASELINE: "c84a148be0e267b85f5cd22a39af3e23652fbe3539bd20c1c714efff5eeff1aa",
    SQL_AUDIT: "3c294466b9d4f9ba0437ad1230e37213ad0ca4dc42d3e79bcb329edffdb82c36",
}

FIELDS = [
    "product_external_id",
    "source",
    "source_price",
    "multiplier",
    "calculated_price_byn",
    "currency",
    "observed_at",
    "age_days",
    "age_bucket",
    "source_reference",
    "source_external_id",
    "price_type",
    "reconstruction_input",
    "visible_price_policy",
    "availability_policy",
    "offer_eligible",
    "offer_policy",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify(path: Path, expected: str) -> None:
    actual = sha256(path)
    if actual != expected:
        raise SystemExit(f"SHA drift for {path.relative_to(ROOT)}: {actual} != {expected}")


def read_semicolon(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream, delimiter=";"))


def age_bucket(days: int) -> str:
    if days <= 7:
        return "0_7_fresh"
    if days <= 30:
        return "8_30_aging"
    if days <= 60:
        return "31_60_stale_reconfirm"
    if days <= 90:
        return "61_90_expired_hold_numeric"
    return "91_plus_obsolete_hold_numeric"


def decimal(value: str, label: str) -> Decimal:
    try:
        result = Decimal(value)
    except InvalidOperation as error:
        raise SystemExit(f"Invalid decimal {label}: {value}") from error
    if result <= 0:
        raise SystemExit(f"Non-positive decimal {label}: {value}")
    return result


def money(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.01')):.2f}"


def main() -> None:
    for path, expected in INPUT_PINS.items():
        verify(path, expected)

    receipt = json.loads(RECEIPT.read_text(encoding="utf-8-sig"))
    baseline = json.loads(COMMERCIAL_BASELINE.read_text(encoding="utf-8-sig"))
    integrity_text = receipt["verification"]["price_integrity"]
    if integrity_text != "0 missing evidence, 0 mismatches, 0 duplicate current evidence":
        raise SystemExit(f"Unexpected Wave240 integrity receipt: {integrity_text}")
    if baseline["current"]["site_products"]["availability"] != {"on_request": 24298}:
        raise SystemExit("Availability baseline drifted from all-on_request")
    if receipt["result"]["media_commercial_changes"] != 0 or receipt["result"]["media_publication_changes"] != 0:
        raise SystemExit("Wave240 receipt unexpectedly changed commercial/publication state through media")

    inputs = [(WAVE240, "wave240_applied_manifest"), (WAVE91, "wave91_separate_exact_links")]
    source_rows: list[tuple[dict[str, str], str]] = []
    for path, label in inputs:
        source_rows.extend((row, label) for row in read_semicolon(path))
    if len(source_rows) != 1067:
        raise SystemExit(f"Current evidence reconstruction drift: expected 1067, got {len(source_rows)}")

    ids = [row["product_external_id"] for row, _ in source_rows]
    references = [row["source_reference"] for row, _ in source_rows]
    duplicate_ids = len(ids) - len(set(ids))
    duplicate_references = len(references) - len(set(references))
    if duplicate_ids or duplicate_references:
        raise SystemExit(
            f"Evidence union duplicates: product_external_id={duplicate_ids}, source_reference={duplicate_references}"
        )

    ledger: list[dict[str, object]] = []
    for row, input_label in source_rows:
        if row["source"] != "legacy_site" or row["currency"] != "BYN" or not row["price_type"].strip():
            raise SystemExit(f"Ineligible commercial row: {row['product_external_id']}")
        source_price = decimal(row["source_price"], f"source_price:{row['product_external_id']}")
        multiplier = decimal(row["multiplier"], f"multiplier:{row['product_external_id']}")
        observed = datetime.fromisoformat(row["observed_at"])
        if observed.tzinfo is None:
            raise SystemExit(f"Naive observed_at: {row['product_external_id']}")
        age_days = (AS_OF_DATE - observed.date()).days
        if age_days < 0:
            raise SystemExit(f"Future observed_at: {row['product_external_id']}")
        bucket = age_bucket(age_days)
        if bucket == "31_60_stale_reconfirm":
            visible_policy = "VISIBLE_PRICE_EVIDENCED_BUT_RECONFIRM_BEFORE_CALLING_CURRENT"
        elif bucket in {"61_90_expired_hold_numeric", "91_plus_obsolete_hold_numeric"}:
            visible_policy = "RECOMMEND_SUPPRESS_NUMERIC_UNTIL_REFRESHED"
        else:
            visible_policy = "VISIBLE_PRICE_ALLOWED_WHILE_CURRENT_EVIDENCE_MATCHES"
        ledger.append(
            {
                "product_external_id": row["product_external_id"],
                "source": row["source"],
                "source_price": row["source_price"],
                "multiplier": row["multiplier"],
                "calculated_price_byn": money(source_price * multiplier),
                "currency": row["currency"],
                "observed_at": row["observed_at"],
                "age_days": age_days,
                "age_bucket": bucket,
                "source_reference": row["source_reference"],
                "source_external_id": row["source_external_id"],
                "price_type": row["price_type"],
                "reconstruction_input": input_label,
                "visible_price_policy": visible_policy,
                "availability_policy": "ON_REQUEST_INDEPENDENT_OF_PRICE_DO_NOT_INFER_STOCK",
                "offer_eligible": "false",
                "offer_policy": "INELIGIBLE_ON_REQUEST_AND_NO_INDEPENDENT_IN_STOCK_EVIDENCE",
            }
        )

    ledger.sort(key=lambda row: str(row["product_external_id"]))
    with LEDGER.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(ledger)

    sources = Counter(str(row["source"]) for row in ledger)
    price_types = Counter(str(row["price_type"]) for row in ledger)
    age_buckets = Counter(str(row["age_bucket"]) for row in ledger)
    inputs_count = Counter(str(row["reconstruction_input"]) for row in ledger)
    age_values = [int(row["age_days"]) for row in ledger]
    result = receipt["result"]
    if result["current_price_evidence"] != len(ledger) or result["current_numeric_prices"] != len(ledger):
        raise SystemExit("Wave240 current counters do not match reconstructed evidence union")

    summary = {
        "schema_version": 1,
        "wave": "wave242d-price-freshness",
        "checked_at": AS_OF_DATE.isoformat(),
        "mode": "read_only_local_evidence_reconstruction",
        "scope": {
            "current_evidence_rows": len(ledger),
            "reconstruction_inputs": dict(sorted(inputs_count.items())),
            "receipt_current_numeric_prices": result["current_numeric_prices"],
            "receipt_published_numeric_prices": result["published_numeric_prices"],
        },
        "freshness": {
            "oldest_observed_at": min(row["observed_at"] for row in ledger),
            "newest_observed_at": max(row["observed_at"] for row in ledger),
            "minimum_age_days": min(age_values),
            "maximum_age_days": max(age_values),
            "age_bucket_counts": dict(sorted(age_buckets.items())),
            "recommended_thresholds": {
                "0_7_fresh": "visible numeric price may be treated as fresh when current evidence matches",
                "8_30_aging": "visible numeric price may remain, with refresh monitoring",
                "31_60_stale_reconfirm": "do not call current without reconfirmation; keep availability on_request",
                "61_90_expired_hold_numeric": "recommend suppressing numeric price until refreshed",
                "91_plus_obsolete_hold_numeric": "numeric price and Offer remain blocked until refreshed",
            },
        },
        "distribution": {
            "source": dict(sorted(sources.items())),
            "price_type": dict(sorted(price_types.items())),
            "currency": {"BYN": len(ledger)},
        },
        "integrity": {
            "reconstructed_duplicate_product_external_ids": duplicate_ids,
            "reconstructed_duplicate_source_references": duplicate_references,
            "receipt_visible_price_without_current_evidence": 0,
            "receipt_current_evidence_visible_price_mismatch": 0,
            "receipt_duplicate_current_evidence_products": 0,
        },
        "policy_recommendation": {
            "visible_price": "A numeric price is a commercial fact only when current evidence matches value and BYN currency. At 31-60 days, reconfirm before describing it as current; do not infer stock.",
            "on_request": "on_request is the independent availability state for all reconstructed rows and remains valid regardless of whether a numeric price is displayed.",
            "offer": "Offer is ineligible for every reconstructed row: on_request is not InStock, and no independent current stock evidence exists. A price alone must never create Offer eligibility.",
        },
        "input_pins": {path.relative_to(ROOT).as_posix(): expected for path, expected in INPUT_PINS.items()},
        "outputs": {
            "ledger": {"path": LEDGER.relative_to(ROOT).as_posix(), "rows": len(ledger), "sha256": sha256(LEDGER)}
        },
        "safety": {
            "network_requests": 0,
            "database_queries": 0,
            "database_mutations": 0,
            "price_changes": 0,
            "availability_changes": 0,
            "offer_schema_changes": 0,
            "publication_changes": 0,
        },
        "limitation": "Current counters are the SHA-pinned Wave240 post-apply receipt; this bounded no-network follow-up did not rerun the live database SQL.",
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report = f"""# Wave242-D RB price-evidence freshness audit

This read-only, no-network audit reconstructs all **1,067** current RB price-evidence rows from the SHA-pinned Wave240 applied manifest (1,065 rows) plus the two separately reviewed exact links retained in Wave91. The union exactly matches the Wave240 post-apply receipt.

## Freshness and consistency

- Source: **1,067 `legacy_site`**, **0 `one_c_x2`**.
- Currency: **1,067 BYN**.
- Observed at: **2026-06-23T00:00:00+03:00** for every row.
- Age on 2026-07-29: **36 days**; all **1,067** fall in `31_60_stale_reconfirm`.
- Price types: **1,010** direct Bitrix legacy prices and **57** approved exact-link legacy prices.
- Reconstructed duplicate product IDs: **0**; duplicate source references: **0**.
- Wave240 current-state counters: price without evidence **0**, evidence/value mismatch **0**, duplicate current evidence **0**.

## Recommended policy (not applied)

1. **Visible numeric price**: keep distinct from availability. Evidence and BYN value must match. At 31-60 days, reconfirm before calling the number current; after 60 days, recommend suppressing the numeric value until refreshed.
2. **`on_request`**: remains the availability truth for these rows and must not be upgraded because a price exists.
3. **Offer eligibility**: **0/1,067**. `on_request` is not `InStock`; an Offer requires independently confirmed current stock plus a matching, fresh price/currency evidence record.

The age thresholds are a Wave242D recommendation, not an existing mutation or release-rule change. The current counters come from the SHA-pinned Wave240 post-apply receipt; no live database query was rerun in this bounded no-network follow-up.

## Artifacts

- `{LEDGER.relative_to(ROOT).as_posix()}` — full 1,067-row ledger.
- `{SUMMARY.relative_to(ROOT).as_posix()}` — deterministic counters, policy and hashes.
- `{SQL_AUDIT.relative_to(ROOT).as_posix()}` — reused canonical read-only SQL, unchanged.

No database, price, availability, Offer schema, publication or application change was made.
"""
    REPORT.write_text(report, encoding="utf-8")
    print(json.dumps({"rows": len(ledger), "age_buckets": age_buckets, "integrity": summary["integrity"]}, default=dict, sort_keys=True))


if __name__ == "__main__":
    main()
