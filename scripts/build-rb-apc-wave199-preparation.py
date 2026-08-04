#!/usr/bin/env python3
"""Build a fail-closed APC battery-pack research queue from a pinned readiness CSV.

This is a research-only boundary.  It never reads or writes the application
database and every output row remains ``safe_to_apply=false``.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path


REQUIRED = {
    "product_external_id", "name", "category_external_id", "identity_ready",
    "has_applied_description", "description_source_tier",
    "description_manufacturer_primary",
}
BATTERY_CATEGORY = "seo:batteries-ups"

# These are APC's product-family tokens, not partial substring matches.
CARTRIDGE_TOKEN = re.compile(r"(?<![A-Z0-9-])(?:APCRBC|RBC)\d+(?![A-Z0-9-])")
SYBT_TOKEN = re.compile(r"(?<![A-Z0-9-])SYBT(?:5|U[12]-PLP)(?![A-Z0-9-])")
# Exact APC external battery-pack SKUs present in the pinned B2B snapshot.
PACK_TOKEN = re.compile(
    r"(?<![A-Z0-9-])(?:"
    r"BR24BPG|SMX120BP|SMX120RMBP2U|SMX48RMBP2U|"
    r"SRT192RMBP2?|SRT48(?:BP|RMBP)|SRT72(?:BP|RMBP)|SRT96(?:BP|RMBP)|"
    r"SRV72RLBP-9A|SU24R2XLBP|SUA24XLBP|SUA48RMXLBP3U|SUA48XLBP|"
    r"SUM48RMXLBP2U|SURT192RMXLBP2|SURT192XLBP|SURT48RMXLBP|SURT48XLBP|"
    r"SYBTU[12]-PLP|UXABP48|XBP48RM1U-LI"
    r")(?![A-Z0-9-])"
)


def strict_bool(value: str, field: str) -> bool:
    normalized = (value or "").strip().casefold()
    if normalized not in {"true", "false"}:
        raise ValueError(f"{field} must be explicitly true or false")
    return normalized == "true"


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = REQUIRED - set(reader.fieldnames or [])
        if missing:
            raise ValueError("readiness CSV missing required columns: " + ", ".join(sorted(missing)))
        rows = list(reader)
    ids = [row["product_external_id"].strip() for row in rows]
    if not all(ids) or len(ids) != len(set(ids)):
        raise ValueError("readiness CSV must have unique nonblank product_external_id values")
    return rows


def apc_model_token(name: str) -> str:
    """Return one exact APC battery/pack token, or empty for non-candidates."""
    normalized = (name or "").upper()
    if not is_apc_named(normalized):
        return ""
    matches = [
        *CARTRIDGE_TOKEN.finditer(normalized),
        *SYBT_TOKEN.finditer(normalized),
        *PACK_TOKEN.finditer(normalized),
    ]
    # SYBTU1/2-PLP belongs to both the dedicated SYBT family and the external
    # pack allowlist. It is still one exact title token, not an ambiguity.
    unique_matches = {(match.start(), match.end(), match.group(0)): match for match in matches}
    if len(unique_matches) != 1:
        return ""
    return next(iter(unique_matches.values())).group(0)


def is_apc_named(name: str) -> bool:
    return re.search(r"(?<![A-Z0-9])APC(?![A-Z0-9])", (name or "").upper()) is not None


def build(
    readiness_path: Path,
    output: Path,
    summary_path: Path,
    expected_records: int,
    *,
    readiness_snapshot_id: str,
    readiness_snapshot_sha256: str,
) -> dict[str, object]:
    raw = readiness_path.read_bytes()
    input_sha256 = hashlib.sha256(raw).hexdigest()
    if not readiness_snapshot_id.strip():
        raise ValueError("readiness_snapshot_id must be nonblank")
    if not re.fullmatch(r"[0-9a-f]{64}", readiness_snapshot_sha256.strip().casefold()):
        raise ValueError("readiness_snapshot_sha256 must be a SHA-256")
    if readiness_snapshot_sha256.strip().casefold() != input_sha256:
        raise ValueError("readiness snapshot SHA-256 does not match input")

    rows = load_csv(readiness_path)
    selected: list[dict[str, str]] = []
    rejected = Counter()
    apc_named_records = 0
    b2b_apc_records = 0
    for row in rows:
        external_id = row["product_external_id"].strip()
        name = row["name"].strip()
        if not is_apc_named(name):
            rejected["not_apc_named_record"] += 1
            continue
        apc_named_records += 1
        token = apc_model_token(name)
        has_applied = strict_bool(row["has_applied_description"], "has_applied_description")
        identity_ready = strict_bool(row["identity_ready"], "identity_ready")
        manufacturer_primary = strict_bool(
            row["description_manufacturer_primary"], "description_manufacturer_primary"
        )

        if not external_id.startswith("bitrix:"):
            rejected["not_existing_bitrix_b2b_card"] += 1
            continue
        if row["category_external_id"].strip() != BATTERY_CATEGORY:
            rejected["outside_b2b_battery_category"] += 1
            continue
        b2b_apc_records += 1
        if not token:
            rejected["generic_or_nonexact_apc_name"] += 1
            continue
        if has_applied or row["description_source_tier"].strip() or manufacturer_primary:
            rejected["already_source_backed"] += 1
            continue
        if identity_ready:
            rejected["already_strict_identity"] += 1
            continue
        selected.append({
            "external_id": external_id,
            "name": name,
            "model_token": token,
            "category_external_id": BATTERY_CATEGORY,
            "required_gate": "exact_apc_model_or_external_battery_pack_sku|pinned_readiness_snapshot|first_party_model_evidence|no_identity_or_variant_collision",
            "safe_to_apply": "false",
        })

    selected.sort(key=lambda row: row["external_id"])
    if len(selected) != expected_records:
        raise ValueError(
            f"deterministic APC selection mismatch: expected {expected_records}, got {len(selected)}"
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(selected[0]) if selected else [
            "external_id", "name", "model_token", "category_external_id", "required_gate", "safe_to_apply",
        ])
        writer.writeheader()
        writer.writerows(selected)
    summary = {
        "input_path": str(readiness_path),
        "input_sha256": input_sha256,
        "input_records": len(rows),
        "apc_named_records": apc_named_records,
        "b2b_apc_records": b2b_apc_records,
        "readiness_snapshot_id": readiness_snapshot_id.strip(),
        "readiness_snapshot_sha256": input_sha256,
        "output_path": str(output),
        "output_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "candidate_records": len(selected),
        "excluded_counts": dict(sorted(rejected.items())),
        "automatic_database_mutations": 0,
        "safe_to_apply_records": 0,
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--readiness", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--expected-records", type=int, required=True)
    parser.add_argument("--readiness-snapshot-id", required=True)
    parser.add_argument("--readiness-snapshot-sha256", required=True)
    args = parser.parse_args()
    print(json.dumps(build(
        args.readiness, args.output, args.summary, args.expected_records,
        readiness_snapshot_id=args.readiness_snapshot_id,
        readiness_snapshot_sha256=args.readiness_snapshot_sha256,
    ), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
