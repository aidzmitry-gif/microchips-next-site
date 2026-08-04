#!/usr/bin/env python3
"""Convert the extracted Bitrix B2B section slice to an unpublished tree CSV."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sections", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    args = parser.parse_args()

    with args.sections.open("r", encoding="utf-8-sig", newline="") as handle:
        source = list(csv.DictReader(handle))
    ids = {row["legacy_section_id"].strip() for row in source}
    rows = []
    boundary_parent_ids = set()
    for row in source:
        external_id = row["legacy_section_id"].strip()
        parent = row["parent_section_id"].strip()
        if parent and parent not in ids:
            boundary_parent_ids.add(parent)
            parent = ""
        path = row["source_section_path"].strip().strip("/")
        if not external_id or not path or not row["name"].strip():
            raise ValueError(f"Incomplete section row: {external_id or '<missing>'}")
        rows.append({
            "external_id": external_id,
            "parent_external_id": parent,
            "name": row["name"].strip(),
            "path": f"catalog/{path}",
        })
    if len({row["external_id"] for row in rows}) != len(rows):
        raise ValueError("Duplicate section identity")
    if len({row["path"] for row in rows}) != len(rows):
        raise ValueError("Duplicate section path")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "external_id", "parent_external_id", "name", "path",
        ])
        writer.writeheader()
        writer.writerows(sorted(rows, key=lambda item: (item["path"].count("/"), item["path"])))
    summary = {
        "sections": len(rows),
        "root_sections": sum(1 for row in rows if not row["parent_external_id"]),
        "boundary_parent_ids": sorted(boundary_parent_ids, key=int),
        "publication_changes": 0,
    }
    args.summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
