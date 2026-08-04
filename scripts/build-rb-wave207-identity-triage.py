#!/usr/bin/env python3
"""Deterministically triage the 153 low-likelihood Wave205 identities.

The command does not search the web and never mutates the database.  It only
extracts an exact model/configuration fingerprint, compares it with the current
product registry, and decides whether a bounded source lookup is possible.
"""
from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import re
import subprocess
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs/audits/generated/rb-b2b-next-source-batch-wave205.csv"
OUTPUT = ROOT / "docs/audits/generated/rb-wave207-identity-triage.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-wave207-identity-triage.summary.json"
WAVE206_FILES = (
    ROOT / "docs/audits/generated/rb-delta-wave206-official-evidence.csv",
    ROOT / "docs/audits/generated/rb-wave206-fiamm-bb-csb-evidence.csv",
    ROOT / "docs/audits/generated/wave206-panasonic-ventura-mnb-evidence.csv",
)
TARGET_CLUSTERS = {
    "AT radio packs": 88,
    "cash-register packs": 18,
    "unresolved_replacement": 26,
    "unresolved_industrial_cell": 9,
    "Vector": 12,
}
EXPECTED_ROWS = 153
EXPECTED_WAVE206_FILE_ROWS = (62, 38, 85)
EXPECTED_WAVE206_ROWS = sum(EXPECTED_WAVE206_FILE_ROWS)

FIELDS = [
    "product_external_id",
    "manufacturer_cluster",
    "name",
    "normalized_model",
    "normalized_configuration",
    "identity_key",
    "identity_signal",
    "route_partition",
    "next_source_route",
    "hold_reason",
    "scope_issue",
    "in_wave_identity_group_size",
    "in_wave_duplicate_candidate",
    "db_exact_name_collision_count",
    "db_exact_name_collision_external_ids",
    "db_identity_collision_count",
    "db_identity_collision_external_ids",
    "db_current_manufacturer",
    "db_current_mpn",
    "wave206_overlap",
    "safe_to_apply",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "").upper()
    value = value.translate(str.maketrans("АВЕКМНОРСТУХ", "ABEKMHOPCTYX"))
    value = value.replace("Ё", "Е")
    return re.sub(r"[^0-9A-ZА-Я]+", "", value)


def chemistry(name: str) -> str:
    upper = unicodedata.normalize("NFKC", name).upper()
    for token, canonical in (
        ("LI-ION", "LIION"),
        ("LITHIUM-ION", "LIION"),
        ("NIMH", "NIMH"),
        ("NI-MH", "NIMH"),
        ("NICD", "NICD"),
        ("NI-CD", "NICD"),
        ("NIFE", "NIFE"),
    ):
        if token in upper:
            return canonical
    return ""


def numeric(name: str, unit: str) -> str:
    match = re.search(rf"(\d+(?:[.,]\d+)?)\s*{unit}\b", name, re.I)
    return match.group(1).replace(",", ".") if match else ""


def first_parenthetical(name: str) -> str:
    match = re.search(r"\(([^()]*)\)", name)
    return match.group(1) if match else ""


def identify(name: str, declared_cluster: str = "") -> dict[str, str]:
    """Return an exact, conservative identity/configuration fingerprint."""
    model = ""
    signal = ""
    route = ""
    scope_issue = ""
    cluster = declared_cluster

    at = re.search(
        r"(?:\bAT\s+([^()]+?)\s+для\s+радиостанц|для\s+радиостанц(?:ий|ии)\s+AT\s+([^()]+?)(?:\s*\(|$))",
        name,
        re.I,
    )
    vector = re.search(r"\bVECTOR\s+(BP[-\s][A-Z0-9]+(?:\s+[A-Z0-9]+)*)\s+для\s+радиостанц", name, re.I)
    industrial = re.search(r"\b(FL[-\s][^()]+?)\s*\(([^()]*(?:ТНЖ|ВНЖ)[^()]*)\)", name, re.I)
    cash = re.search(r"для\s+кассов(?:ых\s+аппаратов|ого\s+аппарата)\s*([^()]*)\s*\(([^()]*)\)", name, re.I)

    if at:
        cluster = "AT"
        model = normalize(at.group(1) or at.group(2) or "")
        signal = "exact_at_configuration_code" if model else ""
        route = "at_supplier_catalogue_by_exact_configuration"
        scope_issue = "AT_is_a_pack_configuration_claim_not_a_verified_manufacturer"
    elif vector:
        cluster = "VECTOR"
        model = normalize(vector.group(1))
        signal = "exact_claimed_vector_model" if model else ""
        route = "vector_catalogue_by_exact_model"
        scope_issue = "claimed_Vector_identity_requires_primary_source_confirmation"
    elif industrial:
        cluster = "INDUSTRIAL_CELL"
        model = f"{normalize(industrial.group(1))}|{normalize(industrial.group(2))}"
        signal = "exact_dual_industrial_designation" if all(model.split("|")) else ""
        route = "industrial_cell_catalogue_by_dual_designation"
        scope_issue = "manufacturer_unresolved_for_dual_designation"
    elif cash:
        cluster = "CASH_REGISTER"
        device = normalize(cash.group(1))
        parenthetical = cash.group(2)
        connector = ""
        for marker in ("MINI TAMIYA", "KET-2P", "FLATPACK", "ROW", "JST", "SM"):
            if re.search(rf"\b{re.escape(marker)}\b", parenthetical, re.I):
                connector = normalize(marker)
                break
        model = device or connector
        signal = "exact_device_or_pack_form" if model else ""
        route = "cash_register_oem_or_assembly_source_by_exact_configuration"
        scope_issue = "assembly_part_number_and_connector_fit_unverified"
    else:
        cluster = normalize(cluster) or "UNRESOLVED"

    configuration = "|".join(
        part
        for part in (
            chemistry(name),
            numeric(name, "V"),
            numeric(name, "MAH"),
            numeric(name, "AH"),
            normalize(first_parenthetical(name)) if cluster == "CASH_REGISTER" else "",
        )
        if part
    )
    identity_key = f"{cluster}|{model}|{configuration}" if model else ""
    actionable = bool(model)
    return {
        "normalized_model": model,
        "normalized_configuration": configuration,
        "identity_key": identity_key,
        "identity_signal": signal,
        "route_partition": "actionable_source_route" if actionable else "hold",
        "next_source_route": route if actionable else "none_identity_resolution_required",
        "hold_reason": "" if actionable else "no_exact_model_device_connector_or_form_factor",
        "scope_issue": scope_issue or "identity_scope_unresolved",
    }


def candidate_union(source: Path) -> list[dict[str, str]]:
    all_rows = read_csv(source)
    selected = [row for row in all_rows if row["manufacturer_cluster"] in TARGET_CLUSTERS]
    counts = Counter(row["manufacturer_cluster"] for row in selected)
    if counts != Counter(TARGET_CLUSTERS):
        raise SystemExit(f"Wave207 cluster mismatch: {dict(counts)}")
    ids = [row["product_external_id"] for row in selected]
    if len(selected) != EXPECTED_ROWS or len(ids) != len(set(ids)):
        raise SystemExit(f"Wave207 union must contain {EXPECTED_ROWS} unique rows")
    return selected


def wave206_ids(paths: tuple[Path, ...]) -> set[str]:
    source_rows = [read_csv(path) for path in paths]
    actual_counts = tuple(len(rows) for rows in source_rows)
    if actual_counts != EXPECTED_WAVE206_FILE_ROWS:
        raise SystemExit(f"Wave206 input counts changed: {actual_counts}")
    rows = [row for batch in source_rows for row in batch]
    ids = [row["product_external_id"] for row in rows]
    if len(rows) != EXPECTED_WAVE206_ROWS or len(ids) != len(set(ids)):
        raise SystemExit(f"Wave206 union must contain {EXPECTED_WAVE206_ROWS} unique rows")
    return set(ids)


def query_current_products() -> list[dict[str, str]]:
    php = (
        "$r=app('db')->table('products')->select('external_id','name','manufacturer','mpn','status')"
        "->orderBy('external_id')->get();"
        "echo json_encode($r,JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES);"
    )
    encoded = base64.b64encode(php.encode("utf-8")).decode("ascii")
    expression = f"eval(base64_decode('{encoded}'));"
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
    if process.returncode or not payload.startswith("["):
        raise SystemExit(f"Current product registry query failed: {payload or process.stderr.strip()}")
    return json.loads(payload)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--summary", type=Path, default=SUMMARY)
    parser.add_argument("--db-snapshot", type=Path, help="JSON product registry fixture; default queries Docker read-only")
    args = parser.parse_args()

    candidates = candidate_union(args.source)
    previous_ids = wave206_ids(WAVE206_FILES)
    overlap = {row["product_external_id"] for row in candidates} & previous_ids
    if overlap:
        raise SystemExit(f"Wave207 overlaps Wave206: {sorted(overlap)}")

    database = (
        json.loads(args.db_snapshot.read_text(encoding="utf-8"))
        if args.db_snapshot
        else query_current_products()
    )
    db_by_id = {str(row["external_id"]): row for row in database}
    if len(db_by_id) != len(database):
        raise SystemExit("Current DB snapshot repeats external_id")

    exact_names: dict[str, list[str]] = defaultdict(list)
    db_identities: dict[str, list[str]] = defaultdict(list)
    for row in database:
        external_id = str(row["external_id"])
        name = str(row.get("name") or "")
        exact_names[normalize(name)].append(external_id)
        fingerprint = identify(name)
        if fingerprint["identity_key"]:
            db_identities[fingerprint["identity_key"]].append(external_id)

    prepared = []
    for candidate in candidates:
        fingerprint = identify(candidate["name"], candidate["manufacturer_cluster"])
        prepared.append({**candidate, **fingerprint})
    identity_sizes = Counter(row["identity_key"] for row in prepared if row["identity_key"])

    output_rows = []
    for row in prepared:
        external_id = row["product_external_id"]
        current = db_by_id.get(external_id, {})
        exact_collision_ids = sorted(
            value for value in exact_names.get(normalize(row["name"]), []) if value != external_id
        )
        identity_collision_ids = sorted(
            value for value in db_identities.get(row["identity_key"], []) if value != external_id
        ) if row["identity_key"] else []
        group_size = identity_sizes.get(row["identity_key"], 0)
        duplicate = group_size > 1 or bool(exact_collision_ids or identity_collision_ids)
        route_partition = row["route_partition"]
        hold_reason = row["hold_reason"]
        if duplicate:
            route_partition = "hold"
            hold_reason = "exact_identity_collision_requires_duplicate_resolution"
        next_source_route = (
            "none_duplicate_or_identity_resolution_required"
            if duplicate
            else row["next_source_route"]
        )
        output_rows.append({
            "product_external_id": external_id,
            "manufacturer_cluster": row["manufacturer_cluster"],
            "name": row["name"],
            "normalized_model": row["normalized_model"],
            "normalized_configuration": row["normalized_configuration"],
            "identity_key": row["identity_key"],
            "identity_signal": row["identity_signal"],
            "route_partition": route_partition,
            "next_source_route": next_source_route,
            "hold_reason": hold_reason,
            "scope_issue": row["scope_issue"],
            "in_wave_identity_group_size": group_size,
            "in_wave_duplicate_candidate": str(group_size > 1).lower(),
            "db_exact_name_collision_count": len(exact_collision_ids),
            "db_exact_name_collision_external_ids": "|".join(exact_collision_ids),
            "db_identity_collision_count": len(identity_collision_ids),
            "db_identity_collision_external_ids": "|".join(identity_collision_ids),
            "db_current_manufacturer": str(current.get("manufacturer") or ""),
            "db_current_mpn": str(current.get("mpn") or ""),
            "wave206_overlap": "false",
            "safe_to_apply": "false",
        })

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(output_rows)

    route_counts = Counter(row["route_partition"] for row in output_rows)
    summary = {
        "schema_version": 1,
        "wave": "wave207",
        "source_records": len(read_csv(args.source)),
        "candidate_records": len(output_rows),
        "cluster_counts": dict(sorted(Counter(row["manufacturer_cluster"] for row in output_rows).items())),
        "route_partition_counts": dict(sorted(route_counts.items())),
        "identity_signal_counts": dict(sorted(Counter(row["identity_signal"] or "none" for row in output_rows).items())),
        "in_wave_duplicate_candidates": sum(row["in_wave_duplicate_candidate"] == "true" for row in output_rows),
        "db_exact_name_collision_candidates": sum(int(row["db_exact_name_collision_count"]) > 0 for row in output_rows),
        "db_identity_collision_candidates": sum(int(row["db_identity_collision_count"]) > 0 for row in output_rows),
        "db_product_records": len(database),
        "db_candidate_records_present": sum(row["product_external_id"] in db_by_id for row in output_rows),
        "db_current_manufacturer_records": sum(bool(row["db_current_manufacturer"]) for row in output_rows),
        "db_current_mpn_records": sum(bool(row["db_current_mpn"]) for row in output_rows),
        "hold_external_ids": [row["product_external_id"] for row in output_rows if row["route_partition"] == "hold"],
        "wave206_records": len(previous_ids),
        "wave206_overlap_records": 0,
        "source_sha256": sha256(args.source),
        "wave206_input_sha256": {path.name: sha256(path) for path in WAVE206_FILES},
        "output_sha256": sha256(args.output),
        "automatic_web_requests": 0,
        "automatic_database_mutations": 0,
        "safe_to_apply_records": 0,
    }
    args.summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
