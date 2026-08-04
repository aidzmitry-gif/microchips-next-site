#!/usr/bin/env python3
"""Read-only DB/commercial/duplicate guard for the 106 Wave204 candidates."""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import math
import re
import subprocess
import time
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "docs/audits/generated"
PROPERTY_VALUES = GENERATED / "bitrix-b2b-catalog-property-values.csv"
EVIDENCE_FILES = (
    GENERATED / "wave204-radio-evidence.csv",
    GENERATED / "wave204-industrial-cell-evidence.csv",
    GENERATED / "wave204-remote-control-evidence.csv",
)
OUTPUT = GENERATED / "rb-wave204-commercial-duplicate-guard.csv"
SUMMARY = GENERATED / "rb-wave204-commercial-duplicate-guard-summary.json"
EXPECTED_FILE_ROWS = (41, 34, 31)
EXPECTED_ROWS = 106
SITE_KEY = "microchips-by"
DEFAULT_BATCH_SIZE = 20

FIELDS = [
    "batch", "product_external_id", "legacy_name", "evidence_partition",
    "strict_identity_token", "voltage_v", "capacity_mah", "legacy_minimum_price",
    "legacy_maximum_price", "legacy_in_stock", "current_product", "current_name",
    "current_product_status", "current_manufacturer", "current_mpn",
    "rb_site_product_count", "rb_site_product", "rb_is_published", "current_price",
    "currency", "availability", "price_evidence_count", "current_price_evidence_count",
    "evidence_calculated_price", "media_count", "published_media_count",
    "verified_published_media_count", "description_draft_count",
    "manufacturer_primary_draft_count", "applied_source_draft_count",
    "offer_schema_present", "strict_duplicate_group_key", "strict_duplicate_group_size",
    "strict_duplicate_candidate", "offer_claim_guard", "safe_to_apply",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def candidate_union() -> list[dict[str, str]]:
    union: list[dict[str, str]] = []
    seen: set[str] = set()
    for path, expected in zip(EVIDENCE_FILES, EXPECTED_FILE_ROWS, strict=True):
        source_rows = read_csv(path)
        if len(source_rows) != expected:
            raise SystemExit(f"{path.name}: expected {expected} rows, got {len(source_rows)}")
        for source in source_rows:
            external_id = source["product_external_id"]
            if external_id in seen:
                raise SystemExit(f"Wave204 evidence overlap: {external_id}")
            seen.add(external_id)
            union.append({
                "batch": source["batch"],
                "product_external_id": external_id,
                "name": source["name"],
                "model_tokens": source["model_tokens"],
                "partition": source["partition"],
            })
    if len(union) != EXPECTED_ROWS:
        raise SystemExit(f"Expected {EXPECTED_ROWS} union rows, got {len(union)}")
    return union


def numeric_token(value: str) -> str:
    match = re.search(r"(\d+(?:[.,]\s*\d+)?)", value or "", re.I)
    return match.group(1).replace(" ", "").replace(",", ".") if match else ""


def strict_identity_token(name: str, model_tokens: str) -> str:
    candidates: list[str] = []
    for parenthetical in re.findall(r"\(([^)]*)\)", name):
        candidates.extend(re.split(r"[,;\s]+", parenthetical))
    candidates.extend(model_tokens.split("|"))
    for raw in candidates:
        token = raw.strip(" (),;").upper()
        if not token:
            continue
        if re.fullmatch(r"\d+(?:[.,]\d+)?(?:MAH|AH|V)", token, re.I):
            continue
        if re.fullmatch(r"\d+S\d+P", token, re.I):
            continue
        if not re.search(r"[A-Z]", token) or not re.search(r"\d", token) or len(token) < 4:
            continue
        return re.sub(r"\s+", "", token)
    return ""


def legacy_property_map(candidate_ids: set[str]) -> dict[str, dict[str, str]]:
    legacy_ids = {external_id.removeprefix("bitrix:"): external_id for external_id in candidate_ids}
    wanted = {"MINIMUM_PRICE", "MAXIMUM_PRICE", "IN_STOCK", "VOLTAGE", "EMKOST_MAH"}
    result: dict[str, dict[str, str]] = {}
    for row in read_csv(PROPERTY_VALUES):
        external_id = legacy_ids.get(row["legacy_element_id"])
        if not external_id or row["property_code"] not in wanted:
            continue
        result.setdefault(external_id, {})[row["property_code"]] = row["source_value_display"]
    return result


def php_query(ids: list[str], site_key: str) -> str:
    escaped_ids = ",".join("'" + value.replace("'", "''") + "'" for value in ids)
    escaped_site = site_key.replace("'", "''")
    return (
        f"$siteId=app('db')->table('sites')->where('key','{escaped_site}')->value('id');"
        "if(!$siteId){throw new RuntimeException('Site not found');}"
        f"$ids=[{escaped_ids}];"
        "$q=app('db')->table('products as p')->whereIn('p.external_id',$ids)"
        "->select('p.id','p.external_id','p.name','p.status','p.manufacturer','p.mpn')"
        "->selectRaw(\"(select count(*) from site_products sp where sp.product_id=p.id and sp.site_id=?) site_product_count\",[$siteId])"
        "->selectRaw(\"(select sp.id from site_products sp where sp.product_id=p.id and sp.site_id=? limit 1) site_product_id\",[$siteId])"
        "->selectRaw(\"(select sp.is_published from site_products sp where sp.product_id=p.id and sp.site_id=? limit 1) site_is_published\",[$siteId])"
        "->selectRaw(\"(select sp.price from site_products sp where sp.product_id=p.id and sp.site_id=? limit 1) current_price\",[$siteId])"
        "->selectRaw(\"(select sp.availability from site_products sp where sp.product_id=p.id and sp.site_id=? limit 1) availability\",[$siteId])"
        "->selectRaw(\"(select pe.currency from site_product_price_evidences pe where pe.site_product_id=(select sp.id from site_products sp where sp.product_id=p.id and sp.site_id=? limit 1) and pe.is_current=true order by pe.observed_at desc limit 1) currency\",[$siteId])"
        "->selectRaw(\"(select pe.calculated_price from site_product_price_evidences pe where pe.site_product_id=(select sp.id from site_products sp where sp.product_id=p.id and sp.site_id=? limit 1) and pe.is_current=true order by pe.observed_at desc limit 1) evidence_calculated_price\",[$siteId])"
        "->selectRaw(\"(select count(*) from site_product_price_evidences pe where pe.site_product_id=(select sp.id from site_products sp where sp.product_id=p.id and sp.site_id=? limit 1)) price_evidence_count\",[$siteId])"
        "->selectRaw(\"(select count(*) from site_product_price_evidences pe where pe.site_product_id=(select sp.id from site_products sp where sp.product_id=p.id and sp.site_id=? limit 1) and pe.is_current=true) current_price_evidence_count\",[$siteId])"
        "->selectRaw(\"(select count(*) from product_media pm where pm.product_id=p.id) media_count\")"
        "->selectRaw(\"(select count(*) from product_media pm where pm.product_id=p.id and pm.is_published=true) published_media_count\")"
        "->selectRaw(\"(select count(*) from product_media pm where pm.product_id=p.id and pm.is_published=true and pm.verification_status='verified') verified_published_media_count\")"
        "->selectRaw(\"(select count(*) from product_description_drafts pd where pd.product_id=p.id) description_draft_count\")"
        "->selectRaw(\"(select count(*) from product_description_drafts pd where pd.product_id=p.id and pd.manufacturer_primary=true) manufacturer_primary_draft_count\")"
        "->selectRaw(\"(select count(*) from product_description_drafts pd where pd.product_id=p.id and pd.status in ('applied','legacy_preview_applied')) applied_source_draft_count\")"
        "->selectRaw(\"(select cast(seo.schema as text) from site_seos seo where seo.site_id=? and seo.resource_type='product' and seo.resource_id=(select sp.id from site_products sp where sp.product_id=p.id and sp.site_id=? limit 1) limit 1) schema_json\",[$siteId,$siteId]);"
        "echo json_encode($q->get(),JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES);"
    )


def query_database(candidates: list[dict[str, str]], site_key: str, batch_size: int) -> list[dict]:
    if not 1 <= batch_size <= 25:
        raise SystemExit("Tinker batch size must be between 1 and 25")
    result: list[dict] = []
    for offset in range(0, len(candidates), batch_size):
        ids = [row["product_external_id"] for row in candidates[offset:offset + batch_size]]
        encoded = base64.b64encode(php_query(ids, site_key).encode("utf-8")).decode("ascii")
        expression = f"eval(base64_decode('{encoded}'));"
        payload = ""
        for _attempt in range(3):
            process = subprocess.run(
                ["docker", "compose", "exec", "-T", "backend", "php", "artisan", "tinker", f"--execute={expression}"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
            payload = process.stdout.strip()
            if process.returncode == 0 and payload.startswith("["):
                break
            time.sleep(0.25)
        if not payload.startswith("["):
            raise SystemExit(f"Unexpected Tinker output for batch {offset}: {payload or process.stderr.strip()}")
        batch = json.loads(payload)
        returned = [row["external_id"] for row in batch]
        if len(returned) != len(set(returned)):
            raise SystemExit(f"Duplicate DB rows in batch {offset}")
        result.extend(batch)
    return result


def decimal_equal(left: object, right: object) -> bool:
    try:
        return float(str(left)) == float(str(right))
    except (TypeError, ValueError):
        return False


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", default=SITE_KEY)
    parser.add_argument("--tinker-batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    args = parser.parse_args()

    candidates = candidate_union()
    properties = legacy_property_map({row["product_external_id"] for row in candidates})
    database = {row["external_id"]: row for row in query_database(candidates, args.site, args.tinker_batch_size)}
    output_rows: list[dict[str, object]] = []
    for candidate in candidates:
        external_id = candidate["product_external_id"]
        db = database.get(external_id)
        legacy = properties.get(external_id, {})
        site_count = int(db["site_product_count"]) if db else 0
        has_site = site_count > 0
        current_price = db.get("current_price") if has_site else None
        current_evidence = int(db["current_price_evidence_count"]) if db else 0
        schema = str(db.get("schema_json") or "") if db else ""
        offer = bool(re.search(r'"offers?"|"@type"\s*:\s*"Offer"', schema, re.I))
        guards = []
        if site_count > 1:
            guards.append("BLOCK_multiple_site_products")
        if has_site and db.get("availability") == "in_stock":
            guards.append("BLOCK_in_stock_without_stock_evidence")
        if has_site and current_price is not None and current_evidence == 0:
            guards.append("BLOCK_price_without_current_evidence")
        if has_site and current_price is not None and current_evidence > 0 and not decimal_equal(current_price, db.get("evidence_calculated_price")):
            guards.append("BLOCK_price_evidence_mismatch")
        if offer and (current_evidence == 0 or current_price is None):
            guards.append("BLOCK_offer_without_current_price_evidence")
        if offer and db.get("availability") == "in_stock":
            guards.append("BLOCK_offer_in_stock_without_stock_evidence")
        output_rows.append({
            "batch": candidate["batch"],
            "product_external_id": external_id,
            "legacy_name": candidate["name"],
            "evidence_partition": candidate["partition"],
            "strict_identity_token": strict_identity_token(candidate["name"], candidate["model_tokens"]),
            "voltage_v": numeric_token(legacy.get("VOLTAGE", "")),
            "capacity_mah": numeric_token(legacy.get("EMKOST_MAH", "")),
            "legacy_minimum_price": legacy.get("MINIMUM_PRICE", ""),
            "legacy_maximum_price": legacy.get("MAXIMUM_PRICE", ""),
            "legacy_in_stock": legacy.get("IN_STOCK", ""),
            "current_product": str(db is not None).lower(),
            "current_name": db.get("name", "") if db else "",
            "current_product_status": db.get("status", "") if db else "",
            "current_manufacturer": db.get("manufacturer", "") if db else "",
            "current_mpn": db.get("mpn", "") if db else "",
            "rb_site_product_count": site_count,
            "rb_site_product": str(has_site).lower(),
            "rb_is_published": str(bool(db.get("site_is_published"))).lower() if has_site else "",
            "current_price": current_price,
            "currency": db.get("currency") if has_site else None,
            "availability": db.get("availability") if has_site else None,
            "price_evidence_count": int(db["price_evidence_count"]) if db else 0,
            "current_price_evidence_count": current_evidence,
            "evidence_calculated_price": db.get("evidence_calculated_price") if has_site else None,
            "media_count": int(db["media_count"]) if db else 0,
            "published_media_count": int(db["published_media_count"]) if db else 0,
            "verified_published_media_count": int(db["verified_published_media_count"]) if db else 0,
            "description_draft_count": int(db["description_draft_count"]) if db else 0,
            "manufacturer_primary_draft_count": int(db["manufacturer_primary_draft_count"]) if db else 0,
            "applied_source_draft_count": int(db["applied_source_draft_count"]) if db else 0,
            "offer_schema_present": str(offer).lower(),
            "strict_duplicate_group_key": "",
            "strict_duplicate_group_size": 0,
            "strict_duplicate_candidate": "false",
            "offer_claim_guard": "|".join(guards) if guards else "no_unsupported_commercial_claim",
            "safe_to_apply": "false",
        })

    grouped = Counter(
        f"{row['strict_identity_token']}|{row['voltage_v']}|{row['capacity_mah']}"
        for row in output_rows
        if row["strict_identity_token"] and row["voltage_v"] and row["capacity_mah"]
    )
    duplicate_groups = {key: size for key, size in grouped.items() if size > 1}
    for row in output_rows:
        key = f"{row['strict_identity_token']}|{row['voltage_v']}|{row['capacity_mah']}"
        if key in duplicate_groups:
            row["strict_duplicate_group_key"] = key
            row["strict_duplicate_group_size"] = duplicate_groups[key]
            row["strict_duplicate_candidate"] = "true"

    with OUTPUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(output_rows)

    blocked = [row for row in output_rows if row["offer_claim_guard"] != "no_unsupported_commercial_claim"]
    missing = [row for row in output_rows if row["current_product"] == "false"]
    summary = {
        "schema_version": 1,
        "wave": "wave204",
        "site_key": args.site,
        "candidate_records": len(output_rows),
        "evidence_file_rows": {path.name: expected for path, expected in zip(EVIDENCE_FILES, EXPECTED_FILE_ROWS, strict=True)},
        "current_db_records": len(output_rows) - len(missing),
        "current_db_missing_records": len(missing),
        "current_db_missing_external_ids": [row["product_external_id"] for row in missing],
        "rb_site_product_records": sum(row["rb_site_product"] == "true" for row in output_rows),
        "current_price_records": sum(row["current_price"] not in (None, "") for row in output_rows),
        "currency_records": sum(bool(row["currency"]) for row in output_rows),
        "in_stock_records": sum(row["availability"] == "in_stock" for row in output_rows),
        "offer_schema_records": sum(row["offer_schema_present"] == "true" for row in output_rows),
        "unsupported_commercial_claims": len(blocked),
        "unsupported_commercial_external_ids": [row["product_external_id"] for row in blocked],
        "legacy_price_claim_records": sum(bool(row["legacy_minimum_price"] or row["legacy_maximum_price"]) for row in output_rows),
        "legacy_in_stock_claim_records": sum(str(row["legacy_in_stock"]).upper() in {"Y", "YES", "TRUE", "1"} for row in output_rows),
        "price_evidence_records": sum(int(row["price_evidence_count"]) for row in output_rows),
        "current_price_evidence_records": sum(int(row["current_price_evidence_count"]) for row in output_rows),
        "media_records": sum(int(row["media_count"]) for row in output_rows),
        "published_media_records": sum(int(row["published_media_count"]) for row in output_rows),
        "verified_published_media_records": sum(int(row["verified_published_media_count"]) for row in output_rows),
        "description_draft_records": sum(int(row["description_draft_count"]) for row in output_rows),
        "manufacturer_primary_draft_records": sum(int(row["manufacturer_primary_draft_count"]) for row in output_rows),
        "applied_source_draft_records": sum(int(row["applied_source_draft_count"]) for row in output_rows),
        "strict_duplicate_groups": len(duplicate_groups),
        "strict_duplicate_candidates": sum(row["strict_duplicate_candidate"] == "true" for row in output_rows),
        "strict_duplicate_group_keys": sorted(duplicate_groups),
        "tinker_batch_size": args.tinker_batch_size,
        "tinker_batches": math.ceil(len(output_rows) / args.tinker_batch_size),
        "evidence_union_records": len(candidates),
        "evidence_input_sha256": {path.name: sha256(path) for path in EVIDENCE_FILES},
        "property_values_sha256": sha256(PROPERTY_VALUES),
        "output_sha256": sha256(OUTPUT),
        "safe_to_apply": False,
        "automatic_database_mutations": 0,
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
