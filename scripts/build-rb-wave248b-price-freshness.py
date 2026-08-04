#!/usr/bin/env python3
"""Fail-closed live freshness audit for visible RB price evidence.

The script reads only published RB cards with a numeric price and their current
price evidence.  It deliberately does not import prices, infer availability,
or turn on Offer schema.  ``one_c_x2`` is accepted only when its persisted
source is exactly ``one_c_x2`` and its multiplier is exactly two; a user
instruction alone never changes an existing legacy-site price.
"""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import subprocess
from collections import Counter
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "docs" / "audits" / "generated"
LEDGER = GENERATED / "rb-wave248b-price-freshness-ledger-2026-07-30.csv"
SUMMARY = GENERATED / "rb-wave248b-price-freshness-2026-07-30.json"
AS_OF = date(2026, 7, 30)
FRESH_DAYS = 30

FIELDS = [
    "product_external_id", "site_product_id", "classification", "reason",
    "site_price_byn", "source", "source_price", "multiplier",
    "calculated_price_byn", "evidence_currency", "site_currency", "observed_at",
    "age_days", "price_value_match", "multiplier_policy_match",
    "source_reference_policy_match", "availability", "offer_eligible", "safe_action",
    "source_reference", "source_external_id", "price_type",
]

POLICY_MULTIPLIER = {"legacy_site": Decimal("1"), "one_c_x2": Decimal("2")}


def query_live_snapshot() -> dict[str, Any]:
    """Request only the fields needed for this audit from the running service."""
    php = r'''
$site=app('db')->table('sites')->where('key','microchips-by')->first(['id','currency_code']);
if (!$site) { throw new RuntimeException('microchips-by site missing'); }
$db=app('db');
$rows=$db->table('site_products as sp')
 ->join('products as p','p.id','=','sp.product_id')
 ->leftJoin('site_product_price_evidences as e',function($join) use($site){$join->on('e.site_product_id','=','sp.id')->where('e.site_id',$site->id)->where('e.is_current',true);})
 ->where('sp.site_id',$site->id)->where('sp.is_published',true)->where('sp.price','>',0)
 ->orderBy('p.external_id')
 ->get(['p.external_id','sp.id as site_product_id','sp.price as site_price','sp.availability','e.id as evidence_id','e.source','e.source_price','e.multiplier','e.calculated_price','e.currency as evidence_currency','e.price_type','e.source_reference','e.source_external_id','e.observed_at','e.evidence_key','e.is_current']);
$allCurrent=$db->table('site_product_price_evidences')->where('site_id',$site->id)->where('is_current',true)->count();
echo json_encode(['site_key'=>'microchips-by','site_currency'=>$site->currency_code,'all_current_evidence_rows'=>$allCurrent,'rows'=>$rows],JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES);
'''
    encoded = base64.b64encode(php.encode("utf-8")).decode("ascii")
    result = subprocess.run(
        ["docker", "compose", "exec", "-T", "backend", "php", "artisan", "tinker", f"--execute=eval(base64_decode('{encoded}')); "],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )
    if result.returncode != 0 or not result.stdout.strip().startswith("{"):
        raise SystemExit(f"Live read-only price query failed: {result.stderr.strip() or result.stdout.strip()}")
    return json.loads(result.stdout)


def money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def decimal(value: Any) -> Decimal | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return Decimal(str(value).strip())
    except InvalidOperation:
        return None


def observed_date(value: Any) -> date | None:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def classify(row: dict[str, Any], site_currency: str, as_of: date = AS_OF) -> dict[str, str]:
    """Classify one visible price. Invalid always wins over freshness."""
    reasons: list[str] = []
    site_price = decimal(row.get("site_price"))
    source_price = decimal(row.get("source_price"))
    multiplier = decimal(row.get("multiplier"))
    calculated = decimal(row.get("calculated_price"))
    source = str(row.get("source") or "")
    observed = observed_date(row.get("observed_at"))
    expected_multiplier = POLICY_MULTIPLIER.get(source)

    if row.get("evidence_id") is None:
        reasons.append("missing_current_evidence")
    if site_price is None or site_price <= 0:
        reasons.append("invalid_visible_price")
    if source_price is None or source_price <= 0:
        reasons.append("invalid_source_price")
    if multiplier is None or multiplier <= 0:
        reasons.append("invalid_multiplier")
    if calculated is None or calculated <= 0:
        reasons.append("invalid_calculated_price")
    if str(row.get("evidence_currency") or "") != site_currency:
        reasons.append("currency_mismatch")
    if expected_multiplier is None:
        reasons.append("unsupported_price_source")
    elif multiplier != expected_multiplier:
        reasons.append("source_multiplier_policy_mismatch")
    if source_price is not None and multiplier is not None and calculated is not None and money(source_price * multiplier) != money(calculated):
        reasons.append("evidence_calculation_mismatch")
    if site_price is not None and calculated is not None and money(site_price) != money(calculated):
        reasons.append("visible_price_evidence_mismatch")
    if not str(row.get("source_reference") or "").strip():
        reasons.append("missing_source_reference")
    if not str(row.get("price_type") or "").strip():
        reasons.append("missing_price_type")
    if observed is None:
        reasons.append("invalid_observed_at")

    age_days = (as_of - observed).days if observed else None
    if age_days is not None and age_days < 0:
        reasons.append("future_observed_at")

    if reasons:
        classification, action = "invalid_mismatch", "SUPPRESS_NUMERIC_PRICE_AND_REPAIR_EVIDENCE"
    elif age_days is not None and age_days <= FRESH_DAYS:
        classification, action = "showable_fresh", "MAY_SHOW_NUMERIC_PRICE_WITH_OBSERVED_DATE"
    else:
        classification, action = "stale_hold", "HOLD_NUMERIC_PRICE_UNTIL_FRESH_SOURCE_EVIDENCE"
        reasons.append(f"observed_price_older_than_{FRESH_DAYS}_days")

    return {
        "product_external_id": str(row.get("external_id") or ""),
        "site_product_id": str(row.get("site_product_id") or ""),
        "classification": classification,
        "reason": ";".join(reasons) if reasons else "current_evidence_within_freshness_window",
        "site_price_byn": f"{money(site_price):.2f}" if site_price is not None else "",
        "source": source,
        "source_price": f"{source_price:.4f}" if source_price is not None else "",
        "multiplier": f"{multiplier:.4f}" if multiplier is not None else "",
        "calculated_price_byn": f"{money(calculated):.2f}" if calculated is not None else "",
        "evidence_currency": str(row.get("evidence_currency") or ""),
        "site_currency": site_currency,
        "observed_at": str(row.get("observed_at") or ""),
        "age_days": str(age_days) if age_days is not None else "",
        "price_value_match": str(bool(site_price is not None and calculated is not None and money(site_price) == money(calculated))).lower(),
        "multiplier_policy_match": str(expected_multiplier is not None and multiplier == expected_multiplier).lower(),
        "source_reference_policy_match": str(bool(str(row.get("source_reference") or "").strip())).lower(),
        "availability": str(row.get("availability") or ""),
        "offer_eligible": "false",
        "safe_action": action,
        "source_reference": str(row.get("source_reference") or ""),
        "source_external_id": str(row.get("source_external_id") or ""),
        "price_type": str(row.get("price_type") or ""),
    }


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(snapshot: dict[str, Any], output_dir: Path = GENERATED) -> tuple[list[dict[str, str]], dict[str, Any]]:
    if snapshot.get("site_key") != "microchips-by" or snapshot.get("site_currency") != "BYN":
        raise SystemExit("Expected microchips-by with BYN currency.")
    rows = snapshot.get("rows")
    if not isinstance(rows, list):
        raise SystemExit("Snapshot rows must be a list.")
    ledger = sorted((classify(row, "BYN") for row in rows), key=lambda row: row["product_external_id"])
    ids = [row["product_external_id"] for row in ledger]
    if len(ids) != len(set(ids)):
        raise SystemExit("Visible price snapshot has duplicate product external IDs.")
    counts = Counter(row["classification"] for row in ledger)
    sources = Counter(row["source"] for row in ledger)
    age_days = Counter(row["age_days"] for row in ledger)
    summary = {
        "schema_version": 1,
        "wave": "wave248b-price-freshness",
        "checked_at": AS_OF.isoformat(),
        "mode": "live_database_read_only",
        "scope": {
            "published_visible_numeric_prices": len(ledger),
            "all_current_evidence_rows": snapshot.get("all_current_evidence_rows"),
            "excluded_non_visible_current_evidence_rows": int(snapshot.get("all_current_evidence_rows", 0)) - len(ledger),
        },
        "freshness_policy": {
            "showable_fresh_max_age_days": FRESH_DAYS,
            "stale_hold": f"more than {FRESH_DAYS} days since observed_at",
            "invalid_mismatch": "any provenance, source-policy, currency, arithmetic or visible-value mismatch",
        },
        "classifications": dict(sorted(counts.items())),
        "sources": dict(sorted(sources.items())),
        "observed_age_days": dict(sorted(age_days.items(), key=lambda item: int(item[0] or "-1"))),
        "x2_rule": {
            "permitted_only_for_persisted_source": "one_c_x2",
            "one_c_x2_required_multiplier": "2.0000",
            "legacy_site_required_multiplier": "1.0000",
            "one_c_x2_rows_in_visible_scope": sources.get("one_c_x2", 0),
            "conclusion": "No x2 has been assumed: the classification checks persisted source and multiplier per row.",
        },
        "commercial_safety": {
            "availability_inferred_from_price": 0,
            "offer_schema_enabled_by_audit": 0,
            "database_mutations": 0,
            "network_requests": 0,
        },
    }
    return ledger, summary


def write_outputs(ledger: list[dict[str, str]], summary: dict[str, Any], output_dir: Path = GENERATED) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = output_dir / LEDGER.name
    summary_path = output_dir / SUMMARY.name
    with ledger_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(ledger)
    summary["outputs"] = {
        "ledger": {"path": ledger_path.relative_to(ROOT).as_posix(), "rows": len(ledger), "sha256": sha256(ledger_path)},
        "summary": {"path": summary_path.relative_to(ROOT).as_posix()},
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, help="Use a JSON snapshot instead of the live read-only Docker query.")
    parser.add_argument("--output-dir", type=Path, default=GENERATED)
    args = parser.parse_args()
    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8")) if args.snapshot else query_live_snapshot()
    ledger, summary = build(snapshot, args.output_dir)
    write_outputs(ledger, summary, args.output_dir)
    print(json.dumps({"rows": len(ledger), "classifications": summary["classifications"], "database_mutations": 0}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
