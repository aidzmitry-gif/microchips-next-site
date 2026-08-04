#!/usr/bin/env python3
"""Build the fail-closed Wave206 Delta evidence partition.

The command has two phases. ``prepare`` selects the 62 Delta rows from the
Wave205 batch and emits only candidates not already covered by the pinned
Wave198 exact-product evidence. ``build`` combines the reused and newly
acquired first-party evidence, verifies every snapshot hash, compares the
legacy capacity claim, and audits strict duplicates against the full canonical
registry. It never connects to the application database.
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
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "docs/audits/generated/rb-b2b-next-source-batch-wave205.csv"
PRIOR = ROOT / "docs/audits/generated/rb-delta-wave198-official-evidence.csv"
NEW = ROOT / "docs/audits/generated/rb-delta-wave206-new-official-evidence.csv"
ACQUISITION_SUMMARY = ROOT / "docs/audits/generated/rb-delta-wave206-acquisition-summary.json"
CANONICAL = ROOT / "docs/audits/generated/full-catalog-canonical-registry.csv"
ACQUISITION = ROOT / "docs/audits/generated/rb-delta-wave206-acquisition-candidates.csv"
OUTPUT = ROOT / "docs/audits/generated/rb-delta-wave206-official-evidence.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-delta-wave206-official-evidence.summary.json"

EXPECTED_ROWS = 62
PUBLISHER = "DELTA Battery / ENERGON"
FIELDS = [
    "batch", "product_external_id", "name", "legacy_model", "partition",
    "evidence_scope", "source_tier", "source_publisher", "source_url",
    "source_assertion", "verified_facts", "snapshot_path", "snapshot_sha256",
    "unsupported_legacy_claims", "conflict_reason", "replacement_manufacturer",
    "replacement_mpn", "manufacturer_mpn_inference", "repeat_handling",
    "duplicate_review", "strict_duplicate_cluster", "safe_to_apply",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def model_key(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "").casefold().replace(",", ".")
    result: list[str] = []
    for index, char in enumerate(value):
        if "a" <= char <= "z" or "0" <= char <= "9":
            result.append(char)
        elif char == "." and index > 0 and index + 1 < len(value) and value[index - 1].isdigit() and value[index + 1].isdigit():
            result.append(char)
    return "".join(result)


def model_from_name(name: str) -> str:
    match = re.fullmatch(r"\s*Аккумулятор\s+Delta\s+(.+?)\s*\([^)]*\)\s*", name, re.I)
    return re.sub(r"\s+", " ", match.group(1)).strip() if match else ""


def legacy_capacity(name: str) -> str:
    match = re.search(r"(\d+(?:[.,]\d+)?)\s*Ah\b", name, re.I)
    return match.group(1).replace(",", ".") if match else ""


def validate_evidence(path: Path) -> dict[str, dict[str, str]]:
    if not path.is_file():
        return {}
    rows = read_csv(path)
    required = {
        "external_id", "model", "source_url", "source_snapshot_path",
        "source_sha256", "content_model_key", "voltage_v", "capacity_ah",
        "evidence_kind", "publisher", "safe_to_apply",
    }
    if not rows or required - set(rows[0]):
        raise SystemExit(f"Invalid evidence schema: {path}")
    result: dict[str, dict[str, str]] = {}
    for row in rows:
        key = model_key(row["model"])
        if not key or key in result or row["content_model_key"] != key:
            raise SystemExit(f"Duplicate or lossy model key in {path}: {row['model']}")
        parsed = urlparse(row["source_url"])
        if parsed.scheme != "https" or (parsed.hostname or "").casefold() not in {"delta-batt.com", "www.delta-batt.com"}:
            raise SystemExit(f"Non-official Delta source: {row['source_url']}")
        snapshot = Path(row["source_snapshot_path"])
        if not snapshot.is_absolute():
            snapshot = ROOT / snapshot
        if not snapshot.is_file() or sha256(snapshot) != row["source_sha256"].casefold():
            raise SystemExit(f"Missing or hash-mismatched snapshot for {row['external_id']}")
        if row["publisher"] != PUBLISHER or row["safe_to_apply"].casefold() != "false":
            raise SystemExit(f"Unsafe evidence contract for {row['external_id']}")
        result[key] = {**row, "source_snapshot_path": snapshot.relative_to(ROOT).as_posix()}
    return result


def candidates() -> list[dict[str, str]]:
    rows = [row for row in read_csv(INPUT) if row["manufacturer_cluster"] == "Delta"]
    if len(rows) != EXPECTED_ROWS or len({row["product_external_id"] for row in rows}) != EXPECTED_ROWS:
        raise SystemExit(f"Wave206 Delta partition drifted: expected {EXPECTED_ROWS}, got {len(rows)}")
    if any(not model_from_name(row["name"]) for row in rows):
        raise SystemExit("Wave206 contains an unparseable Delta product name")
    return rows


def prepare() -> None:
    rows = candidates()
    prior = validate_evidence(PRIOR)
    output = []
    for row in rows:
        model = model_from_name(row["name"])
        if model_key(model) in prior:
            continue
        output.append({
            "external_id": row["product_external_id"],
            "model_candidate_unverified": model,
            "safe_to_apply": "false",
        })
    ACQUISITION.parent.mkdir(parents=True, exist_ok=True)
    with ACQUISITION.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(output[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(output)
    print(json.dumps({
        "input_rows": len(rows), "reused_exact_rows": len(rows) - len(output),
        "acquisition_rows": len(output), "output": ACQUISITION.relative_to(ROOT).as_posix(),
        "output_sha256": sha256(ACQUISITION), "database_mutations": 0,
    }, ensure_ascii=False, indent=2))


def strict_duplicates(rows: list[dict[str, str]]) -> dict[str, list[str]]:
    target = {model_key(model_from_name(row["name"])) for row in rows}
    matches: dict[str, list[str]] = defaultdict(list)
    for row in read_csv(CANONICAL):
        if "delta" not in row["name"].casefold():
            continue
        model = model_from_name(row["name"])
        key = model_key(model)
        if key in target:
            matches[key].append(row["registry_id"])
    return {key: sorted(ids) for key, ids in matches.items() if len(ids) > 1}


def prior_batch_overlap(candidate_ids: set[str]) -> list[dict[str, str]]:
    """Reject repeats from the immediately preceding source-research waves.

    Wave198 is intentionally excluded: its pinned source snapshots are reused
    here to finish identity classification, not reacquired or re-researched.
    """
    overlaps = []
    for path in sorted((ROOT / "docs/audits/generated").glob("*wave20[0-4]*evidence*.csv")):
        try:
            for row in read_csv(path):
                external_id = row.get("product_external_id") or row.get("external_id") or ""
                if external_id in candidate_ids:
                    overlaps.append({"path": path.relative_to(ROOT).as_posix(), "product_external_id": external_id})
        except (UnicodeDecodeError, csv.Error):
            continue
    return overlaps


def build() -> None:
    rows = candidates()
    overlaps = prior_batch_overlap({row["product_external_id"] for row in rows})
    if overlaps:
        raise SystemExit("Wave206 repeats Wave200-204 evidence IDs: " + ", ".join(item["product_external_id"] for item in overlaps))
    prior, new = validate_evidence(PRIOR), validate_evidence(NEW)
    acquisition_summary = json.loads(ACQUISITION_SUMMARY.read_text(encoding="utf-8"))
    ct_source = acquisition_summary.get("ct_scope_snapshot", {})
    ct_snapshot = ROOT / str(ct_source.get("snapshot_path", ""))
    if (
        not ct_snapshot.is_file()
        or sha256(ct_snapshot) != str(ct_source.get("snapshot_sha256", "")).casefold()
        or len(ct_source.get("required_tokens", [])) < 3
    ):
        raise SystemExit("Pinned current CT scope snapshot is missing or hash-mismatched")
    overlap = set(prior) & set(new)
    if overlap:
        raise SystemExit("New acquisition repeats pinned Wave198 model keys: " + ", ".join(sorted(overlap)))
    evidence = {**prior, **new}
    duplicates = strict_duplicates(rows)
    output = []
    for row in rows:
        external_id, name = row["product_external_id"], row["name"]
        model, capacity = model_from_name(name), legacy_capacity(name)
        key, source = model_key(model), evidence.get(model_key(model))
        partition = "no_evidence"
        reason = "No pinned first-party exact-model product page was found in the current Delta stationary-series catalogue."
        if model.upper().startswith("CT "):
            partition = "conflict"
            reason = "DELTA classifies CT as starter batteries for motorcycles and similar equipment; the row is outside the approved non-automotive B2B scope."
        elif source:
            if source["external_id"] != external_id:
                raise SystemExit(f"Exact model evidence belongs to another external ID: {external_id}")
            if capacity and float(capacity) != float(source["capacity_ah"]):
                partition = "conflict"
                reason = f"Legacy capacity {capacity}Ah conflicts with the official exact-model value {source['capacity_ah']}Ah."
            else:
                partition = "exact_safe"
                reason = ""
        cluster = duplicates.get(key, [])
        exact = partition == "exact_safe" and not cluster
        if partition == "exact_safe" and cluster:
            partition = "conflict"
            reason = "Strict normalized manufacturer+model collision exists in the full canonical registry."
        output.append({
            "batch": "wave206_delta",
            "product_external_id": external_id,
            "name": name,
            "legacy_model": model,
            "partition": partition,
            "evidence_scope": "exact_product_page" if source else ("official_series_scope" if model.upper().startswith("CT ") else "none"),
            "source_tier": "manufacturer_primary" if source else ("manufacturer_primary" if model.upper().startswith("CT ") else "none"),
            "source_publisher": source["publisher"] if source else (PUBLISHER if model.upper().startswith("CT ") else ""),
            "source_url": source["source_url"] if source else ("https://www.delta-batt.com/catalog/dlya-mototekhniki/ct/" if model.upper().startswith("CT ") else ""),
            "source_assertion": f"Exact product H1 {source['model']}; {source['voltage_v']}V; {source['capacity_ah']}Ah." if source else ("Official CT series is catalogued for motorcycles and related starter applications." if model.upper().startswith("CT ") else ""),
            "verified_facts": f"manufacturer=Delta|mpn={model}|voltage_v={source['voltage_v']}|capacity_ah={source['capacity_ah']}" if source else ("manufacturer=Delta|series=CT|scope=motorcycle_starter" if model.upper().startswith("CT ") else ""),
            "snapshot_path": source["source_snapshot_path"] if source else (ct_snapshot.relative_to(ROOT).as_posix() if model.upper().startswith("CT ") else ""),
            "snapshot_sha256": source["source_sha256"] if source else (str(ct_source["snapshot_sha256"]) if model.upper().startswith("CT ") else ""),
            "unsupported_legacy_claims": "" if source else ("stationary_ups_category" if model.upper().startswith("CT ") else "manufacturer_identity|mpn|capacity|technology"),
            "conflict_reason": reason,
            "replacement_manufacturer": "Delta" if exact else "",
            "replacement_mpn": model if exact else "",
            "manufacturer_mpn_inference": "explicit_official_exact_product_page" if exact else "none",
            "repeat_handling": "reused_wave198_snapshot" if source and key in prior else ("new_exact_source" if source else "new_review"),
            "duplicate_review": "strict_collision_hold" if cluster else "no_strict_duplicate",
            "strict_duplicate_cluster": "|".join(cluster),
            "safe_to_apply": "true" if exact else "false",
        })
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(output)
    counts = Counter(row["partition"] for row in output)
    safe_ids = [row["product_external_id"] for row in output if row["safe_to_apply"] == "true"]
    summary = {
        "schema_version": 1, "site": "microchips-by", "batch": "wave206_delta", "created_at": "2026-07-29",
        "input": {"path": INPUT.relative_to(ROOT).as_posix(), "sha256": sha256(INPUT), "rows": len(rows)},
        "reused_evidence": {"path": PRIOR.relative_to(ROOT).as_posix(), "sha256": sha256(PRIOR), "matched_rows": sum(model_key(model_from_name(row['name'])) in prior for row in rows)},
        "new_evidence": {"path": NEW.relative_to(ROOT).as_posix(), "sha256": sha256(NEW) if NEW.is_file() else "", "matched_rows": sum(model_key(model_from_name(row['name'])) in new for row in rows)},
        "ct_scope_snapshot": {"path": ct_snapshot.relative_to(ROOT).as_posix(), "sha256": sha256(ct_snapshot), "source_url": ct_source.get("source_url", "")},
        "full_registry": {"path": CANONICAL.relative_to(ROOT).as_posix(), "sha256": sha256(CANONICAL), "rows": len(read_csv(CANONICAL))},
        "output": {"path": OUTPUT.relative_to(ROOT).as_posix(), "sha256": sha256(OUTPUT), "rows": len(output)},
        "partition_counts": {name: counts.get(name, 0) for name in ("exact_safe", "compatibility_only", "conflict", "no_evidence")},
        "safe_to_apply": {"rows": len(safe_ids), "external_ids": safe_ids},
        "strict_duplicates": {"clusters": len(duplicates), "rows": sum(len(ids) for ids in duplicates.values()), "details": duplicates},
        "prior_wave200_204_overlap_rows": 0,
        "policy": {"exact_model_and_snapshot_sha_required": True, "legacy_capacity_must_match": True, "ct_motorcycle_scope_held": True, "database_mutations": 0},
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("prepare", "build"))
    args = parser.parse_args()
    prepare() if args.phase == "prepare" else build()


if __name__ == "__main__":
    main()
