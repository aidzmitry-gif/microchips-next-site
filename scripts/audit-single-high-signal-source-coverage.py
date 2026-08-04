#!/usr/bin/env python3
"""Audit existing source evidence for the bounded 22-item review queue."""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

HEADER = [
    "review_priority",
    "one_c_external_id",
    "legacy_element_id",
    "legacy_name",
    "coverage_status",
    "strongest_scope",
    "source_urls",
    "source_files",
    "next_action",
]


def iter_products(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict) and isinstance(payload.get("products"), list):
        return [row for row in payload["products"] if isinstance(row, dict)]
    return []


def audit(queue: list[dict[str, str]], evidence_files: list[Path]) -> tuple[list[dict[str, str]], dict[str, Any]]:
    evidence: dict[str, list[tuple[Path, dict[str, Any]]]] = defaultdict(list)
    for path in evidence_files:
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            continue
        for product in iter_products(payload):
            external_id = str(product.get("external_id", "")).strip()
            if external_id:
                evidence[external_id].append((path, product))

    rows, summary = classify(queue, evidence)
    summary["evidence_files_scanned"] = len(evidence_files)
    return rows, summary


def classify(
    queue: list[dict[str, str]],
    evidence: dict[str, list[tuple[Path, dict[str, Any]]]],
) -> tuple[list[dict[str, str]], dict[str, Any]]:

    rows: list[dict[str, str]] = []
    counts: Counter[str] = Counter()
    for queue_row in queue:
        external_id = queue_row["one_c_external_id"].strip()
        matches = evidence.get(external_id, [])
        scopes = {
            "exact" if product.get("mpn") else str(product.get("identity_scope", "")).strip()
            for _, product in matches
        }
        scopes.discard("")
        if "exact" in scopes:
            status = "existing_exact_evidence"
            strongest = "exact"
            next_action = "Validate exact legacy name/variant compatibility, then prepare reviewed identity decision."
        elif "model_core" in scopes:
            status = "existing_model_core_evidence"
            strongest = "model_core"
            next_action = "Find exact terminal/pack/variant evidence before linking identities."
        else:
            status = "source_research_required"
            strongest = ""
            next_action = "Research official manufacturer product page or datasheet."
        counts[status] += 1
        rows.append({
            "review_priority": queue_row["review_priority"],
            "one_c_external_id": external_id,
            "legacy_element_id": queue_row["legacy_element_id"],
            "legacy_name": queue_row["legacy_name"],
            "coverage_status": status,
            "strongest_scope": strongest,
            "source_urls": " | ".join(sorted({
                str(product.get("source_url", "")).strip()
                for _, product in matches if str(product.get("source_url", "")).strip()
            })),
            "source_files": " | ".join(sorted({path.as_posix() for path, _ in matches})),
            "next_action": next_action,
        })

    summary = {
        "schema_version": 1,
        "queue_rows": len(queue),
        "evidence_files_scanned": 0,
        "coverage": dict(sorted(counts.items())),
        "identity_decisions_emitted": 0,
        "invariant": "Existing source evidence is reused, but model-core evidence never proves an exact legacy/1C variant link.",
    }
    return rows, summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--imports-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--expected", type=int, default=22)
    args = parser.parse_args()

    with args.queue.open(encoding="utf-8-sig", newline="") as handle:
        queue = list(csv.DictReader(handle))
    if len(queue) != args.expected:
        raise SystemExit(f"Expected {args.expected} queue rows; received {len(queue)}.")
    patterns = [
        "rb-source-backed-description-drafts*.json",
        "rb-source-verified-preview*.json",
        "rb-bulk-source-backed-preview*.json",
    ]
    files = sorted({path for pattern in patterns for path in args.imports_dir.glob(pattern)})
    rows, summary = audit(queue, files)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=HEADER)
        writer.writeheader()
        writer.writerows(rows)
    args.summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
