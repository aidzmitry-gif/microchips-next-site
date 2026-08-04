#!/usr/bin/env python3
"""Merge hold-only research registries into one fail-closed cluster ledger."""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path


def values(rows: list[dict[str, str]], *fields: str) -> str:
    found: list[str] = []
    for row in rows:
        for field in fields:
            value = (row.get(field) or "").strip()
            if value and value not in found:
                found.append(value)
    return " || ".join(found)


def merge(inputs: list[Path], output: Path) -> dict[str, object]:
    if not inputs:
        raise ValueError("At least one input registry is required")
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    source_rows = 0
    for path in inputs:
        if not path.is_file():
            raise ValueError(f"Hold registry is not readable: {path}")
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None or not {"cluster_id", "decision"}.issubset(reader.fieldnames):
                raise ValueError(f"Hold registry requires cluster_id and decision: {path}")
            for row in reader:
                cluster_id = (row.get("cluster_id") or "").strip()
                decision = (row.get("decision") or "").strip()
                if not cluster_id or ":" not in cluster_id or decision != "hold":
                    raise ValueError(f"Unsupported or malformed hold row in {path}")
                grouped[cluster_id].append(row)
                source_rows += 1

    merged: list[dict[str, str]] = []
    for cluster_id, rows in sorted(grouped.items()):
        merged.append({
            "cluster_id": cluster_id,
            "manufacturer_candidate": values(rows, "manufacturer_candidate", "manufacturer"),
            "decision": "hold",
            "reason_code": values(rows, "reason_code") or "primary_source_required",
            "evidence": values(rows, "evidence", "evidence_summary", "evidence_url"),
            "retry_condition": values(rows, "retry_condition"),
        })
    if any(not row["evidence"] or not row["retry_condition"] for row in merged):
        raise ValueError("Every merged hold requires evidence and retry_condition")

    output.parent.mkdir(parents=True, exist_ok=True)
    fields = ["cluster_id", "manufacturer_candidate", "decision", "reason_code", "evidence", "retry_condition"]
    with output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(merged)
    summary = {
        "input_files": [str(path) for path in inputs],
        "source_rows": source_rows,
        "unique_hold_clusters": len(merged),
        "collapsed_duplicate_rows": source_rows - len(merged),
        "invariant": "hold-only ledger; no catalogue, publication or database mutation",
    }
    output.with_suffix(".summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(merge(args.input, args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
