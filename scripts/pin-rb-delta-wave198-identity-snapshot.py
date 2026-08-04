#!/usr/bin/env python3
"""Pin explicit identity-clear states into the Wave 198 source snapshot."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


def build(source: Path, audit_path: Path, output: Path, expected_records: int) -> dict[str, object]:
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    required = {
        "schema_version": 1,
        "site_key": "microchips-by",
        "source_run_id": 763,
        "candidate_scope_records": expected_records,
        "identity_candidate_rows": 0,
        "result": "verified_clear",
    }
    for field, expected in required.items():
        if audit.get(field) != expected:
            raise ValueError(f"identity audit {field} must equal {expected!r}")
    manifest_sha = str(audit.get("source_run_manifest_sha256", ""))
    if len(manifest_sha) != 64 or any(char not in "0123456789abcdef" for char in manifest_sha.casefold()):
        raise ValueError("identity audit requires the pinned source-run manifest SHA-256")

    source_raw = source.read_bytes()
    with source.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fields = list(reader.fieldnames or [])
    if len(rows) != expected_records or "identity_candidate_status" not in fields:
        raise ValueError("source snapshot count/identity column mismatch")
    for row in rows:
        value = row["identity_candidate_status"].strip().casefold()
        if value not in {"", "none"}:
            raise ValueError("identity audit cannot clear a row with a nonempty candidate status")
        row["identity_candidate_status"] = "none"

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)
    summary = {
        "source_path": str(source),
        "source_sha256": hashlib.sha256(source_raw).hexdigest(),
        "identity_audit_path": str(audit_path),
        "identity_audit_sha256": hashlib.sha256(audit_path.read_bytes()).hexdigest(),
        "output_path": str(output),
        "output_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "records": len(rows),
        "explicit_none_records": sum(row["identity_candidate_status"] == "none" for row in rows),
        "automatic_database_mutations": 0,
    }
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-records", type=int, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.source, args.audit, args.output, args.expected_records), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
