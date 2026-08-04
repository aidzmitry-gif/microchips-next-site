#!/usr/bin/env python3
"""Audit Wave249 provenance blockers against already-pinned local evidence only.

No network request and no database mutation is performed.  A row is emitted as
SAFE only when a prior hash-pinned artifact carries the same product identity,
source URL, supported source kind/tier and exact/model-core scope.  Everything
else remains a research queue item rather than receiving inferred provenance.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "docs" / "audits" / "generated"
RECOVERY = GENERATED / "rb-wave246-recovery-source-backed-descriptions.json"
OUTPUT_JSON = GENERATED / "rb-wave250-description-provenance-relink-2026-07-30.json"
OUTPUT_CSV = GENERATED / "rb-wave250-description-provenance-relink-2026-07-30.csv"
QUEUE_CSV = GENERATED / "rb-wave250-description-source-research-queue-2026-07-30.csv"
ALLOWED_SOURCE_PAIRS = {
    ("official_manufacturer_catalogue", "manufacturer_primary"),
    ("official_manufacturer_product_page", "manufacturer_primary"),
    ("official_dealer_product_page", "dealer_backed"),
}
CSV_FIELDS = [
    "product_external_id", "product_id", "site_product_id", "name", "manufacturer", "mpn",
    "category_external_id", "description_sha256", "description_characters", "current_source_kind",
    "current_source_tier", "current_identity_scope", "recovery_source_url", "candidate_source_kind",
    "candidate_source_tier", "candidate_identity_scope", "candidate_identity", "evidence_path",
    "evidence_sha256", "disposition", "hold_reason", "research_priority",
    "manufacturer_blocker_count", "priority_basis", "no_repeat_basis",
]


class AuditError(RuntimeError):
    pass


def load_wave249() -> Any:
    path = ROOT / "scripts" / "build-rb-wave249a-indexable-b2b-cohort.py"
    spec = importlib.util.spec_from_file_location("wave249a", path)
    if spec is None or spec.loader is None:
        raise AuditError("Wave249A module cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize(value: Any) -> str:
    return re.sub(r"[^0-9a-zа-я]+", "", str(value or "").casefold())


def valid_https(value: Any) -> bool:
    parsed = urlparse(str(value or ""))
    return parsed.scheme == "https" and bool(parsed.netloc)


def name_contains(name: Any, identity: Any) -> bool:
    token = str(identity or "").strip()
    if not token:
        return False
    return re.search(rf"(?<![0-9A-Za-zА-Яа-я]){re.escape(token)}(?![0-9A-Za-zА-Яа-я])", str(name or ""), re.I) is not None


def normalize(value: Any) -> str:
    """Unicode-safe catalogue identity normalizer."""
    return re.sub(r"[\W_]+", "", str(value or "").casefold(), flags=re.UNICODE)


def name_contains(name: Any, identity: Any) -> bool:
    """Require a full Unicode token boundary for model-core evidence."""
    token = str(identity or "").strip()
    if not token:
        return False
    return re.search(rf"(?<!\w){re.escape(token)}(?!\w)", str(name or ""), re.I | re.UNICODE) is not None


def iter_dicts(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from iter_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_dicts(child)


def read_artifact(path: Path) -> Iterable[dict[str, Any]]:
    if path.suffix.casefold() == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as stream:
            yield from csv.DictReader(stream)
    elif path.suffix.casefold() == ".json":
        yield from iter_dicts(json.loads(path.read_text(encoding="utf-8-sig")))


def value_from(record: dict[str, Any], *fields: str) -> Any:
    nested = record.get("source_evidence") if isinstance(record.get("source_evidence"), dict) else {}
    for field in fields:
        value = record.get(field)
        if value not in (None, ""):
            return value
        value = nested.get(field)
        if value not in (None, ""):
            return value
    return None


def record_external_id(record: dict[str, Any]) -> str:
    return str(value_from(record, "external_id", "product_external_id") or "").strip()


def blocked_rows(snapshot: dict[str, Any], wave249: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in wave249.choose_primary_categories(snapshot["rows"]):
        manufacturer = str(row.get("manufacturer") or "").strip()
        mpn = str(row.get("mpn") or "").strip()
        description = str(row.get("short_description") or "").strip()
        if not wave249.truth(row.get("is_published")):
            continue
        if not manufacturer or not mpn or not str(row.get("manufacturer_normalized") or "").strip() or not str(row.get("mpn_normalized") or "").strip():
            continue
        if wave249.integer(row.get("identity_pair_catalogue_count")) != 1 or len(description) < 200:
            continue
        if wave249.integer(row.get("matching_applied_description_count")) < 1:
            continue
        provenance_ok, _, _ = wave249.provenance(row)
        if not provenance_ok:
            rows.append(row)
    return rows


def validate_recovery(path: Path, repo_root: Path) -> tuple[dict[str, dict[str, Any]], list[tuple[Path, str]]]:
    recovery = json.loads(path.read_text(encoding="utf-8"))
    if recovery.get("schema_version") != 1 or recovery.get("recovery_status") != "ready" or recovery.get("unresolved") != []:
        raise AuditError("Wave246 recovery manifest is not a complete ready evidence index")
    products = recovery.get("products")
    pins = recovery.get("input_pins")
    if not isinstance(products, list) or not isinstance(pins, list):
        raise AuditError("Wave246 recovery products/input_pins are invalid")
    index: dict[str, dict[str, Any]] = {}
    for row in products:
        external_id = str(row.get("external_id") or "").strip()
        if not external_id or external_id in index:
            raise AuditError("Wave246 recovery external IDs are blank or duplicated")
        index[external_id] = row
    validated_pins: list[tuple[Path, str]] = []
    for pin in pins:
        relative = pin.get("path") if isinstance(pin, dict) else None
        digest = pin.get("sha256") if isinstance(pin, dict) else None
        if not isinstance(relative, str) or not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
            raise AuditError("Wave246 input pin is malformed")
        artifact = repo_root / relative
        if not artifact.is_file() or sha256(artifact) != digest:
            raise AuditError(f"Wave246 pinned evidence drifted: {relative}")
        if artifact.suffix.casefold() in {".json", ".csv"}:
            validated_pins.append((artifact, digest))
    return index, validated_pins


def artifact_index(paths: list[tuple[Path, str]], target_ids: set[str]) -> dict[str, list[tuple[Path, str, dict[str, Any]]]]:
    output: dict[str, list[tuple[Path, str, dict[str, Any]]]] = defaultdict(list)
    for path, digest in paths:
        try:
            records = read_artifact(path)
            for record in records:
                external_id = record_external_id(record)
                if external_id in target_ids:
                    output[external_id].append((path, digest, record))
        except (csv.Error, UnicodeDecodeError, json.JSONDecodeError):
            # A non-ledger JSON/CSV pin is irrelevant unless it can be parsed as
            # structured evidence; never turn a parse failure into provenance.
            continue
    return output


def evidence_candidate(row: dict[str, Any], recovery: dict[str, Any], record: dict[str, Any]) -> dict[str, str] | None:
    source_url = str(value_from(record, "source_url") or "").strip()
    if source_url != str(recovery.get("source_url") or "").strip() or not valid_https(source_url):
        return None
    source_kind = str(value_from(record, "source_kind") or "").strip()
    source_tier = str(value_from(record, "source_tier") or "").strip()
    if (source_kind, source_tier) not in ALLOWED_SOURCE_PAIRS:
        return None
    scope = str(value_from(record, "identity_scope", "evidence_scope") or "").strip()
    if scope not in {"exact", "model_core"}:
        return None
    manufacturer = str(value_from(record, "manufacturer") or recovery.get("manufacturer") or "").strip()
    if normalize(manufacturer) != normalize(row.get("manufacturer")):
        return None
    if scope == "exact":
        identity = str(value_from(record, "mpn", "model") or recovery.get("mpn") or "").strip()
        if normalize(identity) != normalize(row.get("mpn")):
            return None
    else:
        identity = str(value_from(record, "model_core", "model") or recovery.get("model_core") or "").strip()
        if not name_contains(row.get("name"), identity):
            return None
    return {
        "source_url": source_url,
        "source_kind": source_kind,
        "source_tier": source_tier,
        "identity_scope": scope,
        "identity": identity,
    }


def build(snapshot: dict[str, Any], recovery_path: Path, repo_root: Path) -> tuple[list[dict[str, str]], dict[str, Any]]:
    wave249 = load_wave249()
    blocked = blocked_rows(snapshot, wave249)
    if len(blocked) != 403:
        raise AuditError(f"Wave250 must audit the exact 403 Wave249 provenance blockers; found {len(blocked)}")
    recovery, pins = validate_recovery(recovery_path, repo_root)
    target_ids = {str(row["external_id"]) for row in blocked}
    if set(recovery) & target_ids != target_ids:
        raise AuditError("Wave246 recovery does not cover every Wave249 provenance blocker")
    artifacts = artifact_index(pins, target_ids)

    output: list[dict[str, str]] = []
    safe_rows: list[dict[str, str]] = []
    reason_counts: Counter[str] = Counter()
    for row in sorted(blocked, key=lambda item: (str(item.get("manufacturer") or "").casefold(), str(item.get("mpn") or "").casefold(), str(item["external_id"]))):
        external_id = str(row["external_id"])
        recovery_row = recovery[external_id]
        candidates: list[tuple[Path, str, dict[str, str]]] = []
        for path, digest, record in artifacts.get(external_id, []):
            candidate = evidence_candidate(row, recovery_row, record)
            if candidate is not None:
                candidates.append((path, digest, candidate))
        canonical = {
            json.dumps(candidate, ensure_ascii=False, sort_keys=True): candidate
            for _, _, candidate in candidates
        }
        if not candidates:
            disposition = "SOURCE_RESEARCH_REQUIRED"
            reason = "NO_PINNED_ARTIFACT_WITH_COMPLETE_ALLOWED_PROVENANCE_AND_CURRENT_IDENTITY"
            selected_path = ""
            selected_hash = ""
            selected = {}
        elif len(canonical) != 1:
            disposition = "HOLD_CONFLICTING_PINNED_PROVENANCE"
            reason = "MULTIPLE_DISTINCT_ALLOWED_PROVENANCE_DECISIONS"
            selected_path = ""
            selected_hash = ""
            selected = {}
        else:
            selected = next(iter(canonical.values()))
            chosen = min((item for item in candidates if item[2] == selected), key=lambda item: item[0].as_posix())
            selected_path = chosen[0].relative_to(repo_root).as_posix()
            selected_hash = chosen[1]
            disposition = "SAFE_DETERMINISTIC_PROVENANCE_RELINK"
            reason = ""
        result = {
            "product_external_id": external_id,
            "product_id": str(row.get("product_id") or ""),
            "site_product_id": str(row.get("site_product_id") or ""),
            "name": str(row.get("name") or ""),
            "manufacturer": str(row.get("manufacturer") or ""),
            "mpn": str(row.get("mpn") or ""),
            "category_external_id": str(row.get("category_external_id") or ""),
            "description_sha256": hashlib.sha256(str(row.get("short_description") or "").encode("utf-8")).hexdigest(),
            "description_characters": str(len(str(row.get("short_description") or "").strip())),
            "current_source_kind": str(row.get("description_source_kind") or ""),
            "current_source_tier": str(row.get("description_source_tier") or ""),
            "current_identity_scope": str(row.get("description_identity_scope") or ""),
            "recovery_source_url": str(recovery_row.get("source_url") or ""),
            "candidate_source_kind": selected.get("source_kind", ""),
            "candidate_source_tier": selected.get("source_tier", ""),
            "candidate_identity_scope": selected.get("identity_scope", ""),
            "candidate_identity": selected.get("identity", ""),
            "evidence_path": selected_path,
            "evidence_sha256": selected_hash,
            "disposition": disposition,
            "hold_reason": reason,
            "research_priority": "",
            "manufacturer_blocker_count": "",
            "priority_basis": "",
            "no_repeat_basis": "only_current_wave249_invalid_provenance_rows; valid_provenance_and_non_b2b_products_excluded",
        }
        output.append(result)
        reason_counts[reason or "safe"] += 1
        if disposition == "SAFE_DETERMINISTIC_PROVENANCE_RELINK":
            safe_rows.append(result)

    normalized_manufacturers: dict[str, list[dict[str, str]]] = defaultdict(list)
    for result in output:
        normalized_manufacturers[normalize(result["manufacturer"]) or "<blank>"].append(result)

    manufacturer_summary: dict[str, dict[str, Any]] = {}
    for normalized_manufacturer, rows in normalized_manufacturers.items():
        display_names = Counter(row["manufacturer"] or "<blank>" for row in rows)
        manufacturer = min(display_names, key=lambda value: (-display_names[value], value.casefold(), value))
        dispositions = Counter(row["disposition"] for row in rows)
        blocked_count = len(rows)
        research_priority = "P1" if blocked_count >= 20 else "P2" if blocked_count >= 5 else "P3"
        for result in rows:
            if result["disposition"] != "SAFE_DETERMINISTIC_PROVENANCE_RELINK":
                result["research_priority"] = research_priority
                result["manufacturer_blocker_count"] = str(blocked_count)
                result["priority_basis"] = "manufacturer_blocker_volume:P1>=20;P2=5-19;P3<5"
        manufacturer_summary[manufacturer or "<blank>"] = {
            "manufacturer_normalized": normalized_manufacturer,
            "blocked": len(rows),
            "safe_relinks": dispositions["SAFE_DETERMINISTIC_PROVENANCE_RELINK"],
            "research_required": dispositions["SOURCE_RESEARCH_REQUIRED"],
            "conflicts": dispositions["HOLD_CONFLICTING_PINNED_PROVENANCE"],
        }
    summary = {
        "schema_version": 1,
        "wave": "wave250_description_provenance_relink",
        "mode": "live_database_read_only_and_local_pinned_artifacts_only",
        "site_key": "microchips-by",
        "audited_blockers": len(output),
        "safe_deterministic_relinks": len(safe_rows),
        "research_required": sum(row["disposition"] == "SOURCE_RESEARCH_REQUIRED" for row in output),
        "conflicts": sum(row["disposition"] == "HOLD_CONFLICTING_PINNED_PROVENANCE" for row in output),
        "reason_distribution": dict(sorted(reason_counts.items())),
        "manufacturer_summary": dict(sorted(manufacturer_summary.items())),
        "input_pins": {
            "recovery_manifest": {"path": recovery_path.relative_to(repo_root).as_posix(), "sha256": sha256(recovery_path)},
            "validated_recovery_artifacts": len(pins),
        },
        "quality": {
            "network_requests": 0,
            "database_mutations": 0,
            "audited_external_ids_unique": len({row["product_external_id"] for row in output}),
            "safe_rows_with_exact_evidence_pin": sum(bool(row["evidence_path"] and re.fullmatch(r"[a-f0-9]{64}", row["evidence_sha256"])) for row in safe_rows),
        },
        "candidates": safe_rows,
        "research_queue": [row for row in output if row["disposition"] != "SAFE_DETERMINISTIC_PROVENANCE_RELINK"],
    }
    return output, summary


def _group_by(rows: list[dict[str, str]], field: str) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row[field]].append(row)
    return grouped


def write_outputs(rows: list[dict[str, str]], summary: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / OUTPUT_CSV.name
    queue_path = output_dir / QUEUE_CSV.name
    with csv_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    queue = sorted(
        summary["research_queue"],
        key=lambda row: (
            row["research_priority"],
            -int(row["manufacturer_blocker_count"] or 0),
            row["manufacturer"].casefold(),
            row["mpn"].casefold(),
            row["product_external_id"],
        ),
    )
    with queue_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(queue)
    json_path = output_dir / OUTPUT_JSON.name
    summary["outputs"] = {
        "audit_csv": {"path": csv_path.relative_to(ROOT).as_posix(), "rows": len(rows), "sha256": sha256(csv_path)},
        "research_queue_csv": {"path": queue_path.relative_to(ROOT).as_posix(), "rows": len(queue), "sha256": sha256(queue_path)},
        "summary_json": {"path": json_path.relative_to(ROOT).as_posix()},
    }
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--recovery-manifest", type=Path, default=RECOVERY)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--output-dir", type=Path, default=GENERATED)
    args = parser.parse_args()
    wave249 = load_wave249()
    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8")) if args.snapshot else wave249.query_live_snapshot()
    rows, summary = build(snapshot, args.recovery_manifest.resolve(), args.repo_root.resolve())
    write_outputs(rows, summary, args.output_dir.resolve())
    print(json.dumps({
        "audited": len(rows),
        "safe_deterministic_relinks": summary["safe_deterministic_relinks"],
        "research_required": summary["research_required"],
        "conflicts": summary["conflicts"],
        "network_requests": 0,
        "database_mutations": 0,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
