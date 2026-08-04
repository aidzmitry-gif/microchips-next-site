#!/usr/bin/env python3
"""Roll the live Wave242 readiness audit into the no-repeat Wave241 queue."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(previous_path: Path, full_path: Path) -> tuple[list[dict[str, str]], dict[str, int]]:
    previous = read_csv(previous_path)
    full = read_csv(full_path)
    full_by_id = {row["product_external_id"]: row for row in full}
    if len(full_by_id) != len(full):
        raise RuntimeError("The full queue contains duplicate product_external_id values.")

    missing = [row["product_external_id"] for row in previous if row["product_external_id"] not in full_by_id]
    if missing:
        raise RuntimeError(f"The live queue no longer contains {len(missing)} prior no-repeat member(s).")

    rows: list[dict[str, str]] = []
    for priority, prior in enumerate(previous, start=1):
        current = dict(full_by_id[prior["product_external_id"]])
        current["priority"] = str(priority)
        rows.append(current)

    if len({row["product_external_id"] for row in rows}) != len(rows):
        raise RuntimeError("The rolled queue contains duplicate product_external_id values.")

    counts = {
        "rows": len(rows),
        "description_present": sum(row["has_applied_description"] == "true" for row in rows),
        "description_missing": sum(row["has_applied_description"] == "false" for row in rows),
        "verified_image_present": sum(row["has_verified_published_image"] == "true" for row in rows),
        "verified_image_missing": sum(row["has_verified_published_image"] == "false" for row in rows),
    }
    return rows, counts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--previous", type=Path, default=ROOT / "docs/audits/generated/rb-enrichment-queue-wave241.csv")
    parser.add_argument("--full", type=Path, default=ROOT / ".tmp/rb-enrichment-queue-wave242-full.csv")
    parser.add_argument("--readiness", type=Path, default=ROOT / ".tmp/rb-full-content-readiness-wave242-after.csv")
    parser.add_argument("--output", type=Path, default=ROOT / "docs/audits/generated/rb-enrichment-queue-wave242.csv")
    parser.add_argument("--readiness-output", type=Path, default=ROOT / "docs/audits/generated/rb-full-content-readiness-wave242-after.csv")
    parser.add_argument("--summary", type=Path, default=ROOT / "docs/audits/generated/rb-enrichment-queue-wave242.summary.json")
    args = parser.parse_args()

    rows, counts = build(args.previous, args.full)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    shutil.copyfile(args.readiness, args.readiness_output)

    payload = {
        **counts,
        "membership_policy": "exact Wave241 no-repeat membership, refreshed from live Wave242 readiness",
        "previous_queue_sha256": sha256(args.previous),
        "full_live_queue_sha256": sha256(args.full),
        "output_queue_sha256": sha256(args.output),
        "readiness_sha256": sha256(args.readiness_output),
    }
    args.summary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
