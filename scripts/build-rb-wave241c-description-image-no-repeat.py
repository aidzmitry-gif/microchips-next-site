#!/usr/bin/env python3
"""Reconcile Wave240 description+image gaps with prior reviewed evidence."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "docs/audits/generated"
QUEUE = GEN / "rb-enrichment-queue-wave240.csv"
LEDGER = GEN / "rb-wave241c-description-image-no-repeat-ledger.csv"
SKIPS = GEN / "rb-wave241c-reviewed-identity-skips.csv"
ACTIONABLE = GEN / "rb-wave241c-new-description-actionable.csv"
SUMMARY = GEN / "rb-wave241c-description-image-no-repeat.summary.json"
REPORT = ROOT / "docs/audits/2026-07-29-rb-wave241c-description-image-no-repeat.md"

HOLD_SOURCES = [
    GEN / "rb-wave237-fiamm-authorized-identity-ledger.csv",
    GEN / "rb-wave233a-delta-identity-ledger.csv",
    GEN / "rb-wave233-fiamm-identity-ledger.csv",
    GEN / "rb-wave233c-leoch-marathon-csb-identity-ledger.csv",
    GEN / "rb-wave234a-panasonic-mnb-identity-ledger.csv",
    GEN / "rb-wave234b-apc-enersys-identity-ledger.csv",
    GEN / "rb-wave234c-general-security-identity-ledger.csv",
    GEN / "rb-wave234c-residual-identity-holds.csv",
]

ACTION_EVIDENCE = [
    GEN / "rb-wave209a-official-evidence.csv",
    GEN / "rb-wave209c-stationary-evidence.csv",
    GEN / "rb-wave211c-stationary-evidence.csv",
    GEN / "wave206-panasonic-ventura-mnb-evidence.csv",
]

LEDGER_FIELDS = [
    "priority", "product_external_id", "name", "manufacturer", "mpn",
    "category_external_id", "disposition", "evidence_path", "evidence_sha256",
    "evidence_match", "source_tier", "source_url", "source_snapshot_path",
    "source_snapshot_sha256", "prior_decision", "missing_evidence", "next_action",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=LEDGER_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def normalized(value: str | None) -> str:
    return re.sub(r"[^a-zа-яё0-9]+", "", (value or "").casefold())


def external_id(row: dict[str, str]) -> str:
    return row.get("product_external_id") or row.get("external_id") or ""


def row_name(row: dict[str, str]) -> str:
    return row.get("name") or row.get("current_name") or row.get("wave234_name") or ""


def value(row: dict[str, str], *keys: str) -> str:
    for key in keys:
        if row.get(key):
            return row[key]
    return ""


def verify_snapshot(path_value: str, expected_sha256: str) -> None:
    if not path_value and not expected_sha256:
        return
    assert path_value and expected_sha256
    path = Path(path_value)
    if not path.is_absolute():
        path = (ROOT / "docs/imports" / path).resolve() if path_value.startswith("../audits/") else ROOT / path
    assert path.is_file(), path
    assert sha256(path) == expected_sha256, path


def hold_reason(row: dict[str, str], path: Path) -> str:
    reason = value(row, "hold_reason", "conflict_reason", "collision_reason")
    if reason:
        return reason
    partition = row.get("partition", "")
    if path.name.startswith("rb-wave237-") and partition.startswith("hold_"):
        return partition
    return "prior reviewed identity decision is not safe to apply"


def assert_hold(row: dict[str, str], path: Path) -> None:
    if path.name.startswith("rb-wave237-"):
        assert row.get("partition", "").startswith("hold_")
        return
    assert row.get("decision", row.get("wave234_decision", "HOLD")) != "PASS"
    assert row.get("safe_to_apply", "false").casefold() != "true"


def load_hold_index() -> tuple[dict[str, tuple[Path, dict[str, str]]], dict[str, str]]:
    index: dict[str, tuple[Path, dict[str, str]]] = {}
    pins: dict[str, str] = {}
    for path in HOLD_SOURCES:
        pins[path.relative_to(ROOT).as_posix()] = sha256(path)
        for row in read_csv(path):
            candidate = external_id(row)
            if candidate and candidate not in index:
                index[candidate] = (path, row)
    return index, pins


def load_action_index() -> tuple[dict[str, tuple[Path, dict[str, str]]], dict[str, str]]:
    index: dict[str, tuple[Path, dict[str, str]]] = {}
    pins: dict[str, str] = {}
    for path in ACTION_EVIDENCE:
        pins[path.relative_to(ROOT).as_posix()] = sha256(path)
        for row in read_csv(path):
            candidate = external_id(row)
            if candidate and candidate not in index:
                index[candidate] = (path, row)
    return index, pins


def description_manifest_matches(rows: list[dict[str, str]]) -> dict[str, list[str]]:
    by_id = {row["product_external_id"]: row for row in rows}
    signatures = {
        (normalized(row["manufacturer"]), normalized(row["mpn"])): row["product_external_id"]
        for row in rows
    }
    titles = {normalized(row["name"]): row["product_external_id"] for row in rows}
    matches: dict[str, list[str]] = {row["product_external_id"]: [] for row in rows}

    for path in sorted((ROOT / "docs/imports").glob("rb-source-backed-description*.json")):
        try:
            payload: Any = json.loads(path.read_text(encoding="utf-8-sig"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        records: list[dict[str, Any]] = []
        if isinstance(payload, list):
            records = [row for row in payload if isinstance(row, dict)]
        elif isinstance(payload, dict):
            for key in ("products", "records", "descriptions"):
                if isinstance(payload.get(key), list):
                    records = [row for row in payload[key] if isinstance(row, dict)]
                    break
        for record in records:
            matched: set[str] = set()
            record_id = str(record.get("external_id") or record.get("product_external_id") or "")
            if record_id in by_id:
                matched.add(record_id)
            signature = (
                normalized(str(record.get("manufacturer") or "")),
                normalized(str(record.get("mpn") or record.get("model_core") or "")),
            )
            if signature in signatures and all(signature):
                matched.add(signatures[signature])
            title = normalized(str(record.get("display_name") or record.get("name") or record.get("current_name") or ""))
            if title in titles and title:
                matched.add(titles[title])
            for candidate in matched:
                matches[candidate].append(path.relative_to(ROOT).as_posix())
    return {key: sorted(set(paths)) for key, paths in matches.items() if paths}


def base_output(queue_row: dict[str, str]) -> dict[str, str]:
    return {
        "priority": queue_row["priority"],
        "product_external_id": queue_row["product_external_id"],
        "name": queue_row["name"],
        "manufacturer": queue_row["manufacturer"],
        "mpn": queue_row["mpn"],
        "category_external_id": queue_row["category_external_id"],
    }


def build() -> None:
    queue_rows = read_csv(QUEUE)
    target = [
        row for row in queue_rows
        if row["has_applied_description"] == "false"
        and row["has_verified_published_image"] == "false"
    ]
    assert len(queue_rows) == 1247
    assert len(target) == 502
    assert len({row["product_external_id"] for row in target}) == 502
    assert {row["category_external_id"] for row in target} == {"seo:batteries-ups"}

    blank = [row for row in target if not row["manufacturer"]]
    identified = [row for row in target if row["manufacturer"]]
    assert len(blank) == 458 and len(identified) == 44

    holds, hold_pins = load_hold_index()
    actions, action_pins = load_action_index()
    manifest_matches = description_manifest_matches(identified)
    assert manifest_matches == {}

    ledger: list[dict[str, str]] = []
    skips: list[dict[str, str]] = []
    actionable: list[dict[str, str]] = []

    for queue_row in target:
        candidate = queue_row["product_external_id"]
        output = base_output(queue_row)
        if not queue_row["manufacturer"]:
            assert candidate in holds, f"unmapped blank identity: {candidate}"
            path, evidence = holds[candidate]
            assert normalized(row_name(evidence)) == normalized(queue_row["name"]), candidate
            assert_hold(evidence, path)
            snapshot_path = value(evidence, "source_snapshot_path", "snapshot_path", "source_path")
            snapshot_sha = value(evidence, "source_snapshot_sha256", "snapshot_sha256", "source_sha256")
            verify_snapshot(snapshot_path, snapshot_sha)
            output.update({
                "disposition": "SKIP_REVIEWED_IDENTITY_HOLD",
                "evidence_path": path.relative_to(ROOT).as_posix(),
                "evidence_sha256": hold_pins[path.relative_to(ROOT).as_posix()],
                "evidence_match": "exact_external_id+normalized_exact_title",
                "source_tier": value(evidence, "source_tier"),
                "source_url": value(evidence, "source_url"),
                "source_snapshot_path": snapshot_path,
                "source_snapshot_sha256": snapshot_sha,
                "prior_decision": "HOLD",
                "missing_evidence": hold_reason(evidence, path),
                "next_action": "do_not_repeat_research; wait_for_new_exact_primary_identity_evidence",
            })
            skips.append(output)
        else:
            assert candidate in actions, f"unmapped identified action: {candidate}"
            path, evidence = actions[candidate]
            assert normalized(row_name(evidence)) == normalized(queue_row["name"]), candidate
            assert evidence.get("safe_to_apply", "").casefold() == "true", candidate
            assert "exact" in value(evidence, "partition", "evidence_scope", "source_assertion").casefold(), candidate
            evidence_manufacturer = value(evidence, "manufacturer_cluster", "manufacturer", "replacement_manufacturer")
            assert normalized(evidence_manufacturer) == normalized(queue_row["manufacturer"]), candidate
            evidence_model = value(evidence, "model_token", "model_candidate", "model", "replacement_mpn")
            assert normalized(evidence_model) == normalized(queue_row["mpn"]), candidate
            snapshot_path = value(evidence, "source_snapshot_path", "snapshot_path")
            snapshot_sha = value(evidence, "source_snapshot_sha256", "snapshot_sha256")
            verify_snapshot(snapshot_path, snapshot_sha)
            output.update({
                "disposition": "NEW_DESCRIPTION_ACTIONABLE",
                "evidence_path": path.relative_to(ROOT).as_posix(),
                "evidence_sha256": action_pins[path.relative_to(ROOT).as_posix()],
                "evidence_match": "exact_external_id+manufacturer+mpn+normalized_exact_title",
                "source_tier": value(evidence, "source_tier"),
                "source_url": value(evidence, "source_url"),
                "source_snapshot_path": snapshot_path,
                "source_snapshot_sha256": snapshot_sha,
                "prior_decision": "EXACT_PRIMARY_IDENTITY_PASS",
                "missing_evidence": "no prior exact source-backed description manifest; verified published image also absent",
                "next_action": "draft exact description from pinned primary evidence; image remains a separate rights+identity review",
            })
            actionable.append(output)
        ledger.append(output)

    assert len(skips) == 458 and len(actionable) == 44 and len(ledger) == 502
    write_csv(LEDGER, ledger)
    write_csv(SKIPS, skips)
    write_csv(ACTIONABLE, actionable)

    summary = {
        "schema_version": 1,
        "wave": "wave241c_description_image_no_repeat",
        "checked_at": "2026-07-29",
        "input": {
            "path": QUEUE.relative_to(ROOT).as_posix(),
            "sha256": sha256(QUEUE),
            "rows": len(queue_rows),
            "description_false_image_false_rows": len(target),
        },
        "scope": {
            "blank_manufacturer_rows": len(blank),
            "identified_rows": len(identified),
            "reviewed_identity_holds_skipped": len(skips),
            "genuinely_new_description_actionable": len(actionable),
            "prior_exact_description_manifest_matches": len(manifest_matches),
            "description_manifest_prepared": False,
        },
        "skip_evidence_distribution": dict(sorted(Counter(row["evidence_path"] for row in skips).items())),
        "actionable_manufacturer_distribution": dict(sorted(Counter(row["manufacturer"] for row in actionable).items())),
        "actionable_evidence_distribution": dict(sorted(Counter(row["evidence_path"] for row in actionable).items())),
        "input_pins": {**hold_pins, **action_pins},
        "outputs": {
            "ledger": {"path": LEDGER.relative_to(ROOT).as_posix(), "rows": len(ledger), "sha256": sha256(LEDGER)},
            "skips": {"path": SKIPS.relative_to(ROOT).as_posix(), "rows": len(skips), "sha256": sha256(SKIPS)},
            "actionable": {"path": ACTIONABLE.relative_to(ROOT).as_posix(), "rows": len(actionable), "sha256": sha256(ACTIONABLE)},
        },
        "missing_evidence": {
            "blank_rows": "new exact primary identity evidence",
            "actionable_rows": "materialized exact source-backed description and verified reusable image",
        },
        "database_queries": 0,
        "database_mutations": 0,
        "network_requests": 0,
        "apply_performed": False,
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    REPORT.write_text(
        "# Wave241-C description/image no-repeat reconciliation\n\n"
        "The Wave240 queue has exactly 502 UPS-battery rows with neither an applied description nor a verified published image. "
        "All 458 blank-manufacturer rows match a prior reviewed identity HOLD by exact external ID and normalized exact title; they are skipped rather than researched again.\n\n"
        "The remaining 44 rows already have an exact manufacturer/MPN and hash-pinned manufacturer-primary identity evidence: "
        "EnerSys 15, Sonnenschein 8, MNB 8, APC 5, Panasonic 4 and Ventura 4. No prior description manifest matches any of them by external ID, normalized manufacturer+MPN or exact title, so no pre-existing description can be safely replayed. "
        "They are isolated as new description work; image recovery remains a separate rights and visible-identity review.\n\n"
        "No database query, database mutation, network request or apply action is performed.\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    build()
