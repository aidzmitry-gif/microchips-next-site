#!/usr/bin/env python3
"""Build the fail-closed Delta stationary-battery research batch for wave 198.

This tool is deliberately a preparation boundary: it writes research evidence
only and never connects to or mutates the application database.  A supplied
official-evidence CSV must contain an exact normalized model key; a series
page, a prefix match, or a distributor page is not sufficient.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlsplit

REQUIRED = {"external_id", "name", "category_external_id", "transfer_status", "identity_candidate_status", "has_primary_exact_description"}
OFFICIAL_URL = "https://www.delta-batt.com/catalog/"
OFFICIAL_HOSTS = {"delta-batt.com", "www.delta-batt.com"}
OFFICIAL_PUBLISHER = "DELTA Battery / ENERGON"
EVIDENCE_REQUIRED = {
    "external_id", "model", "source_url", "source_snapshot_path", "source_sha256",
    "content_model_key", "voltage_v", "capacity_ah", "evidence_kind", "publisher", "safe_to_apply",
}
SHA256 = re.compile(r"[0-9a-f]{64}", re.I)
PRODUCT_PAGE_PATH = re.compile(r"/(?:catalog|products)/[a-z0-9][a-z0-9._-]*/?", re.I)
DATASHEET_PATH = re.compile(r"/(?:upload|uploads|files|catalog)/(?:[^/]+/)*[^/]+\.pdf", re.I)


def compact(value: str) -> str:
    """Build a punctuation-insensitive key without erasing decimal identity."""
    normalized = unicodedata.normalize("NFKC", value or "").casefold()
    result: list[str] = []
    for index, char in enumerate(normalized):
        if "a" <= char <= "z" or "0" <= char <= "9":
            result.append(char)
        elif (
            char in {".", ","}
            and index > 0
            and index + 1 < len(normalized)
            and normalized[index - 1].isdigit()
            and normalized[index + 1].isdigit()
        ):
            result.append(".")
    return "".join(result)


def model_from_name(name: str) -> str:
    match = re.fullmatch(r"\s*Аккумулятор\s+Delta\s+(.+?)\s*\([^)]*\)\s*", name, re.I)
    if not match:
        return ""
    model = re.sub(r"\s+", " ", match.group(1)).strip()
    # Only known legacy terminal markers collapse to the base model.  Other
    # parenthesized suffixes remain identity-significant.
    return re.sub(r"\s*\((?:T\d+|\d+)\)\s*$", "", model, flags=re.I).strip()


def is_motorcycle_ct(model: str) -> bool:
    normalized = unicodedata.normalize("NFKC", model or "").casefold().strip()
    return re.match(r"^ct(?:[\s\-_.\/]*)(?=\d)", normalized) is not None


def strict_bool(value: str, field: str) -> bool:
    normalized = (value or "").strip().casefold()
    if normalized not in {"true", "false"}:
        raise ValueError(f"{field} must be explicitly true or false")
    return normalized == "true"


def require_sha256(value: str, field: str) -> str:
    normalized = (value or "").strip().casefold()
    if not SHA256.fullmatch(normalized):
        raise ValueError(f"{field} must be a 64-character SHA-256")
    return normalized


def validate_official_url(value: str, evidence_kind: str) -> str:
    source_url = (value or "").strip()
    parsed = urlsplit(source_url)
    try:
        port = parsed.port
    except ValueError as error:
        raise ValueError("official evidence source_url has an invalid port") from error
    if (
        parsed.scheme != "https"
        or (parsed.hostname or "").casefold() not in OFFICIAL_HOSTS
        or parsed.username is not None
        or parsed.password is not None
        or port not in {None, 443}
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("official evidence source_url must be a canonical Delta Battery HTTPS URL")
    path_rule = PRODUCT_PAGE_PATH if evidence_kind == "exact_product_page" else DATASHEET_PATH
    if path_rule.fullmatch(parsed.path) is None:
        raise ValueError(f"official evidence path is not valid for {evidence_kind}")
    return source_url


def load_csv(path: Path, required: set[str]) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError("missing required columns: " + ", ".join(sorted(missing)))
        rows = list(reader)
    ids = [row["external_id"].strip() for row in rows]
    if not all(ids) or len(ids) != len(set(ids)):
        raise ValueError("input must contain unique nonblank external_id values")
    return rows


def load_evidence(path: Path | None) -> tuple[dict[str, dict[str, str]], str | None, int]:
    if path is None:
        return {}, None, 0
    raw = path.read_bytes()
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = EVIDENCE_REQUIRED - set(reader.fieldnames or [])
        if missing:
            raise ValueError("official evidence missing required columns: " + ", ".join(sorted(missing)))
        rows = list(reader)
    result: dict[str, dict[str, str]] = {}
    for row in rows:
        key = compact(row["model"])
        if not key or key in result:
            raise ValueError("official evidence must have unique nonblank exact model keys")
        if row["evidence_kind"] not in {"exact_product_page", "exact_product_datasheet"}:
            raise ValueError("official evidence_kind must be exact_product_page or exact_product_datasheet")
        if row["publisher"].strip() != OFFICIAL_PUBLISHER:
            raise ValueError(f"official evidence publisher must be {OFFICIAL_PUBLISHER}")
        source_url = validate_official_url(row["source_url"], row["evidence_kind"])
        source_sha256 = require_sha256(row["source_sha256"], "source_sha256")
        snapshot_path = Path(row["source_snapshot_path"].strip())
        if not snapshot_path.is_absolute():
            snapshot_path = path.parent / snapshot_path
        if not snapshot_path.is_file():
            raise ValueError("official evidence source_snapshot_path must reference a saved source file")
        if hashlib.sha256(snapshot_path.read_bytes()).hexdigest() != source_sha256:
            raise ValueError("official evidence source snapshot SHA-256 mismatch")
        if row["content_model_key"].strip() != key:
            raise ValueError("official evidence content_model_key must exactly match the lossless model key")
        if not row["external_id"].strip():
            raise ValueError("official evidence external_id must be nonblank")
        if strict_bool(row["safe_to_apply"], "official evidence safe_to_apply"):
            raise ValueError("official evidence must remain safe_to_apply=false")
        for field in ("voltage_v", "capacity_ah"):
            if re.fullmatch(r"\d+(?:\.\d+)?", row[field].strip()) is None:
                raise ValueError(f"official evidence {field} must be an extracted numeric fact")
        result[key] = {
            **row,
            "external_id": row["external_id"].strip(),
            "source_url": source_url,
            "source_snapshot_path": str(snapshot_path),
            "source_sha256": source_sha256,
        }
    return result, hashlib.sha256(raw).hexdigest(), len(rows)


def build(
    input_path: Path,
    output: Path,
    contract: Path,
    expected_records: int,
    evidence_path: Path | None = None,
    *,
    identity_snapshot_id: str,
    identity_snapshot_sha256: str,
) -> dict[str, object]:
    raw = input_path.read_bytes()
    input_sha256 = hashlib.sha256(raw).hexdigest()
    if not identity_snapshot_id.strip():
        raise ValueError("identity_snapshot_id must be nonblank")
    if require_sha256(identity_snapshot_sha256, "identity_snapshot_sha256") != input_sha256:
        raise ValueError("identity snapshot SHA-256 does not match the input snapshot")
    rows = load_csv(input_path, REQUIRED)
    if len(rows) != expected_records:
        raise ValueError(f"input record count mismatch: expected {expected_records}, got {len(rows)}")
    evidence, evidence_sha256, evidence_records = load_evidence(evidence_path)
    prepared = []
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        identity_status = row["identity_candidate_status"].strip().casefold()
        if not identity_status:
            raise ValueError("identity_candidate_status must be explicit; use 'none' only for a checked clear row")
        model = model_from_name(row["name"])
        item: dict[str, object] = {
            "row": row,
            "model": model,
            "key": compact(model),
            "identity_status": identity_status,
            "has_primary": strict_bool(row["has_primary_exact_description"], "has_primary_exact_description"),
        }
        prepared.append(item)
        if item["key"]:
            grouped[str(item["key"])].append(item)

    eligible = []
    rejected = Counter()
    for item in prepared:
        row = item["row"]
        assert isinstance(row, dict)
        model, key = str(item["model"]), str(item["key"])
        if key and len(grouped[key]) > 1:
            rejected["duplicate_base_model_hold"] += 1; continue
        if row["category_external_id"] != "seo:batteries-ups":
            rejected["outside_ups_category"] += 1; continue
        if row["transfer_status"] != "legacy_only_draft_candidate":
            rejected["not_legacy_candidate"] += 1; continue
        if item["identity_status"] != "none":
            rejected["identity_candidate_or_one_c_link"] += 1; continue
        if item["has_primary"]:
            rejected["already_primary_enriched"] += 1; continue
        if not model or is_motorcycle_ct(model):
            rejected["motorcycle_or_unparseable_model"] += 1; continue
        eligible.append((row, model, key))

    eligible_keys = {key for _, _, key in eligible}
    unexpected_evidence = sorted(set(evidence) - eligible_keys)
    if unexpected_evidence:
        raise ValueError("official evidence contains models outside the eligible snapshot: " + ", ".join(unexpected_evidence))
    output_rows = []
    for row, model, key in eligible:
        source = evidence.get(key)
        if source and source["external_id"] != row["external_id"].strip():
            raise ValueError("official evidence external_id does not match the candidate model")
        output_rows.append({
            "external_id": row["external_id"].strip(), "name": row["name"], "manufacturer_candidate": "Delta",
            "model_candidate_unverified": model, "model_key": key,
            "category_external_id": row["category_external_id"],
            "source_acquisition_url": OFFICIAL_URL,
            "exact_official_evidence_status": "exact_match_available" if source else "source_acquisition_required",
            "exact_official_source_url": source["source_url"] if source else "",
            "exact_official_source_sha256": source["source_sha256"] if source else "",
            "evidence_publisher": source["publisher"] if source else "",
            "evidence_kind": source["evidence_kind"] if source else "",
            "required_gate": "lossless_exact_delta_model_key|pinned_first_party_exact_product_page_or_datasheet|pinned_identity_snapshot_no_collision|global_snapshot_no_duplicate_model",
            "safe_to_apply": "false",
        })
    output_rows.sort(key=lambda row: row["external_id"])
    if len(output_rows) != 130:
        raise ValueError(f"deterministic Delta selection mismatch: expected 130, got {len(output_rows)}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(output_rows[0])); writer.writeheader(); writer.writerows(output_rows)
    output_sha256 = hashlib.sha256(output.read_bytes()).hexdigest()
    summary = {
        "input_path": str(input_path), "input_sha256": input_sha256, "input_records": len(rows),
        "identity_snapshot_id": identity_snapshot_id.strip(), "identity_snapshot_sha256": input_sha256,
        "official_evidence_path": str(evidence_path) if evidence_path else None,
        "official_evidence_sha256": evidence_sha256, "official_evidence_records": evidence_records,
        "output_path": str(output), "output_sha256": output_sha256,
        "candidate_records": len(output_rows), "official_exact_matches": sum(r["exact_official_evidence_status"] == "exact_match_available" for r in output_rows),
        "source_acquisition_required": sum(r["exact_official_evidence_status"] == "source_acquisition_required" for r in output_rows),
        "excluded_counts": dict(sorted(rejected.items())), "official_source_contract": {"publisher": OFFICIAL_PUBLISHER, "catalog_url": OFFICIAL_URL, "allowed_evidence_kind": ["exact_product_page", "exact_product_datasheet"], "required_columns": sorted(EVIDENCE_REQUIRED)},
        "automatic_database_mutations": 0, "safe_to_apply_records": 0,
    }
    contract.parent.mkdir(parents=True, exist_ok=True)
    contract.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True); parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True); parser.add_argument("--expected-records", type=int, required=True)
    parser.add_argument("--official-evidence", type=Path)
    parser.add_argument("--identity-snapshot-id", required=True)
    parser.add_argument("--identity-snapshot-sha256", required=True)
    args = parser.parse_args()
    print(json.dumps(build(
        args.input, args.output, args.contract, args.expected_records, args.official_evidence,
        identity_snapshot_id=args.identity_snapshot_id,
        identity_snapshot_sha256=args.identity_snapshot_sha256,
    ), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
